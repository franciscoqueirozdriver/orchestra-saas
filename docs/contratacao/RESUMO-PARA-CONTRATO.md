# Resumo para elaboração do contrato

Data: 04/11/2026.

Documento detalhado: [base de escopo e cronograma](BASE-ESCOPO-E-CRONOGRAMA-INSTAGRAM-WHATSAPP.md).

## Objeto

Adequação do sistema Instagram existente e sua integração com o Orquestra para
encaminhar interessados de comentários/campanhas ao WhatsApp e atendê-los com IA,
contexto da origem, histórico e possibilidade de intervenção humana.

## Já existe

**Instagram:** contas, autenticação, comentários/webhooks, produtos/links,
campanhas, respostas privadas/públicas, filas, pausas e painel de operação.
O contratante informa que está em funcionamento. O projeto será aproveitado;
a nova contratação não pressupõe sua reconstrução. Código, produção e permissões
externas precisam ter uma baseline registrada antes do aceite do escopo.

**Orquestra:** empresas, login, cadastro de agentes, integração textual Z-API,
conversas/histórico, geração de respostas por IA, documentos/RAG, banco, fila,
Docker e preparação/implantação inicial em VPS. O HTTPS e a saúde dos serviços
foram demonstrados em sessão anterior. O atendimento integrado ainda não foi
homologado ponta a ponta com o Instagram.

**Preparação:** documento de intenções para aproveitar o atendente do A Mesa,
código histórico de referência, protótipo e propostas de schema. Trata-se de
planejamento; não representa implementação pronta.

## Será desenvolvido — proposta de escopo

1. Configuração do destino WhatsApp e das relações entre organizações/contas.
2. Encaminhamento por link/CTA e interpretação assistida de telefone voluntariamente
   informado no comentário, conforme o fluxo que as partes escolherem.
3. Ponte autenticada entre aplicações, com evento, contexto, idempotência e erros.
4. Registro mínimo de oportunidade e atribuição à campanha/produto de origem.
5. Continuidade do contexto quando a mensagem chegar ao WhatsApp da empresa.
6. Atendimento natural: agrupamento de fragmentos, correção, cancelamento,
   mudança de assunto, respostas em partes e controle de repetição.
7. Agente explícito, tom da empresa e respostas fundamentadas em conteúdo aprovado.
8. Atendimento humano, feedback de respostas e acompanhamento simples de lacunas.
9. Transcrição de áudio recebido e revisão básica de memórias; sem resposta por voz.
10. Controles de acesso, pausa, opt-out, limites e registro operacional.
11. Testes, homologação real autorizada, implantação, migrações e documentação.

## Jornada de referência

Comentário elegível → orientação/link para WhatsApp → interessado abre o contato
com mensagem sugerida → interessado envia → Orquestra recebe via Z-API → associa
a origem permitida → agente responde → humano assume quando necessário.

Clicar não envia a mensagem nem revela automaticamente o telefone do visitante.
Número em comentário não prova consentimento/titularidade. Um botão nativo em
mensagem Instagram precisa ser validado; o mínimo previsto é link clicável em
ponto homologado. A automação ocorre pelo backend/Z-API, sem controlar WhatsApp Web.

## Cronograma estimado

| Etapa | Prazo de referência |
|---|---|
| Definições, acessos e congelamento das versões | Semana 1 |
| Adequações Instagram e ponte | Semanas 2–3 |
| Contexto e atendimento textual natural | Semanas 4–6 |
| Atendimento humano e áudio | Semanas 7–8 |
| Robustez e homologação | Semanas 9–11 |
| Implantação e transferência | Semana 12 |

Referência de 60 dias úteis, com um desenvolvedor de dedicação principal e apoio
de produto/homologação. Faixa inicial de 10–14 semanas, a confirmar. Espera por
acessos, aprovações externas e mudanças de escopo deve ter tratamento contratual.

## Fora do recorte inicial

Reconstrução Instagram, faturamento SaaS, CRM completo, ERP/Calendar, login único,
robô de navegador, disparos indiscriminados, venda garantida, voz sintetizada,
imagem/vídeo, aprendizado sem revisão e ferramentas externas com escrita.
Infraestrutura, consumo de IA e Z-API são despesas de terceiros a discriminar.
Manutenção, SLA, garantia, preço e propriedade/licenciamento precisam ser acordados.

## Antes de fechar

Confirmar quem inicia a conversa, significado do telefone no comentário, local
do botão/link, inclusão integral de áudio/humano, quantidade de contas/empresas,
volume e limites de uso, equipe, data inicial, aceite, orçamento de serviços e
responsabilidades sobre ativos e dados. O escopo detalhado tem os critérios E01–E12
e marcos M1–M6 para anexar à minuta.
