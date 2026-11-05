// Human takeover pastoral — persistência via whatsapp_decisoes_agente (sem migration, D4)

const TAKEOVER_TTL_MS = 24 * 60 * 60 * 1000;

export const COMANDOS_RETOMAR_IA = ['RETOMAR IA', 'RETOMAR AI', 'RETOMAR BOT', 'VOLTA IA', 'VOLTA AI', 'VOLTA BOT'];

export interface TakeoverStatus {
  ativo: boolean;
  decisaoId?: string;
  mensagemOriginal?: string;
  expiraEm?: string;
}

function takeoverExpirado(criadoEm: string, detalhes: Record<string, unknown> | null): boolean {
  const expira = detalhes?.takeover_expira_em;
  if (typeof expira === 'string') return new Date(expira).getTime() <= Date.now();
  return Date.now() - new Date(criadoEm).getTime() > TAKEOVER_TTL_MS;
}

export function detalhesTakeoverEscalonamento(mensagem: string, extra: Record<string, unknown> = {}) {
  return {
    ...extra,
    mensagem,
    takeover_ativo: true,
    takeover_expira_em: new Date(Date.now() + TAKEOVER_TTL_MS).toISOString(),
  };
}

export async function consultarTakeoverHumano(supabase: any, telefone: string): Promise<TakeoverStatus> {
  if (!telefone) return { ativo: false };

  const { data: decisao, error } = await supabase
    .from('whatsapp_decisoes_agente')
    .select('id, criado_em, detalhes_json')
    .eq('telefone', telefone)
    .eq('acao', 'escalou_humano')
    .order('criado_em', { ascending: false })
    .limit(1)
    .maybeSingle();

  if (error || !decisao) return { ativo: false };

  const detalhes = (decisao.detalhes_json || {}) as Record<string, unknown>;
  if (detalhes.takeover_liberado) return { ativo: false };
  if (takeoverExpirado(decisao.criado_em, detalhes)) return { ativo: false };

  const { data: respostaPastoral } = await supabase
    .from('whatsapp_mensagens')
    .select('id, data_criacao')
    .eq('destinatario_telefone', telefone)
    .eq('tipo_gatilho', 'resposta_pastoral_manual')
    .in('status', ['enviado', 'fila', 'pendente'])
    .gt('data_criacao', decisao.criado_em)
    .limit(1)
    .maybeSingle();

  if (respostaPastoral) return { ativo: false };

  return {
    ativo: true,
    decisaoId: decisao.id,
    mensagemOriginal: typeof detalhes.mensagem === 'string' ? detalhes.mensagem : undefined,
    expiraEm: typeof detalhes.takeover_expira_em === 'string' ? detalhes.takeover_expira_em : undefined,
  };
}

export async function liberarTakeoverHumano(
  supabase: any,
  telefone: string,
  motivo: string,
): Promise<void> {
  const status = await consultarTakeoverHumano(supabase, telefone);
  if (!status.ativo || !status.decisaoId) return;

  const { data: row } = await supabase
    .from('whatsapp_decisoes_agente')
    .select('detalhes_json')
    .eq('id', status.decisaoId)
    .maybeSingle();

  const detalhes = { ...(row?.detalhes_json || {}), takeover_liberado: true, takeover_liberado_motivo: motivo };
  await supabase
    .from('whatsapp_decisoes_agente')
    .update({ detalhes_json: detalhes })
    .eq('id', status.decisaoId);
}

export function textoPareceComandoRetomarIa(textoNorm: string): boolean {
  const t = textoNorm.replace(/\bAI\b/g, 'IA');
  return COMANDOS_RETOMAR_IA.some((c) => t === c || t.startsWith(c + ' '));
}
