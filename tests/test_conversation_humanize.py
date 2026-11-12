from app.conversation.humanize import (delivery_plan, opening, part_delay,
                                       remember_opening, repeated_opening, should_wait)


def test_delivery_plan_is_deterministic_and_bounded():
    parts = ['Oi, tudo bem?', 'A visita pode ser na quinta às 14h.']
    first, second = delivery_plan(parts, 'conv:1'), delivery_plan(parts, 'conv:1')
    assert first == second
    assert len(first) == 2
    assert all(1.0 <= delay <= 6.0 for delay in first)
    assert first[1] >= 1.5


def test_part_delay_prefers_per_part_plan():
    assert part_delay({'part_delays': [1.2, 2.7]}, 1) == 2.7
    assert part_delay({'delay': 3}, 1) == 3
    assert part_delay({'part_delays': ['x']}, 0) == 1


def test_wait_requires_ack_without_pending_question():
    assert should_wait('ok', [], 'Perfeito, registrei.') is True
    assert should_wait('👍', [], 'Registrei.') is True
    assert should_wait('ok', ['confirmar bairro'], 'Qual o bairro?') is False
    assert should_wait('ok', [], 'Qual o bairro?') is False
    assert should_wait('quero orçamento', [], 'Registrei.') is False


def test_opening_memory_prevents_repetition():
    state = remember_opening({}, 'Bom dia! Como posso ajudar?')
    assert repeated_opening(state, 'Bom dia! Tudo certo?') is True
    assert repeated_opening(state, 'O prazo é de cinco dias.') is False
    for index in range(6):
        state = remember_opening(state, f'Abertura {index} com texto suficiente')
    assert len(state['recent_openings']) == 5
    assert opening('  Primeira frase. Resto') == 'Primeira frase. Resto'[:40]
