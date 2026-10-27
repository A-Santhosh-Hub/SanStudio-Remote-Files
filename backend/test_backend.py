"""Checks the deployed Apps Script backend. Reads ../automation/config.json.

Never prints the URL or the secret.
"""
import json
import sys
import urllib.request
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "automation" / "config.json"
TEST_LINK = "https://backend-test.trycloudflare.com"


def post(url, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "text/plain"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.loads(res.read().decode())


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  ({detail})" if detail and not cond else ""))
    return cond


def main():
    if not CONFIG.exists():
        print(f"{CONFIG} not found — copy config.example.json to config.json and fill it in.")
        sys.exit(1)
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    url, secret = cfg.get("apps_script_url", ""), cfg.get("tool_secret", "")
    if "PASTE" in url or "PASTE" in secret or not url or not secret:
        print(f"Fill in {CONFIG} first.")
        sys.exit(1)
    if not url.startswith("https://script.google.com/") or not url.rstrip("/").endswith("/exec"):
        print("apps_script_url should look like https://script.google.com/macros/s/.../exec")
        sys.exit(1)

    ok = True
    r = post(url, {"action": "update", "secret": "wrong-secret", "link": TEST_LINK})
    ok &= check("wrong secret is rejected", r.get("error") == "Unauthorized", r)

    r = post(url, {"action": "update", "secret": secret, "link": "https://evil.example.com"})
    ok &= check("non-trycloudflare link is rejected", r.get("error") == "Invalid link", r)

    r = post(url, {"action": "update", "secret": secret, "link": TEST_LINK})
    ok &= check("tool can save link (secret correct)", r.get("ok") is True, r)

    r = post(url, {"action": "get", "password": "definitely-not-your-password"})
    ok &= check("wrong viewer password is rejected", r.get("error") == "Wrong password.", r)

    print()
    print("All good! Open the sheet: current_link should be " + TEST_LINK if ok else "Some checks failed.")
    print("To test the right password, open the GitHub page in Step 3 (or use the README's PowerShell command).")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
