import asyncio
import json
import logging
from abc import ABC, abstractmethod

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Vendor-neutral text generation with independently validated structured output."""

    @abstractmethod
    async def generate(self, system: str, messages: list[dict], schema: dict | None = None) -> str:
        raise NotImplementedError

    async def generate_structured(self, system: str, messages: list[dict], schema: type[BaseModel]):
        instruction = (
            system
            + "\nReturn only JSON matching this schema: "
            + json.dumps(schema.model_json_schema())
        )
        for attempt in range(2):
            text = await self.generate(instruction, messages, schema.model_json_schema())
            try:
                return schema.model_validate_json(text)
            except ValidationError as exc:
                if attempt:
                    raise AppError(
                        502,
                        "INVALID_PROVIDER_OUTPUT",
                        "The AI provider returned an invalid structured response. Please retry.",
                    ) from exc
                instruction += (
                    "\nYour previous output failed validation. "
                    "Return every required field with the correct type."
                )
        raise RuntimeError("Unreachable generation state")

    @abstractmethod
    async def health_check(self) -> dict:
        raise NotImplementedError


async def provider_request(method: str, url: str, headers: dict, body: dict | None = None):
    """Timeout and sanitize upstream errors; never log credentials or response text."""
    try:
        async with httpx.AsyncClient(timeout=get_settings().llm_timeout_seconds) as client:
            for attempt in range(3):
                response = await client.request(method, url, headers=headers, json=body)
                if response.status_code not in {429, 502, 503, 504} or attempt == 2:
                    break
                try:
                    delay = float(response.headers.get("Retry-After", 1 + attempt))
                except ValueError:
                    delay = 1 + attempt
                if delay > 15:
                    break
                await asyncio.sleep(max(0, delay))
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        logger.warning("llm_request_failed type=%s status=%s", type(exc).__name__, status)
        raise AppError(
            503,
            "PROVIDER_UNAVAILABLE",
            "The AI provider is unavailable. Check its API key, model and quota, then retry.",
        ) from exc
