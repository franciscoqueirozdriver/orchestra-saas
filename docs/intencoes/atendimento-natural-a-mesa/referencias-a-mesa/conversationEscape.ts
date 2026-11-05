// Heurísticas para não prender o usuário no fluxo de roteiro quando a mensagem
// é claramente outra coisa (pergunta gerencial, culto, saudação, etc.).

export function mensagemPareceInteracaoRoteiro(textoNorm: string, textoRaw: string): boolean {
  const t = textoRaw.trim();
  if (t.length > 250) return true;

  if (/\b(PDF|PUBLIC|PUBLICAR|RASCUNHO|REENV|MANDA O|ENVIA O|NAO PUBLIC|VER O PDF)\b/.test(textoNorm)) {
    return true;
  }
  if (/^(SIM|S|NAO|N|OK|PODE|CLARO|BORA|VAMOS|CANCELAR?|CANCELA)($|\s|[!.?,])/i.test(t)) {
    return true;
  }
  if (/\b(CURTI|AJUST|DEIXA FORA|SEM ESSA|PREFIRO|ASSIM ESTA|TA BOM|ESTA BOM|PODE SER|PERFEITO|ESTA PERFEITO|ESTA OTIMO|TA PERFEITO)\b/.test(textoNorm)) {
    return true;
  }
  return false;
}

/**
 * Onde fica a sede da igreja (consulta de local) — distinto de:
 * - atualizar endereço no cadastro de membro ("meu endereço no cadastro da igreja")
 * - endereço da mesa, etc.
 */
export function pareceConsultaEnderecoIgreja(textoNorm: string): boolean {
  // Cadastro/dados pessoais do membro — "cadastro da igreja" = registro, não prédio
  if (/\b(MEU|MINHA|MEUS|MINHAS)\b/.test(textoNorm)) return false;
  if (/\b(CADASTRO|CADASTR|MEMBRO|INSCRIC|REGISTR)\b/.test(textoNorm)) return false;
  if (/\b(ATUALIZ|ALTER|MUDAR|TROCAR|CORRIGIR|COMPLETAR|REVISAR)\b/.test(textoNorm)) return false;

  // Pedido de ação sem pergunta de local ("preciso de ajuda com endereço" ≠ sede)
  if (/\b(PRECISO|PRECISAMOS|QUERO|GOSTARIA)\b/.test(textoNorm) &&
    !/\b(QUAL|ONDE|LOCAL|SABER|SABE|INFORM|ME DIZ|ME FALA)\b/.test(textoNorm)) {
    return false;
  }

  // Pergunta explícita sobre local da sede
  if (/\b(QUAL|ONDE|LOCAL|SABER|SABE)\b/.test(textoNorm) &&
    /\b(ENDERECO|FICA|FICAM|FICA A|FICAR)\b/.test(textoNorm) &&
    /\b(IGREJA|SEDE|CONGREGACAO|CULTO)\b/.test(textoNorm)) {
    return true;
  }
  if (/\b(ENDERECO|LOCAL|ONDE FICA|ONDE E|ONDE EH)\b/.test(textoNorm) &&
    /\b(IGREJA|SEDE|CONGREGACAO|CULTO|A MESA)\b/.test(textoNorm)) {
    return true;
  }
  return false;
}

export function mensagemParecePerguntaForaDoRoteiro(textoNorm: string, textoRaw: string): boolean {
  if (mensagemPareceInteracaoRoteiro(textoNorm, textoRaw)) return false;
  if (pareceAssuntoCadastroPessoal(textoNorm)) return true;
  if (textoRaw.includes('?')) return true;
  if (/\b(QUANTOS|QUANTAS|QTD|PESSOAS|MEMBROS|MESAS|CULTOS|CULTO|HORARIO|ENDERECO|BAIRRO|VISITANTES|LIDERES|CADASTR|PROXIMO EVENTO|MINHA MESA|FREQUEN|PRESENC|PRESENÇ|FALT|AUSENT|CHECK.?IN|BRIEFING)\b/.test(textoNorm)) {
    return true;
  }
  if (/^(OI|OLA|BOM DIA|BOA TARDE|BOA NOITE|OBRIGAD)/.test(textoNorm)) return true;
  return false;
}

/** Pedido explícito de escrita/revisão — não é contagem gerencial. */
export function parecePedidoAtualizacaoCadastral(textoNorm: string): boolean {
  if (
    /\b(QUANTOS|QUANTAS|LISTA|TOTAL|NUMERO)\b/.test(textoNorm) &&
    /\bCADASTRAD/.test(textoNorm) &&
    !/\b(ATUALIZ|CORRIGIR|MUDAR|ALTERAR|COMPLETAR|REVISAR)\b/.test(textoNorm)
  ) {
    return false;
  }
  if (/\b(ATUALIZ|CORRIGIR|COMPLETAR|MUDAR|ALTERAR|REVISAR|TROCAR)\b/.test(textoNorm) &&
    /\b(CADASTRO|DADOS|ENDERECO|TELEFONE|CEP|BAIRRO|ESTADO CIVIL)\b/.test(textoNorm)) {
    return true;
  }
  if (/\b(QUERO|PRECISO|GOSTARIA|COMO|PODE)\b/.test(textoNorm) && /\b(ATUALIZ|CADASTRO)\b/.test(textoNorm)) {
    return true;
  }
  return false;
}

/** Líder quer alterar cadastro de outras pessoas — painel, não fluxo self-serve WhatsApp. */
export function parecePedidoAtualizacaoCadastroMembros(textoNorm: string): boolean {
  if (!parecePedidoAtualizacaoCadastral(textoNorm) && !/\b(CADASTRO)\b/.test(textoNorm)) return false;
  return /\b(MEMBROS|OUTRAS PESSOAS|PLATAFORMA|PESSOAS CADASTRADAS|CADASTRO DE MEMBROS|OUTRO MEMBRO|DE OUTRAS|DOS MEMBROS|DE MEMBROS)\b/.test(textoNorm);
}

/**
 * A pessoa está falando do cadastro/dados DELA — consulta ou atualização.
 * Prioridade pela frase; não misturar com estatísticas ("quantos cadastrados").
 */
export function pareceAssuntoCadastroPessoal(textoNorm: string): boolean {
  if (parecePedidoAtualizacaoCadastroMembros(textoNorm)) return false;

  // Mesa mais próxima do endereço/casa — consulta de localização, não cadastro pessoal
  if (
    /\b(MESA|MESAS)\b/.test(textoNorm) &&
    /\b(PROXIMA|PRÓXIMA|PROXIMO|PRÓXIMO|PERTO|PROXIMIDADE)\b/.test(textoNorm)
  ) {
    return false;
  }

  // Consulta gerencial de listas (cadastro incompleto, sem mesa…) — não fluxo pessoal
  if (
    /\b(CADASTRO INCOMPLETO|CADASTROS INCOMPLETOS|PENDENTES DE CADASTRO|SEM MESA|NOVOS CADASTROS|SEM DATA DE NASCIMENTO|SEM DATA NASCIMENTO)\b/.test(textoNorm) &&
    !/\b(MEU|MINHA|MEUS|MINHAS)\b/.test(textoNorm)
  ) {
    return false;
  }

  if (
    /\b(QUANTOS|QUANTAS|LISTA|TOTAL|NUMERO)\b/.test(textoNorm) &&
    /\b(CADASTRAD|PESSOAS|MEMBROS)\b/.test(textoNorm) &&
    !/\b(MEU|MINHA|MEUS|MINHAS)\b/.test(textoNorm)
  ) {
    return false;
  }

  // Contagem/listagem gerencial no cadastro (ex.: "quantas Sofia temos no cadastro?")
  if (
    /\b(QUANTOS|QUANTAS|QUEM|QUAIS|LISTA|LISTAR|NUMERO|TOTAL)\b/.test(textoNorm) &&
    /\b(CADASTRO|CADASTRAD)\b/.test(textoNorm) &&
    !/\b(MEU|MINHA|MEUS|MINHAS)\b/.test(textoNorm)
  ) {
    return false;
  }

  // Líder de mesa consultando membros (não cadastro pessoal)
  if (/\bMINHA MESA\b/.test(textoNorm) && /\b(MEMBROS|MEMBRO|MORAM|BAIRRO)\b/.test(textoNorm)) {
    return false;
  }

  if (parecePedidoAtualizacaoCadastral(textoNorm)) return true;

  if (/\b(MEU|MINHA|MEUS|MINHAS)\b/.test(textoNorm) && /\b(CADASTRO|DADOS|INFORMACOES)\b/.test(textoNorm)) {
    return true;
  }

  if (/\b(CONFERE|VERIFICA|VERIFICAR|CHECA|CONSULTA|REVISA|REVISAR)\b/.test(textoNorm) &&
    /\b(CADASTRO|DADOS)\b/.test(textoNorm)) {
    return true;
  }

  if (/\bCADASTRO\b/.test(textoNorm) &&
    /\b(COMPLETO|ATUALIZAD|PENDENTE|FALTA|INCOMPLETO|CERTO|CORRETO|OK|ESTA|ESTAO)\b/.test(textoNorm)) {
    return true;
  }

  if (/\b(MEU|MINHA|MEUS|MINHAS)\b/.test(textoNorm) &&
    /\b(SOBRE|DO|NO|DA)\b/.test(textoNorm) &&
    /\bCADASTRO\b/.test(textoNorm)) {
    return true;
  }

  if (/\b(MEU|MINHA)\b/.test(textoNorm) &&
    /\b(TELEFONE|ENDERECO|CEP|BAIRRO|NASCIMENTO|ESTADO CIVIL|DATA DE NASCIMENTO)\b/.test(textoNorm)) {
    return true;
  }

  if (/\b(MUDAR|ALTERAR|TROCAR)\b/.test(textoNorm) &&
    /\b(TELEFONE|ENDERECO|CEP|BAIRRO|NASCIMENTO|ESTADO CIVIL|NUMERO|COMPLEMENTO)\b/.test(textoNorm) &&
    !/\b(OUTRO|MEMBRO|PESSOA)\b/.test(textoNorm)) {
    return true;
  }

  if (/\b(NUMERO|COMPLEMENTO|APTO|APARTAMENTO|BLOCO)\b/.test(textoNorm) &&
    /\b(ENDERECO|ENDEREC|MORADIA|CASA|RESIDENCIA)\b/.test(textoNorm)) {
    return true;
  }

  return false;
}

export function pareceConsultaStatusCadastroPessoal(textoNorm: string): boolean {
  if (!pareceAssuntoCadastroPessoal(textoNorm)) return false;
  if (parecePedidoAtualizacaoCadastral(textoNorm)) return false;
  return /\b(CONFERE|VERIFICA|VERIFICAR|CHECA|COMO ESTA|TA CERTO|ESTA CERTO|COMPLETO|ATUALIZAD|PENDENTE|FALTA|INCOMPLETO|MEU CADASTRO|MINHA CADASTRO|DADOS)\b/.test(textoNorm) ||
    (/\bCADASTRO\b/.test(textoNorm) && textoNorm.includes('?'));
}
