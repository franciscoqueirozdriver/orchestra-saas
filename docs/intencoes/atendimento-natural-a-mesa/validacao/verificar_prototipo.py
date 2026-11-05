"""Verificação documental: funções puras + integridade, sem acessar rede/banco."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('politicas_conversa', root / 'codigo-proposto/politicas_conversa.py')
p = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = p
spec.loader.exec_module(p)

checks = 0

def check(value):
    global checks
    if not value:
        raise AssertionError('cenário documental falhou')
    checks += 1

check(p.decidir(p.Estado(1), 'Cancela!') == p.Acao.CANCELAR)
check(p.decidir(p.Estado(1), 'Não. Quero o endereço') == p.Acao.RESPONDER)
check(p.decidir(p.Estado(1), 'Quero um atendente') == p.Acao.HUMANO)
check(p.decidir(p.Estado(1, mode='human'), 'Qual o horário?') == p.Acao.SILENCIAR)
check(p.decidir(p.Estado(1), 'algo', ambiguo=True) == p.Acao.ESCLARECER)
check(p.decidir(p.Estado(1, clarification_count=1), 'algo', ambiguo=True) == p.Acao.HUMANO)
check(not p.resposta_valida(p.Estado(1), p.Estado(2)))
check(not p.resposta_valida(p.Estado(1), p.Estado(1, cancel_epoch=1)))
check(not p.resposta_valida(p.Estado(1), p.Estado(1, mode='human')))
check(p.resposta_valida(p.Estado(1), p.Estado(1)))
check(p.dividir_resposta('') == [])
for texto in ['x' * 901, 'Uma frase. ' * 150, 'Primeiro parágrafo.\n\nSegundo parágrafo. ' * 40]:
    partes = p.dividir_resposta(texto, 200)
    check(all(0 < len(parte) <= 200 for parte in partes))
    check(''.join(''.join(partes).split()) == ''.join(texto.split()))
check(400 <= p.pausa_ms('Oi') <= 1000)
check(1500 <= p.pausa_ms('x' * 1000, campanha=True) <= 4000)
manifest = json.loads((root / 'referencias-a-mesa/manifesto.json').read_text())
for entry in manifest['files']:
    data = (root / entry['snapshot']).read_bytes()
    check(hashlib.sha256(data).hexdigest() == entry['sha256'])
print(f'{checks} verificações documentais passaram; SQL e integrações não executados.')
