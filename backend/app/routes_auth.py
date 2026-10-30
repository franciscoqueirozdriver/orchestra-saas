from hashlib import sha256

from fastapi import APIRouter, HTTPException, Request, status
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import CurrentUser, DbSession
from app.models import Tenant, User
from app.schemas import LoginRequest, LoginResponse
from app.security import create_access_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["autenticação"])


def _response(db: Session, user: User) -> LoginResponse:
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first() if user.tenant_id else None
    return LoginResponse(access_token=create_access_token(user.id), role=user.role, tenant_name=tenant.name if tenant else None, tenant_id=tenant.id if tenant else None)


def _rate_limit(request: Request, email: str) -> tuple[Redis, str]:
    remote = request.client.host if request.client else "unknown"
    email_hash = sha256(email.lower().encode("utf-8")).hexdigest()[:20]
    key = f"login:rate:{remote}:{email_hash}"
    client = Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
    try:
        count = client.incr(key)
        if count == 1:
            client.expire(key, 60)
    except RedisError as exc:
        client.close()
        raise HTTPException(status_code=503, detail="Serviço de autenticação temporariamente indisponível") from exc
    if count > 8:
        client.close()
        raise HTTPException(status_code=429, detail="Muitas tentativas. Aguarde um minuto e tente novamente.")
    return client, key


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: DbSession) -> LoginResponse:
    email = str(payload.email).lower()
    rate_client, rate_key = _rate_limit(request, email)
    try:
        user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
        if user is None or not verify_password(user.password_hash, payload.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos")
        rate_client.delete(rate_key)
        return _response(db, user)
    finally:
        rate_client.close()


@router.get("/me", response_model=LoginResponse)
def me(db: DbSession, user: CurrentUser) -> LoginResponse:
    return _response(db, user)
