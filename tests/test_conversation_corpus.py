import json
from pathlib import Path

from app.conversation.behavior import command, transition
from app.conversation.humanize import should_wait

CASES = json.loads(Path('tests/fixtures/conversation_cases.json').read_text())


def test_corpus_has_at_least_forty_cases():
    assert len(CASES) >= 40


def test_every_case_matches_turn_policy():
    for case in CASES:
        state = transition(case.get('previous') or {}, case['incoming'])
        assert state['mode'] == case['mode'], case['id']
        assert command(case['incoming']) == case.get('command'), case['id']


def test_wait_expectations_match_deterministic_guard():
    cases = [case for case in CASES if case.get('expect') in {'wait', 'reply'}]
    assert cases
    for case in cases:
        expected = case['expect'] == 'wait'
        assert should_wait(case['incoming'], case.get('pending') or [],
                           case.get('last_assistant') or '') is expected, case['id']
