# Prompts e Resultados Relevantes

Somente prompts que levaram a decisões ou mudanças relevantes, junto com resumo da resposta e como foi verificada. Não arquivar conversas inteiras por padrão.

## Modelo por arquivo

```
# Prompt — <assunto curto>

Data:
Agente/modelo:
Contexto lido:
SHA de entrada:

Prompt:
<texto completo do prompt enviado>

Resultado:
<resumo do que o agente devolveu>

Como foi verificado:
<comando, teste, ou ambiente usado para confirmar>

Erros encontrados:
<erro 1>
<erro 2>

Decisões tomadas:
<decisão 1>

Arquivos alterados:
<caminho 1>
<caminho 2>

SHA de saída:
```

## Regras

- Sanitizar antes de gravar: não incluir chaves, tokens, `.env`, payloads reais, dados de clientes ou conteúdo de conversas.
- Usar para evitar reenviar o mesmo prompt sem saber o resultado anterior.
- Referenciar este arquivo em `CONTEXTO.md` quando relevante.
