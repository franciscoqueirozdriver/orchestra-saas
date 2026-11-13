from types import SimpleNamespace
import httpx
import pytest
from pydantic import ValidationError
from app.provider_catalog import catalog
from app.schemas import LLMConfigUpsert
from app.llm_client import complete,LLMError,resolved_protocol
from app.embedding_config import embedding_spec,embedding_request_config
from app.security import encrypt_secret


def test_presets_include_mesa_providers_and_return_fresh_metadata():
    data=catalog();ids={p['id'] for p in data['presets']}
    assert {'gemini','groq','mistral','openrouter','openai','xai','anthropic','openai-compatible'}<=ids
    protocols={p['id'] for p in data['protocols']}
    for p in data['presets']:
        assert p['protocol'] in protocols
        if p['base_url']:LLMConfigUpsert(provider=p['id'],protocol=p['protocol'],base_url=p['base_url'],model='synthetic')
    data['presets'][0]['base_url']='https://mutated.invalid'
    assert catalog()['presets'][0]['base_url']!='https://mutated.invalid'
    assert data['custom_providers'] is True and not data['live_provider_verified']


@pytest.mark.parametrize('provider',['custom-acme','mistral','openrouter'])
def test_new_provider_brands_need_no_schema_or_adapter_when_protocol_matches(monkeypatch,provider):
    config=LLMConfigUpsert(provider=provider,protocol='chat-completions',base_url='https://synthetic.invalid/api/v1',model='vendor/new-model',api_key='synthetic-key')
    calls=[]
    monkeypatch.setattr('app.llm_client.validate_public_https',lambda _:None)
    monkeypatch.setattr('app.llm_client.httpx.post',lambda url,**kwargs:calls.append((url,kwargs)) or httpx.Response(200,json={'choices':[{'message':{'content':'synthetic answer'},'finish_reason':'stop'}]}))
    assert complete(config.provider,config.base_url,config.model,config.api_key,'synthetic',[],protocol=config.protocol)=='synthetic answer'
    assert calls[0][0]=='https://synthetic.invalid/api/v1/chat/completions'
    assert calls[0][1]['json']['model']=='vendor/new-model'


@pytest.mark.parametrize('label,provider,protocol,base_url,model,expected_url', [
    ('NVIDIA - Mistral Large 4', 'openai-compatible', 'chat-completions', 'https://integrate.api.nvidia.com/v1', 'mistralai/mistral-large-4-1t-a52b', 'https://integrate.api.nvidia.com/v1/chat/completions'),
    ('Gemini', 'gemini', 'gemini', 'https://generativelanguage.googleapis.com/v1beta', 'gemini-3.5-flash-lite', 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent'),
    ('Groq', 'groq', 'chat-completions', 'https://api.groq.com/openai/v1', 'qwen/qwen3.8-27b', 'https://api.groq.com/openai/v1/chat/completions'),
    ('OpenRouter', 'openrouter', 'chat-completions', 'https://openrouter.ai/api/v1', 'openrouter/free', 'https://openrouter.ai/api/v1/chat/completions'),
    ('Gemini Gemma', 'gemini', 'gemini', 'https://generativelanguage.googleapis.com/v1beta', 'gemma-4-31b-it', 'https://generativelanguage.googleapis.com/v1beta/models/gemma-4-31b-it:generateContent'),
    ('NVIDIA - Step 5', 'openai-compatible', 'chat-completions', 'https://integrate.api.nvidia.com/v1', 'stepfun-ai/step-5-preview', 'https://integrate.api.nvidia.com/v1/chat/completions'),
    ('NVIDIA - DeepSeek Flash', 'openai-compatible', 'chat-completions', 'https://integrate.api.nvidia.com/v1', 'deepseek-ai/deepseek-v4.1-flash', 'https://integrate.api.nvidia.com/v1/chat/completions'),
    ('NVIDIA - Nemotron Lightning', 'openai-compatible', 'chat-completions', 'https://integrate.api.nvidia.com/v1', 'nvidia/nemotron-3.5-lightning-30b-a3b', 'https://integrate.api.nvidia.com/v1/chat/completions'),
    ('NVIDIA - GPT OSS', 'openai-compatible', 'chat-completions', 'https://integrate.api.nvidia.com/v1', 'openai/gpt-oss-20b', 'https://integrate.api.nvidia.com/v1/chat/completions'),
])
def test_current_panel_models_follow_their_saved_protocol_contract_without_live_calls(
    monkeypatch, label, provider, protocol, base_url, model, expected_url,
):
    calls=[]
    monkeypatch.setattr('app.llm_client.validate_public_https',lambda _:None)

    def fake_post(url, **kwargs):
        calls.append((url,kwargs))
        if protocol=='gemini':
            return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':'synthetic answer'}]},'finishReason':'STOP'}]})
        return httpx.Response(200,json={'choices':[{'message':{'content':'synthetic answer'},'finish_reason':'stop'}]})

    monkeypatch.setattr('app.llm_client.httpx.post',fake_post)
    result=complete(provider,base_url,model,'synthetic-key','synthetic instructions',
                    [{'role':'user','content':'synthetic request'}],protocol=protocol,max_output_tokens=64)

    assert result=='synthetic answer', label
    assert len(calls)==1
    assert calls[0][0]==expected_url
    payload=calls[0][1]['json']
    assert (payload['contents'][0]['parts'][0]['text'] if protocol=='gemini'
            else payload['messages'][1]['content'])=='synthetic request'
    if protocol!='gemini':
        assert payload['model']==model


def test_protocol_is_explicit_independent_of_provider_brand():
    assert resolved_protocol('custom-relay','gemini')=='gemini'
    with pytest.raises(ValidationError):LLMConfigUpsert(provider='custom',protocol='unimplemented-protocol',base_url='https://synthetic.invalid',model='synthetic')


@pytest.mark.parametrize('suffix',['/chat/completions','/responses','/messages','/embeddings','/models/synthetic:generateContent'])
def test_full_operation_url_is_not_accepted_as_api_root(suffix):
    with pytest.raises(ValidationError):LLMConfigUpsert(provider='custom',base_url='https://synthetic.invalid/v1'+suffix,model='synthetic')


def test_native_model_prefix_normalization_does_not_change_openrouter_ids():
    native=LLMConfigUpsert(provider='gemini',base_url='https://synthetic.invalid/v1beta',model='models/synthetic',api_key='  synthetic-key  ')
    assert native.model=='synthetic' and native.api_key=='synthetic-key'
    compatible=LLMConfigUpsert(provider='openrouter',base_url='https://synthetic.invalid/v1',model='vendor/synthetic')
    assert compatible.model=='vendor/synthetic'


def test_native_generation_does_not_silently_inherit_an_embedding_endpoint():
    row=SimpleNamespace(provider='gemini',protocol='gemini',base_url='https://synthetic.invalid/v1beta',embedding_base_url=None,embedding_model='synthetic',api_key_encrypted=encrypt_secret('generation-key'),embedding_api_key_encrypted=None)
    assert embedding_spec(row) is None
    with pytest.raises(LLMError) as exc:embedding_request_config(row)
    assert exc.value.category=='configuration'
    row.embedding_base_url='https://embedding.invalid/v1';row.embedding_api_key_encrypted=encrypt_secret('embedding-key')
    assert embedding_request_config(row)==('https://embedding.invalid/v1','synthetic','embedding-key')


def test_google_embeddings_request_1536_and_normalize_without_changing_other_providers(monkeypatch):
    from app.embedding_client import embed_texts
    monkeypatch.setattr('app.embedding_client.validate_public_https',lambda _:None)
    calls=[]
    def post(url,**kwargs):
        calls.append((url,kwargs))
        return httpx.Response(200,json={'data':[{'index':0,'embedding':[2.0]+[0.0]*1535}]})
    monkeypatch.setattr('app.embedding_client.httpx.post',post)
    result=embed_texts('https://generativelanguage.googleapis.com/v1beta/openai','gemini-embedding-001','synthetic-key',['Synthetic text'])
    assert calls[-1][1]['json']['dimensions']==1536
    assert calls[-1][0].endswith('/openai/embeddings')
    assert calls[-1][1]['headers']['Authorization']=='Bearer synthetic-key'
    assert result[0][0]==1.0 and len(result[0])==1536
    embed_texts('https://other.invalid/v1','synthetic','synthetic-key',['Synthetic text'])
    assert 'dimensions' not in calls[-1][1]['json']


@pytest.mark.parametrize('size',[1024,3072])
def test_wrong_embedding_dimensions_are_rejected(monkeypatch,size):
    from app.embedding_client import embed_texts
    monkeypatch.setattr('app.embedding_client.validate_public_https',lambda _:None)
    monkeypatch.setattr('app.embedding_client.httpx.post',lambda *a,**k:httpx.Response(200,json={'data':[{'embedding':[1.0]*size}]}))
    with pytest.raises(LLMError,match='1536 dimensões por trecho'):
        embed_texts('https://synthetic.invalid/v1','synthetic','synthetic',['Synthetic'])
