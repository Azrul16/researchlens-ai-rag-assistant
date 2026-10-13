from urllib.parse import quote

from app.core.config import get_settings
from app.core.errors import AppError
from app.llm.base import LLMProvider, provider_request


class GeminiProvider(LLMProvider):
    """Gemini GenerateContent REST with native JSON schema response configuration."""

    def headers(self):
        key = get_settings().gemini_api_key.get_secret_value()
        if not key:
            raise AppError(
                503, "PROVIDER_NOT_CONFIGURED", "Set GEMINI_API_KEY in the backend .env file."
            )
        return {"x-goog-api-key": key, "Content-Type": "application/json"}

    async def generate(self, system, messages, schema=None):
        config = {"temperature": 0, "maxOutputTokens": 8192}
        if schema:
            config.update({"responseMimeType": "application/json", "responseJsonSchema": schema})
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [
                {
                    "role": "model" if message["role"] == "assistant" else "user",
                    "parts": [{"text": message["content"]}],
                }
                for message in messages
            ],
            "generationConfig": config,
        }
        model = quote(get_settings().gemini_model, safe="")
        response = await provider_request(
            "POST",
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            self.headers(),
            body,
        )
        try:
            text = "".join(
                part.get("text", "")
                for part in response["candidates"][0]["content"]["parts"]
                if not part.get("thought", False)
            )
            if not text:
                raise ValueError("Empty response")
            return text
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise AppError(
                502, "INVALID_PROVIDER_OUTPUT", "Gemini returned no usable response."
            ) from exc

    async def health_check(self):
        if not get_settings().gemini_api_key.get_secret_value():
            return {"provider": "gemini", "configured": False, "reachable": None}
        model = quote(get_settings().gemini_model, safe="")
        await provider_request(
            "GET",
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}",
            self.headers(),
        )
        return {"provider": "gemini", "configured": True, "reachable": True}
