# 구조 설명 (개발자용)

이 문서는 코드를 **고치려는 사람**을 위한 것입니다. 사용법은 `INTERNAL_TEST_GUIDE.md`,
JSON 규격은 `docs/recordings_rule.md`를 보세요.

---

## 1. 한 줄 요약

> **레코딩 JSON 하나 = MCP tool 하나.** 단, JSON이 코드로 변환되지는 않습니다.

이 구분이 핵심입니다. "JSON이 tool이 된다"는 **매핑 관계로는 맞고**, "JSON으로 셀레늄
코드를 생성한다"는 **틀립니다.**

| | 실제 동작 |
|---|---|
| 서버 기동 시 | JSON → 검증된 데이터 객체 + tool 목록 등록 |
| tool 호출 시 | **하나의 공통 실행기**가 그 데이터를 읽으며 셀레늄을 조종 |

레코딩이 100개로 늘어도 **실행 코드는 늘지 않습니다.** 해석할 데이터가 하나 더 생길 뿐입니다.
처음 설계할 때 "레코딩마다 .py를 생성"하는 방식(codegen)과 저울질했고, 이 방식을 택했습니다.
생성된 문자열이 코드로 실행될 여지가 없고, 액션을 하나 고치면 모든 레코딩에 동시에 적용되기
때문입니다.

---

## 2. 모듈 지도

각 파일이 **무엇을 책임지는지**입니다. 고칠 곳을 찾을 때 이 표부터 보세요.

| 파일 | 책임 | 고치는 경우 |
|---|---|---|
| `config.py` | 환경변수 읽기·검증 | 새 설정 추가 |
| `schema.py` | JSON 규격 (Pydantic) | 새 필드·액션 타입·셀렉터 타입 추가 |
| `recording_loader.py` | `recordings/*.json` 스캔·검증 | 로드 단계 경고 추가 |
| `mcp_registration.py` | MCP tool 등록, 호출 받기 | tool 인자 스키마, 응답 포맷 |
| `interpreter.py` | 스텝 순회, 에러 정책, 결과 조립 | 실행 흐름, 에러 분류, 재시도 |
| `selenium_runner.py` | 실제 브라우저 조작 | **액션 구현, 셀렉터 해석** (대부분 여기) |
| `result_models.py` | 결과 JSON 형태 | 결과에 필드 추가 |
| `server.py` | 조립 + stdio 서버 기동 | 거의 안 건드림 |

의존 방향은 **한쪽으로만** 흐릅니다. 역방향 import를 만들지 마세요.

```
server → mcp_registration → interpreter → selenium_runner → schema/config
                     ↘ recording_loader ↗
```

---

## 3. 서버 기동 흐름 (등록)

`python server.py` 한 번에 아래가 전부 끝납니다.

```
1. recording_loader.load_all_recordings()
     recordings/*.json 을 하나씩 읽어 schema.Recording 으로 검증
     깨진 파일은 경고만 남기고 건너뜀  ← 한 파일 때문에 서버가 죽지 않게

2. mcp_registration.ToolRegistry(recordings)
     레코딩마다 build_input_model() 로 Pydantic 입력 모델을 즉석 생성
       variables: {"sku": {...}} → class place_purchase_order__Input(sku: str, ...)
     이게 "등록"의 실체. self.models[id] 에 '클래스 자체'가 저장됨

3. Server(on_list_tools=..., on_call_tool=...) 로 핸들러 연결
4. stdio_server() 로 표준입출력을 MCP 통신 채널로 열고 대기
```

**중요**: 이 시점에 브라우저는 뜨지 않습니다. 셀레늄은 아직 전혀 관여하지 않습니다.

`tools/list` 요청이 오면 `ToolRegistry.list_tools()`가 2번에서 만들어둔 것을 **조회만 해서**
`types.Tool(name=id, description=..., inputSchema=모델의 JSON Schema)`로 돌려줍니다.

---

## 4. tool 호출 흐름 (실행)

```
LLM: tools/call(name="place_purchase_order", arguments={"sku": "SKU-1001", ...})
  │
  ├─ mcp_registration.call_tool()
  │    · recordings[name] 조회 (없으면 에러 결과)
  │    · models[name].model_validate(arguments) 로 인자 검증 → bound_vars
  │    · asyncio.to_thread(...) 로 별도 스레드에서 실행
  │        └ 셀레늄은 동기 코드라, 그냥 돌리면 MCP 이벤트 루프 전체가 멈춤
  │
  ├─ interpreter.RecordingInterpreter.run(bound_vars)
  │    · sr.new_driver()            브라우저 실행 (실패해도 결과로 반환)
  │    · driver.get(start_url)
  │    · 로그인 선행 스텝 (설정된 경우)
  │    · for step in recording.steps:
  │         _run_step() → sr.execute_step()
  │    · 끝나면 settle 대기 후 최종 스크린샷
  │    · ToolResult 조립
  │
  └─ 결과를 JSON 직렬화해 TextContent 로 반환 (실패 시 스크린샷을 ImageContent 로 첨부)
```

### 스텝 하나가 실행되는 과정

```
interpreter._run_step(step)
  │  재시도 정책(on_error), stale element 1회 자동 재시도, step_log 기록
  │
  └ selenium_runner.execute_step(driver, step, bound_vars, extracted, ctx)
      │  1. 열려있는 다이얼로그 정리 (auto_handle_alert)
      │  2. wait_before 적용
      │  3. dispatch() ─ step.action 문자열로 분기
      │       "click"  → _click_element(_find(...))
      │       "input"  → _type_into(...)
      │       "extract"→ _extract(...)
      │       ...
      │  4. 도중 다이얼로그가 뜨면 닫고 한 번 더 시도
      │  5. wait_after 적용
      └ 추출값 dict 반환 (없으면 None)
```

`dispatch()`는 **거대한 if/elif 분기**입니다. 일부러 그렇게 뒀습니다 — 액션을 찾을 때
한 곳만 보면 되고, 디스패치 테이블보다 추적이 쉽습니다.

---

## 5. 세 가지 핵심 개념

### 5-1. 요소 찾기: `resolve_element()`

셀렉터 배열을 **순서대로** 시도하고, 하나라도 맞으면 그걸 씁니다.

```
_scan(driver, target, require_visible)   ← 한 바퀴 돌며 각 셀렉터 시도
  └ _locator_for(sel)                    ← 셀렉터 타입 → (By, 값) 변환
```

`_locator_for()`가 타입별 변환의 **유일한 지점**입니다. 새 셀렉터 타입은 여기만 고칩니다.

타임아웃까지 못 찾으면, 포기 전에 **보이지 않는 요소**까지 한 번 더 봅니다
(`allow_hidden`). 포털이 숨은 런처 앵커로 창을 띄우는 패턴 때문입니다. 단
`assert visible` 같은 건 이 예외를 쓰면 안 되므로 `_HIDDEN_OK_ACTIONS`로 제한합니다.

**못 쓰는 셀렉터는 건너뜁니다** — 모르는 타입이든, 문법이 깨졌든. 배열 전체가 날아가지
않게 하기 위함이고, 전부 못 쓰면 각각의 이유를 결과에 담습니다.

### 5-2. 값 가져오기: `resolve_value()`

```
literal        → 적힌 값 그대로
variable       → bound_vars[name]      (tool 호출 인자)
extracted_ref  → extracted[name]       (앞선 extract 스텝 결과)
expression     → 허용된 함수만 평가     (today/now/concat/random_int)
```

`expression`은 **임의 코드 실행이 아닙니다.** 화이트리스트 함수만 직접 파싱해서 계산합니다.
`eval()`을 쓰지 마세요 — 레코딩은 외부에서 들어오는 데이터입니다.

### 5-3. 창 관리: `ExecutionContext`

스텝 하나를 넘어 **살아남아야 하는 상태**를 들고 있습니다.

```python
ctx.tabs        # open_tab 의 extract_as 이름 → 윈도우 핸들
ctx.openers     # 핸들 → 그 창을 연 창
ctx.frame_stack # iframe_enter 로 들어간 경로
ctx.root_handle # 레코딩이 시작된 창
```

버튼을 눌러 새 창이 떠도 **셀레늄은 원래 창을 계속 봅니다.** `open_tab`이 새 창을 이름으로
묶고, `switch_tab`이 그 이름으로 옮겨갑니다. `tab_ref`는 이름/`latest`/`opener`/
`{extracted_ref}` 네 형태를 받습니다 (`resolve_tab_ref()`).

---

## 6. 무엇을 어디에 추가하나

| 하고 싶은 것 | 고칠 곳 |
|---|---|
| **새 액션 추가** | ① `schema.ActionType`에 값 추가<br>② 필요하면 `Step._validate_shape`에 필수 필드 검사<br>③ `selenium_runner.dispatch()`에 분기 + 구현 함수<br>④ 요소가 필요하면 `schema._NEEDS_TARGET`에 추가 |
| **새 셀렉터 타입** | ① `schema.SelectorType`에 값 추가<br>② `selenium_runner._locator_for()`에 변환 추가 |
| **새 값 타입** | ① `schema.ValueSource.type` Literal에 추가<br>② `selenium_runner.resolve_value()`에 분기 |
| **새 설정** | `config.py`에 `_int_env`/`_choice_env`/`_bool_env`로 추가하고 `effective_settings()`에도 넣기 |
| **결과에 필드 추가** | `result_models.ToolResult` + `interpreter`에서 채우기 |
| **새 에러 종류** | `result_models.ErrorDetail.error_type` Literal + `interpreter._classify_error()` |

---

## 7. 깨뜨리면 안 되는 규칙

실제로 사고가 났던 것들입니다. 고칠 때 지켜주세요.

**① stdout은 MCP 전용입니다.**
로그는 반드시 `sys.stderr`로. stdout에 `print()` 하면 프로토콜이 깨집니다.

**② 하나가 잘못돼도 전체를 죽이지 않습니다.**
- 깨진 JSON 파일 하나 → 그 파일만 스킵, 나머지 tool은 등록
- 모르는 액션 → 그 스텝만 실패, 레코딩은 등록됨
- 못 쓰는 셀렉터 → 건너뛰고 다음 폴백
- 잘못된 설정값 → 경고 후 기본값

**③ 실패는 항상 `ToolResult`로 돌아갑니다.**
예외를 밖으로 던지면 호출자는 `status`도 `step_log`도 스크린샷도 못 받습니다.
`call_tool()`과 `run()`에 포괄 예외 처리가 있는 이유입니다.

**④ 대기 로직이 다이얼로그를 닫으면 안 됩니다.**
뒤따르는 `alert` 스텝이 닫을 창을 못 찾게 됩니다. `_document_ready()`가 다이얼로그를 만나면
`None`을 돌려주고 대기를 멈춥니다. (실제로 이것 때문에 로그인 레코딩이 실패했었습니다.)

**⑤ 셀레늄 호출은 반드시 별도 스레드에서.**
`asyncio.to_thread` 없이 호출하면 서버 전체가 멈춥니다.

**⑥ 레코딩은 외부 데이터입니다.**
`eval()`/`exec()`로 처리하지 마세요.

---

## 8. 설계상 알고 있어야 할 선택들

| 선택 | 이유 | 영향 |
|---|---|---|
| tool 호출마다 새 브라우저 | 상태 공유가 없어 단순 | 매번 로그인 필요 → `USER_DATA_DIR`로 완화 |
| `fixed_delay`를 상한으로 해석 | 명세대로면 14스텝에 40초+ | `FIXED_DELAY_MODE=sleep`로 되돌릴 수 있음 |
| `window_open_call` 등은 실행 안 함 | 관찰 기록이지 지시가 아님 | 실행하면 창이 두 번 열림 |
| 모르는 action은 런타임 실패 | 레코더가 앞서가도 tool은 살아있음 | 오타가 로드 때 안 잡힘 |
| 로그인은 레코딩에 없음 | 자격증명 기록은 보안 문제 | 사람이 직접 로그인할 때까지 대기 |

---

## 9. 테스트

```bash
python -m http.server 8000     # test_page/ 에서 (픽스처 서버)
python scripts/manual_test.py  # MCP 없이 인터프리터만
python scripts/mcp_e2e_test.py # 실제 MCP 프로토콜까지
```

`test_page/`의 픽스처들은 각각 실제로 겪은 문제를 재현한 것입니다 — 중첩 iframe 안의
contenteditable, 숨은 런처 앵커, 숫자 id, 자기 자신을 닫는 팝업 등. 액션을 고칠 때
해당 픽스처로 확인하세요.
