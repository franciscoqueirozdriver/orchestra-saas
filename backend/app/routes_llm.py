from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.dependencies import CurrentUser, DbSession, TenantId
from app.models import Agent, LLMConfig, ModelRun
from app.schemas import LLMConfigUpsert
from app.security import encrypt_secret
router = APIRouter(prefix="/api/llm", tags=["provedores de IA"])

def _require_admin(user):
    if user.role not in {"platform_admin","tenant_admin"}: raise HTTPException(403,"Ação restrita a administradores")

def _read(row):
    return {"id":row.id,"configured":True,"name":row.name,"provider":row.provider,"protocol":row.protocol,"model":row.model,"base_url":row.base_url,"enabled":row.enabled,"is_default":row.is_default,"max_output_tokens":row.max_output_tokens,"embedding_model":row.embedding_model,"embedding_base_url":row.embedding_base_url or "","has_api_key":bool(row.api_key_encrypted),"has_embedding_api_key":bool(row.embedding_api_key_encrypted or row.api_key_encrypted),"cooldown_until":row.cooldown_until.isoformat() if row.cooldown_until else None,"last_error_category":row.last_error_category}

def _get(db,tenant_id,config_id):
    row=db.query(LLMConfig).filter(LLMConfig.tenant_id==tenant_id,LLMConfig.id==config_id).first()
    if not row: raise HTTPException(404,"Conexão não encontrada")
    return row

def _save(db,tenant_id,payload,row=None):
    if row is None:
        if not payload.api_key: raise HTTPException(422,"Informe a chave para criar a conexão")
        # Serializes concurrent creation/default changes for this company.
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),{"key":"llm:"+tenant_id})
        row=LLMConfig(tenant_id=tenant_id,is_default=not db.query(LLMConfig).filter(LLMConfig.tenant_id==tenant_id,LLMConfig.is_default.is_(True)).first(),api_key_encrypted=encrypt_secret(payload.api_key) or "")
        db.add(row)
    for field in ["name","provider","protocol","base_url","model","enabled","max_output_tokens","embedding_model","embedding_base_url"]: setattr(row,field,getattr(payload,field))
    if payload.api_key: row.api_key_encrypted=encrypt_secret(payload.api_key) or row.api_key_encrypted
    if payload.embedding_api_key: row.embedding_api_key_encrypted=encrypt_secret(payload.embedding_api_key)
    row.cooldown_until=None;row.last_error_category=None
    db.commit();db.refresh(row)
    return _read(row)

@router.get("/connections")
def list_connections(db:DbSession,tenant_id:TenantId):
    return [_read(x) for x in db.query(LLMConfig).filter(LLMConfig.tenant_id==tenant_id).order_by(LLMConfig.created_at).all()]

@router.post("/connections",status_code=201)
def create_connection(payload:LLMConfigUpsert,db:DbSession,tenant_id:TenantId,user:CurrentUser):
    _require_admin(user);return _save(db,tenant_id,payload)

@router.put("/connections/{config_id}")
def update_connection(config_id:str,payload:LLMConfigUpsert,db:DbSession,tenant_id:TenantId,user:CurrentUser):
    _require_admin(user);return _save(db,tenant_id,payload,_get(db,tenant_id,config_id))

@router.post("/connections/{config_id}/default")
def make_default(config_id:str,db:DbSession,tenant_id:TenantId,user:CurrentUser):
    _require_admin(user)
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),{"key":"llm:"+tenant_id})
    row=_get(db,tenant_id,config_id)
    db.query(LLMConfig).filter(LLMConfig.tenant_id==tenant_id).update({LLMConfig.is_default:False},synchronize_session="fetch")
    db.flush();row.is_default=True;db.commit();return _read(row)

@router.post("/connections/{config_id}/resume")
def resume_connection(config_id:str,db:DbSession,tenant_id:TenantId,user:CurrentUser):
    _require_admin(user);row=_get(db,tenant_id,config_id);row.cooldown_until=None;row.last_error_category=None;db.commit();return _read(row)

@router.delete("/connections/{config_id}",status_code=204)
def delete_connection(config_id:str,db:DbSession,tenant_id:TenantId,user:CurrentUser):
    _require_admin(user);row=_get(db,tenant_id,config_id)
    agents=db.query(Agent).filter(Agent.tenant_id==tenant_id).all()
    if row.is_default or any(x.llm_config_id==config_id or config_id in (x.fallback_config_ids or []) for x in agents):
        raise HTTPException(409,"Remova os vínculos e altere a conexão padrão antes de excluir")
    db.delete(row);db.commit()

@router.get("/config")
def get_llm_config(db:DbSession,tenant_id:TenantId):
    row=db.query(LLMConfig).filter(LLMConfig.tenant_id==tenant_id,LLMConfig.is_default.is_(True)).first()
    return _read(row) if row else {"configured":False,"provider":"openai-compatible","model":"","base_url":"","embedding_model":"text-embedding-3-small","embedding_base_url":"","has_api_key":False,"has_embedding_api_key":False}

@router.put("/config")
def upsert_llm_config(payload:LLMConfigUpsert,db:DbSession,tenant_id:TenantId,user:CurrentUser):
    _require_admin(user)
    row=db.query(LLMConfig).filter(LLMConfig.tenant_id==tenant_id,LLMConfig.is_default.is_(True)).first()
    return _save(db,tenant_id,payload,row)

@router.get("/runs")
def list_runs(db:DbSession,tenant_id:TenantId):
    rows=db.query(ModelRun).filter(ModelRun.tenant_id==tenant_id).order_by(ModelRun.created_at.desc()).limit(100).all()
    return [{"id":x.id,"conversation_id":x.conversation_id,"revision":x.revision,"context_hash":x.context_hash,"attempts":x.attempts,"status":x.status,"selected_config_id":x.selected_config_id,"created_at":x.created_at.isoformat()} for x in rows]
