# Plano para aprovação — atendimento natural no Orquestra

Status: E0–E5 aprovados pelo usuário em branch separada para testes. Merge/deploy não autorizados.
Preparado em 05/11/2026, sobre a linha local 328e2b0, que contém a integração f3a8140
mais a ingestão privada. Não altera a aplicação, schema, serviços ou fornecedores.

## Decisão proposta

Aprovar a adaptação seletiva das capacidades do A Mesa para o Orquestra, em vez de
importar a aplicação inteira. Primeiro melhorar o núcleo da conversa e a passagem
para uma pessoa; depois adicionar WaMe como segundo fornecedor. Manter contexto,
memória, consentimento, fila e regras de negócio independentes do transporte.

Base documental: INTENCOES.md, manifesto dos snapshots e validacao/CENARIOS.md.
Este plano detalha a próxima execução; não substitui o histórico nem promove os
SQL de migracoes-propostas à cadeia Alembic.

## Situação conferida e trabalho a reaproveitar

- Branch local conferida: feature/ingestao-privada-whatsapp, sem alterações antes
  deste planejamento. Integração recuperada e documentação permanecem preservadas.
- Há snapshots históricos do Mesa, protótipo Python e matriz C01–C16; são referências,
  não módulos já integrados. O histórico escolhido é dd19753; consultar também
  449fed5/ac23e89 e comparar com a versão atual antes de selecionar comportamentos.
- Nesta rodada foi conferido status do repositório Mesa, sem alterações pendentes;
  ainda não foi repetida a auditoria funcional do código atual e de todo o histórico.
  Isso é a primeira entrega da execução, não uma validação já concluída.
- Orquestra já tem atribuição de agente, revisão da conversa, separação do último
  inbound, janela de agrupamento, histórico limitado, RAG/memória, outbox, locks
  PostgreSQL, scheduler, políticas e contratos simulados de provedores. Ampliar e
  testar esses mecanismos, sem criar implementações concorrentes dos mesmos conceitos.
- Staging SQLite e transcrição offline da PR de ingestão são privados e separados.
  Não equivalem a áudio integrado ao atendimento nem a conhecimento aprovado na busca.
- Estado real de GitHub/PRs e ambiente publicado deverá ser reconferido no início.
  O código da VPS pode continuar diferente; nenhuma publicação é consequência deste plano.

## Primeira entrega a aprovar: núcleo conversacional

| Etapa | Trabalho e resultado verificável | Estimativa de esforço |
|---|---|---:|
| E0 — confirmar referências | Ler instruções do Mesa, comparar histórico/atual, mapear C01–C16 para o runtime atual, registrar o que reaproveitar/rejeitar; congelar baseline e diálogos sintéticos | 8–12 h |
| E1 — estabilizar turnos e interromper | Reutilizar debounce/revisões, definir teto de espera, tratar cancelar/opt-out/humano antes da IA; fechar takeover/resume com autorização e indicador no painel | 16–24 h |
| E2 — contexto e continuidade | Estado persistido e contexto com validade; tratar follow-up, correção, negação com novo pedido, mudança lateral de assunto e retomada sem loops; distinguir usuário/operador/fonte citada | 24–40 h |
| E3 — tom por cliente | Perfil configurável por empresa/agente: formalidade, concisão, vocabulário, emojis, limites e exemplos aprovados; guard de saída sem mutilar dados ou inventar fatos | 16–24 h |
| E4 — entrega em partes e fronteira do fornecedor | Persistir partes ordenadas, revalidar antes de cada envio, cancelar partes obsoletas, presença opcional sem bloquear texto; interface comum de transporte com Z-API preservada | 16–24 h |
| E5 — revisão e homologação interna | Painel mínimo de intervenção/estado, cenários integrados, testes de concorrência e migrations, comparação de diálogos e relatório de evidências/riscos | 12–20 h |
| **Total inicial estimado** | **Implementação local, testes e revisão; sem publicação/piloto real** | **92–144 h** |

Estimativas são faixas de engenharia, não prazo contratado nem promessa de execução
em tempo corrido. Com uma pessoa dedicada, representam aproximadamente 12–18 dias
de 8 h de esforço; reservar 3–5 semanas de calendário para revisões e ajustes. E0
confirma ou revisa a previsão antes dos blocos maiores. Aprovação não obriga ampliar
escopo se a auditoria revelar uma dependência material nova: registrar impacto e
apresentar ajuste antes de incorporar essa dependência.

E1 entra antes da entrega em partes: atender/cancelar com segurança é pré-condição.
E4 pode começar pela interface do transporte em paralelo lógico a E2/E3, mas o plano
não pressupõe trabalho de vários agentes nem execução concorrente no repositório.

## O que será reaproveitado do Mesa

| Capacidade | Tratamento no primeiro ciclo |
|---|---|
| C01 presença/pausa | Opcional, limitada por configuração/capacidade do fornecedor; sem demora artificial obrigatória |
| C02 divisão da resposta | Portar princípios e testes, adaptar à outbox durável com partes |
| C03 agrupamento | Ampliar a implementação existente; uma fonte de verdade para janela e revisão |
| C04 estado/assunto | Recuperar mecanismos úteis; eliminar gates repetitivos e matchers amplos |
| C05 contexto | Persistir intenção/argumentos quando necessários, com validade e evidência; sem fluxo gerencial da igreja |
| C06 cancelamento | Integrar à revisão e às partes; não prometer cancelar mensagem já aceita externamente |
| C07 humano | Assumir/retomar e enviar pelo fluxo autorizado, com autoria e estado visível |
| C08 perfil | Configuração por cliente/agente, sem nomes/telefones fixos nem identidade religiosa embutida |
| C09 saída | Preservar sentido e fatos; não impor gírias, perguntas finais ou emojis a toda resposta |
| C10 áudio | Fora do primeiro ciclo; depende de pipeline online e política de processamento próprios |
| C11 ferramentas | Fora do primeiro ciclo; não copiar cadastros, relatórios ou ações de negócio do Mesa |
| C12 fallback | Preservar o roteador existente e seus contratos; estender somente quando exigido por mudança comprovada |
| C13 correção/lacunas | Recuperação conversacional básica no núcleo; painel completo de qualidade em ciclo posterior |
| C14 memória | Usar a base existente com proveniência/validação de conteúdo utilizado; impedir promoção automática de histórico; CRUD avançado e publicação do acervo ficam separados |
| C15 operação | Preservar consentimento, limites e pausa global; não incluir campanhas novas neste ciclo |
| C16 avaliação | Casos sintéticos, regressões históricas e teste de isolamento em todas as etapas |

Se a auditoria da memória atual revelar uso de conteúdo sem aprovação/proveniência,
o primeiro ciclo deve impedir esse uso ou mantê-lo desabilitado por política. Não
se adia uma correção de segurança para entregar uma tela de memória mais tarde.

## Critérios de aceite

### Comportamento da conversa

Usar todos os cenários aplicáveis de validacao/CENARIOS.md, com fixtures fictícias.
Adicionar casos de mesmo diálogo com dois perfis de cliente e conteúdo factual igual.

- Fragmentos rápidos recebem uma resposta ao pedido completo; entrada contínua
  tem teto configurado sem perder mensagens. O valor do teto será definido em E0.
- Saudação não encobre pedido. “Não, quero outra coisa” preserva o novo pedido.
- Follow-up usa contexto válido; contexto expirado não vira suposição silenciosa.
- No máximo uma clarificação repetida por episódio; depois há saída segura e
  opção humana verdadeira. Não prometer atendente/fila indisponível.
- Correção vincula a pergunta/resposta anterior; o bot não reinicia um roteiro
  ignorando o que a pessoa acabou de explicar.
- Tom muda por perfil sem alterar preço, regra, permissão ou afirmação factual.
- Quando perguntado, o agente informa ser automatizado; não se passa por pessoa.
- Texto longo preserva itens/dados; nova entrada interrompe partes antigas ainda
  não enviadas. Presença que falha não impede o texto.

Testes determinísticos exigem aprovação integral. Qualidade subjetiva será revisada
em pelo menos 20 diálogos sintéticos com checklist de clareza, continuidade,
repetição e adequação ao tom. Registrar avaliador, versão/modelo e divergências;
nenhum caso crítico de fato inventado ou vazamento entre empresas pode ser aceito.
Não atribuir pontuação de “mais humano” antes dessa avaliação. Replays com modelo
real dependem de ambiente e autorização adequados; mocks não certificam qualidade.

### Segurança e consistência

- Duas empresas não compartilham perfil, contexto, memória, contatos ou credenciais.
- Replay, dois workers e scheduler concorrente não geram dois envios intencionais
  para o mesmo trabalho. Não prometer exactly-once no provedor externo.
- Takeover/cancelamento/opt-out durante inferência ou intervalo entre partes
  invalidam o que ainda não foi enviado; efeito externo já iniciado é registrado.
- Timeout ambíguo continua unknown, sem reenvio automático por outro fornecedor.
- Mudança de perfil/agente/política invalida geração antiga conforme regra definida.
- Migrations novas testadas em banco descartável: instalação limpa, upgrade da
  baseline, dados sintéticos preservados e compatibilidade para reversão de código.
- Falhas de fila/gateway ficam visíveis sem registrar conversa privada, segredo ou
  URL de mídia. Estados e métricas operacionais não expõem conteúdo pessoal.

## Entrega técnica, banco e documentação

- Implementar em Python sobre modelos/filas atuais. TypeScript e SQL do Mesa
  servem como referência de comportamento, não para copiar dependências da aplicação.
- Reconciliar drafts com Alembic até 0004 antes de gerar revisões novas. Nenhuma
  mudança histórica, create_all mutável, coluna duplicada ou backfill de consentimento.
- Preferir schema aditivo e recursos desligados por padrão. Estruturas prováveis:
  perfil versionado, contexto/turnos, autoria de intervenção e partes da outbox.
  Modelo final e constraints por empresa são entregas revisáveis de E0/E1/E4.
- Configuração no painel para administradores autorizados; operadores recebem
  permissões explícitas para assumir/responder/retomar, sem administrar credenciais.
- Commits organizados, testes e PR por bloco coerente; preservar a integração,
  ingestão e documentos existentes. Não incluir fontes privadas nem alterar o Mesa.
- Registrar em docs/consolidacao o que foi implementado, apenas simulado, revisado
  por pessoas, homologado externamente e o que permanece pendente.

## Etapas posteriores, com aprovação própria

1. **WaMe como segundo fornecedor:** implementar adaptador e escolha por conexão,
   callbacks, estados, credenciais e piloto com número separado. Manter Z-API.
   Estimativa anterior de 48–80 h é referência; reestimar após E4 e descontar a
   separação do transporte já feita, evitando cobrar/contar o mesmo trabalho duas vezes.
   Identificadores incluem conexão/fornecedor; sem fallback automático de envio.
2. **Intervenção MCP:** “assumir → pausar → responder → registrar → retomar” por
   ferramenta ligada ao Orquestra. MCP direto da WaMe não garante pausa prévia no
   Orquestra e precisa de homologação própria. Acesso externo a mensagens não está
   autorizado pela aprovação deste plano.
3. **Áudio no atendimento e ferramentas:** download seguro, limites/retentativas,
   processamento autorizado e integração ao turno; ferramentas somente leitura
   primeiro. Escrita exige idempotência, permissão e confirmação quando aplicável.
   Ingestão offline de arquivos não deve ser convertida em serviço de produção sem
   avaliar recursos, privacidade, retenção e política de uso de provedores.
4. **Conhecimento e melhoria contínua:** confirmar empresa da amostra, revisão por
   escuta, anonimização humana e validade factual; só depois planejar lote maior e
   publicação separada na busca. Painel de lacunas, memórias e revisão avançada.

Não incluir Instagram novo, CRM, faturamento, clonagem de voz, visão de vídeo,
campanhas, arquitetura multiagente ou importação integral do Mesa nesta aprovação.

## Publicação e reversão

Desenvolvimento não depende de publicar para começar. Antes de qualquer piloto,
revisar as PRs pendentes, reconferir os três ambientes e fazer a primeira publicação
controlada por SHA, com envio suspenso, mediante autorização correspondente.

Para o novo núcleo: schema aditivo → código com recursos desligados → validação
operacional → piloto por empresa com destinatários autorizados → avaliação → expansão.
Usar scripts/release.py e o runbook, recusar VPS com alterações pendentes, preservar
backups privados e imagens/configuração anteriores. Homologar os sites que compartilham
Caddy. Não usar o banco de produção para testes ou migrations experimentais.

Reversão inicial por flag/empresa. Antes de retomar o código anterior, reconciliar
partes enviadas/dispatching/unknown para impedir repetição. Preservar registros e
schema aditivo; downgrade destrutivo não é mecanismo automático de reversão.

## O que a aprovação autoriza

Aprovar **E0–E5 do núcleo conversacional** autoriza leitura do Mesa/histórico,
desenvolvimento local, testes isolados, commits e publicação de branches/PRs para
revisão. Não autoriza merge, deploy, migrations de produção, mensagens reais,
conexão MCP a contas reais, transferência de conversas a IA ou lote integral do
acervo. WaMe, MCP e demais etapas posteriores serão propostas separadamente.

Na execução, a primeira devolutiva será a matriz de E0 com decisões de reaproveitamento,
riscos encontrados e confirmação da estimativa; depois seguem os blocos na ordem
aprovada. Progresso e limites da execução em docs/consolidacao/2026-11-05-nucleo-mesa.md.
