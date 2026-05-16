from __future__ import annotations

import json
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import Any


SERVICES = ["payment-api", "checkout-service", "auth-service", "notification-worker"]


def event_id(prefix: str, index: int) -> str:
    return f"{prefix}_{int(time.time() * 1000)}_{index}"


def route_for(service: str) -> str:
    return {
        "payment-api": "/payments",
        "checkout-service": "/checkout",
        "auth-service": "/login",
        "notification-worker": "email-queue",
    }.get(service, "/demo")


def normal_events(count: int, service: str | None, environment: str) -> list[dict[str, Any]]:
    events = []
    for index in range(max(1, count)):
        event_service = service or SERVICES[index % len(SERVICES)]
        level = "warn" if index % 11 == 0 else "info"
        latency_ms = random.randint(70, 260) if level == "info" else random.randint(450, 900)
        events.append(
            {
                "eventId": event_id("evt_demo", index),
                "timestamp": datetime.now(UTC).isoformat(),
                "service": event_service,
                "environment": environment,
                "level": level,
                "message": message_for(event_service, level),
                "statusCode": 202 if level == "warn" else 200,
                "latencyMs": latency_ms,
                "traceId": f"trace_demo_{index}",
                "requestId": f"req_demo_{index}",
                "metadata": {
                    "route": route_for(event_service),
                    "region": "local",
                    "script": "send_demo_events",
                    "sample": index,
                },
            }
        )
    return events


def error_spike_events(
    baseline_count: int,
    spike_count: int,
    service: str,
    environment: str,
) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    events: list[dict[str, Any]] = []
    for index in range(max(1, baseline_count)):
        timestamp = now - timedelta(minutes=45 - (index % 30))
        events.append(
            {
                "eventId": event_id("evt_baseline", index),
                "timestamp": timestamp.isoformat(),
                "service": service,
                "environment": environment,
                "level": "info",
                "message": "Checkout baseline request succeeded",
                "statusCode": 200,
                "latencyMs": 110 + (index % 30),
                "metadata": {"script": "generate_error_spike", "phase": "baseline", "route": route_for(service)},
            }
        )
    for index in range(max(1, spike_count)):
        events.append(
            {
                "eventId": event_id("evt_error_spike", index),
                "timestamp": now.isoformat(),
                "service": service,
                "environment": environment,
                "level": "error",
                "message": f"Checkout provider timeout for request req_{index} after {2400 + index}ms",
                "statusCode": 504,
                "latencyMs": 2400 + index,
                "metadata": {"script": "generate_error_spike", "phase": "spike", "route": route_for(service)},
            }
        )
    return events


def latency_spike_events(
    baseline_count: int,
    spike_count: int,
    service: str,
    environment: str,
) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    events: list[dict[str, Any]] = []
    for index in range(max(1, baseline_count)):
        timestamp = now - timedelta(minutes=45 - (index % 30))
        events.append(
            {
                "eventId": event_id("evt_latency_baseline", index),
                "timestamp": timestamp.isoformat(),
                "service": service,
                "environment": environment,
                "level": "info",
                "message": "Checkout request completed",
                "statusCode": 200,
                "latencyMs": 100 + (index % 25),
                "metadata": {"script": "generate_latency_spike", "phase": "baseline", "route": route_for(service)},
            }
        )
    for index in range(max(1, spike_count)):
        events.append(
            {
                "eventId": event_id("evt_latency_spike", index),
                "timestamp": now.isoformat(),
                "service": service,
                "environment": environment,
                "level": "info",
                "message": "Checkout request completed slowly",
                "statusCode": 200,
                "latencyMs": 1800 + (index * 35),
                "metadata": {"script": "generate_latency_spike", "phase": "spike", "route": route_for(service)},
            }
        )
    return events


def recovery_events(count: int, service: str, environment: str) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    return [
        {
            "eventId": event_id("evt_recovery", index),
            "timestamp": (now + timedelta(seconds=index)).isoformat(),
            "service": service,
            "environment": environment,
            "level": "info",
            "message": "Checkout request recovered successfully",
            "statusCode": 200,
            "latencyMs": 120 + (index % 20),
            "metadata": {"script": "generate_recovery_events", "phase": "recovery", "route": route_for(service)},
        }
        for index in range(max(1, count))
    ]


def message_for(service: str, level: str) -> str:
    if level == "warn":
        return f"{service} latency higher than usual"
    return f"{service} handled request successfully"


def post_event(api_url: str, project_key: str, event: dict[str, Any]) -> dict[str, Any]:
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


def send_events(api_url: str, project_key: str, events: list[dict[str, Any]], dry_run: bool = False) -> int:
    print(f"Prepared {len(events)} events for {api_url}")
    if dry_run:
        preview = events[0] if events else {}
        print(f"dry-run: first event preview: {json.dumps(preview, sort_keys=True)}")
        return 0

    try:
        for index, event in enumerate(events, start=1):
            accepted = post_event(api_url, project_key, event)
            print(f"[{index}/{len(events)}] accepted eventId={accepted['eventId']} jobId={accepted['jobId']}")
    except urllib.error.HTTPError as exc:
        print(f"request failed: HTTP {exc.code} {exc.read().decode('utf-8')}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"request failed: {exc}", file=sys.stderr)
        return 1
    return 0
