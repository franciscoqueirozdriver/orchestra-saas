from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.dependencies import CurrentUser, DbSession, TenantId
from app.models import Agent, Conversation, User, ZapiInstance
from app.schemas import AgentCreate, AgentUpdate

router = APIRouter(prefix="/api", tags=["operação"])


def _require_admin(user: User) -> None:
    if user.role not in {"platform_admin", "tenant_admin"}:
        raise HTTPException(status_code=403, detail="Ação restrita a administradores")


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
    return [{"id": x.id, "name": x.name, "description": x.description, "system_prompt": x.system_prompt, "enabled": x.enabled, "auto_reply_enabled": x.auto_reply_enabled, "created_at": x.created_at.isoformat()} for x in rows]


@router.post("/agents", status_code=201)
def create_agent(payload: AgentCreate, db: DbSession, tenant_id: TenantId, user: CurrentUser) -> dict:
    _require_admin(user)
    row = Agent(tenant_id=tenant_id, **payload.model_dump())
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Já existe um agente com esse nome nesta empresa") from exc
    db.refresh(row)
    return {"id": row.id, "name": row.name, "description": row.description, "system_prompt": row.system_prompt, "enabled": row.enabled, "auto_reply_enabled": row.auto_reply_enabled}


@router.put("/agents/{agent_id}")
def update_agent(agent_id: str, payload: AgentUpdate, db: DbSession, tenant_id: TenantId, user: CurrentUser) -> dict:
    _require_admin(user)
    row = db.query(Agent).filter(Agent.id == agent_id, Agent.tenant_id == tenant_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Já existe um agente com esse nome nesta empresa") from exc
    db.refresh(row)
    return {"id": row.id, "name": row.name, "description": row.description, "system_prompt": row.system_prompt, "enabled": row.enabled, "auto_reply_enabled": row.auto_reply_enabled}


@router.delete("/agents/{agent_id}", status_code=204)
def delete_agent(agent_id: str, db: DbSession, tenant_id: TenantId, user: CurrentUser) -> None:
    _require_admin(user)
    row = db.query(Agent).filter(Agent.id == agent_id, Agent.tenant_id == tenant_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    db.delete(row)
    db.commit()
