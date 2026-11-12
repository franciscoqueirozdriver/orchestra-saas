import json
import re
from pathlib import Path


CASES_PATH = Path(__file__).parent / 'fixtures' / 'conversation_response_cases.json'
REQUIRED = {'id', 'category', 'business_context', 'turns', 'known_facts',
            'desired_behavior', 'critical_failures'}


def test_synthetic_response_evaluation_cases_have_reviewable_rubric():
    cases = json.loads(CASES_PATH.read_text(encoding='utf-8'))
    assert len(cases) >= 8
    assert len({case['id'] for case in cases}) == len(cases)
    assert {'context_continuity', 'minimum_friction', 'operational_truthfulness',
            'business_grounding', 'conversation_naturalness'} <= {case['category'] for case in cases}

    for case in cases:
        assert REQUIRED <= case.keys()
        assert case['turns']
        assert case['known_facts']
        assert case['desired_behavior'].strip()
        assert case['critical_failures']
        assert all(turn['role'] in {'customer', 'assistant'} and turn['text'].strip()
                   for turn in case['turns'])


def test_synthetic_response_cases_do_not_contain_contact_identifiers():
    cases = json.loads(CASES_PATH.read_text(encoding='utf-8'))
    serialized = json.dumps(cases, ensure_ascii=False)
    assert not re.search(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b', serialized)
    assert not re.search(r'(?<!\d)(?:\+?\d[ .()-]*){10,13}(?!\d)', serialized)
