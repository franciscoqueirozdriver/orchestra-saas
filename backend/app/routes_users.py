from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError

from app.dependencies import CurrentUser, DbSession, TenantId
from app.models import User
from app.security import hash_password

router = APIRouter(prefix="/api/users", tags=["usuários"])


def require_admin(user):
    if user.role not in {"platform_admin", "tenant_admin"}:
        raise HTTPException(403, "Ação restrita a administradores da empresa")


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    role: str = Field(pattern="^(tenant_admin|operator)$")


class UserStatus(BaseModel):
    is_active: bool


def serialize(user):
    return {"id":user.id,"full_name":user.full_name,"email":user.email,"role":user.role,"is_active":user.is_active,"created_at":user.created_at.isoformat()}


@router.get("")
def list_users(db: DbSession, tenant_id: TenantId, user: CurrentUser):
    require_admin(user)
    return [serialize(row) for row in db.query(User).filter(User.tenant_id==tenant_id).order_by(User.created_at,User.id).all()]


@router.post("", status_code=201)
def create_user(payload: UserCreate, db: DbSession, tenant_id: TenantId, user: CurrentUser):
    require_admin(user)
    row=User(tenant_id=tenant_id,email=str(payload.email).lower(),full_name=payload.full_name.strip(),password_hash=hash_password(payload.password),role=payload.role)
    db.add(row)
    try:db.commit()
    except IntegrityError as exc:
        db.rollback();raise HTTPException(409,"Este e-mail já está cadastrado") from exc
    db.refresh(row)
    return serialize(row)


@router.patch("/{user_id}")
def update_user(user_id: str, payload: UserStatus, db: DbSession, tenant_id: TenantId, user: CurrentUser):
    require_admin(user)
    row=db.query(User).filter(User.id==user_id,User.tenant_id==tenant_id).first()
    if row is None:raise HTTPException(404,"Usuário não encontrado nesta empresa")
    if row.id==user.id and not payload.is_active:raise HTTPException(409,"Não é possível desativar a própria conta")
    if row.role=="tenant_admin" and not payload.is_active:
        admins=db.query(User).filter(User.tenant_id==tenant_id,User.role=="tenant_admin",User.is_active.is_(True)).count()
        if admins<=1:raise HTTPException(409,"A empresa precisa manter pelo menos um administrador ativo")
    row.is_active=payload.is_active;db.commit();return serialize(row)
