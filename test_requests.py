"""
AI Illustration Agent — Sample Test Requests
==============================================
Run these tests after starting the server locally:

    cd app && uvicorn main:app --port 8080 --reload

Then in a separate terminal:

    python tests/test_requests.py
"""

import json
import sys
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8080"


def _post(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def _get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=10) as resp:
        return json.loads(resp.read())


def test_health():
    print("── Test: Health Check ──────────────────────")
    resp = _get("/")
    assert resp["status"] == "ok", f"Expected 'ok', got {resp['status']}"
    print(f"  status            : {resp['status']}")
    print(f"  version           : {resp['version']}")
    print(f"  gemini_configured : {resp['gemini_configured']}")
    print("  ✅ PASSED\n")


def test_generate_basic():
    print("── Test: Basic Generation ──────────────────")
    payload = {
        "prompt": "A futuristic city skyline at night with neon reflections on rain-soaked streets",
        "style": "digital_art",
        "aspect_ratio": "16:9",
        "detail_level": "detailed",
    }
    resp = _post("/generate", payload)
    assert resp["success"], f"Expected success=True, errors={resp.get('errors')}"
    assert len(resp["illustration_description"]) > 50, "Description too short"
    print(f"  success     : {resp['success']}")
    print(f"  mood        : {resp['mood']}")
    print(f"  style_tags  : {resp['style_tags']}")
    print(f"  palette     : {resp['color_palette']}")
    print(f"  time_ms     : {resp['processing_time_ms']}")
    print(f"  description : {resp['illustration_description'][:120]}…")
    print("  ✅ PASSED\n")


def test_generate_auto_style():
    print("── Test: Auto Style Detection ──────────────")
    payload = {
        "prompt": "A Victorian-era scientist surrounded by bubbling potions and arcane instruments",
    }
    resp = _post("/generate", payload)
    assert resp["success"], f"Expected success=True, errors={resp.get('errors')}"
    print(f"  auto-selected style: {resp['metadata'].get('reasoning_style_used', 'N/A')}")
    print(f"  mood               : {resp['mood']}")
    print("  ✅ PASSED\n")


def test_generate_watercolor():
    print("── Test: Watercolor Style ──────────────────")
    payload = {
        "prompt": "A tranquil Japanese garden with koi pond and stone lanterns",
        "style": "watercolor",
        "aspect_ratio": "1:1",
        "detail_level": "moderate",
    }
    resp = _post("/generate", payload)
    assert resp["success"], f"Expected success=True, errors={resp.get('errors')}"
    assert "watercolor" in resp["metadata"].get("reasoning_style_used", ""), \
        "Style not preserved in metadata"
    print(f"  style   : {resp['metadata']['reasoning_style_used']}")
    print(f"  palette : {resp['color_palette']}")
    print("  ✅ PASSED\n")


def test_invalid_prompt():
    print("── Test: Invalid Prompt (too short) ────────")
    import urllib.error
    payload = {"prompt": "hi"}  # Below min_length=3... actually 2 chars
    try:
        _post("/generate", {"prompt": ""})  # Empty prompt
        print("  ❌ FAILED — expected HTTP error")
        sys.exit(1)
    except urllib.error.HTTPError as exc:
        assert exc.code == 422, f"Expected 422, got {exc.code}"
        print(f"  received 422 as expected ✅ PASSED\n")


def main():
    print("\n🎨  AI Illustration Agent — Test Suite\n")
    try:
        test_health()
        test_generate_basic()
        test_generate_auto_style()
        test_generate_watercolor()
        test_invalid_prompt()
        print("══════════════════════════════════════════")
        print("✅  All tests passed!")
    except AssertionError as exc:
        print(f"\n❌  Test failed: {exc}")
        sys.exit(1)
    except ConnectionRefusedError:
        print(
            "\n⚠️  Could not connect to server. "
            "Make sure it is running on http://localhost:8080"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
