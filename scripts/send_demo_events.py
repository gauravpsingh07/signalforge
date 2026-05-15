import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request


SERVICES = ["checkout-service", "payment-api", "auth-service", "notification-worker"]
LEVELS = ["info", "info", "info", "warn", "error"]


def build_events(count: int, service: str | None, environment: str) -> list[dict]:
    now_ms = int(time.time() * 1000)
    events = []
    for index in range(count):
        event_service = service or SERVICES[index % len(SERVICES)]
        level = LEVELS[index % len(LEVELS)]
        status_code = 500 if level == "error" else 202 if level == "warn" else 200
        latency_ms = random.randint(80, 350) if level == "info" else random.randint(650, 1800)
        events.append(
            {
                "eventId": f"evt_demo_{now_ms}_{index}",
                "service": event_service,
                "environment": environment,
                "level": level,
                "message": message_for(event_service, level),
                "statusCode": status_code,
                "latencyMs": latency_ms,
                "metadata": {"route": route_for(event_service), "region": "local", "sample": index},
            }
        )
    return events


def message_for(service: str, level: str) -> str:
    if level == "error":
        return f"{service} request failed after retry"
    if level == "warn":
        return f"{service} latency higher than usual"
    return f"{service} handled request successfully"


def route_for(service: str) -> str:
    return {
        "checkout-service": "/checkout",
        "payment-api": "/payments",
        "auth-service": "/login",
        "notification-worker": "email-queue",
    }.get(service, "/demo")


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
    parser.add_argument("--count", type=int, default=24, help="Number of demo events to send.")
    parser.add_argument("--service", help="Optional service name to use for every event.")
    parser.add_argument("--environment", default="production", help="Event environment.")
    args = parser.parse_args()

    events = build_events(max(1, args.count), args.service, args.environment)
    print(f"Sending {len(events)} demo events to {args.api_url}")
    try:
        for event in events:
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
