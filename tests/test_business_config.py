from types import SimpleNamespace
from app.conversation.business import merge_business_profile, render_business_block


def test_merge_keeps_base_and_applies_only_known_override_keys():
    base = {'name': 'Empresa A', 'hours': '9h às 18h', 'policies': ['troca em 7 dias']}
    merged = merge_business_profile(base, {'hours': '8h às 17h', 'inventado': 'x'})
    assert merged['name'] == 'Empresa A'
    assert merged['hours'] == '8h às 17h'
    assert 'inventado' not in merged


def test_render_labels_approved_configuration_and_limits_catalog():
    products = [SimpleNamespace(name=f'Produto {i}', description='d', price_text='R$ 10',
                                conditions='c') for i in range(50)]
    processes = [SimpleNamespace(name=f'Processo {i}', description='d', steps=['a', 'b'],
                                 sla_text='2 dias') for i in range(30)]
    text = render_business_block({'name': 'Empresa A'}, products, processes)
    assert 'configuração aprovada do negócio' in text.lower()
    assert text.count('Produto:') == 40
    assert text.count('Processo:') == 20
    assert all(len(line) <= 600 for line in text.splitlines())


def test_render_labels_missing_catalog_rule():
    text = render_business_block({'name': 'Empresa A'}, [], [])
    assert 'não invente' in text.lower() or 'confirme' in text.lower()
