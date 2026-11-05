from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.dependencies import CurrentUser, DbSession, TenantId
from app.models import Agent, Conversation, User, ZapiInstance, LLMConfig
from app.schemas import AgentCreate, AgentUpdate

router = APIRouter(prefix="/api", tags=["operação"])


def _require_admin(user: User) -> None:
    if user.role not in {"platform_admin", "tenant_admin"}:
        raise HTTPException(status_code=403, detail="Ação restrita a administradores")


def _validate_models(db, tenant_id, primary, fallbacks):
    identifiers = ([primary] if primary else []) + (fallbacks or [])
    if len(identifiers) != len(set(identifiers)):
        raise HTTPException(422, "Não repita conexões na cadeia de modelos")
    if identifiers and db.query(LLMConfig).filter(LLMConfig.tenant_id == tenant_id, LLMConfig.id.in_(identifiers)).count() != len(identifiers):
        raise HTTPException(422, "Conexão de modelo inválida para esta empresa")


@router.get("/dashboard/summary")
def dashboard_summary(db: DbSession, tenant_id: TenantId) -> dict:
    agents = db.query(func.count(Agent.id)).filter(Agent.tenant_id == tenant_id).scalar() or 0
    active_agents = db.query(func.count(Agent.id)).filter(Agent.tenant_id == tenant_id, Agent.enabled.is_(True)).scalar() or 0
    instances = db.query(func.count(ZapiInstance.id)).filter(ZapiInstance.tenant_id == tenant_id, ZapiInstance.is_active.is_(True)).scalar() or 0
    open_conversations = db.query(func.count(Conversation.id)).filter(Conversation.tenant_id == tenant_id, Conversation.status == "open").scalar() or 0
    return {"counts": {"agents": agents, "active_agents": active_agents, "instances": instances, "open_conversations": open_conversations}}


@router.get("/agents")
def list_agents(db: DbSession, tenant_id: TenantId) -> list[dict]:
    rows = db.query(Agent).filter(Agent.tenant_id == tenant_id).order_by(Agent.created_at.desc()).all()
    return [{"id": x.id, "name": x.name, "description": x.description, "system_prompt": x.system_prompt, "enabled": x.enabled, "auto_reply_enabled": x.auto_reply_enabled, "llm_config_id": x.llm_config_id, "fallback_config_ids": x.fallback_config_ids, "created_at": x.created_at.isoformat()} for x in rows]


@router.post("/agents", status_code=201)
def create_agent(payload: AgentCreate, db: DbSession, tenant_id: TenantId, user: CurrentUser) -> dict:
    _require_admin(user)
    _validate_models(db, tenant_id, payload.llm_config_id, payload.fallback_config_ids)
    row = Agent(tenant_id=tenant_id, **payload.model_dump())
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Já existe um agente com esse nome nesta empresa") from exc
    db.refresh(row)
    return {"id": row.id, "name": row.name, "description": row.description, "system_prompt": row.system_prompt, "enabled": row.enabled, "auto_reply_enabled": row.auto_reply_enabled, "llm_config_id": row.llm_config_id, "fallback_config_ids": row.fallback_config_ids}


@router.put("/agents/{agent_id}")
def update_agent(agent_id: str, payload: AgentUpdate, db: DbSession, tenant_id: TenantId, user: CurrentUser) -> dict:
    _require_admin(user)
    row = db.query(Agent).filter(Agent.id == agent_id, Agent.tenant_id == tenant_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    changes = payload.model_dump(exclude_unset=True)
    if any(value is None for key, value in changes.items() if key != "llm_config_id"):
        raise HTTPException(422, "Campos obrigatórios não podem ser nulos")
    _validate_models(db, tenant_id, changes.get("llm_config_id", row.llm_config_id), changes.get("fallback_config_ids", row.fallback_config_ids))
    for field, value in changes.items():
        setattr(row, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Já existe um agente com esse nome nesta empresa") from exc
    db.refresh(row)
    return {"id": row.id, "name": row.name, "description": row.description, "system_prompt": row.system_prompt, "enabled": row.enabled, "auto_reply_enabled": row.auto_reply_enabled, "llm_config_id": row.llm_config_id, "fallback_config_ids": row.fallback_config_ids}


@router.delete("/agents/{agent_id}", status_code=204)
def delete_agent(agent_id: str, db: DbSession, tenant_id: TenantId, user: CurrentUser) -> None:
    _require_admin(user)
    row = db.query(Agent).filter(Agent.id == agent_id, Agent.tenant_id == tenant_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    db.delete(row)
    db.commit()
