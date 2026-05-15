import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def build_events() -> list[dict]:
    now_ms = int(time.time() * 1000)
    return [
        {
            "eventId": f"evt_demo_{now_ms}_info",
            "service": "checkout-service",
            "environment": "production",
            "level": "info",
            "message": "Checkout page loaded",
            "statusCode": 200,
            "latencyMs": 128,
            "metadata": {"route": "/checkout", "region": "local"},
        },
        {
            "eventId": f"evt_demo_{now_ms}_warn",
            "service": "payment-api",
            "environment": "production",
            "level": "warn",
            "message": "Payment provider response slower than usual",
            "statusCode": 202,
            "latencyMs": 840,
            "metadata": {"provider": "demo-pay", "region": "local"},
        },
        {
            "eventId": f"evt_demo_{now_ms}_error",
            "service": "notification-worker",
            "environment": "production",
            "level": "error",
            "message": "Email delivery retry scheduled",
            "statusCode": 500,
            "latencyMs": 1450,
            "metadata": {"queue": "email", "attempt": 1},
        },
    ]


def post_event(api_url: str, project_key: str, event: dict) -> dict:
    request = urllib.request.Request(
        f"{api_url.rstrip('/')}/v1/events",
        data=json.dumps(event).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {project_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Send SignalForge demo events.")
    parser.add_argument("--project-key", required=True, help="Raw SignalForge ingestion API key.")
    parser.add_argument("--api-url", default="http://localhost:8000", help="SignalForge API base URL.")
    args = parser.parse_args()

    print(f"Sending {len(build_events())} demo events to {args.api_url}")
    try:
        for event in build_events():
            accepted = post_event(args.api_url, args.project_key, event)
            print(f"accepted eventId={accepted['eventId']} jobId={accepted['jobId']}")
    except urllib.error.HTTPError as exc:
        print(f"request failed: HTTP {exc.code} {exc.read().decode('utf-8')}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"request failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
