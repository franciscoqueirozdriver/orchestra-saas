"""Presets are conveniences, never an allowlist of provider brands or model IDs."""
PROTOCOLS = [
    {'id':'chat-completions','label':'OpenAI Chat Completions'},
    {'id':'responses','label':'OpenAI Responses'},
    {'id':'gemini','label':'Google Gemini nativo'},
    {'id':'anthropic','label':'Anthropic Messages'},
    {'id':'auto','label':'Automático (compatibilidade legada)'},
]
PRESETS = [
    {'id':'gemini','label':'Google Gemini','protocol':'gemini','base_url':'https://generativelanguage.googleapis.com/v1beta'},
    {'id':'groq','label':'Groq','protocol':'chat-completions','base_url':'https://api.groq.com/openai/v1'},
    {'id':'mistral','label':'Mistral AI','protocol':'chat-completions','base_url':'https://api.mistral.ai/v1'},
    {'id':'openrouter','label':'OpenRouter','protocol':'chat-completions','base_url':'https://openrouter.ai/api/v1'},
    {'id':'openai','label':'OpenAI','protocol':'responses','base_url':'https://api.openai.com/v1'},
    {'id':'xai','label':'xAI','protocol':'responses','base_url':'https://api.x.ai/v1'},
    {'id':'anthropic','label':'Anthropic / Claude','protocol':'anthropic','base_url':'https://api.anthropic.com/v1'},
    {'id':'openai-compatible','label':'OpenAI compatível','protocol':'chat-completions','base_url':''},
]


def catalog():
    # Return fresh objects; changes by callers cannot modify process-wide defaults.
    return {'protocols':[dict(p) for p in PROTOCOLS],'presets':[dict(p) for p in PRESETS],
            'custom_providers':True,'embedding_dimensions':1536,
            'model_catalog':'manual','live_provider_verified':False}
