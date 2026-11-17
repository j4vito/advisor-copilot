"""The only place that talks to the Anthropic API."""

import json

from app.llm import settings


class LLMError(RuntimeError):
    """The model call failed, or the model answered with something we cannot use."""


def call_model(system: str, user: str, schema: dict, max_tokens: int) -> dict:
    """One Messages API call whose answer is forced to match `schema`. Returns the parsed JSON."""
    import anthropic  # imported here so offline mode works without the package

    client = anthropic.Anthropic(api_key=settings.api_key())
    try:
        response = client.messages.create(
            model=settings.model(),
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
    except anthropic.AuthenticationError as exc:
        raise LLMError("La API key no es válida (ANTHROPIC_API_KEY). Quítala de .env para usar las respuestas grabadas.") from exc
    except anthropic.APIStatusError as exc:
        raise LLMError(f"La llamada al modelo falló: HTTP {exc.status_code} ({type(exc).__name__}).") from exc
    except anthropic.APIConnectionError as exc:
        raise LLMError("No se pudo conectar con la API de Anthropic.") from exc

    if response.stop_reason != "end_turn":
        raise LLMError(f"El modelo no terminó la respuesta (stop_reason={response.stop_reason}).")
    text = "".join(block.text for block in response.content if block.type == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"El modelo devolvió JSON no válido: {exc}") from exc
