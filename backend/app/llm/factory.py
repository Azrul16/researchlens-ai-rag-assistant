from app.core.config import get_settings
from app.llm.gemini_provider import GeminiProvider
from app.llm.groq_provider import GroqProvider


def get_llm_provider():
    return GroqProvider() if get_settings().llm_provider == "groq" else GeminiProvider()
