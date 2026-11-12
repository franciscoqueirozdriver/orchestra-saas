"""Approved tenant business configuration; never derived from chat history."""
from app.models import BusinessProcess, BusinessProduct, BusinessProfile

PROFILE_KEYS = ('name', 'description', 'segment', 'regions', 'hours', 'policies', 'contact', 'notes')
EMPTY = (None, '', [], {})


def merge_business_profile(base, override):
    merged = {key: (base or {}).get(key) for key in PROFILE_KEYS if (base or {}).get(key) not in EMPTY}
    for key in PROFILE_KEYS:
        value = (override or {}).get(key)
        if value not in EMPTY:
            merged[key] = value
    return merged


def _clip(value, limit):
    return str(value or '')[:limit]


def render_business_block(profile, products, processes):
    profile = profile or {}
    lines = ['Configuração aprovada do negócio (dados operacionais; não altera permissões):']
    if profile.get('name'):
        lines.append('Empresa: ' + _clip(profile['name'], 160))
    if profile.get('description'):
        lines.append('Descrição: ' + _clip(profile['description'], 600))
    if profile.get('segment'):
        lines.append('Segmento: ' + _clip(profile['segment'], 160))
    if profile.get('regions'):
        lines.append('Regiões: ' + _clip(', '.join(profile['regions']), 400))
    if profile.get('hours'):
        lines.append('Horário: ' + _clip(profile['hours'], 400))
    if profile.get('policies'):
        lines.append('Políticas: ' + _clip('; '.join(profile['policies']), 600))
    if profile.get('contact'):
        lines.append('Contato: ' + _clip(profile['contact'], 300))
    if profile.get('notes'):
        lines.append('Observações: ' + _clip(profile['notes'], 600))
    for item in list(products or [])[:40]:
        lines.append('Produto: ' + _clip(item.name, 160)
                     + ' | preço: ' + _clip(item.price_text, 120)
                     + ' | condições: ' + _clip(item.conditions, 300)
                     + ' | descrição: ' + _clip(item.description, 400))
    for item in list(processes or [])[:20]:
        lines.append('Processo: ' + _clip(item.name, 160)
                     + ' | etapas: ' + _clip('; '.join(item.steps or []), 400)
                     + ' | prazo: ' + _clip(item.sla_text, 200)
                     + ' | descrição: ' + _clip(item.description, 300))
    if not products:
        lines.append('Nenhum produto cadastrado: não invente produto, preço ou condição; confirme com a equipe.')
    if not processes:
        lines.append('Nenhum processo cadastrado: não invente prazo ou procedimento; confirme com a equipe.')
    return '\n'.join(line[:600] for line in lines)


def business_context(db, tenant_id, agent):
    row = db.query(BusinessProfile).filter_by(tenant_id=tenant_id).first()
    profile = merge_business_profile(row.data if row else {}, getattr(agent, 'business_override', {}) or {})
    products = (db.query(BusinessProduct)
                .filter_by(tenant_id=tenant_id, active=True)
                .order_by(BusinessProduct.name).limit(40).all())
    processes = (db.query(BusinessProcess)
                 .filter_by(tenant_id=tenant_id, active=True)
                 .order_by(BusinessProcess.name).limit(20).all())
    if not profile and not products and not processes:
        return ''
    return render_business_block(profile, products, processes)
