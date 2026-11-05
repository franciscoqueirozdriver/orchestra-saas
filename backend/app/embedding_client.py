import httpx
import math
from urllib.parse import urlparse

from app.config import settings
from app.llm_client import LLMError
from app.url_safety import UnsafeExternalURL, validate_public_https


def embed_texts(base_url: str, model: str, api_key: str, texts: list[str]) -> list[list[float]]:
    if settings.embedding_dimensions != 1536:
        raise LLMError("A versão atual usa embeddings de 1536 dimensões no banco; altere schema/migração antes de mudar")
    if not texts:
        return []
    if len(texts) > 128:
        raise LLMError("Envie no máximo 128 trechos por lote")
    try:
        validate_public_https(base_url)
    except UnsafeExternalURL as exc:
        raise LLMError(str(exc)) from exc
    payload={"model":model,"input":texts}
    if urlparse(base_url).hostname=="generativelanguage.googleapis.com":
        payload["dimensions"]=1536
    try:
        response = httpx.post(
            base_url.rstrip("/") + "/embeddings",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=httpx.Timeout(settings.llm_request_timeout_seconds, connect=8.0),
            follow_redirects=False,
        )
    except httpx.HTTPError as exc:
        raise LLMError("Não foi possível conectar ao provedor de embeddings") from exc
    if not response.is_success:
        raise LLMError(f"O provedor de embeddings retornou HTTP {response.status_code}")
    try:
        data = response.json()
        vectors = [row["embedding"] for row in sorted(data["data"], key=lambda row: row.get("index", 0))]
    except (ValueError, KeyError, TypeError) as exc:
        raise LLMError("Resposta inválida do endpoint embeddings") from exc
    if len(vectors) != len(texts) or any(not isinstance(vector, list) or len(vector) != 1536 for vector in vectors):
        raise LLMError("O modelo de embeddings precisa retornar 1536 dimensões por trecho")
    try:
        result=[[float(value) for value in vector] for vector in vectors]
        if any(not math.isfinite(value) for vector in result for value in vector):raise ValueError()
    except (ValueError,TypeError,OverflowError) as exc:
        raise LLMError("Embeddings contêm valores inválidos") from exc
    if urlparse(base_url).hostname=="generativelanguage.googleapis.com":
        for vector in result:
            norm=math.sqrt(sum(value*value for value in vector))
            if not math.isfinite(norm) or norm==0:raise LLMError("Embedding Gemini inválido")
            vector[:]=[value/norm for value in vector]
    return result
