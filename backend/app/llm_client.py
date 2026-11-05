"""Provider contracts. Provider labels and model identifiers remain user-configurable."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import math
from urllib.parse import quote
import httpx
from app.config import settings
from app.url_safety import UnsafeExternalURL, validate_public_https


class LLMError(RuntimeError):
    def __init__(self, message, *, category="invalid_response", status_code=0, retry_after=0):
        super().__init__(message)
        self.category = category
        self.status_code = status_code
        self.retry_after = retry_after

    @property
    def permits_fallback(self):
        return self.category in {"quota", "rate_limit", "unavailable", "authentication", "context_length", "invalid_response", "output_limit"}


def _delay(value):
    try:
        seconds = float(value)
        return max(0, math.ceil(seconds)) if math.isfinite(seconds) else 0
    except (ValueError, TypeError, OverflowError):
        try:
            return max(0, math.ceil((parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()))
        except (ValueError, TypeError, OverflowError):
            return 0


def _provider_error(response):
    # Inspect only for classification; do not persist or echo remote messages/prompts/secrets.
    try:
        body = response.json()
        error = body.get("error", {}) if isinstance(body, dict) else {}
        if not isinstance(error, dict): error = {}
    except ValueError:
        error = {}
    code = str(error.get("code") or error.get("type") or error.get("status") or "").lower()
    description = str(error.get("message") or "").lower()
    status = response.status_code
    quota_codes = {"insufficient_quota", "credit_balance_exhausted", "organization_spend_limit_exceeded", "project_spend_limit_exceeded", "organization_usage_limit_exceeded", "usage_limit_exceeded", "billing_hard_limit_reached"}
    if code in {"content_policy_violation", "safety", "prohibited_content", "invalid_prompt"}:
        category = "safety"
    elif code in quota_codes or status == 402 or (status in {400,429} and any(x in description for x in ["credit balance", "insufficient quota", "billing", "exceeded your current quota", "quota exceeded"])):
        category = "quota"
    elif code in {"context_length_exceeded", "context_window_exceeded"} or (status in {400,413} and any(x in description for x in ["context length", "context window", "too many tokens", "input token count", "input is too long"])):
        category = "context_length"
    elif status == 429: category = "rate_limit"
    elif status in {401,403}: category = "authentication"
    elif status >= 500 or status in {408,409}: category = "unavailable"
    else: category = "invalid_request"
    return LLMError(f"Provedor de IA: {category} (HTTP {status})", category=category, status_code=status, retry_after=_delay(response.headers.get("retry-after")))


def _post(url, api_key, payload, *, extra_headers=None):
    try: validate_public_https(url)
    except UnsafeExternalURL as exc: raise LLMError("Destino de IA não permitido", category="unsafe_destination") from exc
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    headers.update(extra_headers or {})
    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=httpx.Timeout(settings.llm_request_timeout_seconds, connect=8), follow_redirects=False)
    except httpx.HTTPError as exc:
        raise LLMError("Provedor de IA indisponível", category="unavailable") from exc
    if not response.is_success: raise _provider_error(response)
    try: data = response.json()
    except ValueError as exc: raise LLMError("Resposta inválida do provedor de IA") from exc
    if not isinstance(data, dict): raise LLMError("Resposta inválida do provedor de IA")
    return data


def resolved_protocol(provider, protocol="auto"):
    if protocol != "auto": return protocol
    return {"xai":"responses", "openai":"responses", "anthropic":"anthropic", "claude":"anthropic", "gemini":"gemini", "google":"gemini"}.get(provider.lower(), "chat-completions")


def complete(provider, base_url, model, api_key, system_prompt, history, *, protocol="auto", max_output_tokens=2048):
    protocol = resolved_protocol(provider, protocol)
    messages = [{"role": x["role"], "content": x["content"]} for x in history if x.get("role") in {"user","assistant"}]
    base = base_url.rstrip("/")
    if protocol == "responses":
        data = _post(base + "/responses", api_key, {"model":model,"instructions":system_prompt,"input":messages,"max_output_tokens":max_output_tokens,"store":False})
        if data.get("error"):
            code = str((data.get("error") or {}).get("code", ""))
            raise LLMError("Falha na geração de IA", category="rate_limit" if code == "rate_limit_exceeded" else "invalid_response")
        if data.get("status") == "incomplete": raise LLMError("Resposta incompleta; limite de saída", category="output_limit")
        blocks = [part for item in data.get("output",[]) if isinstance(item,dict) and item.get("type")=="message" for part in item.get("content",[]) if isinstance(part,dict)]
        if any(x.get("type")=="refusal" for x in blocks): raise LLMError("Resposta recusada pelo provedor", category="safety")
        result = data.get("output_text") or "\n".join(x["text"] for x in blocks if x.get("type")=="output_text" and isinstance(x.get("text"),str))
    elif protocol == "anthropic":
        data = _post(base + "/messages",api_key,{"model":model,"system":system_prompt,"messages":messages,"max_tokens":max_output_tokens},extra_headers={"anthropic-version":"2026-10-21"})
        if data.get("stop_reason") in {"refusal"}: raise LLMError("Resposta recusada pelo provedor",category="safety")
        if data.get("stop_reason")=="max_tokens": raise LLMError("Resposta incompleta; limite de saída",category="output_limit")
        result = "\n".join(x["text"] for x in data.get("content",[]) if isinstance(x,dict) and x.get("type")=="text" and isinstance(x.get("text"),str))
    elif protocol == "gemini":
        contents = [{"role":"model" if x["role"]=="assistant" else "user","parts":[{"text":x["content"]}]} for x in messages]
        data = _post(base + "/models/" + quote(model,safe="") + ":generateContent",api_key,{"systemInstruction":{"parts":[{"text":system_prompt}]},"contents":contents,"generationConfig":{"maxOutputTokens":max_output_tokens}},extra_headers={"Authorization":"", "x-goog-api-key":api_key})
        candidates = data.get("candidates") or []
        if data.get("promptFeedback",{}).get("blockReason") or any(x.get("finishReason") in {"SAFETY","PROHIBITED_CONTENT","BLOCKLIST","RECITATION"} for x in candidates): raise LLMError("Resposta bloqueada pelo provedor",category="safety")
        candidate = candidates[0] if candidates else {}
        if candidate.get("finishReason")=="MAX_TOKENS": raise LLMError("Resposta incompleta; limite de saída",category="output_limit")
        result = "\n".join(x["text"] for x in candidate.get("content",{}).get("parts",[]) if isinstance(x.get("text"),str) and not x.get("thought"))
    elif protocol == "chat-completions":
        data = _post(base + "/chat/completions",api_key,{"model":model,"messages":[{"role":"system","content":system_prompt}]+messages})
        try:
            choice = data["choices"][0]
            if choice.get("finish_reason")=="content_filter" or choice.get("message",{}).get("refusal"): raise LLMError("Resposta recusada pelo provedor",category="safety")
            if choice.get("finish_reason")=="length": raise LLMError("Resposta incompleta; limite de saída",category="output_limit")
            result = choice["message"]["content"]
        except (KeyError,IndexError,TypeError) as exc: raise LLMError("Resposta inválida do provedor") from exc
    else: raise LLMError("Protocolo não implementado",category="invalid_request")
    if not isinstance(result,str) or not result.strip(): raise LLMError("Provedor não retornou texto")
    return result.strip()
