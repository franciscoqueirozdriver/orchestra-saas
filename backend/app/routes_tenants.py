from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError

from app.dependencies import CurrentUser, DbSession, require_platform_admin
from app.models import Tenant, User
from app.schemas import TenantCreate
from app.security import hash_password

router = APIRouter(prefix="/api/tenants", tags=["empresas"])


@router.get("")
def list_tenants(db: DbSession, _admin: User = Depends(require_platform_admin)) -> list[dict]:
    rows = db.query(Tenant).order_by(Tenant.created_at.desc()).all()
    return [{"id": row.id, "name": row.name, "slug": row.slug, "status": "active" if row.is_active else "inactive", "created_at": row.created_at.isoformat()} for row in rows]


@router.post("", status_code=201)
def create_tenant(payload: TenantCreate, db: DbSession, _admin: User = Depends(require_platform_admin)) -> dict:
    email = str(payload.owner_email).lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Já existe um usuário com esse e-mail")
    tenant = Tenant(name=payload.name.strip(), slug=payload.slug)
    db.add(tenant)
    db.flush()
    owner = User(tenant_id=tenant.id, email=email, password_hash=hash_password(payload.owner_password), full_name=payload.owner_name.strip(), role="tenant_admin")
    db.add(owner)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="O slug ou e-mail já está cadastrado") from exc
    return {"id": tenant.id, "name": tenant.name, "slug": tenant.slug, "status": "active", "created_at": tenant.created_at.isoformat(), "owner_email": owner.email}
