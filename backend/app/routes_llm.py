from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException

from app.dependencies import CurrentUser, DbSession, TenantId
from app.models import LLMConfig, User
from app.schemas import LLMConfigUpsert
from app.security import encrypt_secret

router = APIRouter(prefix="/api/llm", tags=["provedores de IA"])


def _require_admin(user: User) -> None:
    if user.role not in {"platform_admin", "tenant_admin"}:
        raise HTTPException(status_code=403, detail="Ação restrita a administradores")


def _provider_host_ok(provider: str, base_url: str) -> bool:
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").lower()
    if provider == "groq":
        return host == "api.groq.com" and parsed.path.rstrip("/") == "/openai/v1"
    if provider == "xai":
        return host == "api.x.ai" and parsed.path.rstrip("/") == "/v1"
    return True


@router.get("/config")
def get_llm_config(db: DbSession, tenant_id: TenantId) -> dict:
    row = db.query(LLMConfig).filter(LLMConfig.tenant_id == tenant_id).first()
    if row is None:
        return {"configured": False, "provider": "openai-compatible", "model": "", "base_url": "", "embedding_model": "text-embedding-3-small", "embedding_base_url": "", "has_api_key": False, "has_embedding_api_key": False}
    return {"configured": True, "provider": row.provider, "model": row.model, "base_url": row.base_url, "embedding_model": row.embedding_model, "embedding_base_url": row.embedding_base_url or "", "has_api_key": bool(row.api_key_encrypted), "has_embedding_api_key": bool(row.embedding_api_key_encrypted or row.api_key_encrypted)}


@router.put("/config")
def upsert_llm_config(payload: LLMConfigUpsert, db: DbSession, tenant_id: TenantId, user: CurrentUser) -> dict:
    _require_admin(user)
    if not _provider_host_ok(payload.provider, payload.base_url):
        raise HTTPException(status_code=422, detail="URL base incompatível com o provedor selecionado")
    if payload.embedding_base_url and not _provider_host_ok("openai-compatible", payload.embedding_base_url):
        raise HTTPException(status_code=422, detail="URL de embeddings inválida")
    row = db.query(LLMConfig).filter(LLMConfig.tenant_id == tenant_id).first()
    if row is None and not payload.api_key:
        raise HTTPException(status_code=422, detail="Informe a API key do provedor para criar a configuração")
    if row is None:
        row = LLMConfig(tenant_id=tenant_id, provider=payload.provider, base_url=payload.base_url, model=payload.model, embedding_model=payload.embedding_model, embedding_base_url=payload.embedding_base_url or None, embedding_api_key_encrypted=encrypt_secret(payload.embedding_api_key), api_key_encrypted=encrypt_secret(payload.api_key) or "")
        db.add(row)
    else:
        row.provider = payload.provider
        row.base_url = payload.base_url
        row.model = payload.model
        row.embedding_model = payload.embedding_model
        if payload.api_key:
            row.api_key_encrypted = encrypt_secret(payload.api_key) or row.api_key_encrypted
        if payload.embedding_api_key:
            row.embedding_api_key_encrypted = encrypt_secret(payload.embedding_api_key)
        row.embedding_base_url = payload.embedding_base_url or None
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"configured": True, "provider": row.provider, "model": row.model, "base_url": row.base_url, "embedding_model": row.embedding_model, "embedding_base_url": row.embedding_base_url or "", "has_api_key": True, "has_embedding_api_key": bool(row.embedding_api_key_encrypted or row.api_key_encrypted)}
