// Gate de retomada quando há conversa ativa ociosa (sem interação por X minutos).

export const CONVERSA_IDLE_MINUTES = Number(
  Deno.env.get('WHATSAPP_CONVERSA_IDLE_MINUTES') || '30',
);

export interface ConversaEstadoRow {
  id: string;
  fluxo_ativo: string;
  etapa_atual: string;
  contexto_json?: Record<string, unknown> | null;
  atualizado_em?: string | null;
}

export function minutosDesde(iso: string | null | undefined, referencia = Date.now()): number {
  if (!iso) return Infinity;
  const ms = referencia - new Date(iso).getTime();
  if (!Number.isFinite(ms) || ms < 0) return 0;
  return Math.floor(ms / 60_000);
}

export function conversaEstaOciosa(
  conversa: ConversaEstadoRow,
  limiteMinutos = CONVERSA_IDLE_MINUTES,
): boolean {
  if (conversa.etapa_atual === 'aguardando_retomada_ociosa') return false;
  return minutosDesde(conversa.atualizado_em) >= limiteMinutos;
}

export function descreverTemaConversa(conversa: ConversaEstadoRow): string {
  const ctx = (conversa.contexto_json || {}) as Record<string, unknown>;
  const fluxo = conversa.fluxo_ativo;
  const etapa = conversa.etapa_atual;
  const campo = typeof ctx.campo_atual === 'string' ? ctx.campo_atual : null;

  if (fluxo === 'roteiro_estudo') {
    if (etapa === 'aguardando_confirmacao') return 'publicação do roteiro de estudo';
    if (etapa === 'processando') return 'processamento do roteiro de estudo';
    if (etapa === 'aguardando_validacao_campo') return 'revisão do roteiro de estudo';
    return 'roteiro de estudo';
  }

  if (fluxo === 'relatorios') {
    if (etapa === 'confirmando_relatorio') return 'o relatório que a gente estava combinando';
    return 'relatórios';
  }

  if (fluxo === 'interpretacao_capacidade') {
    return 'o que eu tinha entendido do seu pedido';
  }

  if (fluxo === 'atualizacao_cadastral') {
    if (etapa === 'escolhendo_campo') return 'atualização do seu cadastro';
    if (etapa === 'perguntando_campo' && campo) {
      const labels: Record<string, string> = {
        endereco: 'endereço no cadastro',
        bairro: 'bairro no cadastro',
        cep: 'CEP no cadastro',
        telefone: 'telefone no cadastro',
        estado_civil: 'estado civil no cadastro',
        data_nascimento: 'data de nascimento no cadastro',
      };
      return `atualização do ${labels[campo] || campo}`;
    }
    if (etapa === 'confirmando_campo' && campo) return `confirmação de ${campo} no cadastro`;
    if (etapa === 'aguardando_ajuda_endereco') return 'cadastro do endereço';
    if (etapa === 'aguardando_horario') return 'agendamento da atualização cadastral';
    return 'atualização do seu cadastro';
  }

  return 'assunto anterior';
}

export function mensagemGateRetomadaOciosa(conversa: ConversaEstadoRow): string {
  const tema = descreverTemaConversa(conversa);
  const min = minutosDesde(conversa.atualizado_em);
  const tempo = min >= 120
    ? `${Math.floor(min / 60)} h`
    : min >= 60
      ? '1 h'
      : `${Math.max(min, CONVERSA_IDLE_MINUTES)} min`;

  if (conversa.fluxo_ativo === 'relatorios') {
    return (
      `A gente tinha parado em ${tema} (última mensagem há cerca de ${tempo}). ` +
      'Quer seguir daqui ou prefere outro assunto?'
    );
  }

  return (
    `Ainda tenho uma conversa aberta sobre ${tema} (última interação há cerca de ${tempo}).\n\n` +
    'Quer CONTINUAR de onde parou ou tratar como assunto NOVO?\n\n' +
    'Responda CONTINUAR ou NOVA.'
  );
}

export function pareceRespostaContinuarConversa(textoNorm: string): boolean {
  return /^(CONTINUAR|CONTINUA|RETOMAR|RETOMO|SEGUIR|SIM|S|OK|PODE|CLARO|VAMOS)($|\s|[!.?,])/i.test(textoNorm.trim()) ||
    /\b(CONTINUAR|RETOMAR|SEGUIR DE ONDE|DE ONDE PAROU|SEGUIR DAQUI|PODE SEGUIR)\b/.test(textoNorm);
}

export function pareceRespostaNovaConversa(textoNorm: string): boolean {
  return /^(NOVA|NOVO|OUTRO|OUTRA|CANCELAR?|CANCELA|NAO|N)($|\s|[!.?,])/i.test(textoNorm.trim()) ||
    /\b(ASSUNTO NOVO|NOVA CONVERSA|OUTRO ASSUNTO|PREFERE OUTRO|COMECAR DO ZERO|COMECAR DE NOVO)\b/.test(textoNorm);
}

export function montarContextoGateOcioso(
  ctx: Record<string, unknown>,
  mensagemAdiada: string,
  conversa: ConversaEstadoRow,
  gateMotivo: 'ociosidade' | 'mudanca_assunto' = 'ociosidade',
): Record<string, unknown> {
  return {
    ...ctx,
    mensagem_adiada_ociosa: mensagemAdiada,
    mensagem_adiada_ociosa_em: new Date().toISOString(),
    etapa_anterior_ociosa: conversa.etapa_atual,
    fluxo_anterior_ocioso: conversa.fluxo_ativo,
    gate_motivo: gateMotivo,
  };
}

export function limparContextoGateOcioso(ctx: Record<string, unknown>): Record<string, unknown> {
  const novo = { ...ctx };
  delete novo.mensagem_adiada_ociosa;
  delete novo.mensagem_adiada_ociosa_em;
  delete novo.etapa_anterior_ociosa;
  delete novo.fluxo_anterior_ocioso;
  delete novo.gate_motivo;
  delete novo.gate_retomada_tentativas;
  return novo;
}
