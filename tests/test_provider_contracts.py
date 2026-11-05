import httpx
import pytest
from app.llm_client import complete, LLMError


@pytest.mark.parametrize('provider,base,model,response,suffix', [
    ('groq', 'https://api.groq.com/openai/v1', 'synthetic', {'choices': [{'message': {'content': 'ok'}, 'finish_reason': 'stop'}]}, '/chat/completions'),
    ('xai', 'https://api.x.ai/v1', 'synthetic', {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'ok'}]}]}, '/responses'),
    ('anthropic', 'https://api.anthropic.com/v1', 'synthetic', {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': 'ok'}]}, '/messages'),
    ('gemini', 'https://generativelanguage.googleapis.com/v1beta', 'synthetic', {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': 'internal', 'thought': True}, {'text': 'ok'}]}}]}, '/models/synthetic:generateContent'),
])
def test_contracts_use_correct_auth_limits_history_and_no_tools(monkeypatch, provider, base, model, response, suffix):
    captured = {}
    monkeypatch.setattr('app.llm_client.validate_public_https', lambda _: None)
    def post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return httpx.Response(200, json=response)
    monkeypatch.setattr('app.llm_client.httpx.post', post)
    history = [{'role': 'user', 'content': 'synthetic question'}]
    assert complete(provider, base, model, 'test-only-key', 'synthetic instruction', history, max_output_tokens=256) == 'ok'
    assert captured['url'] == base + suffix
    headers, body = captured['headers'], captured['json']
    if provider == 'gemini':
        assert headers['x-goog-api-key'] == 'test-only-key'
        assert 'Authorization' not in headers
        assert body['generationConfig']['maxOutputTokens'] == 256
        assert body['contents'][0]['parts'][0]['text'] == 'synthetic question'
    else:
        assert headers['Authorization'] == 'Bearer test-only-key'
        assert body.get('max_tokens', body.get('max_output_tokens')) == 256
    if provider == 'anthropic':
        assert headers['anthropic-version'] == '2026-10-21'
        assert body['system'] == 'synthetic instruction'
    if provider == 'xai':
        assert body['store'] is False
        assert body['input'] == history
    assert 'tools' not in body
    assert captured['follow_redirects'] is False


@pytest.mark.parametrize('provider,response', [
    ('groq', {'choices': [{'finish_reason': 'content_filter', 'message': {'content': 'blocked'}}]}),
    ('xai', {'output': [{'type': 'message', 'content': [{'type': 'refusal', 'refusal': 'blocked'}]}]}),
    ('anthropic', {'stop_reason': 'refusal', 'content': []}),
    ('gemini', {'promptFeedback': {'blockReason': 'SAFETY'}}),
])
def test_provider_refusals_never_allow_fallback(monkeypatch, provider, response):
    monkeypatch.setattr('app.llm_client._post', lambda *a, **kw: response)
    with pytest.raises(LLMError) as exc:
        complete(provider, 'https://provider.invalid/v1', 'synthetic', 'test-key', '', [])
    assert exc.value.category == 'safety'
    assert not exc.value.permits_fallback


@pytest.mark.parametrize('provider,response', [
    ('groq', {'choices': [None]}),
    ('xai', {'output': None}),
    ('anthropic', {'content': None}),
    ('gemini', {'candidates': [None]}),
])
def test_malformed_success_payloads_are_typed_safe_errors(monkeypatch, provider, response):
    monkeypatch.setattr('app.llm_client._post', lambda *a, **kw: response)
    with pytest.raises(LLMError) as exc:
        complete(provider, 'https://provider.invalid/v1', 'synthetic', 'test-key', '', [])
    assert exc.value.category == 'invalid_response'
