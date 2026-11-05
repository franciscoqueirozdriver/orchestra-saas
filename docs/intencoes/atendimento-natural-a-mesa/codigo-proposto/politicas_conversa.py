"""Protótipo documental puro. Não importado pelo runtime do Orquestra.

Adaptação dos conceitos do A Mesa; sem rede, banco, LLM ou envio WhatsApp.
A classificação semântica real e a aplicação transacional ainda serão implementadas.
"""
from dataclasses import dataclass
from enum import Enum
import re
import unicodedata


class Acao(str, Enum):
    RESPONDER = 'responder'
    CANCELAR = 'cancelar'
    HUMANO = 'humano'
    SILENCIAR = 'silenciar'
    ESCLARECER = 'esclarecer'
    RETOMAR = 'retomar'


def normalizar(texto: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').strip().lower()


@dataclass(frozen=True)
class Estado:
    revision: int
    cancel_epoch: int = 0
    mode: str = 'ai'
    clarification_count: int = 0


def decidir(estado: Estado, texto: str, ambiguo: bool = False) -> Acao:
    """Comandos exatos têm prioridade; não engolir 'não, quero outra coisa'.

    RETOMAR aqui é só candidato: o chamador verifica autorização, consentimento e
    política. Classificador e contato não podem liberar takeover protegido sozinhos.
    """
    t = normalizar(texto).rstrip('!.?')
    if t in {'cancelar', 'cancela', 'pare'}:
        return Acao.CANCELAR
    if t in {'quero falar com uma pessoa', 'quero um atendente', 'atendimento humano'}:
        return Acao.HUMANO
    if t == 'retomar ia':
        return Acao.RETOMAR
    if estado.mode != 'ai':
        return Acao.SILENCIAR
    if ambiguo:
        return Acao.ESCLARECER if estado.clarification_count < 1 else Acao.HUMANO
    return Acao.RESPONDER


def resposta_valida(esperado: Estado, atual: Estado) -> bool:
    """Revalidar antes de CADA bolha; não substitui lock/transação no dispatcher."""
    return (atual.mode == 'ai' and esperado.revision == atual.revision
            and esperado.cancel_epoch == atual.cancel_epoch)


def dividir_resposta(texto: str, limite: int = 900) -> list[str]:
    """Preserva parágrafos/frases quando possível, com corte duro como último recurso.

    Não coloca '(Parte i/n)' no diálogo comum. Formatação de listas e links precisa
    de tratamento específico na implementação final; esta é uma política de texto.
    """
    if limite < 20:
        raise ValueError('limite deve ser >= 20')
    resto = texto.strip()
    partes: list[str] = []
    while len(resto) > limite:
        janela = resto[:limite + 1]
        cortes = [janela.rfind('\n\n')]
        cortes += [m.end() for m in re.finditer(r'[.!?](?=\s)', janela)]
        corte = max((x for x in cortes if limite // 3 <= x <= limite), default=0)
        if not corte:
            corte = janela.rfind(' ', 0, limite + 1)
        if corte <= 0:
            corte = limite
        partes.append(resto[:corte].strip())
        resto = resto[corte:].strip()
    if resto:
        partes.append(resto)
    return partes


def pausa_ms(texto: str, campanha: bool = False) -> int:
    if campanha:
        return min(4000, max(1500, len(texto) * 40))
    return min(1000, max(400, len(texto) * 12))
