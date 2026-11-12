from types import SimpleNamespace

from app.conversation.business import business_context
from app.models import BusinessProduct, BusinessProfile


def test_business_context_is_tenant_scoped(runtime):
    with runtime.db() as db:
        db.add_all([
            BusinessProfile(tenant_id='tenant-a', data={'name': 'Empresa A'}),
            BusinessProfile(tenant_id='tenant-b', data={'name': 'Empresa B'}),
            BusinessProduct(tenant_id='tenant-a', name='Produto A'),
            BusinessProduct(tenant_id='tenant-b', name='Produto B'),
        ])
        db.commit()
    with runtime.db() as db:
        block = business_context(db, 'tenant-a', SimpleNamespace(business_override={}))
    assert 'Produto A' in block
    assert 'Produto B' not in block
    assert 'Empresa B' not in block
