"""The only place that talks to the Anthropic API."""

import json

from app.llm import settings


class LLMError(RuntimeError):
    """The model answered, but not with something we can use."""


def call_model(system: str, user: str, schema: dict, max_tokens: int) -> dict:
    """One Messages API call whose answer is forced to match `schema`. Returns the parsed JSON."""
    import anthropic  # imported here so mock mode works without the package

    client = anthropic.Anthropic(api_key=settings.api_key())
    response = client.messages.create(
        model=settings.model(),
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
    )
    if response.stop_reason != "end_turn":
        raise LLMError(f"El modelo no terminó la respuesta (stop_reason={response.stop_reason}).")
    text = "".join(block.text for block in response.content if block.type == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"El modelo devolvió JSON no válido: {exc}") from exc
