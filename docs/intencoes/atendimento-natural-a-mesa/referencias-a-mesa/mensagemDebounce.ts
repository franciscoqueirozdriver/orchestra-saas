// Debounce inbound WhatsApp — agrupa mensagens rápidas do mesmo telefone antes do processamento.
// Postgres (multi-instância Edge) + fallback in-process para testes locais.

import { textoPareceComandoRetomarIa } from './humanTakeover.ts';
import { textoPareceConteudoRoteiroEstudo } from './autonomyGate.ts';

export const DEBOUNCE_INBOUND_MS = Number(Deno.env.get('WHATSAPP_DEBOUNCE_MS') || '2500');
export const DEBOUNCE_MAX_ESPERA_MS = Number(Deno.env.get('WHATSAPP_DEBOUNCE_MAX_MS') || '30000');

/** Webhook irmão já processou o lote debounced — não responder de novo. */
export const DEBOUNCE_JA_PROCESSADO = Symbol('debounce_ja_processado');

interface BufferDebounce {
  partes: string[];
  timer: ReturnType<typeof setTimeout> | null;
  flushPromise: Promise<unknown> | null;
  flushResolve: ((v: unknown) => void) | null;
}

const buffers = new Map<string, BufferDebounce>();

/** Comandos, roteiro colado e fluxos de campo único não devem ser concatenados. */
export function deveAplicarDebounceInbound(textoRecebido: string, textoNorm: string): boolean {
  if (!textoRecebido?.trim()) return false;
  if (textoRecebido.length > 400) return false;
  if (textoPareceComandoRetomarIa(textoNorm)) return false;
  if (textoNorm === 'CANCELAR' || textoNorm.startsWith('CANCELA')) return false;
  if (['SAIR', 'PARAR', 'UNSUBSCRIBE'].includes(textoNorm)) return false;
  if (textoPareceConteudoRoteiroEstudo(textoRecebido)) return false;
  if (/\b\d{1,2}[/\-.]\d{1,2}[/\-.]\d{4}\b/.test(textoRecebido)) return false;
  return true;
}

/** Resposta curta para saudação sem pergunta — nunca silenciar o usuário. */
export function montarRespostaSaudacaoSimples(tratamento?: string | null): string {
  const nome = (tratamento || '').trim();
  if (nome) return `Oi, ${nome}! Bom te ver por aqui. Em que posso ajudar?`;
  return 'Oi! Bom te ver por aqui. Em que posso ajudar?';
}

/** Saudação curta sem pergunta — usada só para debounce, não para silenciar resposta. */
export function pareceSaudacaoSemPergunta(textoNorm: string): boolean {
  const t = (textoNorm || '').trim();
  if (!t || t.length > 60) return false;
  if (t.includes('?')) return false;
  if (/\b(QUANTOS|QUANTAS|QUEM|QUAL|QUAIS|LISTA|LISTAR|TRAGA|BUSCA|MEMBROS|VISITANTES|CULTO|FALT|BRIEFING)\b/.test(t)) {
    return false;
  }
  if (/^(OI|OLA|OLÁ|BOM DIA|BOA TARDE|BOA NOITE|HEY|E AI|E AÍ|BOM DIA)[!.?\s,]*$/i.test(t)) return true;
  const palavras = t.split(/\s+/).filter(Boolean);
  return palavras.length <= 4 &&
    /^(OI|OLA|BOM|BOA|BOM DIA|BOA TARDE|BOA NOITE)/.test(palavras.slice(0, 2).join(' '));
}

export interface ConversaDebounceHint {
  fluxo_ativo?: string;
  etapa_atual?: string;
}

/** Cadastro campo-a-campo e confirmação de roteiro exigem resposta imediata por mensagem. */
export function conversaRequerRespostaImediata(conversa: ConversaDebounceHint | null | undefined): boolean {
  if (!conversa?.fluxo_ativo) return false;
  if (conversa.fluxo_ativo === 'atualizacao_cadastral') return true;
  if (conversa.fluxo_ativo === 'relatorios') return true;
  if (
    conversa.fluxo_ativo === 'roteiro_estudo' &&
    ['aguardando_confirmacao', 'aguardando_validacao_campo', 'processando'].includes(conversa.etapa_atual || '')
  ) {
    return true;
  }
  return false;
}

export function concatenarPartesDebounce(partes: string[]): string {
  return partes.map((p) => p.trim()).filter(Boolean).join('\n');
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function acumularDebounceDb(
  supabase: any,
  telefone: string,
  texto: string,
  janelaMs: number,
): Promise<string | null> {
  const { data, error } = await supabase.rpc('whatsapp_debounce_acumular', {
    p_telefone: telefone,
    p_texto: texto,
    p_janela_ms: janelaMs,
  });
  if (error) {
    console.warn('[DEBOUNCE_DB] acumular falhou, fallback in-process:', error.message);
    return null;
  }
  return typeof data === 'string' ? data : null;
}

async function claimDebounceDb(
  supabase: any,
  telefone: string,
): Promise<string[] | null> {
  const { data, error } = await supabase.rpc('whatsapp_debounce_claim', { p_telefone: telefone });
  if (error) {
    console.warn('[DEBOUNCE_DB] claim falhou:', error.message);
    return null;
  }
  const partes = (data as { partes?: unknown } | null)?.partes;
  if (!Array.isArray(partes)) return null;
  return partes.filter((p): p is string => typeof p === 'string');
}

/**
 * Debounce via Postgres — funciona entre instâncias Edge.
 * Retorna DEBOUNCE_JA_PROCESSADO quando outra instância já processou o lote.
 */
export async function debounceMensagemInboundDb<T>(
  supabase: any,
  telefone: string,
  texto: string,
  janelaMs: number,
  onFlush: (textoConcatenado: string) => Promise<T>,
): Promise<T | typeof DEBOUNCE_JA_PROCESSADO> {
  const flushInicial = await acumularDebounceDb(supabase, telefone, texto, janelaMs);
  if (!flushInicial) {
    return debounceMensagemInbound(telefone, texto, janelaMs, onFlush);
  }

  const inicio = Date.now();
  while (Date.now() - inicio < DEBOUNCE_MAX_ESPERA_MS) {
    const { data: row } = await supabase
      .from('whatsapp_debounce_inbound')
      .select('flush_at')
      .eq('telefone', telefone)
      .maybeSingle();

    if (!row?.flush_at) {
      return DEBOUNCE_JA_PROCESSADO;
    }

    const waitMs = new Date(row.flush_at).getTime() - Date.now();
    if (waitMs > 0) await sleep(Math.min(waitMs, 500));

    const partes = await claimDebounceDb(supabase, telefone);
    if (partes?.length) {
      const merged = concatenarPartesDebounce(partes);
      console.log(`[DEBOUNCE_DB] Flush ${telefone}: ${partes.length} parte(s)`);
      return onFlush(merged);
    }

    await sleep(120);
  }

  console.warn(`[DEBOUNCE_DB] Timeout ${telefone} — processando mensagem isolada`);
  return onFlush(texto);
}

/** Fallback in-process (mesma instância Edge). */
export function debounceMensagemInbound<T>(
  telefone: string,
  texto: string,
  janelaMs: number,
  onFlush: (textoConcatenado: string) => Promise<T>,
): Promise<T> {
  if (!telefone?.trim()) return onFlush(texto);

  let buf = buffers.get(telefone);
  if (!buf) {
    buf = { partes: [], timer: null, flushPromise: null, flushResolve: null };
    buffers.set(telefone, buf);
  }

  buf.partes.push(texto);

  if (!buf.flushPromise) {
    buf.flushPromise = new Promise((resolve) => {
      buf!.flushResolve = resolve;
    });
  }

  if (buf.timer) clearTimeout(buf.timer);

  buf.timer = setTimeout(async () => {
    const atual = buffers.get(telefone);
    if (!atual) return;

    const merged = concatenarPartesDebounce(atual.partes);
    buffers.delete(telefone);

    try {
      const result = await onFlush(merged);
      atual.flushResolve?.(result);
    } catch (err) {
      atual.flushResolve?.(Promise.reject(err));
    }
  }, janelaMs);

  return buf.flushPromise as Promise<T>;
}

/** Limpa buffers in-process — útil em testes. */
export function limparBuffersDebounce(): void {
  for (const buf of buffers.values()) {
    if (buf.timer) clearTimeout(buf.timer);
  }
  buffers.clear();
}
