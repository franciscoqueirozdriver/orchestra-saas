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
