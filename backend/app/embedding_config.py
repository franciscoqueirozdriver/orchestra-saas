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


def connection_embedding_config(connection):
    """An explicit selection authorizes using this connection's generation key."""
    if not connection.enabled:
        raise LLMError('Habilite a conexão selecionada para a busca',category='configuration')
    protocol=resolved_protocol(connection.provider,connection.protocol)
    if protocol=='anthropic':
        raise LLMError('Esta conexão não oferece o protocolo de embeddings suportado',category='configuration')
    base=connection.base_url.rstrip('/')
    if protocol=='gemini' and not base.endswith('/openai'):
        base+='/openai'
    key=decrypt_secret(connection.api_key_encrypted)
    if not key:raise LLMError('A conexão selecionada não possui chave',category='configuration')
    return base,key


def knowledge_embedding_config(db, tenant_id):
    """Dedicated or linked search configuration, with legacy compatibility."""
    from app.models import KnowledgeSearchConfig, LLMConfig
    from types import SimpleNamespace
    row=db.get(KnowledgeSearchConfig,tenant_id)
    if row:
        if row.connection_id:
            connection=db.query(LLMConfig).filter_by(id=row.connection_id,tenant_id=tenant_id).first()
            if connection is None:raise LLMError('Conexão da busca indisponível',category='configuration')
            base,key=connection_embedding_config(connection)
            if base!=row.embedding_base_url:
                raise LLMError('O endpoint da conexão mudou; revise a configuração da busca',category='configuration')
            return base,row.embedding_model,key
        return embedding_request_config(SimpleNamespace(
            embedding_base_url=row.embedding_base_url,embedding_model=row.embedding_model,
            embedding_api_key_encrypted=row.embedding_api_key_encrypted,api_key_encrypted=None))
    legacy=db.query(LLMConfig).filter_by(tenant_id=tenant_id,is_default=True).first()
    if legacy is None:
        raise LLMError('Configure a busca na base de conhecimento antes de indexar',category='configuration')
    return embedding_request_config(legacy)
