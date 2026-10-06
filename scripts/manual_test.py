"""MCP 없이 인터프리터만 직접 호출하는 스모크 테스트.

사전 준비: `python -m http.server 8000` 을 test_page/ 디렉터리에서 실행해둘 것.
"""
import os
import sys

# Repeated test runs would otherwise leave a browser window behind each time.
# Must be set before config is imported (below) for it to take effect.
os.environ.setdefault("MCP_TOOL_GENERATOR_KEEP_BROWSER", "0")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interpreter import RecordingInterpreter
from recording_loader import load_all_recordings
from schema import ErrorPolicy
import config


def main():
    recordings, errors = load_all_recordings(config.RECORDINGS_DIR)
    for e in errors:
        print(f"[WARN] {e}")

    recording = recordings["place_purchase_order"]
    interpreter = RecordingInterpreter(recording)

    bound_vars = {"sku": "SKU-1001", "quantity": 3, "note": "test order"}

    print("=== normal call (expect success) ===")
    result = interpreter.run(bound_vars)
    print(result.model_dump_json(indent=2))
    assert result.status == "success", f"expected success, got {result.status}: {result.error}"
    assert result.scenario_id == "place_purchase_order"
    assert result.results.get("item_name") == "Widget A", result.results
    assert "Order #12345" in result.results.get("confirmation_message", ""), result.results
    assert result.failed_step is None
    assert [s.status for s in result.step_log] == ["success"] * len(result.step_log)
    assert result.screenshot_path and os.path.exists(result.screenshot_path)

    print("\n=== bad selector call (expect failed / selector_not_found) ===")
    broken = recordings["place_purchase_order"].model_copy(deep=True)
    broken.steps[0].target.selectors[0].value = "#does-not-exist"
    broken_interpreter = RecordingInterpreter(broken)
    result2 = broken_interpreter.run(bound_vars)
    print(result2.model_dump_json(indent=2))
    assert result2.status == "failed"
    assert result2.failed_step == "enter_sku"
    assert result2.error.error_type == "selector_not_found"
    assert result2.error.screenshot_path and os.path.exists(result2.error.screenshot_path)

    print("\n=== on_error 'skip' (expect partial) ===")
    skipping = recordings["place_purchase_order"].model_copy(deep=True)
    skipping.steps[0].target.selectors[0].value = "#does-not-exist"
    skipping.steps[0].on_error = ErrorPolicy(strategy="skip")
    result3 = RecordingInterpreter(skipping).run(bound_vars)
    assert result3.status == "partial", result3.status
    assert result3.failed_step is None
    print(f"status={result3.status}, step_log statuses={[s.status for s in result3.step_log]}")

    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    main()
