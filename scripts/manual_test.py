"""MCP 없이 인터프리터만 직접 호출하는 스모크 테스트.

사전 준비: `python -m http.server 8000` 을 test_page/ 디렉터리에서 실행해둘 것.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interpreter import RecordingInterpreter
from recording_loader import load_all_recordings
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
    assert result.extracted.get("item_name") == "Widget A", result.extracted
    assert "Order #12345" in result.extracted.get("confirmation_message", ""), result.extracted
    assert result.screenshot_path and os.path.exists(result.screenshot_path)

    print("\n=== bad selector call (expect error / selector_not_found) ===")
    broken = recordings["place_purchase_order"].model_copy(deep=True)
    broken.steps[0].target.selectors[0].value = "#does-not-exist"
    broken.steps[0].wait_after.timeout_ms = 1500
    broken_interpreter = RecordingInterpreter(broken)
    result2 = broken_interpreter.run(bound_vars)
    print(result2.model_dump_json(indent=2))
    assert result2.status == "error"
    assert result2.error.error_type == "selector_not_found"
    assert result2.error.screenshot_path and os.path.exists(result2.error.screenshot_path)

    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    main()
