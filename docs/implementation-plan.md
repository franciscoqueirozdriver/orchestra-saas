# Plano de execução e evidências

Autorização: implementar as pendências do escopo original, preservando Z-API como transporte exclusivo.
A stack existente será mantida. Não substituir o projeto nem habilitar respostas sem configuração explícita.

1. Confiabilidade: associação agente/instância; política central de consentimento, bloqueio e frequência; outbox assíncrona; callbacks de status/conexão; recuperação periódica; readiness; testes com PostgreSQL e Redis isolados.
2. Operação no painel: configurar políticas/vínculos, consentimento, pausa humana e outbox; auditoria e usuários.
3. Memória e conhecimento: curadoria individual, propostas de aprendizado, aprovação/versionamento, busca com relevância e proveniência; testes de isolamento.
4. Modelos e mídia: adaptadores por contrato, fallback, envio/recebimento de mídia, transcrição e voz, download privado com proteção SSRF.
5. Ferramentas: catálogo comercial e orçamentos determinísticos; Google Calendar via OAuth com autorização por empresa, idempotência e aprovação; multiagentes com ferramentas restritas.
6. Produção: métricas, alertas, retenção/exclusão, backup automático externo e restauração; testes reais Z-API, IA, Calendar e domínio/VPS.

Cada etapa exige testes antes da seguinte. Integrações HTTP simuladas não homologam provedores reais.
Credenciais de IA/Calendar e um contato de teste autorizado são necessários para homologação real, usando formulários seguros, nunca valores no repositório.

## Linha de base
- 20 testes unitários passaram em contêiner descartável, sem credenciais reais.
- Serviços existentes mantidos durante desenvolvimento.
- Documentação oficial Z-API: índice de 250 páginas e seis páginas adicionais de segurança/operação baixadas para consulta em 30/10/2026. Métodos/rotas conferidos também na navegação HTML oficial (Markdown omite alguns métodos).
- Referências: https://developer.z-api.io/llms.txt e https://developer.z-api.io/webhooks/update-every-webhooks .

## Prazos
A ordem é por dependências e critérios de aceite; não há promessa de prazo sem volume de uso, limites dos provedores e homologação externa. O progresso será registrado por implementação e evidência.
