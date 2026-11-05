# Base técnica para contrato — integração Instagram e atendimento WhatsApp

**Data:** 04/11/2026. **Finalidade:** fornecer informações verificáveis para elaboração do contrato de desenvolvimento, anexos de escopo, entregáveis e cronograma. Este documento descreve o produto e propõe um recorte de contratação; não fixa preço, partes, condições comerciais ou prazo juridicamente acordado.

## 1. Objeto pretendido

Adequar o sistema Instagram já existente e integrá-lo ao Orquestra para transformar interações de potenciais clientes no Instagram em oportunidades de atendimento pelo WhatsApp, com identificação de origem, histórico e atendimento automatizado em linguagem natural, conforme configurações de cada empresa.

O sistema Instagram não será reconstruído. Receberá as alterações necessárias para encaminhamento e rastreabilidade. O Orquestra será a base do atendimento por WhatsApp e receberá evolução conversacional inspirada no código do projeto A Mesa, adaptada à arquitetura multiempresa.

Descrição resumida sugerida para o objeto técnico:

> Desenvolvimento e integração de funcionalidades de encaminhamento de interessados originados em comentários e campanhas do Instagram para atendimento via WhatsApp, mediante adequações na plataforma Instagram existente e evolução da plataforma Orquestra, compreendendo identificação de origem, registro de oportunidades, continuidade de contexto, configuração do atendente virtual, atendimento humano, testes, implantação e documentação, dentro dos limites do anexo de escopo.

## 2. Fontes e limites deste levantamento

| Projeto | Local/revisão de referência | Papel |
|---|---|---|
| Instagram Link / MySalesAgent | `/home/Alessandra/Documentos/instagram-link`; HEAD `fd3ffd3`, com numerosas alterações locais não commitadas | Origem dos comentários, campanhas e encaminhamento |
| Orquestra | `/home/Alessandra/Documentos/orchestra-saas`; HEAD `f6d0e2a` | Atendimento WhatsApp multiempresa |
| A Mesa | Referências históricas do pacote `docs/intencoes/atendimento-natural-a-mesa/` | Fonte de conceitos e código para adaptação conversacional |

Revisão baseada em arquivos locais e documentação operacional existente. Não foi feita nova consulta a produção, novas mensagens reais ou auditoria de contas externas nesta sessão. O contratante informa que o Instagram já funciona. O handoff de 03/11 registra painel publicado em `mysalesagent.tech`, com envios pausados naquela ocasião; disponibilidade de telas não comprova que campanhas estejam liberadas hoje.

Antes de assinar, congelar em tag/commit a versão de cada aplicação, incluindo as alterações locais do Instagram que efetivamente serão entregues como preexistentes. A lista abaixo separa código existente, evidência anterior e trabalho futuro; não transformar pendência de homologação em entrega concluída.

## 3. O que já foi desenvolvido — patrimônio técnico preexistente

### 3.1 Sistema Instagram

Existem código e interfaces para:

- Autenticação e autorização administrativa, organizações e controle de acesso.
- Conexão de contas profissionais Instagram via OAuth e armazenamento cifrado de tokens.
- Recepção de webhooks com verificação de assinatura e persistência de eventos/comentários.
- Cadastro de produtos e links, associação de campanhas a publicações e regras por palavras/gatilhos.
- Preparação e envio de resposta privada ao comentário, respostas públicas e histórico de operação.
- Fila persistente, controles de pausa em camadas, limites, proteção contra reenvio e registro de resultado incerto.
- Painel de contas, publicações, campanhas, catálogo, resultados e controles de operação.
- Recursos adicionais de links, relatórios, ofertas e integrações Shopee, que já pertencem ao projeto existente e não compõem a nova integração WhatsApp por consequência automática.
- Código local de continuação de links após resposta em direct; isso não deve ser confundido com atendimento WhatsApp ou com botões homologados.

**Evidências consultadas:** `apps/api/main.py`, `apps/api/accounts.py`, `apps/api/catalog.py`, `apps/worker/dispatch.py`, `packages/domain/webhook_comments.py`, `packages/domain/link_delivery.py`, `packages/meta/private_reply.py`, `packages/meta/direct_message.py`, migrations existentes e `docs/HANDOFF.md`.

**Limites relevantes:** a documentação registra homologações externas pendentes e pausas operacionais. O handoff de 02/11 informa botões desligados. Não consta neste levantamento uma ponte implementada com o Orquestra, nem identificação automática do telefone WhatsApp de quem comenta.

### 3.2 Orquestra

Já implementado no código:

- API FastAPI, painel web, login, administrador da plataforma e cadastro/seleção de empresas.
- Separação lógica por empresa, com autorização e consultas filtradas no backend.
- Cadastro de agentes com nome, descrição, instruções e controle de auto-resposta.
- Cadastro de instâncias Z-API, consulta de conexão, configuração de webhook e envio manual de texto.
- Recepção de mensagens, identificação de conversa, histórico, fila Celery/Redis e deduplicação de callbacks.
- Geração de respostas de texto por provedor configurado: Groq, xAI ou endpoint compatível com OpenAI.
- Histórico recente e janela de agrupamento de mensagens, com verificação de revisão antes do envio.
- Base de conhecimento com importação de documentos, embeddings de 1.536 dimensões e recuperação por empresa.
- Cifra de credenciais, bootstrap do administrador, migrações, contêineres Docker, proxy Caddy/HTTPS e scripts de backup/restauração.
- Correção da exibição de erros nos formulários e tratamento de slug duplicado, no commit `f6d0e2a`.

**Evidência operacional anterior:** o usuário mostrou implantação na VPS Hostinger, serviços iniciados, worker respondendo e `https://app.salex.tech/health` retornando sucesso. Nas sessões anteriores, 20 testes automatizados passaram e houve teste isolado de backup/restauração. Esses fatos não constituem homologação completa de atendimento real, vendas, áudio ou integração Instagram–WhatsApp.

**Limites:** não há ponte Instagram–WhatsApp; não há CRM completo; áudio, tomada de atendimento humano, seleção refinada de agente, gestão de memória e apresentação humanizada avançada ainda precisam de implementação. O cadastro de vários agentes hoje seleciona o primeiro elegível no fluxo automático. O simples cadastro de um agente não o transforma em equipe multiagente.

### 3.3 Trabalho preparatório realizado

Foi criado o pacote `docs/intencoes/atendimento-natural-a-mesa/`, com 16 capacidades de evolução, snapshots históricos sanitizados, protótipo Python, três drafts SQL, cenários de aceitação e plano de implantação/reversão.

Esse pacote é especificação e referência. Seus SQL não foram aplicados e seus exemplos não estão integrados ao runtime. Não descrevê-lo no contrato como funcionalidade pronta.

## 4. Jornada comercial que será desenvolvida

### 4.1 Origem por comentário

1. Interessado comenta em publicação/campanha monitorada pelo sistema Instagram existente.
2. O sistema aplica a elegibilidade e registra o contexto da campanha, produto e comentário.
3. Quando existir número informado voluntariamente no comentário, a adequação identifica o candidato a telefone, normaliza e sinaliza ambiguidades. Um número escrito não prova titularidade nem autorização para contato automático.
4. O interessado recebe ou encontra uma orientação/link para continuar no WhatsApp, no formato permitido e homologado para a conta e a operação.
5. A ponte registra a oportunidade e o contexto; o atendimento é iniciado conforme a opção de contato contratada e as regras operacionais aprovadas.

O escopo não promete descobrir um número que o Instagram não forneça. Não haverá scraping, adivinhação ou associação por nome de usuário.

### 4.2 Origem por botão ou link

1. Em ponto definido do fluxo Instagram ou em página intermediária, oferecer ação de continuar no WhatsApp.
2. Abrir o contato WhatsApp da empresa com mensagem sugerida e referência de origem.
3. A pessoa confirma o envio da mensagem no WhatsApp.
4. O Orquestra recebe o inbound pela Z-API e associa a referência ao contexto autorizado.
5. O agente responde conforme a empresa, produto/campanha e base de conhecimento.

**Distinção necessária:** abrir WhatsApp Web/app não é enviar mensagem. O site não recebe automaticamente o telefone do visitante nem deve acessar a sessão pessoal do navegador. No computador, pode ser usada URL compatível com WhatsApp Web; no celular, link de abertura compatível com o aplicativo. Sessão, aplicativo e comportamento do dispositivo são dependências do usuário.

A automação do atendimento continua no backend/Z-API. Não integra este escopo automatizar a interface de WhatsApp Web, ler cookies/sessões ou controlar o navegador do cliente.

### 4.3 Ponto a fechar antes da implementação

A expressão “comentário com número do WhatsApp” pode significar o telefone do interessado no comentário ou o número comercial apresentado ao interessado. O contrato deve registrar qual dos casos vale, podendo incluir ambos com fluxos distintos.

**Premissa usada no cronograma:** encaminhamento iniciado pelo interessado via link/mensagem e captura assistida de telefone informado voluntariamente. Primeiro contato automático para qualquer número extraído de comentário é escopo adicional a validar, não comportamento presumido.

Botão nativo dentro de resposta privada do Instagram não está garantido neste recorte. O entregável mínimo é link clicável no ponto homologado; se botão nativo for obrigatório, a aprovação técnica desse formato é um gate anterior ao prazo fechado. Não confundir botão do painel/landing page com botão de mensagem suportado pela Meta.

## 5. Escopo novo proposto para contratação

| ID | Entrega | Conteúdo verificável | Aceite mínimo |
|---|---|---|---|
| E01 | Definição e congelamento das bases | Inventário, fluxos aprovados, mapeamento de contas/empresas, versões preexistentes e ambiente de teste | Documento aprovado com jornada e limites, sem recontratar o Instagram inteiro |
| E02 | Adequações no Instagram | Configurar destino WhatsApp por organização/conta/campanha; link/CTA, identificação opcional de telefone no texto, contexto de origem e prévia | Operador configura sem editar código; comentário elegível gera uma oportunidade sem expor dados de outra conta |
| E03 | Ponte de integração | Endpoint autenticado, contrato de evento, idempotência, retentativas locais seguras, rastreabilidade e referência temporária | Mesmo evento repetido não cria duplicatas; integração não depende de bancos compartilhados |
| E04 | Oportunidades e atribuição | Registro mínimo de lead, canal, campanha, produto, referência e estado de encaminhamento/conversa | Ver origem e situação; clique é distinguido de mensagem recebida |
| E05 | Continuidade de atendimento | Resolver tenant/instância/agente, vincular contexto ao inbound e usar o contexto na resposta | Mensagem recebida inicia conversa na empresa correta, sem inferir identidade Instagram pelo telefone |
| E06 | Conversação natural | Debounce contextual, cancelamento, correção do pedido, mudança de assunto, retomada, pausa/presença opcional, bolhas ordenadas e controle de repetição | Corpus de conversas aprovado; interrupção impede partes obsoletas e clarificação não entra em loop |
| E07 | Configuração do agente e conhecimento | Agente explícito por instância/conversa, tom por empresa, documentos e política de resposta baseada em evidência | Alteração de configuração refletida em conversa nova/teste; bot não inventa preço/disponibilidade sem fonte |
| E08 | Atendimento humano e qualidade | Assumir/retomar, resposta humana registrada, feedback de erro e fila simples de lacunas | IA respeita takeover; encaminhamento tem registro real; correções não viram memória aprovada automaticamente |
| E09 | Áudio recebido e contexto | Transcrição de áudio, tratamento de falha, vínculo ao turno, revisão/aprovação básica de memórias | Áudio de teste é transcrito e respondido; falha pede texto; não inclui resposta por voz |
| E10 | Segurança e operação da integração | Credenciais cifradas, autorização, opt-out, limites, pausa operacional, auditoria minimizada e proteção de referências | Eventos inválidos e cruzamento de empresas rejeitados; pausa bloqueia novos efeitos |
| E11 | Testes e homologação | Unitários, integração, concorrência, falhas externas e jornada real autorizada com contas/números de teste | Evidência de Instagram → encaminhamento → inbound WhatsApp → resposta; aceite externo separado de entrega |
| E12 | Implantação e transferência | Migrações versionadas, backup/restauração, publicação nos ambientes acordados, manual e orientação ao operador | Versão identificada, procedimento de reversão e demonstração de operação |

E01–E12 formam uma proposta técnica a confirmar, não uma declaração de que tudo já foi comercialmente contratado. O aproveitamento do A Mesa integra E06–E09 conforme o recorte acima. O pacote de intenções é mais amplo: ferramentas externas, ações de escrita e capacidades futuras não entram automaticamente neste escopo.

A entrega E04 é um acompanhamento de oportunidades e conversas, sem funil CRM completo, tarefas comerciais, previsão de receita ou integração ERP.

## 6. Arquitetura e mudanças técnicas previstas

### 6.1 Integração entre aplicações

Manter serviços independentes. O Instagram continua responsável por contas, comentários, produtos/campanhas e suas filas. O Orquestra continua responsável por conversas, agentes, conhecimento e WhatsApp.

Criar mapeamento explícito `organização/conta Instagram → empresa/instância/agente Orquestra`. IDs não são equivalentes entre bancos. A configuração de uma organização não concede acesso a outra.

Evento proposto: `instagram.lead_handoff.v1`. Campos mínimos: identificador único, versão, data, organização de origem, conta, campanha/publicação/comentário quando disponíveis, referência de produto, resumo autorizado, preferência de contato e motivo de encaminhamento. Telefone é opcional e exige tratamento apropriado. Credenciais nunca entram no evento.

A origem deve enviar evento com autenticação e proteção contra replay; o destino resolve o tenant pelo vínculo cadastrado, nunca apenas por um tenant arbitrário informado no JSON. Reconciliar evento recebido/pendente/falho. Detalhar política de retentativas e estados `unknown` antes de qualquer envio externo automático.

O link usa código opaco, curto e com expiração, sem telefone pessoal ou texto integral do comentário na URL pública. A referência pode ser repassada por terceiros: serve para atribuição/contexto, não como prova de identidade ou autorização para revelar dados privados. Se a pessoa apagar o código da mensagem, usar fallback e pedir contexto, sem associar por suposição.

### 6.2 Estrutura de dados e migrações a desenvolver

| Sistema | Mudanças previstas |
|---|---|
| Instagram | Configuração do destino por organização/conta/campanha; fila de integração; eventos/referências de encaminhamento; evidência de origem; estado e erro sanitizado |
| Orquestra | Vínculos da origem, oportunidades e referências; associação a conversas; políticas e estado conversacional; agente atribuído; turnos; partes de outbox; feedback/qualidade; mídias/transcrição; revisão de memória |
| Ambos | Índices, unicidade/idempotência, retenção/exclusão e controle de autorização coerentes com cada banco |

Instagram usa runner próprio de migrações com checksum; Orquestra usa Alembic. As alterações terão migrações próprias em cada projeto. Não executar SQL Supabase do A Mesa no Orquestra. Revisar compatibilidade da migração inicial Orquestra, que usa metadados vivos, antes de novas revisões.

Os três drafts do pacote de intenções cobrem evolução conversacional, mas **não incluem ainda o schema da ponte Instagram, os leads e os vínculos entre aplicações**. Essa modelagem e seu código fazem parte do desenvolvimento futuro E02–E05.

### 6.3 Aproveitamento do A Mesa

Adaptar conceitos e código: pausas/presença, chunking, debounce contextual, cancelamento, proteção de mudança de assunto, contexto de turnos, revisão de saída, áudio, tomada humana e feedback. Testar contra os bugs históricos de gates repetitivos, negação que descarta o pedido e duplicação de resposta.

Não copiar cadastro de membros, relatórios pastorais, nomes/telefones, cultos, regras religiosas ou credenciais. Não prometer naturalidade apenas por usar determinado modelo: validar clareza, continuidade, correção e resolução do pedido em cenários acordados.

## 7. Cronograma estimado e marcos

**Estimativa de planejamento:** 12 semanas de trabalho, com faixa inicial de 10–14 semanas, para o recorte E01–E12. Referência de 60 dias úteis em semanas de cinco dias, sem datas fixas de início e término. Não é prazo já medido ou acordado.

Premissas: um desenvolvedor full stack com dedicação principal, acesso a responsável por produto e apoio pontual de homologação/operação; uma organização piloto, uma conta Instagram e uma instância WhatsApp para aceite de ponta a ponta, preservando a arquitetura multiempresa. Volume, carga e número de contas simultâneas devem ser quantificados antes de fechar o prazo. Uma pessoa em dedicação parcial exige reestimativa.

| Marco | Janela proposta | Dias úteis | Entregas e saída |
|---|---|---:|---|
| M1 — definição e baseline | Semana 1 | 5 | E01, fluxo do telefone/CTA definido, bases congeladas, acessos e roteiro de aceite |
| M2 — encaminhamento Instagram | Semanas 2–3 | 10 | E02–E03: configuração, CTA/link, referência, evento e ponte em teste |
| M3 — atendimento integrado | Semanas 4–6 | 15 | E04–E07: lead/contexto, agente explícito, fluxo textual natural e envio por partes |
| M4 — humano e áudio | Semanas 7–8 | 10 | E08–E09: takeover, resposta humana, feedback, áudio e memória revisada básica |
| M5 — robustez e aceite | Semanas 9–11 | 15 | E10–E11: controles, falhas, concorrência, regressões e homologação real autorizada |
| M6 — implantação e transferência | Semana 12 | 5 | E12: migrações, backup, implantação, demonstração e documentação |
| **Total de referência** | **12 semanas** | **60** | Entrega sujeita aos critérios e dependências definidos |

Segurança, privacidade e testes são trabalhados desde M1; M5 concentra a homologação final. Os marcos não autorizam deixar proteção de dados ou isolamento apenas para o fim.

Cada marco deve ter demonstração e registro de aceite/pendências. Prazo de resposta do contratante para avaliação, tratamento de bloqueios e eventuais pagamentos por marco são campos comerciais a definir. Rejeição por desvio do escopo acordado gera correção; funcionalidade nova exige avaliação de mudança.

Não estão incluídos nesses 60 dias os períodos de espera por aprovação/liberação de plataformas, compra de serviços, indisponibilidade de acesso ou decisões do contratante. O contrato deve definir como esses eventos afetam o cronograma; não presumir suspensão ilimitada nem atribuir automaticamente toda falha ao cliente.

## 8. Dependências e responsabilidades a registrar

### Contratante / responsável pelo produto

- Definir empresa, produtos/serviços, objetivos de atendimento, conteúdo aprovado e contatos responsáveis.
- Disponibilizar acesso apropriado aos projetos e contas, respeitando credenciais individuais e sem envio de senhas em documentos.
- Disponibilizar conta Instagram compatível, aplicativo/permissões necessários e instância/número WhatsApp/Z-API.
- Manter VPS, domínio/DNS e serviços externos necessários contratados.
- Informar política de contato, retenção, exclusão, finalidade dos dados e regras de encaminhamento.
- Fornecer números/contas de teste autorizados e operador humano para homologação.
- Avaliar entregas nos prazos comerciais definidos e decidir o fluxo em caso de ambiguidade.

### Desenvolvedor / contratada

- Entregar adequações, ponte e evolução do Orquestra no recorte acordado.
- Manter segregação de empresas e preservar funcionalidades preexistentes afetadas pela integração.
- Versionar código/schema, testar, registrar limitações e preparar implantação/reversão.
- Documentar configuração, operação, incidentes e serviços externos utilizados.
- Comunicar necessidade de mudança de escopo ou bloqueio técnico com evidência e alternativas.

### Serviços externos e despesas

Custos de VPS, domínio, Z-API, inferência/transcrição/embeddings, Meta quando aplicável e outros fornecedores são separados do preço de desenvolvimento, salvo acordo expresso. Não presumir chamadas gratuitas ou volume ilimitado. Estabilidade, aprovação e políticas dos fornecedores não são controladas pelo desenvolvedor; a integração deve tratar suas falhas de maneira prevista.

## 9. Limites e itens fora do escopo inicial

- Reconstrução completa da plataforma Instagram, redesign geral ou correção ilimitada de problemas legados não relacionados à integração.
- Migração total de autenticação, fusão dos bancos ou login único entre aplicações. Se desejado, orçar separadamente.
- Garantia de aprovação de aplicativo/permissões Meta, formato nativo de botão ou recuperação de conta bloqueada.
- Disparo indiscriminado para números de comentários, prospecção automatizada e descoberta de telefones não fornecidos.
- Robô de navegador, controle de WhatsApp Web pessoal e compartilhamento de sessão/cookies.
- Cobrança SaaS, assinatura, pagamento, faturamento e checkout.
- CRM/ERP/Calendar, ferramentas externas com efeitos de escrita, agendamentos comerciais e criação automática de pedidos.
- Respostas por voz, interpretação de imagens/vídeos e tratamento completo de mídia além do áudio recebido definido em E09.
- Aprendizado autônomo sem revisão, equipe multiagente, treinamento de modelo próprio e garantia de resposta indistinguível de pessoa.
- Garantia de venda, faturamento, conversão, aprovação em plataforma ou alcance orgânico.
- Atendimento humano prestado pela contratada e operação comercial contínua.
- Manutenção contínua, suporte com SLA, plantão, prazo de garantia e alterações após aceite, que precisam de condições próprias.
- Desenvolvimento adicional de Shopee; sua presença na base Instagram não amplia este escopo.

## 10. Critérios objetivos para aceite final

1. Configurar a origem Instagram e o destino WhatsApp por interface, com autorização e empresa correta.
2. Receber comentário de teste elegível e gerar uma única oportunidade/evento apesar de replay.
3. Apresentar link/CTA homologado; abrir WhatsApp no dispositivo compatível com mensagem sugerida.
4. Quando a pessoa enviar a mensagem, registrar inbound e recuperar o contexto da referência válida; sem referência, fallback explícito.
5. Atendente responder ao assunto/produto com conteúdo aprovado, sem misturar empresas ou dados de terceiros.
6. Conversa suportar fragmentação, correção, cancelamento e mudança de assunto sem loop nem envio obsoleto.
7. Operador assumir e retomar com histórico; IA respeitar suspensão e política de retomada.
8. Áudio de teste válido virar texto/contexto; erro resultar em aviso útil e sem alegação falsa de compreensão.
9. Credencial inválida, webhook adulterado, referência vencida, falha de provedor e indisponibilidade de fila terem tratamento documentado.
10. Registro diferenciar clique, mensagem recebida, aceite externo e entrega quando houver confirmação homologada.
11. Backup/restauração e implantação/reversão demonstrados em ambiente apropriado, sem apagar produção para testar.
12. Entregar código, migrações, instruções e lista das dependências/limitações nas versões acordadas.

Definir antes da assinatura: tamanho máximo/duração do áudio, formatos de documentos, volume de mensagens, quantidade de contas/empresas para teste, compatibilidade de navegadores, métricas de desempenho e janela de suporte. Não usar adjetivos como “instantâneo”, “ilimitado” ou “100% humano” no lugar desses limites.

## 11. Decisões pendentes para fechar o contrato

- Quem são contratante e contratada e quem possui os códigos/ativos preexistentes de cada projeto?
- Contratação inclui E01–E12 por inteiro ou somente a ponte e o atendimento textual inicial?
- O telefone no comentário é do interessado ou é o contato comercial? O primeiro contato será iniciado por quem?
- O botão exigido é nativo no Instagram, link no direct/comentário ou botão de página intermediária? Quais alternativas são aceitas?
- Haverá domínio/painel único ou dois painéis ligados? O cronograma considera dois sistemas independentes e ponte autenticada.
- Quantas organizações, contas Instagram e instâncias WhatsApp entram no piloto e na operação prevista?
- Quem assume a fila humana e em quais horários? Há capacidade real para prometer retorno?
- Qual provedor/modelo, orçamento de consumo e política de fallback/transcrição serão aprovados?
- Qual data de início, dedicação da equipe, preço, forma de pagamento e prazo de validação por marco?
- Quais regras comerciais de propriedade/licenciamento, uso de componentes do A Mesa, garantia, manutenção e suporte serão acordadas?

Esses campos devem ser levados à pessoa/IA que elaborará o instrumento. Não preencher com valores ou fatos inventados.

## 12. Instrução pronta para a IA que elaborará o contrato

> Utilize este documento como anexo técnico para preparar uma minuta de prestação de serviços de desenvolvimento e integração. Diferencie expressamente ativos preexistentes, adequações no Instagram e funcionalidades futuras do Orquestra. Use E01–E12 como proposta de escopo e M1–M6 como cronograma estimado a confirmar. Não descreva como entregue o que consta como planejado, nem imponha reconstrução do sistema Instagram existente. Não prometa que clique envia mensagem, que o telefone é fornecido pela Meta ou que o bot será indistinguível de humano. Marque campos comerciais, responsabilidades sobre dados e direitos dos componentes preexistentes para preenchimento e revisão pelas partes. Separe despesas de terceiros, aceite, mudanças de escopo, implantação, garantia e manutenção. Liste as decisões pendentes antes de transformar a estimativa de 12 semanas em prazo contratual fechado.
