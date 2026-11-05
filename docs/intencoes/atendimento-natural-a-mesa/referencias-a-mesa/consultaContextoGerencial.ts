// Contexto multi-turno para consultas gerenciais — follow-ups sem regex por frase.
// O Gemini recebe histórico recente (pergunta + resumo da tool) e escolhe a ferramenta.

import { registrarDecisaoAgente } from './autonomyGate.ts';
import {
  pareceFollowUpBreakdownStatus,
  pareceFollowUpListarStatusGrupo,
} from './consultaListasCadastro.ts';

const JANELA_CONTEXTO_MS = 45 * 60 * 1000;
const MAX_TURNOS_HISTORICO = 4;

export interface TurnoConsultaGerencial {
  pergunta: string;
  resposta: string;
  ferramenta?: string;
  args?: Record<string, unknown>;
  criadoEm?: string;
}

export function resumirResultadoTool(
  nomeTool: string,
  resultado: Record<string, unknown>,
): string {
  const fmt = resultado.textoFormatado;
  if (typeof fmt === 'string' && fmt.trim()) {
    const t = fmt.trim();
    return t.length > 500 ? `${t.slice(0, 500)}…` : t;
  }
  const total = typeof resultado.total === 'number' ? resultado.total : null;
  const ret = typeof resultado.retornados === 'number' ? resultado.retornados : null;
  if (total !== null) {
    return ret !== null && ret < total
      ? `[${nomeTool}] total=${total}, mostrados=${ret}`
      : `[${nomeTool}] total=${total}`;
  }
  return `[${nomeTool}] consulta executada`;
}

export async function registrarTurnoConsultaGerencial(
  supabase: any,
  telefone: string,
  turno: {
    pergunta: string;
    resposta: string;
    ferramenta?: string;
    args?: Record<string, unknown>;
    total?: number;
    retornados?: number;
    resumoPorStatus?: Record<string, number>;
  },
): Promise<void> {
  if (!telefone || !turno.pergunta?.trim()) return;

  const respostaCurta = turno.resposta.length > 600
    ? `${turno.resposta.slice(0, 600)}…`
    : turno.resposta;

  await registrarDecisaoAgente(supabase, telefone, turno.ferramenta || 'consulta_gerencial', 'baixo', 'respondeu', {
    contexto_gerencial: true,
    pergunta: turno.pergunta.trim(),
    resumo_resposta: respostaCurta,
    ferramenta: turno.ferramenta,
    args: turno.args,
    total: turno.total,
    retornados: turno.retornados,
    resumo_por_status: turno.resumoPorStatus,
  });
}

export interface ContextoConsultaGerencial {
  historico: TurnoConsultaGerencial[];
  ultimaPergunta?: string;
  ultimaFerramenta?: string;
  textoOrigem?: string;
}

function sintetizarTurnoDeLogLista(
  det: Record<string, unknown>,
  intencao?: string,
): TurnoConsultaGerencial | null {
  const replay = det.consulta_replay as { ferramenta?: string; textoNorm?: string } | undefined;
  const pergunta = replay?.textoNorm || (typeof det.mensagem === 'string' ? det.mensagem : '');
  if (!pergunta) return null;
  const total = typeof det.total === 'number' ? det.total : null;
  const retornados = typeof det.retornados === 'number' ? det.retornados : null;
  const ferramenta = replay?.ferramenta || intencao || 'consulta_gerencial';
  const resposta = total !== null
    ? retornados !== null && retornados < total
      ? `[${ferramenta}] total=${total}, mostrados=${retornados}`
      : `[${ferramenta}] total=${total}`
    : `[${ferramenta}] consulta anterior`;
  return { pergunta, resposta, ferramenta };
}

/** Últimos turnos da liderança — ordem cronológica para multi-turn Gemini. */
export async function buscarHistoricoConsultaGerencial(
  supabase: any,
  telefone: string,
  maxTurnos = MAX_TURNOS_HISTORICO,
): Promise<TurnoConsultaGerencial[]> {
  const ctx = await buscarContextoConsultaGerencial(supabase, telefone, maxTurnos);
  return ctx.historico;
}

/** Contexto unificado: turnos explícitos + fallback de log_lista_longa (consulta truncada). */
export async function buscarContextoConsultaGerencial(
  supabase: any,
  telefone: string,
  maxTurnos = MAX_TURNOS_HISTORICO,
): Promise<ContextoConsultaGerencial> {
  const desde = new Date(Date.now() - JANELA_CONTEXTO_MS).toISOString();
  const { data, error } = await supabase
    .from('whatsapp_decisoes_agente')
    .select('detalhes_json, criado_em, intencao_detectada')
    .eq('telefone', telefone)
    .gte('criado_em', desde)
    .order('criado_em', { ascending: false })
    .limit(30);

  if (error || !data?.length) {
    return { historico: [] };
  }

  const turnos: TurnoConsultaGerencial[] = [];
  let fallbackLog: TurnoConsultaGerencial | null = null;

  for (const row of data) {
    const det = row.detalhes_json as Record<string, unknown> | null;
    if (!det) continue;

    if (det.contexto_gerencial) {
      const pergunta = typeof det.pergunta === 'string' ? det.pergunta : '';
      const resposta = typeof det.resumo_resposta === 'string' ? det.resumo_resposta : '';
      if (pergunta && resposta) {
        turnos.push({
          pergunta,
          resposta,
          ferramenta: typeof det.ferramenta === 'string' ? det.ferramenta : undefined,
          args: det.args as Record<string, unknown> | undefined,
          criadoEm: row.criado_em,
        });
      }
    } else if (!fallbackLog && det.log_lista_longa) {
      fallbackLog = sintetizarTurnoDeLogLista(det, row.intencao_detectada);
    }

    if (turnos.length >= maxTurnos) break;
  }

  const historico = (turnos.length ? turnos : fallbackLog ? [fallbackLog] : []).reverse();
  const ultimo = historico[historico.length - 1];

  return {
    historico,
    ultimaPergunta: ultimo?.pergunta,
    ultimaFerramenta: ultimo?.ferramenta,
    textoOrigem: ultimo?.pergunta,
  };
}

export function montarInstrucaoContextoGerencial(turnos: TurnoConsultaGerencial[]): string {
  if (!turnos.length) return '';
  return `
Histórico recente desta conversa (use para follow-ups — interprete a intenção, não exija mesmas palavras):
${turnos.map((t, i) => `${i + 1}. Usuário: "${t.pergunta}"\n   Resposta: ${t.resposta.slice(0, 350)}${t.resposta.length > 350 ? '…' : ''}`).join('\n')}

Follow-ups ("são todos membros?", "relaciona os líderes", "e os visitantes?") → interprete pelo histórico e chame a ferramenta certa com os parâmetros corretos. Nunca invente números.`;
}

/** Bloco extra quando só há log de lista truncada (consulta anterior na janela). */
export function montarInstrucaoUltimaConsulta(ctx: ContextoConsultaGerencial): string {
  if (!ctx.textoOrigem) return '';
  const ferr = ctx.ultimaFerramenta ? ` (${ctx.ultimaFerramenta})` : '';
  return `
Última consulta deste telefone${ferr}: "${ctx.textoOrigem}"
Follow-ups curtos referem-se a essa consulta — reutilize o mesmo tipo/filtro da ferramenta, ajustando só o que mudou (ex.: statusFiltro, breakdown por status).`;
}

function normalizarCurto(texto: string): string {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase().trim();
}

/** Follow-up curto reconhecível só pelo texto — router usa antes de autosserviço/membro. */
export function pareceFollowUpGerencialCurto(textoNorm: string): boolean {
  const t = (textoNorm || '').trim();
  if (!t || t.length > 120) return false;
  return (
    pareceFollowUpBreakdownStatus(t) ||
    pareceFollowUpListarStatusGrupo(t) ||
    /\b(E\s+)?OS\s+(\d+\s+)?(VISITANTES|MEMBROS|LIDERES)\b/.test(t) ||
    /\b(DE QUAL|QUAL)\s+MESA\b/.test(t)
  );
}

/** Mensagem curta com contexto recente → só follow-ups com sinal explícito (resto vai pro Gemini). */
export function pareceFollowUpCurtoComContexto(textoRecebido: string, ctx: ContextoConsultaGerencial): boolean {
  if (!ctx.historico.length) return false;
  const t = (textoRecebido || '').trim();
  if (!t || t.length > 120) return false;

  const norm = normalizarCurto(t);
  return (
    pareceFollowUpBreakdownStatus(norm) ||
    pareceFollowUpListarStatusGrupo(norm) ||
    /\b(E\s+)?OS\s+(\d+\s+)?(VISITANTES|MEMBROS|LIDERES)\b/.test(norm) ||
    /\b(DE QUAL|QUAL)\s+MESA\b/.test(norm)
  );
}
