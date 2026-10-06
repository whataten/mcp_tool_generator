# 사내망 테스트 가이드

사내망 PC에서 이 프로젝트를 실행해 사내 시스템 레코딩을 테스트하는 절차입니다.
위에서부터 순서대로 진행하세요.

---

## 0. 시작 전 확인 (중요)

### 0-1. 실제 시스템에 실제로 반영됩니다

이 도구는 셀레늄으로 **진짜 브라우저를 조작**합니다. 레코딩에 발주 제출·저장·삭제 같은
쓰기 동작이 들어 있으면 **사내 시스템에 실제로 반영됩니다.** 되돌릴 수 없습니다.

- 처음에는 **조회성 레코딩**(검색/조회만 하는 것)으로 시작하세요.
- 쓰기 동작을 테스트해야 한다면 **테스트 계정 / 테스트 데이터**로 하세요.

### 0-2. 파이썬 버전 확인

```
python --version
```

**Python 3.13 (64비트)여야 합니다.** `wheels\` 폴더의 패키지 중 4개가 3.13 전용으로
받아온 것이라, 버전이 다르면 오프라인 설치가 실패합니다.

- 3.13이 아니면 → 사내망에서 인터넷이 되는지 확인 후 `pip install -r requirements.txt`를
  그냥 시도하거나, 밖에서 해당 버전용 wheel을 다시 받아와야 합니다.

### 0-3. 브라우저 버전 확인

Edge 주소창에 `edge://version` 입력 → 버전 확인.

**`131.0.2903.146`이어야 합니다.** 챙겨온 `drivers\msedgedriver.exe`가 이 버전 전용입니다.
다르면 4단계 실행 시 `SessionNotCreatedException`이 납니다.

### 0-4. 폴더 위치

프로젝트 폴더를 **경로가 짧은 위치**(예: `C:\work\mcp_tool_generator`)에 두세요.
경로가 깊으면 설치 중 Windows 260자 제한(`WinError 206`)에 걸립니다.

---

## 1. 패키지 설치 (오프라인)

프로젝트 폴더에서:

```
python -m venv .venv
```

```
.venv\Scripts\python.exe -m pip install --no-index --find-links=wheels -r requirements.txt
```

마지막에 `Successfully installed ... mcp-2.1.1 ... selenium-4.48.0 ...`이 나오면 성공입니다.

> 이후 모든 명령은 `.venv\Scripts\python.exe`를 사용합니다. conda 환경을 쓰신다면
> 그 환경의 python 경로로 바꿔서 쓰시면 됩니다.

---

## 2. 레코딩 JSON 배치

사내 시스템 기준으로 만든 레코딩 JSON 파일을 `recordings\` 폴더에 넣습니다.

파일명은 자유이며, JSON 안의 `id` 값이 곧 MCP tool 이름이 됩니다.

확인해야 할 항목:

| 항목 | 확인 내용 |
|---|---|
| `start_url` | 사내 시스템의 실제 URL로 되어 있는지 |
| `id` | 영문/숫자/밑줄만 사용 (tool 이름이 됨) |
| `description` | 10자 이상 |
| 로그인 스텝 | **매 호출마다 `start_url`부터 새로 시작하므로, 로그인이 필요한 시스템이면 로그인 스텝이 레코딩에 포함되어 있어야 합니다** |

---

## 3. 드라이버 경로 설정

**cmd 사용 시:**
```
set MCP_TOOL_GENERATOR_DRIVER_PATH=%CD%\drivers\msedgedriver.exe
```

**PowerShell 사용 시:**
```
$env:MCP_TOOL_GENERATOR_DRIVER_PATH = "$PWD\drivers\msedgedriver.exe"
```

> cmd와 PowerShell은 환경변수 문법이 다릅니다. PowerShell에서 `set VAR=값`을 쓰면
> 적용되지 않으니 주의하세요.

브라우저가 Chrome이라면 추가로 (기본값은 `edge`라 Edge를 쓰신다면 설정 불필요):

```
set MCP_TOOL_GENERATOR_BROWSER=chrome
```
```
$env:MCP_TOOL_GENERATOR_BROWSER = "chrome"
```

### 창 동작 관련 옵션

| 환경변수 | 값 | 설명 |
|---|---|---|
| `MCP_TOOL_GENERATOR_WINDOW_MODE` | `visible` (기본) | 평범한 창으로 띄움 |
| | `background` | 창을 화면 밖에 두어 작업을 방해하지 않음. 스크린샷은 정상 |
| | `headless` | 창을 아예 안 띄움. 가장 빠르지만 SSO 로그인 페이지가 거부하는 경우가 있음 |
| `MCP_TOOL_GENERATOR_KEEP_BROWSER` | `1` (기본) | tool 호출이 끝나도 창을 닫지 않음 |
| | `0` | 끝나면 창을 닫음 (반복 테스트 시 권장) |
| `MCP_TOOL_GENERATOR_ALERT_ACTION` | `accept` (기본) | alert/confirm 창이 뜨면 확인(OK)을 눌러 진행 |
| | `dismiss` | 취소(Cancel)를 눌러 진행 |
| | `error` | 닫지 않고 그 스텝을 실패 처리 (`alert_open`) |

> **`KEEP_BROWSER=1`이면 tool 호출마다 창이 하나씩 쌓입니다.** 여러 번 테스트하실 때는
> `0`으로 두시거나, 중간중간 창을 직접 닫아주세요.

---

## 4. 등록 확인 + 실행 테스트

같은 창에서(환경변수가 유지된 상태로) 실행합니다.

**권장 방식 — `key=value`** (cmd/PowerShell 모두 동일하게 동작, 따옴표 문제 없음):

```
.venv\Scripts\python.exe scripts\mcp_e2e_test.py <레코딩id> 변수명=값 변수명2=값2
```

예시 — 레코딩 `id`가 `search_customer_info`이고 `variables`에 `customer_id`가 있다면:

```
.venv\Scripts\python.exe scripts\mcp_e2e_test.py search_customer_info customer_id=12345
```

**값에 공백·특수문자가 있으면 JSON 파일로:**

`args.json` 파일을 만들어서 (UTF-8로 저장)
```json
{ "customer_id": "12345", "memo": "공백 있는 값" }
```
```
.venv\Scripts\python.exe scripts\mcp_e2e_test.py search_customer_info args.json
```

> **PowerShell에서 `"{\"key\": \"값\"}"` 같은 JSON 문자열을 직접 넘기지 마세요.**
> PowerShell이 따옴표를 제거해버려서 `JSONDecodeError`가 납니다. (cmd에서는 동작하지만
> 위의 `key=value` 방식이 어느 셸에서든 안전합니다.)

실행하면:

1. `=== list_tools ===` 아래에 등록된 tool 목록이 출력됩니다.
   여기에 내 레코딩이 안 보이면 → JSON이 검증에 실패한 것. `[WARN]` 메시지 확인.
2. 브라우저 창이 실제로 뜨고 동작이 재생됩니다. (눈으로 확인 가능)
3. 결과 JSON이 출력되고 마지막에 `RESULT: success` 또는 `RESULT: error`가 찍힙니다.

> 창을 띄우지 않고 돌리려면 실행 전에 `set MCP_TOOL_GENERATOR_HEADLESS=1` (cmd) /
> `$env:MCP_TOOL_GENERATOR_HEADLESS = "1"` (PowerShell). 첫 테스트는 창을 띄워서
> 눈으로 확인하시는 것을 권합니다.

---

## 5. 결과 판독법

출력된 JSON에서 볼 곳:

결과 JSON은 `recordings_rule.md` 11장의 실행 결과 스키마를 따릅니다.

| 필드 | 의미 |
|---|---|
| `scenario_id` | 실행된 레코딩의 `id` |
| `status` | `success` = 전부 성공 / `failed` = 중간에 실패 / `partial` = 일부 스텝이 `skip` 정책으로 건너뛰어짐 |
| `failed_step` | 실패한 스텝의 `id` (성공이면 `null`) |
| `results` | `extract_as`로 읽어온 값들. 최상위 `outputs`가 있으면 그 목록으로 걸러짐 |
| `step_log[]` | 스텝별 `success` / `failed` / `skipped`와 소요 시간. `skipped`에는 사유(`note`)가 붙습니다 |
| `started_at` / `finished_at` | 실행 시작·종료 시각 |
| `error.error_type` | 실패 원인 분류 |
| `error.attempted_selectors` | 시도했지만 못 찾은 셀렉터 목록 |
| `alerts_handled` | 자동으로 닫은 alert 창의 문구 목록. 예상 못한 안내창이 떴는지 여기서 확인 |
| `screenshot_path` | **성공/실패 모두 스크린샷이 남습니다.** 이 경로의 png를 열어보면 그 순간 화면을 볼 수 있습니다 |

`status`가 `success`여도 `results` 값이 이상하면(빈 문자열 등) 논리적으로는 실패입니다.
스크린샷을 같이 확인하세요.

`step_log`에서 `skipped`는 두 가지 경우입니다 — `condition`이 맞지 않아 건너뛴 스텝이거나,
레코더가 남긴 관찰용 이벤트(`window_open_call` 등, 아래 11장)입니다.

---

## 6. 문제 해결

### `SessionNotCreatedException`
브라우저와 드라이버 버전 불일치입니다. 아래 둘 중 하나의 메시지로 나타납니다:

```
This version of Microsoft Edge WebDriver only supports Microsoft Edge version 131
Current browser version is 152.0.xxxx.xx
```
```
Microsoft Edge failed to start: exited normally.
(The process started from msedge location ... is no longer running,
 so msedgedriver is assuming that msedge has crashed.)
```

`edge://version`으로 실제 브라우저 버전을 확인하세요. 챙겨온 드라이버는
`131.0.2903.146` 전용입니다. 버전이 다르면 그 버전에 맞는 드라이버를
`https://msedgedriver.microsoft.com/<버전>/edgedriver_win64.zip` 에서 받아야 합니다
(사내망에서 이 주소가 막혀 있다면 외부에서 받아 다시 들고 와야 합니다).

### `selector_not_found`
셀렉터가 페이지에서 안 잡힌 경우입니다. `error.screenshot_path`의 스크린샷을 먼저 여세요.

- 로그인 화면에 멈춰 있다면 → 로그인 스텝이 레코딩에 없거나 실패한 것
- 원하는 화면인데 못 찾는다면 → 셀렉터가 실제 DOM과 안 맞는 것 (F12로 확인)
- 화면이 아직 로딩 중이라면 → 해당 스텝의 `wait_after.timeout_ms`를 늘리기

### `WinError 206` (설치 중)
경로가 너무 깁니다. 프로젝트를 `C:\work\` 같은 짧은 경로로 옮기고 재시도하세요.

### tool 목록에 내 레코딩이 안 보임
JSON 검증 실패입니다. 실행 시 출력되는 `[WARN]` 메시지에 어느 파일의 어떤 필드가
잘못됐는지 나옵니다.

### 브라우저는 뜨는데 페이지가 안 열림 / 인증서 경고
사내 시스템이 자체 서명 인증서를 쓰는 경우일 수 있습니다.
해당 인증서를 OS/브라우저 신뢰 저장소에 설치하는 것이 정석입니다.

---

## 7. 현재 지원하지 않는 것 (막히면 참고)

아래는 지금 인터프리터가 처리하지 못합니다. 사내 시스템이 이 방식을 쓰면 별도 개발이 필요합니다.

- **OS 파일 선택 다이얼로그를 실제로 띄우는 업로드** — `upload_file` 액션은 파일 경로를
  `<input type="file">`에 직접 넣는 방식이라 OS 창이 뜨는 경우는 다루지 못합니다
- **OS 클립보드를 실제로 거치는 복사·붙여넣기** — 값을 직접 읽어 넣는 방식으로 대신합니다 (9장)
- **`network_idle` 대기** — CDP를 쓰지 않아 "로딩 완료 + 짧은 여유"로 근사합니다

> `alert()` / `confirm()` / `prompt()` 창은 지원합니다 (8장).
> 새 창·팝업도 지원합니다 (10장) — 팝업으로 뜨는 SSO 로그인도 `switch_tab`으로 다룰 수 있습니다.
> iframe 안의 요소도 `target.frame_path` 또는 `iframe_enter`/`iframe_exit`로 다룰 수 있습니다.

---

## 8. alert 창 처리

로그인 직후 안내창이 뜨는 것처럼 javascript 다이얼로그가 뜨면, 그게 닫히기 전까지는
브라우저의 다른 모든 조작이 막힙니다. 두 가지 방식으로 처리됩니다.

**자동 처리 (레코딩에 아무것도 안 해도 됨)**

다이얼로그가 뜨면 `MCP_TOOL_GENERATOR_ALERT_ACTION` 설정대로(기본 `accept` = 확인) 닫고
하던 스텝을 이어서 진행합니다. 닫은 창의 문구는 결과 JSON의 `alerts_handled`에 남습니다:

```json
"alerts_handled": ["비밀번호 만료가 30일 남았습니다."]
```

**명시적 처리 (레코딩에 `alert` 스텝 추가)**

언제 어떤 창이 뜨는지 알고 있고, 그 문구를 결과로 받고 싶을 때 씁니다:

```json
{
  "id": "close_notice_alert",
  "action": "alert",
  "alert_action": "accept",
  "extract_as": "login_notice",
  "wait_after": { "timeout_ms": 5000 }
}
```

- `alert_action`: `accept`(확인) 또는 `dismiss`(취소). 생략 시 `accept`
- `extract_as`: 창 문구를 이 이름으로 `extracted`에 담음 (생략 가능)
- `alert_input`: `prompt()` 창에 입력할 텍스트 (해당될 때만)
- 지정한 시간 안에 창이 안 뜨면 `alert_not_found`로 실패합니다

**확인/취소가 있는 `confirm()` 창**도 동일하게 처리됩니다. `accept`가 확인, `dismiss`가
취소입니다. confirm은 누른 버튼에 따라 실제 동작이 갈리므로(확인하면 로그인 진행, 취소하면
진행 안 함), 아래를 주의하세요.

> **기본값이 `accept`라는 것은, 예상 못 한 확인창도 자동으로 "확인"이 눌린다는 뜻입니다.**
> "정말 삭제하시겠습니까?" 같은 창도 마찬가지입니다. 쓰기 동작이 있는 레코딩에서는
> 확인창을 `alert` 스텝으로 명시해두거나, `MCP_TOOL_GENERATOR_ALERT_ACTION=error`로 두고
> 처리되지 않은 창은 실패로 잡히게 하는 편이 안전합니다.

---

## 9. 화면의 값을 복사해서 다른 곳에 붙여넣기

발주번호처럼 화면에 뜬 값을 그대로 다른 입력란에 넣어야 할 때 씁니다.
`extract`로 읽어둔 값을 뒤 스텝에서 `"type": "extracted_ref"`로 가져다 씁니다.

```json
{
  "id": "copy_order_no",
  "action": "extract",
  "target": { "selectors": [{ "type": "css", "value": "#order-no" }] },
  "options": { "extract_type": "text" },
  "extract_as": "order_no"
},
{
  "id": "paste_order_no",
  "action": "input",
  "target": { "selectors": [{ "type": "css", "value": "#search-input" }] },
  "value": { "type": "extracted_ref", "name": "order_no" }
}
```

`value`에 쓸 수 있는 네 가지:

| type | 값의 출처 |
|---|---|
| `variable` | tool 호출 시 넘어온 인자 (`name`이 `variables`의 키) |
| `literal` | 레코딩에 고정으로 적어둔 값 (`value`) |
| `extracted_ref` | 앞선 `extract` 스텝이 읽어둔 값 (`name`이 그 스텝의 `extract_as`) |
| `expression` | 허용된 함수만 쓰는 계산식: `today()`, `now()`, `concat()`, `random_int()`. 예: `"today() + '-report'"` |

`extract`는 `options.extract_type`으로 무엇을 읽을지 정합니다 — `text`(기본) / `value`(입력값) /
`attribute`(`options.attribute_name` 필요) / `html` / `count`.

> **OS 클립보드(Ctrl+C/Ctrl+V)를 쓰지 않습니다.** 클립보드는 사용자가 쓰던 복사 내용을
> 덮어쓰고 다른 프로그램과도 얽혀서 자동화에 불안정합니다. 화면의 값을 직접 읽어 넣는
> 지금 방식이 결과는 같으면서 훨씬 안정적입니다. 화면에 "복사" 버튼이 있다면 그 버튼도
> `click`으로 눌러주되(사내 시스템이 클릭 여부를 기록할 수 있으므로), 실제 값은 위처럼
> `extract`로 읽으시면 됩니다.
>
> 참고 예시: `recordings/copy_order_no_and_search.json`

---

## 10. 새 창(팝업)으로 focus 옮기기

메일쓰기처럼 버튼을 누르면 새 창이 뜨는 경우, **창이 떠도 셀레늄은 원래 창을 계속 보고
있습니다.** 새 창의 요소를 건드리려면 그 창을 이름으로 묶어두고(`open_tab`) 전환
(`switch_tab`)해야 합니다.

```json
{
  "id": "step_001",
  "action": "click",
  "target": { "selectors": [{ "type": "text", "value": "메일쓰기", "exact": true }] },
  "wait_after": { "timeout_ms": 3000 }
},
{
  "id": "step_003",
  "action": "open_tab",
  "extract_as": "compose_tab",
  "wait_after": { "timeout_ms": 5000 }
},
{
  "id": "step_004",
  "action": "switch_tab",
  "options": { "tab_ref": "compose_tab" }
},

  ... 새 창에서의 input / select_option / click 스텝들 ...

{
  "id": "step_012",
  "action": "switch_tab",
  "options": { "tab_ref": "opener" }
}
```

**`open_tab`** — 새로 뜬 창을 `extract_as`의 이름으로 묶어둡니다. 세 가지 형태가 있습니다.

| 형태 | 동작 |
|---|---|
| `target` + `options.trigger: "click_target"` | 그 요소를 클릭해서 창을 열고 묶음 |
| `options.url` | 그 URL로 새 창을 열고 묶음 |
| 둘 다 없음 | 앞선 스텝 때문에 이미 떠 있는(또는 곧 뜰) 창을 묶음 — 실제 레코더가 쓰는 형태 |

세 경우 모두 **활성 창은 바뀌지 않습니다.** `switch_tab`을 해야 focus가 옮겨갑니다.

**`switch_tab`** — `options.tab_ref`로 대상을 지정합니다.

| `tab_ref` | 의미 |
|---|---|
| `"compose_tab"` (이름) | `open_tab`의 `extract_as`로 묶어둔 창 |
| `{ "type": "extracted_ref", "name": "compose_tab" }` | 위와 동일 (객체 형태) |
| `"latest"` | 가장 최근에 열린 창 |
| `"opener"` | 지금 창을 열어준 창(= 원래 창)으로 복귀 |

**`close_tab`** — `options.tab_ref`로 지정한 창을 닫고 opener로 돌아옵니다. 생략하면 현재 창.
팝업이 스스로 닫히는 경우(아래)에는 안 써도 됩니다.

> 팝업에서 "발송"/"선택 완료"를 누르면 팝업이 스스로 닫히고 값이 원래 창에 반영되는 방식이
> 사내 시스템에 흔합니다. 이때도 `switch_tab`(`opener`)으로 돌아와서 반영된 값을
> `extract`하면 됩니다. 이미 닫힌 창을 `close_tab` 해도 에러가 아니라 그냥 넘어갑니다.
>
> 참고 예시: `recordings/compose_mail_in_popup.json` (메일쓰기 → 새 창 → 발송 → 복귀),
> `recordings/pick_employee_in_popup.json` (담당자 검색 팝업)

- 창을 지정한 시간 안에 못 찾으면 `tab_not_found`로 실패합니다.
- 막히면 어느 지점에서 어떤 화면이었는지(스크린샷) 기록해두시면 이후 대응이 쉽습니다.

---

## 11. 레코더가 남기는 관찰용 이벤트

실제 레코더는 `window_open_call`, `sso_popup_recover` 처럼 **브라우저에서 무슨 일이
일어났는지 관찰한 기록**도 함께 남깁니다. 이것들은 재현할 동작이 아니라 흔적이라
실행기는 건너뜁니다 (`step_log`에 `skipped`로 남습니다).

```json
{ "id": "step_002", "action": "window_open_call",
  "options": { "message": "window.open() called", "options": { "url": "...", "opened": true } } }
```

창을 열게 만든 **클릭을 재현하면 창은 알아서 다시 열리기 때문에**, 이 이벤트까지 실행하면
창이 두 번 열립니다. 그래서 의도적으로 실행하지 않습니다.

레코더가 앞으로 새로운 action을 추가해도, 그 스텝만 실패하고 나머지는 계속 실행됩니다
(`recordings_rule.md` 13장의 하위 호환 원칙). 레코딩 전체가 등록 불가가 되지는 않습니다.

---

## 12. 스텝 실패 시의 동작 지정 (`on_error`)

스텝에 `on_error`를 달면 실패했을 때의 처리를 바꿀 수 있습니다.

```json
"on_error": { "strategy": "retry", "retry_count": 2, "retry_interval_ms": 1000 }
```

| `strategy` | 동작 |
|---|---|
| `abort` (기본) | 전체 실행 중단, `status: "failed"` |
| `skip` | 그 스텝만 건너뛰고 계속, 최종 `status: "partial"` |
| `retry` | `retry_count`만큼 재시도 후에도 실패하면 중단 |

가끔 뜨는 안내 배너처럼 **있을 수도 없을 수도 있는 요소**는 `skip`으로, 네트워크가 느려
가끔 놓치는 스텝은 `retry`로 두면 재현 성공률이 올라갑니다.

---

## 부록 A: 지원 액션 목록

`docs/recordings_rule.md` 7~10장의 카탈로그를 모두 지원합니다.

**탐색 · 탭/창** — `navigate`(`options.url`), `back`, `forward`, `reload`,
`open_tab`, `switch_tab`, `close_tab`, `resize_window`(`options.width/height`)

**마우스 · 키보드 · 폼** — `click`(`options.button`, `click_count`), `dblclick`,
`right_click`, `hover`, `drag_and_drop`(`options.target_selector`),
`input`(`options.clear_first`), `clear`, `key_press`(`options.key`, `modifiers`),
`select_option`(`options.by`: value/label/index), `check`, `uncheck`, `radio_select`,
`upload_file`(`file_path` 변수)

**다이얼로그 · 컨텍스트** — `alert`(`alert_action`, prompt면 `value`),
`iframe_enter`, `iframe_exit`, `scroll`(`options.direction`, `amount_px`), `focus`, `blur`

**추출 · 검증** — `extract`(`options.extract_type`), `assert`(`options.assert_type`, `expected`),
`screenshot`(`options.full_page`), `wait`

관찰용(실행하지 않고 건너뜀) — `window_open_call`, `sso_popup_recover`

## 부록 B: 셀렉터

`target.selectors` 배열은 **앞에서부터 순서대로 시도**해서 먼저 잡히는 것을 씁니다.

지원 타입: `css`, `xpath`, `text`, `role`, `test_id`, `aria_label`, `placeholder`
(`text`/`aria_label`/`placeholder`는 `exact: false`로 부분 일치 가능)

| `target` 필드 | 의미 |
|---|---|
| `nth` | 여러 개 매칭될 때 몇 번째를 쓸지 (0부터) |
| `frame_path` | iframe 안의 요소일 때, 바깥에서 안쪽 순서로 iframe 셀렉터 나열 |
| `scroll_into_view` | 조작 전 화면에 보이도록 스크롤 (기본 `true`) |

## 부록 C: 대기 조건 (`wait_before` / `wait_after`)

```json
"wait_before": {
  "timeout_ms": 8000,
  "wait_until": "selector_visible",
  "target": { "selectors": [{ "type": "css", "value": "#welcome" }] }
}
```

`wait_until`: `fixed_delay`(기본) / `selector_visible` / `selector_hidden` /
`network_idle` / `dom_content_loaded` / `load` / `dialog_present`

> **`fixed_delay`의 기본 동작 하나는 명세와 다릅니다.** 명세대로 `timeout_ms`를 꽉 채워
> 자면 스텝마다 3초씩 자느라 재현이 매우 느려집니다. 그래서 기본값은 `timeout_ms`를
> **상한**으로 보고 페이지 로딩이 끝나는 즉시 넘어갑니다. 명세 그대로 전부 재우려면
> `set MCP_TOOL_GENERATOR_FIXED_DELAY_MODE=sleep` 으로 바꾸세요.
