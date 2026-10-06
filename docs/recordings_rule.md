# 브라우저 액션 레코딩 JSON 스키마 명세서

2026년 9월 21일 · @Someone

Multi-Agent 기반 Self-Evolving MCP 플랫폼에서, 사용자가 브라우저에서 수행하는 모든 조작(클릭, 입력, 새 창/탭 관리, alert 처리 등)을 기록하고 그 결과를 재사용 가능한 JSON으로 추출하기 위한 스키마와 상세 명세서입니다.

## 1. 개요

이 문서는 Multi-Agent 기반 Self-Evolving MCP 플랫폼에서 **사용자가 브라우저에서 수행한 액션을 기록(Record)하고, 그 결과를 재실행 가능한 JSON(Replay Script)으로 추출**하기 위한 스키마 명세서입니다.

**사용 흐름**

1. 레코더 에이전트가 사용자의 브라우저 세션을 관찰하며 클릭, 입력, 새 창 열기, alert 처리 등 모든 액션을 순서대로 캡처한다.
2. 캡처된 액션들을 아래 스키마에 맞는 `steps` 배열로 변환한다.
3. 변환된 JSON은 다른 에이전트(Executor)가 그대로 읽어 동일한 흐름을 자동 재현하거나, Self-Evolving 루프에서 실패 지점을 분석하고 스스로 스텝을 수정하는 데 사용된다.

**설계 원칙**

- **행동과 데이터의 분리**: 어떤 요소를 어떻게 조작했는지(`action`, `target`)와 어떤 값이 오갔는지(`value`, `extract_as`)를 분리해, 같은 스크립트를 다른 계정/데이터로 재사용할 수 있게 한다.
- **셀렉터 폴백**: 하나의 요소를 CSS/XPath/텍스트 등 여러 방식으로 동시에 기술해, 페이지 구조가 약간 바뀌어도 재실행이 끊기지 않게 한다.
- **동기화 명시**: 네트워크 지연, 애니메이션, 다이얼로그 등 타이밍 이슈를 `wait_before` / `wait_after`로 각 스텝에 명시적으로 남긴다.
- **결과의 구조화**: 화면에서 읽어낸 값은 `extract_as`로 이름을 붙여, 최종적으로 하나의 평평한(flat) 결과 JSON으로 모을 수 있게 한다.
- **버전 호환**: `schema_version` 필드로 스키마 자체의 진화(신규 action 타입 추가 등)를 추적한다.

아래 섹션은 순서대로 (2) 최상위 구조 → (3) variables → (4) target → (5) value → (6) step 공통 필드 → (7)~(10) action 카탈로그 → (11) 실행 결과 스키마 → (12) 전체 예시 → (13) 확장 가이드로 구성됩니다.

## 2. 최상위 스키마 구조 (Root Schema)

|필드|타입|필수|설명|
|---|---|---|---|
|`schema_version`|integer|O|이 JSON 스키마 자체의 버전. 하위 호환이 깨지는 변경 시에만 증가 (13장 참고)|
|`id`|string|O|시나리오의 고유 식별자. snake_case 권장 (예: `login_with_confirm`)|
|`name`|string|O|사람이 읽는 시나리오 이름|
|`description`|string|O|시나리오가 하는 일에 대한 자연어 설명 (에이전트의 계획 수립/설명 생성에 사용)|
|`start_url`|string|O|실행을 시작할 초기 URL|
|`variables`|object|X|실행 시 외부에서 주입되는 입력값 정의 (3장)|
|`steps`|array<Step>|O|순서대로 실행되는 액션 목록 (6~10장)|
|`outputs`|array<string>|X|최종 결과 JSON에 포함할 `extract_as` 이름 목록. 생략 시 등장한 모든 `extract_as` 값을 포함 (11장)|
|`metadata`|object|X|생성 시각, 생성 에이전트 버전, 원본 녹화 세션 ID 등 자유 형식 부가 정보|

**예시 골격**

```
{  "schema_version": 1,  "id": "login_with_confirm",  "name": "Login With Confirm Dialog",  "description": "...",  "start_url": "https://example.com/login",  "variables": { "...": "..." },  "steps": [ "..." ],  "outputs": ["confirm_question", "welcome_message"],  "metadata": { "recorded_at": "2026-09-21T13:00:00+09:00", "recorder_version": "0.4.0" }}
```

## 3. `variables` 정의

`variables`는 시나리오 실행 시 외부(사용자, 다른 에이전트, 시크릿 저장소)에서 주입되는 입력값의 명세입니다. 각 키는 변수 이름이며, 값은 아래 필드를 갖는 객체입니다.

|필드|타입|필수|설명|
|---|---|---|---|
|`type`|enum|O|`string` \| `secret` \| `number` \| `boolean` \| `enum` \| `file_path`|
|`required`|boolean|O|실행 전 반드시 값이 주입되어야 하는지 여부|
|`description`|string|O|이 변수가 무엇인지에 대한 설명 (에이전트가 값을 요청/생성할 때 사용)|
|`default`|any|X|`required: false`일 때 사용할 기본값|
|`options`|array<string>|X|`type: "enum"`일 때만 사용, 허용되는 값 목록|
|`sensitive`|boolean|X|로그/트레이스에 값을 마스킹해야 하는지. `type: "secret"`이면 항상 `true`로 간주|

**타입별 비고**

- `string` / `number` / `boolean`: 일반 값. 실행 로그와 결과 JSON에 그대로 노출될 수 있음.
- `secret`: 비밀번호, API 키 등. 레코더는 값 자체를 저장하지 않고 변수 참조만 남기며, 실행 시 별도 시크릿 저장소에서 주입. 로그에는 항상 마스킹.
- `file_path`: `upload_file` 액션(8장)에서 사용할 로컬 파일 경로.
- `enum`: 드롭다운 선택처럼 값의 범위가 고정된 경우.

```
"variables": {  "username": { "type": "string", "required": true, "description": "사내 시스템 로그인 아이디" },  "password": { "type": "secret", "required": true, "description": "사내 시스템 로그인 비밀번호" },  "remember_me": { "type": "boolean", "required": false, "default": false, "description": "로그인 상태 유지 체크박스" },  "upload_doc_path": { "type": "file_path", "required": false, "description": "첨부할 신청서 파일 경로" }}
```

## 4. `target` (Selector) 정의

요소를 다루는 모든 액션(`click`, `input`, `hover` 등)은 `target` 객체로 대상을 지정합니다.

```
"target": {  "selectors": [    { "type": "test_id", "value": "login-submit" },    { "type": "css", "value": "#login-btn" },    { "type": "text", "value": "로그인", "exact": false }  ],  "nth": 0,  "frame_path": [],  "scroll_into_view": true}
```

|필드|타입|필수|설명|
|---|---|---|---|
|`selectors`|array<Selector>|O|같은 요소를 가리키는 셀렉터 후보 목록. **배열 순서 = 시도 우선순위**. 첫 번째부터 시도하고 실패 시 다음으로 폴백|
|`nth`|integer|X|셀렉터가 여러 요소에 매칭될 때 선택할 인덱스 (0-based). 기본값 0|
|`frame_path`|array<Selector>|X|요소가 iframe 안에 있을 때, 바깥에서부터 안쪽까지 순서대로 iframe을 찾아 들어가기 위한 셀렉터 경로. 최상위 문서면 빈 배열|
|`scroll_into_view`|boolean|X|액션 실행 전 요소를 뷰포트로 스크롤할지 여부. 기본값 `true`|

**Selector 객체**

|필드|타입|설명|
|---|---|---|
|`type`|enum|`css` \| `xpath` \| `text` \| `role` \| `test_id` \| `aria_label` \| `placeholder`|
|`value`|string|셀렉터 값 (CSS 문자열, XPath 식, 텍스트 내용, ARIA role 이름 등)|
|`exact`|boolean|`type: "text"` \| `"aria_label"` \| `"placeholder"`일 때만 사용. `true`면 완전 일치, `false`면 부분 일치. 기본값 `true`|
|`role_name`|string|`type: "role"`일 때 접근성 role과 함께 매칭할 accessible name (선택)|

**우선순위 권장 원칙**: `test_id` > `aria_label`/`role` > `css`(안정적인 id/data 속성) > `text` > `xpath`(가장 깨지기 쉬움, 최후 수단) 순으로 레코더가 후보를 채운다.

## 5. `value` 표현식 정의

`input`, `select_option`, `alert`(prompt) 등 값을 필요로 하는 액션은 `value` 필드에 값의 출처를 명시합니다. 값을 리터럴로 하드코딩하지 않고 출처를 구분해, 같은 스크립트를 다른 데이터로 재사용하거나 이전 스텝의 추출 결과를 이어 쓸 수 있게 합니다.

|`type`|예시|설명|
|---|---|---|
|`literal`|`{ "type": "literal", "value": "홍길동" }`|스크립트에 고정된 값|
|`variable`|`{ "type": "variable", "name": "username" }`|`variables`에 정의된 입력값 참조|
|`extracted_ref`|`{ "type": "extracted_ref", "name": "welcome_message" }`|이전 스텝에서 `extract_as`로 저장한 값을 참조 (예: 검색 결과 제목을 다음 입력값으로 재사용)|
|`expression`|`{ "type": "expression", "value": "today() + '-report'" }`|레코더가 지원하는 제한된 표현식 언어로 계산되는 값 (날짜 조합, 문자열 결합 등). 임의 스크립트 실행이 아닌 화이트리스트 함수만 허용|

**비고**

- `secret` 타입 변수를 참조하는 `value`는 실행 로그에 항상 마스킹되어 남습니다.
- `expression`은 신뢰할 수 없는 코드 실행을 막기 위해 별도의 임의 JS 실행 채널이 아니라, 플랫폼이 사전에 정의한 안전한 함수 집합(`today()`, `concat()`, `random_int()` 등)만 허용합니다. 범용 스크립트 실행이 필요하면 8~10장의 `execute_script` 액션(고급, 기본 비활성)을 사용합니다.

## 6. Step 공통 필드

모든 `steps[]` 원소는 아래 공통 필드를 가지며, `action` 값에 따라 7~10장에서 정의하는 액션별 필드가 추가됩니다.

|필드|타입|필수|설명|
|---|---|---|---|
|`id`|string|O|스텝 고유 식별자. 결과/에러 리포트에서 스텝을 참조하는 키|
|`action`|enum|O|액션 타입 (7~10장 카탈로그의 값 중 하나)|
|`target`|Target|액션별|요소를 조작하는 액션에서 필수 (4장)|
|`value`|Value|액션별|값을 입력/전달하는 액션에서 필수 (5장)|
|`options`|object|X|액션별 추가 파라미터 (예: `scroll`의 `direction`, `key_press`의 `key`)|
|`extract_as`|string|X|이 스텝의 결과값을 저장할 이름. 지정 시 최종 output JSON(11장)의 키가 됨|
|`wait_before`|Wait|X|액션 실행 **전** 대기 조건|
|`wait_after`|Wait|X|액션 실행 **후** 대기 조건 (예시 JSON의 `timeout_ms`는 이 객체의 축약형)|
|`on_error`|ErrorPolicy|X|이 스텝이 실패했을 때의 처리 방식. 생략 시 시나리오 기본 정책(중단) 적용|
|`condition`|Condition|X|이 스텝을 실행할지 여부를 결정하는 조건 (예: 이전 추출값이 특정 조건일 때만 실행)|

`**Wait**` **객체**

|필드|타입|설명|
|---|---|---|
|`timeout_ms`|integer|최대 대기 시간(ms). 초과 시 `on_error` 정책 적용|
|`wait_until`|enum|`fixed_delay` \| `selector_visible` \| `selector_hidden` \| `network_idle` \| `dom_content_loaded` \| `load` \| `dialog_present`. 생략 시 `fixed_delay`(단순 대기)로 간주|
|`target`|Target|`wait_until`이 `selector_visible`/`selector_hidden`일 때 대상 요소|

> 최상위 예시의 `"wait_after": { "timeout_ms": 5000 }`는 `wait_until` 생략 → 최대 5초의 고정 대기를 의미합니다.

`**ErrorPolicy**` **객체**

```
"on_error": { "strategy": "retry", "retry_count": 2, "retry_interval_ms": 1000 }
```

|필드|타입|설명|
|---|---|---|
|`strategy`|enum|`abort`(전체 실행 중단, 기본값) \| `skip`(이 스텝만 건너뛰고 계속) \| `retry`(재시도 후에도 실패하면 abort)|
|`retry_count`|integer|`strategy: "retry"`일 때 최대 재시도 횟수|
|`retry_interval_ms`|integer|재시도 간 대기 시간|

`**Condition**` **객체 (선택)**

```
"condition": { "source": "extracted_ref", "name": "welcome_message", "op": "contains", "value": "관리자" }
```

Self-Evolving 루프에서 에이전트가 분기 로직을 스스로 추가할 때 사용하는 필드로, `op`는 `equals` | `contains` | `exists` | `not_exists` 등을 지원합니다.

## 7. 액션 카탈로그 (1) — 탐색 · 탭/창 관리

|`action`|대상|필수 입력|산출/부가 필드|설명|
|---|---|---|---|---|
|`navigate`|없음|`options.url`|-|지정 URL로 이동|
|`back`|없음|없음|-|브라우저 뒤로가기|
|`forward`|없음|없음|-|브라우저 앞으로가기|
|`reload`|없음|없음|`options.hard` (boolean, 캐시 무시 새로고침 여부)|현재 페이지 새로고침|
|`open_tab`|없음|`options.url`(선택)|`extract_as`에 새 `tab_id` 저장 가능|새 탭/창을 열고, 이후 `switch_tab`으로 전환하기 전까지는 현재 활성 탭은 그대로 유지|
|`switch_tab`|없음|`options.tab_ref`(직전 `open_tab`의 `extract_as` 값 참조, 또는 `"latest"` \| `"opener"`)|-|이후 스텝들이 조작할 대상 탭/창을 전환|
|`close_tab`|없음|`options.tab_ref`(생략 시 현재 활성 탭)|-|지정 탭을 닫고, 닫은 탭이 활성 탭이었다면 opener 탭으로 자동 복귀|
|`resize_window`|없음|`options.width`, `options.height`|-|뷰포트/창 크기 변경 (반응형 UI 재현용)|

**예시 — 새 창 열기 후 전환**

```
{ "id": "open_help", "action": "open_tab",  "target": { "selectors": [{ "type": "css", "value": "#help-link" }] },  "options": { "trigger": "click_target" },  "extract_as": "help_tab", "wait_after": { "timeout_ms": 5000 } },{ "id": "switch_to_help", "action": "switch_tab",  "options": { "tab_ref": { "type": "extracted_ref", "name": "help_tab" } } }
```

> `open_tab`이 `target`을 함께 가지면, URL로 직접 여는 것이 아니라 해당 요소를 클릭했을 때 열리는 새 탭(예: `target="_blank"` 링크)을 캡처했다는 의미이며 `options.trigger: "click_target"`로 구분합니다.

## 8. 액션 카탈로그 (2) — 마우스 · 키보드 · 폼 조작

|`action`|`target`|`value`|부가 `options`|설명|
|---|---|---|---|---|
|`click`|필수|-|`button`(`left`\|`right`\|`middle`), `click_count`|단일 클릭|
|`dblclick`|필수|-|-|더블 클릭|
|`right_click`|필수|-|-|우클릭 (컨텍스트 메뉴 오픈)|
|`hover`|필수|-|-|마우스 오버 (툴팁/서브메뉴 트리거)|
|`drag_and_drop`|필수 (시작 요소)|-|`options.target_selector`(드롭 대상 Selector)|요소를 다른 요소 위로 드래그|
|`input`|필수|필수|`clear_first`(boolean, 기본 `true`)|텍스트 입력 필드에 값 입력|
|`clear`|필수|-|-|입력 필드 값 비우기|
|`key_press`|선택(포커스된 요소에 누르려면 생략 가능)|-|`options.key`(예: `"Enter"`, `"Tab"`, `"Escape"`), `options.modifiers`(`["Shift","Ctrl"]`)|키보드 키 입력|
|`select_option`|필수 (`<select>`)|필수 (`literal`\|`variable`로 옵션 값 지정)|`options.by`(`"value"`\|`"label"`\|`"index"`)|드롭다운에서 옵션 선택|
|`check` / `uncheck`|필수 (체크박스)|-|-|체크박스를 체크/해제된 상태로 강제 설정 (토글 아님, 멱등)|
|`radio_select`|필수 (선택할 라디오 옵션)|-|-|라디오 그룹에서 특정 옵션 선택|
|`upload_file`|필수 (`<input type="file">`)|필수 (`file_path` 타입 변수 참조)|`options.multiple`(boolean)|로컬 파일을 파일 입력 요소에 첨부|

**예시 — select_option / upload_file**

```
{ "id": "choose_dept", "action": "select_option",  "target": { "selectors": [{ "type": "css", "value": "#department" }] },  "value": { "type": "literal", "value": "engineering" },  "options": { "by": "value" } },{ "id": "attach_resume", "action": "upload_file",  "target": { "selectors": [{ "type": "css", "value": "#resume-input" }] },  "value": { "type": "variable", "name": "upload_doc_path" } }
```

## 9. 액션 카탈로그 (3) — 다이얼로그 · 컨텍스트 전환

|`action`|`target`|전용 필드|설명|
|---|---|---|---|
|`alert`|없음|`alert_action`(`"accept"`\|`"dismiss"`), `value`(prompt형일 때 입력할 값)|브라우저 네이티브 `alert`/`confirm`/`prompt` 다이얼로그 처리. `extract_as` 지정 시 다이얼로그의 메시지 텍스트를 저장 (예시의 `confirm_question`)|
|`iframe_enter`|필수 (iframe 요소 자신)|-|이후 스텝들의 `target` 탐색 범위를 이 iframe 내부로 전환 (또는 각 스텝의 `target.frame_path`로 매번 명시하는 방식과 양자택일)|
|`iframe_exit`|없음|-|탐색 범위를 상위 문서(또는 최상위 문서)로 복귀|
|`scroll`|선택 (요소 기준 스크롤 시)|`options.direction`(`"up"`\|`"down"`\|`"to_element"`), `options.amount_px`|페이지 또는 특정 요소로 스크롤|
|`focus`|필수|-|요소에 포커스 이동 (탭 순서 검증, 키 입력 준비 등에 사용)|
|`blur`|필수|-|요소에서 포커스 해제 (`blur` 이벤트로 트리거되는 유효성 검사 등을 재현)|

`**alert**` **액션 상세**

```
{ "id": "confirm_login", "action": "alert",  "alert_action": "accept",  "extract_as": "confirm_question",  "wait_after": { "timeout_ms": 5000 } }
```

- `alert_action: "accept"`는 `alert`/`confirm`에서는 확인(OK) 버튼을, `prompt`에서는 값 입력 후 확인을 의미합니다.
- `alert_action: "dismiss"`는 취소(Cancel)를 의미합니다.
- `prompt` 다이얼로그에 값을 입력해야 한다면 `value` 필드를 함께 사용합니다: `"value": { "type": "variable", "name": "reason" }`.
- `extract_as`로 저장되는 값은 다이얼로그가 사용자에게 보여준 메시지 텍스트이며, 이는 11장의 output JSON에 그대로 포함됩니다.

## 10. 액션 카탈로그 (4) — 추출 · 검증 · 스크린샷 · 대기

|`action`|`target`|전용 필드|설명|
|---|---|---|---|
|`extract`|필수|`options.extract_type`(`"text"`\|`"value"`\|`"attribute"`\|`"html"`\|`"count"`), `options.attribute_name`(속성 추출 시)|요소에서 값을 읽어 `extract_as`에 저장. **입력은 없고 출력만 있는 액션**|
|`assert`|필수|`options.assert_type`(`"visible"`\|`"hidden"`\|`"enabled"`\|`"disabled"`\|`"text_equals"`\|`"text_contains"`\|`"value_equals"`\|`"count_equals"`), `options.expected`|화면 상태를 검증. 실패 시 `on_error` 정책 적용|
|`screenshot`|선택(생략 시 전체 페이지)|`options.full_page`(boolean)|현재 화면 또는 특정 요소를 이미지로 캡처. `extract_as` 지정 시 결과 JSON에 이미지 참조(파일 경로/URL)로 저장|
|`wait`|선택|`Wait` 객체(6장)를 `options`에 그대로 사용|별도 액션 없이 순수하게 대기만 수행 (네트워크 응답, 애니메이션 종료 대기 등)|

`**extract**` **예시 (원본 예시의** `**read_welcome**`**과 동일 패턴)**

```
{ "id": "read_welcome", "action": "extract",  "target": { "selectors": [{ "type": "css", "value": "#welcome" }] },  "options": { "extract_type": "text" },  "extract_as": "welcome_message",  "wait_after": { "timeout_ms": 8000 } }
```

`**assert**` **예시**

```
{ "id": "verify_logged_in", "action": "assert",  "target": { "selectors": [{ "type": "css", "value": ".user-avatar" }] },  "options": { "assert_type": "visible" },  "on_error": { "strategy": "abort" } }
```

`extract`는 값을 "가져와서 기록"하는 데, `assert`는 조건을 "만족하는지 확인"하는 데 쓰입니다 — 후자는 실패 시 바로 에러로 처리되어 Self-Evolving 루프가 실패 지점을 정확히 짚어낼 수 있게 합니다.

## 11. 실행 결과(Output) 스키마

시나리오를 실행하면, `steps` 안에서 `extract_as`로 이름 붙여진 값들이 모여 하나의 결과 JSON으로 만들어집니다. 이 결과는 최상위 `outputs` 필드로 필터링할 수 있습니다.

```
{  "scenario_id": "login_with_confirm",  "status": "success",  "started_at": "2026-09-21T13:00:00+09:00",  "finished_at": "2026-09-21T13:00:07+09:00",  "results": {    "confirm_question": "정말 로그인 하시겠습니까?",    "welcome_message": "홍길동님, 환영합니다."  },  "failed_step": null,  "step_log": [    { "step_id": "enter_username", "status": "success", "duration_ms": 320 },    { "step_id": "confirm_login", "status": "success", "duration_ms": 210 }  ]}
```

|필드|타입|설명|
|---|---|---|
|`scenario_id`|string|실행된 시나리오의 `id`|
|`status`|enum|`success` \| `failed` \| `partial`(일부 스텝이 `skip` 정책으로 건너뛰어짐)|
|`results`|object|`extract_as` 이름 → 추출된 값. `outputs` 미지정 시 등장한 모든 `extract_as` 포함|
|`failed_step`|string \| null|실패한 스텝의 `id`. 성공 시 `null`|
|`step_log`|array|각 스텝의 실행 상태와 소요 시간 (디버깅 및 Self-Evolving 분석용)|

Self-Evolving 에이전트는 `failed_step`과 `step_log`를 근거로 실패한 스텝의 `target.selectors`를 보강하거나 `wait_after.timeout_ms`를 조정하는 식으로 스크립트를 스스로 수정합니다.

## 12. 전체 예시 JSON

원본 예시(로그인 + confirm 다이얼로그)에 새 창 열기 → 전환 → 드롭다운 선택 → 파일 업로드 → 검증까지 이어지도록 확장한 예시입니다.

```
{  "schema_version": 1,  "id": "login_and_submit_request",  "name": "Login, Open Help Tab, Submit Request Form",  "description": "사내 시스템에 로그인한 뒤, 도움말을 새 탭으로 확인하고, 신청서 폼에 부서를 선택하고 파일을 첨부해 제출합니다.",  "start_url": "https://intranet.example.com/login",  "variables": {    "username": { "type": "string", "required": true, "description": "사내 시스템 로그인 아이디" },    "password": { "type": "secret", "required": true, "description": "사내 시스템 로그인 비밀번호" },    "upload_doc_path": { "type": "file_path", "required": true, "description": "첨부할 신청서 파일 경로" }  },  "steps": [    { "id": "enter_username", "action": "input",      "target": { "selectors": [{ "type": "css", "value": "#username-input" }] },      "value": { "type": "variable", "name": "username" },      "wait_after": { "timeout_ms": 5000 } },    { "id": "enter_password", "action": "input",      "target": { "selectors": [{ "type": "css", "value": "#password-input" }] },      "value": { "type": "variable", "name": "password" },      "wait_after": { "timeout_ms": 5000 } },    { "id": "click_login", "action": "click",      "target": { "selectors": [{ "type": "test_id", "value": "login-submit" }, { "type": "css", "value": "#login-btn" }] },      "wait_after": { "timeout_ms": 5000 } },    { "id": "confirm_login", "action": "alert", "alert_action": "accept",      "extract_as": "confirm_question", "wait_after": { "timeout_ms": 5000 } },    { "id": "open_help", "action": "open_tab",      "target": { "selectors": [{ "type": "text", "value": "도움말", "exact": true }] },      "options": { "trigger": "click_target" },      "extract_as": "help_tab", "wait_after": { "timeout_ms": 5000 } },    { "id": "switch_to_help", "action": "switch_tab",      "options": { "tab_ref": { "type": "extracted_ref", "name": "help_tab" } } },    { "id": "close_help", "action": "close_tab", "options": { "tab_ref": "latest" } },    { "id": "choose_dept", "action": "select_option",      "target": { "selectors": [{ "type": "css", "value": "#department" }] },      "value": { "type": "literal", "value": "engineering" },      "options": { "by": "value" } },    { "id": "attach_resume", "action": "upload_file",      "target": { "selectors": [{ "type": "css", "value": "#resume-input" }] },      "value": { "type": "variable", "name": "upload_doc_path" } },    { "id": "submit_form", "action": "click",      "target": { "selectors": [{ "type": "css", "value": "#submit-btn" }] },      "wait_after": { "timeout_ms": 5000, "wait_until": "network_idle" } },    { "id": "read_welcome", "action": "extract",      "target": { "selectors": [{ "type": "css", "value": "#welcome" }] },      "options": { "extract_type": "text" },      "extract_as": "welcome_message", "wait_after": { "timeout_ms": 8000 } }  ],  "outputs": ["confirm_question", "welcome_message"]}
```

## 13. 버전 관리 및 확장 가이드

`**schema_version**`**을 올려야 하는 경우 (Breaking Change)**

- 기존 `action` 타입의 필수 필드가 추가/삭제/이름 변경되는 경우
- `target`, `value`, `Wait` 등 공통 객체의 구조가 바뀌는 경우
- 기존 액션의 의미가 달라지는 경우 (예: `click`의 기본 동작이 변경)

**올리지 않아도 되는 경우 (Backward-Compatible)**

- 새로운 `action` 타입 추가 (기존 실행기는 모르는 타입을 만나면 `on_error` 정책에 따라 스킵/중단하면 되므로 호환 유지)
- 기존 객체에 선택 필드(optional) 추가
- `metadata` 등 자유 형식 필드 내부 확장

**새 액션 타입을 추가하는 절차**

1. 카탈로그(7~10장)에 항목을 추가하고, 어떤 카테고리(탐색/조작/전환/추출)에 속하는지 표기한다.
2. 필수/선택 입력 필드와, 있다면 `extract_as`로 저장되는 출력 형태를 명시한다.
3. 기존 액션과 필드를 최대한 재사용한다 (예: 새 마우스 제스처는 `click`처럼 `target` + `options`만으로 표현 가능한지 먼저 검토).
4. Self-Evolving 에이전트가 실패를 스스로 진단할 수 있도록, 이 액션이 실패했을 때 `step_log`에 남길 실패 사유 코드를 함께 정의한다.
5. 실행기(Executor)와 레코더 양쪽에 동시 반영하고, 한쪽만 지원하는 과도기에는 `metadata.recorder_version` / `metadata.executor_min_version`으로 최소 호환 버전을 명시한다.

**하위 호환 원칙**

실행기는 알 수 없는 필드를 만나면 무시하고, 알 수 없는 `action` 값을 만나면 해당 스텝을 실패 처리하되 전체 실행은 시나리오의 최상위 정책(`on_error` 기본값)을 따릅니다. 이를 통해 스키마가 계속 확장되어도 과거에 기록된 시나리오 JSON들이 최대한 오래 재사용될 수 있게 합니다.