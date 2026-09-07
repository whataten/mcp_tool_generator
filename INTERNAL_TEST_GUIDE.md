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

| 필드 | 의미 |
|---|---|
| `status` | `success` = 전 스텝 완료 / `error` = 중간에 실패 |
| `step_results[]` | 위에서부터 훑어서 `"status": "error"`가 처음 나오는 곳이 실패 지점 |
| `extracted` | `extract` 스텝으로 읽어온 값. 기대한 값이 맞는지 확인 |
| `error.error_type` | 실패 원인 분류 |
| `error.attempted_selectors` | 시도했지만 못 찾은 셀렉터 목록 |
| `alerts_handled` | 자동으로 닫은 alert 창의 문구 목록. 예상 못한 안내창이 떴는지 여기서 확인 |
| `screenshot_path` | **성공/실패 모두 스크린샷이 남습니다.** 이 경로의 png를 열어보면 그 순간 화면을 볼 수 있습니다 |

`status`가 `success`여도 `extracted` 값이 이상하면(빈 문자열 등) 논리적으로는 실패입니다.
스크린샷을 같이 확인하세요.

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

- **iframe 안의 요소** — 최상위 문서에서만 찾습니다
- **파일 업로드 다이얼로그** (OS 창이라 셀레늄이 제어 불가)
- **OS 클립보드를 실제로 거치는 복사·붙여넣기** — 값을 직접 읽어 넣는 방식으로 대신합니다 (9장)

> `alert()` / `confirm()` / `prompt()` 창은 지원합니다 (8장).
> 새 창·팝업도 지원합니다 (10장) — 팝업으로 뜨는 SSO 로그인도 `switch_window`로 다룰 수 있습니다.

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
`extract`로 읽어둔 값을 뒤 스텝에서 `"type": "extracted"`로 가져다 씁니다.

```json
{
  "id": "copy_order_no",
  "action": "extract",
  "target": { "selectors": [{ "type": "css", "value": "#order-no" }] },
  "extract_as": "order_no"
},
{
  "id": "paste_order_no",
  "action": "input",
  "target": { "selectors": [{ "type": "css", "value": "#search-input" }] },
  "value": { "type": "extracted", "name": "order_no" }
}
```

`value`에 쓸 수 있는 세 가지:

| type | 값의 출처 |
|---|---|
| `variable` | tool 호출 시 넘어온 인자 (`name`이 `variables`의 키) |
| `literal` | 레코딩에 고정으로 적어둔 값 (`value`) |
| `extracted` | 앞선 `extract` 스텝이 읽어둔 값 (`name`이 그 스텝의 `extract_as`) |

> **OS 클립보드(Ctrl+C/Ctrl+V)를 쓰지 않습니다.** 클립보드는 사용자가 쓰던 복사 내용을
> 덮어쓰고 다른 프로그램과도 얽혀서 자동화에 불안정합니다. 화면의 값을 직접 읽어 넣는
> 지금 방식이 결과는 같으면서 훨씬 안정적입니다. 화면에 "복사" 버튼이 있다면 그 버튼도
> `click`으로 눌러주되(사내 시스템이 클릭 여부를 기록할 수 있으므로), 실제 값은 위처럼
> `extract`로 읽으시면 됩니다.
>
> 참고 예시: `recordings/copy_order_no_and_search.json`

---

## 10. 새 창(팝업)에서 작업하기

버튼을 눌러 새 창이 떠도 **셀레늄은 원래 창을 계속 보고 있습니다.** 새 창의 요소를
건드리려면 `switch_window`로 옮겨가야 합니다.

```json
{
  "id": "open_picker",
  "action": "click",
  "target": { "selectors": [{ "type": "css", "value": "#open-picker-btn" }] }
},
{
  "id": "switch_to_picker",
  "action": "switch_window",
  "window_target": "new",
  "wait_after": { "timeout_ms": 8000 }
},

  ... 새 창에서의 input / click / extract 스텝들 ...

{
  "id": "switch_back_to_main",
  "action": "switch_window",
  "window_target": "original"
}
```

`window_target` 값:

| 값 | 의미 |
|---|---|
| `new` | 가장 최근에 열린 창으로 이동 (창이 뜰 때까지 `wait_after`만큼 기다림) |
| `original` | 레코딩을 시작한 원래 창으로 복귀 |
| `match` | `window_match`에 적은 문자열이 URL 또는 제목에 포함된 창으로 이동 |

- 새 창이 여러 개 뜨는 경우에는 `match`로 어느 창인지 지정하는 편이 안전합니다.
- 팝업이 스스로 닫히지 않는다면 `close_window` 액션으로 닫고 원래 창으로 돌아올 수 있습니다.
- 지정한 시간 안에 창을 못 찾으면 `window_not_found`로 실패합니다.

> 팝업에서 "선택 완료"를 누르면 팝업이 스스로 닫히고 값이 원래 창에 반영되는 방식이 흔한데,
> 이때도 `switch_window`(`original`)로 돌아와서 반영된 값을 `extract`하면 됩니다.
>
> 참고 예시: `recordings/pick_employee_in_popup.json`

막히면 어느 지점에서 어떤 화면이었는지(스크린샷) 기록해두시면 이후 대응이 쉽습니다.

---

## 부록: 지원 액션 목록

레코딩 JSON의 `action`에 쓸 수 있는 값입니다.

| action | 동작 | 필요한 필드 |
|---|---|---|
| `input` | 텍스트 입력 | `target`, `value` |
| `click` | 클릭 | `target` |
| `select` | 드롭다운 선택 | `target`, `value` |
| `navigate` | URL 이동 | `value` (이동할 주소) |
| `wait` | 대기 | `target` 있으면 그 요소를 기다림, 없으면 시간만큼 대기 |
| `extract` | 화면에서 값 읽기 | `target`, `extract_as` (결과 key), `extract_attribute` (선택) |
| `alert` | alert/confirm 창 닫기 | `alert_action` (선택), `extract_as` (선택), `alert_input` (선택) |
| `switch_window` | 다른 창으로 이동 | `window_target`, `window_match` (`match`일 때) |
| `close_window` | 현재 창을 닫고 원래 창으로 복귀 | 없음 |

셀렉터는 `target.selectors` 배열에 여러 개 넣으면 **앞에서부터 순서대로 시도**해서
먼저 잡히는 것을 사용합니다 (css/xpath 혼용 가능).
