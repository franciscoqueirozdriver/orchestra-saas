from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tenant, User
from app.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Annotated[Session, Depends(get_db)]) -> User:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida ou expirada", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise unauthorized
    except (jwt.PyJWTError, ValueError):
        raise unauthorized
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if user is None:
        raise unauthorized
    return user


def get_tenant_id(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    requested_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
) -> str:
    if user.role == "platform_admin":
        if not requested_tenant_id:
            raise HTTPException(status_code=400, detail="Selecione uma empresa para esta operação")
        tenant = db.query(Tenant).filter(Tenant.id == requested_tenant_id, Tenant.is_active.is_(True)).first()
        if tenant is None:
            raise HTTPException(status_code=404, detail="Empresa não encontrada")
        return tenant.id
    if user.tenant_id is None:
        raise HTTPException(status_code=403, detail="Usuário sem empresa associada")
    if requested_tenant_id and requested_tenant_id != user.tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado para outra empresa")
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id, Tenant.is_active.is_(True)).first()
    if tenant is None:
        raise HTTPException(status_code=403, detail="Empresa inativa ou não encontrada")
    return tenant.id


def require_platform_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "platform_admin":
        raise HTTPException(status_code=403, detail="Ação restrita ao administrador da plataforma")
    return user


DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
TenantId = Annotated[str, Depends(get_tenant_id)]
