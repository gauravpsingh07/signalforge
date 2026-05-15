import hashlib
import re

UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
TRACE_RE = re.compile(r"\b(trace|request|req|span|correlation)[_-][a-z0-9]{3,}\b", re.IGNORECASE)
ISO_TS_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}[tT ]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?\b")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
WHITESPACE_RE = re.compile(r"\s+")


def normalize_message(message: str) -> str:
    normalized = message.strip().lower()
    normalized = UUID_RE.sub("<uuid>", normalized)
    normalized = ISO_TS_RE.sub("<timestamp>", normalized)
    normalized = TRACE_RE.sub(lambda match: f"{match.group(1).lower()}_<id>", normalized)
    normalized = NUMBER_RE.sub("<number>", normalized)
    normalized = WHITESPACE_RE.sub(" ", normalized)
    return normalized.strip()


def fingerprint_hash(
    *,
    service: str,
    environment: str,
    level: str,
    status_code: int | None,
    normalized_message: str,
) -> str:
    key = "|".join(
        [
            service,
            environment,
            level,
            str(status_code or ""),
            normalized_message,
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
