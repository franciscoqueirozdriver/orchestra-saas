"""Keep embedding transport independent of generation protocol and credentials."""
from app.llm_client import resolved_protocol, LLMError
from app.security import decrypt_secret


def embedding_spec(row):
    base=row.embedding_base_url
    if not base:
        if resolved_protocol(row.provider,row.protocol) in {'gemini','anthropic'}:
            return None
        base=row.base_url
    return (base.rstrip('/'),row.embedding_model)


def embedding_request_config(row):
    spec=embedding_spec(row)
    key=decrypt_secret(row.embedding_api_key_encrypted) or decrypt_secret(row.api_key_encrypted)
    if spec is None or not key:
        raise LLMError('Configure separadamente o endpoint compatível de embeddings e sua chave para usar a busca',category='configuration')
    return spec[0],spec[1],key


def knowledge_embedding_config(db, tenant_id):
    """Dedicated search configuration; retain the legacy default until migrated."""
    from app.models import KnowledgeSearchConfig, LLMConfig
    from types import SimpleNamespace
    row=db.get(KnowledgeSearchConfig,tenant_id)
    if row:
        return embedding_request_config(SimpleNamespace(
            embedding_base_url=row.embedding_base_url,embedding_model=row.embedding_model,
            embedding_api_key_encrypted=row.embedding_api_key_encrypted,api_key_encrypted=None))
    legacy=db.query(LLMConfig).filter_by(tenant_id=tenant_id,is_default=True).first()
    if legacy is None:
        raise LLMError('Configure a busca na base de conhecimento antes de indexar',category='configuration')
    return embedding_request_config(legacy)
