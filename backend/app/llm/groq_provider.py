from app.core.config import get_settings
from app.core.errors import AppError
from app.llm.base import LLMProvider, provider_request


class GroqProvider(LLMProvider):
    """Groq Chat Completions; JSON mode plus Pydantic for model portability."""

    def headers(self):
        key = get_settings().groq_api_key.get_secret_value()
        if not key:
            raise AppError(
                503, "PROVIDER_NOT_CONFIGURED", "Set GROQ_API_KEY in the backend .env file."
            )
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    async def generate(self, system, messages, schema=None):
        body = {
            "model": get_settings().groq_model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": 0,
            "max_completion_tokens": 1500
            if schema and schema.get("title") == "GeneratedAnswer"
            else 4096,
        }
        if schema:
            if get_settings().groq_model in {
                "qwen/qwen3.8-27b",
                "openai/gpt-oss-20b",
                "openai/gpt-oss-120b",
            }:
                body["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": "research_response", "strict": True, "schema": schema},
                }
            else:
                body["response_format"] = {"type": "json_object"}
        response = await provider_request(
            "POST", "https://api.groq.com/openai/v1/chat/completions", self.headers(), body
        )
        try:
            result = response["choices"][0]["message"]["content"]
            if not isinstance(result, str) or not result:
                raise ValueError("Empty response")
            return result
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise AppError(
                502, "INVALID_PROVIDER_OUTPUT", "Groq returned an empty response."
            ) from exc

    async def health_check(self):
        if not get_settings().groq_api_key.get_secret_value():
            return {"provider": "groq", "configured": False, "reachable": None}
        response = await provider_request(
            "GET", "https://api.groq.com/openai/v1/models", self.headers()
        )
        models = [model["id"] for model in response.get("data", [])]
        return {
            "provider": "groq",
            "configured": True,
            "reachable": get_settings().groq_model in models,
        }
