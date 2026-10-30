import httpx

from app.config import settings
from app.url_safety import UnsafeExternalURL, validate_public_https


class LLMError(RuntimeError):
    pass


def _post(url: str, api_key: str, payload: dict) -> dict:
    try:
        validate_public_https(url)
    except UnsafeExternalURL as exc:
        raise LLMError(str(exc)) from exc
    try:
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=httpx.Timeout(settings.llm_request_timeout_seconds, connect=8.0),
            follow_redirects=False,
        )
    except httpx.HTTPError as exc:
        raise LLMError("Não foi possível conectar ao provedor de IA configurado") from exc
    if not response.is_success:
        # Não registrar nem retornar o corpo do provedor; pode conter prompts ou dados pessoais.
        raise LLMError(f"O provedor de IA retornou HTTP {response.status_code}")
    try:
        data = response.json()
    except ValueError as exc:
        raise LLMError("Resposta inválida do provedor de IA") from exc
    if not isinstance(data, dict):
        raise LLMError("Resposta inválida do provedor de IA")
    return data


def complete(provider: str, base_url: str, model: str, api_key: str, system_prompt: str, history: list[dict[str, str]]) -> str:
    if provider == "xai":
        # xAI Responses API em modo texto. Ferramentas remotas e MCP não são habilitados.
        url = base_url.rstrip("/") + "/responses"
        inputs = [{"role": item["role"], "content": item["content"]} for item in history if item.get("role") in {"user", "assistant"}]
        data = _post(url, api_key, {"model": model, "instructions": system_prompt, "input": inputs})
        text = data.get("output_text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        fragments: list[str] = []
        for item in data.get("output", []):
            if item.get("type") == "message":
                for part in item.get("content", []):
                    if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                        fragments.append(part["text"])
        result = "\n".join(fragments).strip()
        if not result:
            raise LLMError("O provedor não retornou texto para a resposta")
        return result

    # Groq e OpenAI-compatible: endpoint Chat Completions, sem ferramentas.
    url = base_url.rstrip("/") + "/chat/completions"
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend({"role": item["role"], "content": item["content"]} for item in history if item.get("role") in {"user", "assistant"})
    data = _post(url, api_key, {"model": model, "messages": messages})
    try:
        result = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("Resposta inválida do endpoint chat/completions") from exc
    if not isinstance(result, str) or not result.strip():
        raise LLMError("O provedor não retornou texto para a resposta")
    return result.strip()
