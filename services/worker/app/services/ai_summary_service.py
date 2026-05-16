import json
import re
from dataclasses import dataclass
from typing import Any, Callable

import httpx

from app.config import get_settings
from app.services.event_store_service import EventStoreService


SUMMARY_KEYS = {
    "summary",
    "affectedService",
    "impact",
    "likelyCause",
    "timeline",
    "recommendedActions",
    "confidence",
}
SENSITIVE_KEY_PATTERN = re.compile(r"(api[_-]?key|token|secret|password|authorization|cookie|jwt)", re.IGNORECASE)
API_KEY_PATTERN = re.compile(r"sf_(?:live|demo)_[A-Za-z0-9_\-]+")
JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_\-]+?\.[A-Za-z0-9_\-]+?\.[A-Za-z0-9_\-]+?\b")
BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE)


@dataclass(frozen=True)
class SummaryResult:
    payload: dict[str, Any]
    source: str
    error: str | None = None


class AiSummaryService:
    def __init__(
        self,
        event_store: EventStoreService | None = None,
        gemini_client: Callable[[dict[str, Any]], str] | None = None,
    ) -> None:
        self.event_store = event_store or EventStoreService()
        self.gemini_client = gemini_client

    def summarize_incident(
        self,
        incident: dict[str, Any],
        anomalies: list[dict[str, Any]],
    ) -> SummaryResult:
        context = self.build_context(incident, anomalies)
        if not get_settings().gemini_api_key and self.gemini_client is None:
            return SummaryResult(self.fallback_summary(context), "fallback")
        try:
            raw = self._call_gemini(context)
            return SummaryResult(validate_summary_json(raw, incident), "gemini")
        except Exception as exc:
            payload = self.fallback_summary(context)
            payload["error"] = str(exc)
            return SummaryResult(payload, "fallback", str(exc))

    def build_context(self, incident: dict[str, Any], anomalies: list[dict[str, Any]]) -> dict[str, Any]:
        events = self.event_store.list_events(
            project_id=incident["project_id"],
            service=incident["service"],
            environment=incident["environment"],
            limit=10,
        )
        sample_messages = [redact_text(str(event.get("message", ""))) for event in events[:5]]
        return sanitize_for_ai(
            {
                "incident": {
                    "id": incident["id"],
                    "title": incident["title"],
                    "service": incident["service"],
                    "environment": incident["environment"],
                    "severity": incident["severity"],
                    "status": incident["status"],
                    "started_at": incident["started_at"],
                    "updated_at": incident["updated_at"],
                },
                "anomaly_metrics": [
                    {
                        "type": anomaly.get("anomaly_type"),
                        "severity": anomaly.get("severity"),
                        "score": anomaly.get("score"),
                        "baseline_value": anomaly.get("baseline_value"),
                        "observed_value": anomaly.get("observed_value"),
                        "window_start": anomaly.get("window_start"),
                        "window_end": anomaly.get("window_end"),
                    }
                    for anomaly in anomalies
                ],
                "top_fingerprints": sorted({anomaly.get("fingerprint_hash") for anomaly in anomalies if anomaly.get("fingerprint_hash")}),
                "counts": {
                    "anomalies": len(anomalies),
                    "sample_messages": len(sample_messages),
                },
                "sample_messages": sample_messages,
                "timeline": [
                    {
                        "time": anomaly.get("created_at") or anomaly.get("window_start"),
                        "event": f"{anomaly.get('anomaly_type', 'anomaly').replace('_', ' ')} detected",
                    }
                    for anomaly in anomalies
                ],
            }
        )

    def fallback_summary(self, context: dict[str, Any]) -> dict[str, Any]:
        incident = context["incident"]
        anomalies = context["anomaly_metrics"]
        first_type = str(anomalies[0]["type"]).replace("_", " ") if anomalies else "anomaly"
        return {
            "summary": (
                f"{incident['severity'].title()} incident in {incident['service']} "
                f"for {incident['environment']} based on {len(anomalies)} grouped anomalies. "
                f"The first signal was {first_type}."
            ),
            "affectedService": incident["service"],
            "impact": f"{incident['service']} is showing abnormal {first_type} signals in {incident['environment']}.",
            "likelyCause": "Deterministic anomaly signals indicate a service regression or upstream dependency issue.",
            "timeline": context["timeline"][:5]
            or [{"time": incident["started_at"], "event": "Incident opened from deterministic anomaly detection"}],
            "recommendedActions": [
                f"Inspect recent deployments and configuration changes for {incident['service']}",
                "Review related fingerprints and sample events for common failure patterns",
                "Check upstream dependencies, latency, and error budgets for the affected window",
            ],
            "confidence": "medium",
        }

    def _call_gemini(self, context: dict[str, Any]) -> str:
        if self.gemini_client:
            return self.gemini_client(context)

        settings = get_settings()
        prompt = (
            "You summarize SignalForge incidents after deterministic anomaly detection and grouping. "
            "Do not decide whether an anomaly exists. Return strict JSON only with keys: "
            "summary, affectedService, impact, likelyCause, timeline, recommendedActions, confidence. "
            "Do not include secrets or raw metadata.\n\n"
            f"Incident context:\n{json.dumps(context, sort_keys=True)}"
        )
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
        )
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                url,
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"responseMimeType": "application/json"},
                },
            )
            response.raise_for_status()
            data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


def validate_summary_json(raw: str, incident: dict[str, Any]) -> dict[str, Any]:
    payload = json.loads(strip_code_fence(raw))
    if not isinstance(payload, dict):
        raise ValueError("Gemini summary must be a JSON object")
    missing = SUMMARY_KEYS - payload.keys()
    if missing:
        raise ValueError(f"Gemini summary missing keys: {', '.join(sorted(missing))}")
    if not isinstance(payload["timeline"], list) or not isinstance(payload["recommendedActions"], list):
        raise ValueError("Gemini summary timeline and recommendedActions must be arrays")
    payload["affectedService"] = str(payload.get("affectedService") or incident["service"])
    payload["confidence"] = str(payload.get("confidence") or "medium")
    return sanitize_for_ai(payload)


def strip_code_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    return text


def sanitize_for_ai(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if SENSITIVE_KEY_PATTERN.search(str(key)):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = sanitize_for_ai(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_for_ai(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def redact_text(value: str) -> str:
    text = API_KEY_PATTERN.sub("[REDACTED_API_KEY]", value)
    text = JWT_PATTERN.sub("[REDACTED_JWT]", text)
    return BEARER_PATTERN.sub("Bearer [REDACTED_TOKEN]", text)
