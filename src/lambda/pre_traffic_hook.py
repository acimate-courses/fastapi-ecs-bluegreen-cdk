import json
import os
import time
import urllib.request


def probe(url: str, timeout=2):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        code = resp.getcode()
        body = resp.read(200).decode("utf-8", errors="ignore")
        return code, body


def handler(event, context):
    # This hook is intended for AfterAllowTestTraffic
    url = os.environ.get("TEST_URL")
    if not url:
        raise ValueError("TEST_URL not set")

    attempts = 12
    delay = 5
    last_error = None

    for i in range(attempts):
        try:
            code, _ = probe(url)
            if 200 <= code < 400:
                return {"status": "Succeeded", "code": code}
            last_error = f"Unexpected status: {code}"
        except Exception as e:
            last_error = str(e)

        time.sleep(delay)

    raise RuntimeError(f"Test traffic validation failed: {last_error}")
