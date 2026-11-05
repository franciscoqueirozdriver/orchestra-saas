# Código proposto, sem integração

`politicas_conversa.py` demonstra regras puras de prioridade de comandos, limite
na clarificação, invalidação e divisão de texto. Não envia mensagens nem implementa
por si só o catálogo inteiro de intenções. Os valores de pausa são referências
históricas do A Mesa; devem ser ajustados com testes de experiência e latência.

Integração futura obrigatória:

- Resolver tenant no backend e não aceitar tenant arbitrário do classificador.
- Handoff retorna resultado real (`queued`, `unavailable`) antes de gerar promessa.
- Command routing semântico deve preservar texto residual de negação/correção.
- Atualizar revisão/epoch e cancelar partes em transação; não incrementar revisão
  por mensagem outbound. Revalidar também policy, instância, consentimento e agente.
- Dispatcher usa lease/claim e serialização por conversa. Um claim expirado em
  `dispatching` não autoriza reenvio: estado ambíguo exige reconciliação.
- Presence só quando suportada/validada no contrato Z-API atual, sem logar URLs com
  token. Nenhum endpoint externo novo está homologado por esta documentação.
- Cache Redis é auxiliar; persistência no banco é a fonte de verdade. Não portar
  fallback in-process de debounce como mecanismo distribuído de produção.
- Áudio: HTTPS público validado em cada salto, sem redirecionamento livre, limite
  de tamanho/duração/tempo e MIME real; cifrar localizador temporário e removê-lo
  ao expirar. Minimizador atual do webhook precisa mudar de forma controlada.
- Fallback de provedores precisa adaptar as diferenças Chat Completions/Responses
  e tool calling; não basta trocar a URL. Nunca reenviar ação externa já executada.

Para verificar somente este protótipo: `python3 validacao/verificar_prototipo.py`
a partir da pasta de intenções. Não exige pacotes do backend.
