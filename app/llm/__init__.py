"""Model layer: read a chat into structured data, and write the reply.

Without ANTHROPIC_API_KEY both functions run in mock mode (see `mock.py`).
"""

from app.llm.client import LLMError
from app.llm.draft import draft, reply_text
from app.llm.extract import extract

__all__ = ["extract", "draft", "reply_text", "LLMError"]
