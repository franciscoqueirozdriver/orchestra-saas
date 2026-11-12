"""Tenant business configuration. Writes require a tenant administrator."""
from fastapi import APIRouter, HTTPException

from app.control import serialized_mutation
from app.dependencies import CurrentUser, DbSession, TenantId
from app.models import BusinessProcess, BusinessProduct, BusinessProfile
from app.schemas import BusinessProcessWrite, BusinessProductWrite, BusinessProfileUpdate

router = APIRouter(prefix='/api/business', tags=['business'])


def _admin(user):
    if user.role not in {'platform_admin', 'tenant_admin'}:
        raise HTTPException(403, detail='Ação restrita a administradores')


def _product(row):
    return {'id': row.id, 'name': row.name, 'description': row.description,
            'price_text': row.price_text, 'conditions': row.conditions, 'active': row.active}


def _process(row):
    return {'id': row.id, 'name': row.name, 'description': row.description,
            'steps': row.steps, 'sla_text': row.sla_text, 'active': row.active}


@router.get('/profile')
def read_profile(db: DbSession, tenant_id: TenantId):
    row = db.query(BusinessProfile).filter_by(tenant_id=tenant_id).first()
    return {'version': row.version if row else 0, 'data': row.data if row else {}}


@router.put('/profile')
@serialized_mutation
def save_profile(payload: BusinessProfileUpdate, db: DbSession, tenant_id: TenantId, user: CurrentUser):
    _admin(user)
    row = db.query(BusinessProfile).filter_by(tenant_id=tenant_id).first()
    data = payload.model_dump()
    if row is None:
        row = BusinessProfile(tenant_id=tenant_id, version=1, data=data)
        db.add(row)
    else:
        row.data = data
        row.version += 1
    db.commit()
    return {'version': row.version, 'data': row.data}


@router.get('/products')
def list_products(db: DbSession, tenant_id: TenantId):
    return [_product(row) for row in db.query(BusinessProduct)
            .filter_by(tenant_id=tenant_id).order_by(BusinessProduct.name).all()]


@router.post('/products', status_code=201)
@serialized_mutation
def create_product(payload: BusinessProductWrite, db: DbSession, tenant_id: TenantId, user: CurrentUser):
    _admin(user)
    row = BusinessProduct(tenant_id=tenant_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return _product(row)


@router.patch('/products/{product_id}')
@serialized_mutation
def update_product(product_id: str, payload: BusinessProductWrite, db: DbSession, tenant_id: TenantId, user: CurrentUser):
    _admin(user)
    row = db.query(BusinessProduct).filter_by(tenant_id=tenant_id, id=product_id).first()
    if row is None:
        raise HTTPException(404, detail='Produto não encontrado')
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.commit()
    return _product(row)


@router.delete('/products/{product_id}', status_code=204)
@serialized_mutation
def delete_product(product_id: str, db: DbSession, tenant_id: TenantId, user: CurrentUser):
    _admin(user)
    row = db.query(BusinessProduct).filter_by(tenant_id=tenant_id, id=product_id).first()
    if row is None:
        raise HTTPException(404, detail='Produto não encontrado')
    db.delete(row)
    db.commit()


@router.get('/processes')
def list_processes(db: DbSession, tenant_id: TenantId):
    return [_process(row) for row in db.query(BusinessProcess)
            .filter_by(tenant_id=tenant_id).order_by(BusinessProcess.name).all()]


@router.post('/processes', status_code=201)
@serialized_mutation
def create_process(payload: BusinessProcessWrite, db: DbSession, tenant_id: TenantId, user: CurrentUser):
    _admin(user)
    row = BusinessProcess(tenant_id=tenant_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return _process(row)


@router.patch('/processes/{process_id}')
@serialized_mutation
def update_process(process_id: str, payload: BusinessProcessWrite, db: DbSession, tenant_id: TenantId, user: CurrentUser):
    _admin(user)
    row = db.query(BusinessProcess).filter_by(tenant_id=tenant_id, id=process_id).first()
    if row is None:
        raise HTTPException(404, detail='Processo não encontrado')
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.commit()
    return _process(row)


@router.delete('/processes/{process_id}', status_code=204)
@serialized_mutation
def delete_process(process_id: str, db: DbSession, tenant_id: TenantId, user: CurrentUser):
    _admin(user)
    row = db.query(BusinessProcess).filter_by(tenant_id=tenant_id, id=process_id).first()
    if row is None:
        raise HTTPException(404, detail='Processo não encontrado')
    db.delete(row)
    db.commit()
