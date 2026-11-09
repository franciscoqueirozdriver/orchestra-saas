from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.dependencies import CurrentUser
from app.outbound_control import outbound_status, set_outbound_enabled

router = APIRouter(prefix="/api/settings", tags=["configurações"])


def _require_admin(user) -> None:
    if user.role not in {"platform_admin", "tenant_admin"}:
        raise HTTPException(status_code=403, detail="Ação restrita a administradores")


class OutboundUpdate(BaseModel):
    enabled: bool
    confirm_real_sends: bool = False


@router.get("/outbound")
def get_outbound(user: CurrentUser) -> dict:
    _require_admin(user)
    return outbound_status()


@router.put("/outbound")
def put_outbound(payload: OutboundUpdate, user: CurrentUser) -> dict:
    _require_admin(user)
    if payload.enabled and not payload.confirm_real_sends:
        raise HTTPException(
            status_code=422,
            detail="Confirme que deseja liberar envios reais de WhatsApp",
        )
    try:
        set_outbound_enabled(payload.enabled)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return outbound_status()
