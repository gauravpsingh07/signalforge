import json
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings

QUEUE_KEY = "signalforge:jobs"


class QueueConsumer:
    async def pop(self) -> dict[str, Any] | None:
        settings = get_settings()
        if settings.upstash_redis_rest_url and settings.upstash_redis_rest_token:
            return await self._pop_upstash()
        return self._pop_local()

    async def requeue(self, payload: dict[str, Any]) -> None:
        settings = get_settings()
        if settings.upstash_redis_rest_url and settings.upstash_redis_rest_token:
            await self._push_upstash(payload)
            return
        self._append_local(payload)

    def _append_local(self, payload: dict[str, Any]) -> None:
        path = Path(get_settings().local_queue_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as queue_file:
            queue_file.write(json.dumps(payload, default=str) + "\n")

    def _pop_local(self) -> dict[str, Any] | None:
        path = Path(get_settings().local_queue_path)
        if not path.exists():
            return None

        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            path.write_text("", encoding="utf-8")
            return None

        first = lines[0]
        path.write_text("\n".join(lines[1:]) + ("\n" if len(lines) > 1 else ""), encoding="utf-8")
        return json.loads(first)

    async def _pop_upstash(self) -> dict[str, Any] | None:
        settings = get_settings()
        url = settings.upstash_redis_rest_url.rstrip("/")
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{url}/rpop/{QUEUE_KEY}",
                headers={"Authorization": f"Bearer {settings.upstash_redis_rest_token}"},
            )
            response.raise_for_status()
            data = response.json()
            result = data.get("result")
            if not result:
                return None
            parsed = json.loads(result)
            # Producers JSON-encode the payload before the REST call, so the
            # stored element can arrive single- or double-encoded depending on
            # how the REST gateway handled the request body.
            if isinstance(parsed, str):
                parsed = json.loads(parsed)
            return parsed

    async def _push_upstash(self, payload: dict[str, Any]) -> None:
        settings = get_settings()
        url = settings.upstash_redis_rest_url.rstrip("/")
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{url}/lpush/{QUEUE_KEY}",
                headers={"Authorization": f"Bearer {settings.upstash_redis_rest_token}"},
                json=json.dumps(payload, default=str),
            )
            response.raise_for_status()
