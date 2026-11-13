# Handoff — planejamento de modelos padrão por empresa e agente

**Data:** 13/11/2026
**Estado inicial:** `main` / `origin/main` em `c6b29a4c38af02fca8ee5a5c74eeb29acbfea0e6`.
**Branch:** `plan/company-model-routing`.
**Objetivo:** preparar proposta revisável; não implementar a configuração.

## Fontes

Lidos `AGENTS.md`, documentos essenciais de `docs/ai/`, handoff `2026-11-13-configuracao-provedores.md`, modelos/rotas/router/schemas de agente e LLM, `frontend/llm-ui.js`, migration `0003_model_routing.py` e testes relevantes em `tests/integration/test_runtime_safety.py`. Pesquisadas documentações oficiais dos modelos listados no plano. Nenhuma chamada a provedor foi feita.

## Resultado

Plano em `docs/planos/2026-11-13-roteamento-modelos-empresa-e-agentes.md`. O usuário esclareceu que já escolhe a conexão padrão no painel e que essa escolha deve ser herdada pelo agente, mas pode ser alterada nele. Conexões, modelos e credenciais ficam em um cadastro único em Configurações de modelos; o agente só mostra/reordena referências. O usuário também pediu um campo editável de habilidades por conexão, preenchido com capacidades documentadas conhecidas. O plano usa essa informação para orientar a escolha manual, nunca para roteamento automático.

O código atual não guarda política de alternativas da empresa. Agentes sem `llm_config_id` herdam `LLMConfig.is_default` em tempo de execução. O plano propõe materializar essa principal para agentes antigos durante um backfill aditivo, preservando a rota efetiva e evitando que mudanças futuras do padrão os alterem; não foi implementado e requer aprovação técnica do backfill.

As avaliações dos nove modelos são hipóteses de adequação documental. Os probes registrados em handoff são mínimos e não equivalem a benchmark de qualidade. Gemini padrão e demais configurações reais não foram consultados ou alterados.

## Alterações intencionais

- Novo plano: `docs/planos/2026-11-13-roteamento-modelos-empresa-e-agentes.md`.
- Novo handoff: este arquivo.
- Atualização do índice e dos documentos canônicos para marcar a proposta como planejada.

Arquivos privados e não rastreados existentes foram preservados fora do escopo; não foram abertos nem staged. Sem código funcional, migration, teste, banco, VPS, provedor, commit, push, merge ou deploy.

## Verificações e próximo passo

`git diff --check` passou; links/caminhos internos nos cinco documentos foram verificados sem caminhos ausentes. A revisão simples não detectou atribuição de credencial nos dois documentos novos. Nenhum teste de software foi executado, pois esta alteração é documental. Próximo passo: usuário revisar/aprovar o plano; só então iniciar implementação isolada. Manter o padrão Gemini atual até que o usuário escolha outra conexão no painel.

## Estado Git

Branch de planejamento criada sobre o SHA acima. O status final deve confirmar exatamente os cinco documentos esperados e manter privados os untracked originais; nada foi publicado.
