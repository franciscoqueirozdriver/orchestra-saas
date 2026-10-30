# Testes automatizados

Os testes são unitários e usam HTTP simulado; não enviam mensagens reais à Z-API nem chamam provedores de IA. Na pasta do projeto, execute `python -m venv .venv`, `. .venv/bin/activate`, `pip install -r backend/requirements-dev.txt` e `pytest -q`. Para homologação real, use uma instância de sandbox da Z-API e credenciais próprias, nunca incluídas no repositório.
