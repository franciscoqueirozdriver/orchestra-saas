from app.control import serialized_mutation
from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.dependencies import CurrentUser, DbSession, TenantId
from app.models import Agent, LLMConfig, ModelRun, KnowledgeDocument, KnowledgeSearchConfig
from app.schemas import LLMConfigUpsert
from app.provider_catalog import catalog
from app.embedding_config import embedding_spec
from app.llm_client import LLMError, complete, resolved_protocol
from app.security import encrypt_secret
from time import monotonic
router = APIRouter(prefix="/api/llm", tags=["provedores de IA"])

_TEST_ERROR_MESSAGES={
    'authentication':'O fornecedor recusou a autenticação. Confira a chave e se o modelo está liberado para esta conta.',
    'quota':'O fornecedor indicou limite ou saldo insuficiente.',
    'rate_limit':'O fornecedor limitou as requisições. Aguarde e tente novamente.',
    'unavailable':'O fornecedor não respondeu dentro do prazo ou está indisponível.',
    'context_length':'O fornecedor recusou o tamanho do teste.',
    'output_limit':'O fornecedor respondeu, mas limitou a saída do teste.',
    'safety':'O fornecedor bloqueou a resposta de teste.',
    'unsafe_destination':'A URL desta conexão não passou na validação de segurança.',
    'invalid_request':'O fornecedor recusou o protocolo, modelo ou formato da requisição.',
    'invalid_response':'O fornecedor respondeu em um formato inesperado.',
    'configuration':'A conexão está incompleta para testar o modelo.',
}

def _test_result(*,ok,model,started,category=None,status_code=None):
    result={'ok':ok,'model':model,'elapsed_ms':round((monotonic()-started)*1000)}
    if ok:
        result['message']='O modelo respondeu ao teste.'
    else:
        result['category']=category or 'invalid_response'
        result['status_code']=status_code or None
        result['message']=_TEST_ERROR_MESSAGES.get(result['category'],'Não foi possível validar a conexão. Revise os dados e tente novamente.')
    return result

def _require_admin(user):
    if user.role not in {"platform_admin","tenant_admin"}: raise HTTPException(403,"Ação restrita a administradores")

def _read(row):
    return {"resolved_protocol":resolved_protocol(row.provider,row.protocol),"embedding_configured":bool(embedding_spec(row) and (row.embedding_api_key_encrypted or row.api_key_encrypted)),"has_dedicated_embedding_key":bool(row.embedding_api_key_encrypted),"id":row.id,"configured":True,"name":row.name,"provider":row.provider,"protocol":row.protocol,"model":row.model,"base_url":row.base_url,"enabled":row.enabled,"is_default":row.is_default,"max_output_tokens":row.max_output_tokens,"embedding_model":row.embedding_model,"embedding_base_url":row.embedding_base_url or "","has_api_key":bool(row.api_key_encrypted),"has_embedding_api_key":bool(row.embedding_api_key_encrypted or row.api_key_encrypted),"cooldown_until":row.cooldown_until.isoformat() if row.cooldown_until else None,"last_error_category":row.last_error_category}

def _get(db,tenant_id,config_id):
    row=db.query(LLMConfig).filter(LLMConfig.tenant_id==tenant_id,LLMConfig.id==config_id).first()
    if not row: raise HTTPException(404,"Conexão não encontrada")
    return row

def _save(db,tenant_id,payload,row=None):
    from types import SimpleNamespace
    creating=row is None
    fields=['name','provider','protocol','base_url','model','enabled','max_output_tokens','embedding_model','embedding_base_url']
    changes={field:getattr(payload,field) for field in fields if creating or field in payload.model_fields_set}
    frozen_key=None
    if not creating:
        if row.base_url!=payload.base_url and not payload.api_key:
            raise HTTPException(422,'Ao alterar a URL da geração, informe a chave novamente')
        old_spec=embedding_spec(row)
        prospective=SimpleNamespace(**{field:changes.get(field,getattr(row,field)) for field in fields})
        if 'embedding_base_url' in changes and changes['embedding_base_url']!=row.embedding_base_url:
            requested=changes['embedding_base_url'] or prospective.base_url
            if requested!=(old_spec[0] if old_spec else None) and not payload.embedding_api_key:
                raise HTTPException(422,'Ao alterar a URL de embeddings, informe a chave de embeddings novamente')
        generation_moves=row.base_url!=prospective.base_url
        separate_key_rotates=payload.api_key and old_spec and old_spec[0]!=prospective.base_url
        if old_spec and generation_moves and 'embedding_base_url' not in changes:
            changes['embedding_base_url']=old_spec[0]
            prospective.embedding_base_url=old_spec[0]
        if old_spec and (generation_moves or separate_key_rotates) and not payload.embedding_api_key and not row.embedding_api_key_encrypted:
            frozen_key=row.api_key_encrypted
        if row.is_default and not db.get(KnowledgeSearchConfig,tenant_id) and old_spec and old_spec!=embedding_spec(prospective) and db.query(KnowledgeDocument).filter_by(tenant_id=tenant_id,status='indexed').first():
            raise HTTPException(409,'Há documentos indexados: preserve a URL/modelo de embeddings; sua alteração exige reindexação planejada')
    else:
        if not payload.api_key:raise HTTPException(422,'Informe a chave para criar a conexão')
        prospective=payload
    if payload.embedding_api_key and embedding_spec(prospective) is None:
        raise HTTPException(422,'Informe uma URL separada para a chave de embeddings no protocolo nativo')
    if resolved_protocol(prospective.provider,prospective.protocol)=='gemini' and changes.get('model','').startswith('models/'):
        changes['model']=changes['model'][len('models/'):]
        if not changes['model']:raise HTTPException(422,'Informe o identificador do modelo Gemini')
    if creating:
        db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,0))'),{'key':'llm:'+tenant_id})
        row=LLMConfig(tenant_id=tenant_id,is_default=not db.query(LLMConfig).filter_by(tenant_id=tenant_id,is_default=True).first(),api_key_encrypted=encrypt_secret(payload.api_key) or '')
        db.add(row)
    for field,value in changes.items():setattr(row,field,value)
    if frozen_key:row.embedding_api_key_encrypted=frozen_key
    if payload.api_key:row.api_key_encrypted=encrypt_secret(payload.api_key) or row.api_key_encrypted
    if payload.embedding_api_key:row.embedding_api_key_encrypted=encrypt_secret(payload.embedding_api_key)
    row.cooldown_until=None;row.last_error_category=None
    db.commit();db.refresh(row)
    return _read(row)

@router.get("/connections")
def list_connections(db:DbSession,tenant_id:TenantId):
    return [_read(x) for x in db.query(LLMConfig).filter(LLMConfig.tenant_id==tenant_id).order_by(LLMConfig.created_at).all()]

@router.post("/connections",status_code=201)
@serialized_mutation
def create_connection(payload:LLMConfigUpsert,db:DbSession,tenant_id:TenantId,user:CurrentUser):
    _require_admin(user);return _save(db,tenant_id,payload)

@router.put("/connections/{config_id}")
@serialized_mutation
def update_connection(config_id:str,payload:LLMConfigUpsert,db:DbSession,tenant_id:TenantId,user:CurrentUser):
    _require_admin(user);return _save(db,tenant_id,payload,_get(db,tenant_id,config_id))

@router.post("/connections/{config_id}/test")
def test_connection(config_id:str,db:DbSession,tenant_id:TenantId,user:CurrentUser):
    """Probe a saved generation connection without persisting the provider result."""
    _require_admin(user)
    row=_get(db,tenant_id,config_id)
    started=monotonic()
    from app.security import decrypt_secret
    api_key=decrypt_secret(row.api_key_encrypted)
    if not api_key:
        return _test_result(ok=False,model=row.model,started=started,category='configuration')
    try:
        answer=complete(
            row.provider,row.base_url,row.model,api_key,
            'Este é um teste técnico de conexão. Responda somente com: OK.',
            [{'role':'user','content':'Responda somente: OK'}],
            protocol=row.protocol,max_output_tokens=64,
        )
        if not answer.strip():
            return _test_result(ok=False,model=row.model,started=started,category='invalid_response')
        return _test_result(ok=True,model=row.model,started=started)
    except LLMError as exc:
        return _test_result(ok=False,model=row.model,started=started,category=exc.category,status_code=exc.status_code)
    except Exception:
        # Never echo provider bodies, URLs, keys, or exception text to the client.
        return _test_result(ok=False,model=row.model,started=started,category='invalid_response')

@router.post("/connections/{config_id}/default")
@serialized_mutation
def make_default(config_id:str,db:DbSession,tenant_id:TenantId,user:CurrentUser):
    _require_admin(user)
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),{"key":"llm:"+tenant_id})
    row=_get(db,tenant_id,config_id)
    if not row.enabled:raise HTTPException(409,'Habilite a conexão antes de defini-la como padrão')
    previous=db.query(LLMConfig).filter_by(tenant_id=tenant_id,is_default=True).first()
    if previous and not db.get(KnowledgeSearchConfig,tenant_id) and previous.id!=row.id and embedding_spec(previous)!=embedding_spec(row) and db.query(KnowledgeDocument).filter_by(tenant_id=tenant_id,status='indexed').first():
        raise HTTPException(409,'Há documentos indexados: mantenha a mesma configuração de embeddings antes de mudar o padrão')
    for agent in db.query(Agent).filter_by(tenant_id=tenant_id,llm_config_id=None):
        if row.id in (agent.fallback_config_ids or []):
            raise HTTPException(409,'Remova esta conexão das alternativas dos agentes que usam o padrão antes de promovê-la')
    db.query(LLMConfig).filter(LLMConfig.tenant_id==tenant_id).update({LLMConfig.is_default:False},synchronize_session="fetch")
    db.flush();row.is_default=True;db.commit();return _read(row)

@router.post("/connections/{config_id}/resume")
@serialized_mutation
def resume_connection(config_id:str,db:DbSession,tenant_id:TenantId,user:CurrentUser):
    _require_admin(user);row=_get(db,tenant_id,config_id);row.cooldown_until=None;row.last_error_category=None;db.commit();return _read(row)

@router.delete("/connections/{config_id}",status_code=204)
@serialized_mutation
def delete_connection(config_id:str,db:DbSession,tenant_id:TenantId,user:CurrentUser):
    _require_admin(user);row=_get(db,tenant_id,config_id)
    agents=db.query(Agent).filter(Agent.tenant_id==tenant_id).all()
    if db.query(KnowledgeSearchConfig).filter_by(tenant_id=tenant_id,connection_id=config_id).first():
        raise HTTPException(409,"Esta conexão é usada pela busca da base de conhecimento")
    if row.is_default or any(x.llm_config_id==config_id or config_id in (x.fallback_config_ids or []) for x in agents):
        raise HTTPException(409,"Remova os vínculos e altere a conexão padrão antes de excluir")
    db.delete(row);db.commit()

@router.get("/config")
def get_llm_config(db:DbSession,tenant_id:TenantId):
    row=db.query(LLMConfig).filter(LLMConfig.tenant_id==tenant_id,LLMConfig.is_default.is_(True)).first()
    return _read(row) if row else {"configured":False,"provider":"openai-compatible","model":"","base_url":"","embedding_model":"text-embedding-3-small","embedding_base_url":"","has_api_key":False,"has_embedding_api_key":False}

@router.put("/config")
@serialized_mutation
def upsert_llm_config(payload:LLMConfigUpsert,db:DbSession,tenant_id:TenantId,user:CurrentUser):
    _require_admin(user)
    row=db.query(LLMConfig).filter(LLMConfig.tenant_id==tenant_id,LLMConfig.is_default.is_(True)).first()
    return _save(db,tenant_id,payload,row)

@router.get("/runs")
def list_runs(db:DbSession,tenant_id:TenantId):
    rows=db.query(ModelRun).filter(ModelRun.tenant_id==tenant_id).order_by(ModelRun.created_at.desc()).limit(100).all()
    return [{"id":x.id,"conversation_id":x.conversation_id,"revision":x.revision,"context_hash":x.context_hash,"attempts":x.attempts,"status":x.status,"selected_config_id":x.selected_config_id,"created_at":x.created_at.isoformat()} for x in rows]


@router.get('/provider-presets')
def provider_presets(tenant_id:TenantId):
    return catalog()
