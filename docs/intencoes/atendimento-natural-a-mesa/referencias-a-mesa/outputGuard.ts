// Output guard WhatsApp — pós-LLM (padrão SARA output-guard + output-enforcer).
// Toda resposta do bot passa aqui antes de enfileirar em whatsapp_mensagens.

export type GuardOutputContext = 'membro' | 'gerencial' | 'pastoral' | 'geral';

export interface GuardOutputOpts {
  telefone?: string;
  contexto?: GuardOutputContext;
  /** Respostas gerenciais podem ser longas (chunk depois). */
  maxPalavras?: number;
  /** Se true, números/contagens sem evidência de tool → fallback seguro. */
  exigirGrounding?: boolean;
}

export interface GuardOutputResult {
  texto: string;
  violacoes: string[];
  substituido: boolean;
}

const FALLBACK_SEGURO =
  'Desculpa, deixa eu reformular! Pode repetir o que você precisa de outro jeito?';

const LEAK_MARKERS: Array<{ pattern: RegExp; label: string }> = [
  { pattern: /\b(gemini|groq|claude|gpt-?\d|openai|langchain)\b/i, label: 'model_name_leak' },
  { pattern: /system[_ ]instruction/i, label: 'system_instruction_leak' },
  { pattern: /persona[_ ]instruction/i, label: 'persona_instruction_leak' },
  { pattern: /você é o assistente da igreja/i, label: 'system_prompt_echo' },
  { pattern: /regras:\s*\n\s*-/i, label: 'rules_list_leak' },
  { pattern: /<\|im_start\|>/i, label: 'chatml_marker' },
  { pattern: /<\|system\|>/i, label: 'system_marker' },
  { pattern: /\b(?:supabase|edge function|whatsapp-receber)\b/i, label: 'infra_leak' },
  { pattern: /\b(?:src|dist|_shared)\/[\w./-]+\.(?:ts|tsx|js)\b/i, label: 'source_path_leak' },
];

const FRASES_ROBOTICAS: Array<{ pattern: RegExp; label: string }> = [
  { pattern: /como posso ajudar\?\s*$/i, label: 'saudacao_generica' },
  { pattern: /vi que você tem interesse/i, label: 'vendas_generico' },
  { pattern: /sou um assistente (virtual|de ia)/i, label: 'bot_self_identify' },
];

const EMOJI_RE = /\p{Extended_Pictographic}/gu;
const SENTENCE_END_RE = /[.!?…](?:\s|$)/g;

function contarPalavras(texto: string): number {
  const t = texto.trim();
  if (!t) return 0;
  return t.split(/\s+/).length;
}

function truncarPalavras(texto: string, maxPalavras: number): string {
  const palavras = texto.trim().split(/\s+/);
  if (palavras.length <= maxPalavras) return texto;

  const candidato = palavras.slice(0, maxPalavras).join(' ');
  let ultimoFim = -1;
  let m: RegExpExecArray | null;
  const re = new RegExp(SENTENCE_END_RE.source, 'g');
  while ((m = re.exec(candidato)) !== null) {
    ultimoFim = m.index + 1;
  }
  if (ultimoFim >= maxPalavras * 2) {
    return candidato.slice(0, ultimoFim).trim();
  }
  return candidato.trim().replace(/[,;:]+$/, '') + '…';
}

function removerMarkdownExcessivo(texto: string): string {
  const enfatizado = [...texto.matchAll(/\*\*[^*]+\*\*|\*[^*]+\*|__[^_]+__|_[^_]+_/g)]
    .reduce((s, m) => s + m[0].length, 0);
  if (texto.length === 0 || enfatizado / texto.length < 0.1) return texto;
  return texto
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/_([^_]+)_/g, '$1');
}

function limitarEmoji(texto: string, max: number): string {
  let kept = 0;
  return texto.replace(EMOJI_RE, (ch) => {
    kept++;
    return kept <= max ? ch : '';
  }).replace(/\s{2,}/g, ' ').trim();
}

export function validarVazamentoPrompt(texto: string): { safe: boolean; violacoes: string[] } {
  const violacoes: string[] = [];
  for (const { pattern, label } of LEAK_MARKERS) {
    if (pattern.test(texto)) violacoes.push(label);
  }
  return { safe: violacoes.length === 0, violacoes };
}

export function validarTomRobótico(texto: string): { safe: boolean; violacoes: string[] } {
  const violacoes: string[] = [];
  for (const { pattern, label } of FRASES_ROBOTICAS) {
    if (pattern.test(texto)) violacoes.push(label);
  }
  return { safe: violacoes.length === 0, violacoes };
}

/** Contagens inventadas — heurística leve quando exigirGrounding=true. */
export function pareceContagemSemEvidencia(texto: string): boolean {
  const t = texto.trim();
  // Contagem determinística buscar_pessoas (idade/faixa explícita ou aviso de recorte)
  if (/^Temos\s+\d{1,4}\s+/i.test(t)) {
    if (/\d+\s+anos\b/i.test(t)) return false;
    if (/\bsem data de nascimento não entraram nesse recorte\b/i.test(t)) return false;
    if (/\b(pessoas|membros|visitantes|l[ií]deres|cadastrad)\b/i.test(t)) return false;
  }
  if (/^\d{1,4}\s*[—\-–]\s/i.test(t)) return false;
  if (/^Distribuição por faixa ministerial:/i.test(t)) return false;
  if (/^Nenhuma pessoa encontrada nesse recorte/i.test(t)) return false;
  if (/^A média de idade\b/i.test(t)) return false;
  if (/^Média de idade por faixa ministerial:/i.test(t)) return false;

  const temNumeroComSubstantivo = /\b(\d{1,4})\s*(pessoas|membros|cadastrados|cadastradas|faltaram|presentes|visitantes?|l[ií]deres?)\b/i.test(texto)
    || (/\b\d{1,4}\b/.test(texto) && /\bmembros?\b/i.test(texto));
  if (!temNumeroComSubstantivo) return false;
  // Listas determinísticas costumam ter bullets ou quebras numeradas
  if (/^\s*[-•]\s/m.test(texto) || /\n\s*\d+[.)]\s/.test(texto)) return false;
  // Breakdown curto vindo de tool (listar_cadastro / buscar_pessoas)
  if (/^(Sim|Não)\s*[—\-–]/i.test(texto.trim())) return false;
  if (/\bno total\b/i.test(texto) && /\bmembros?\b/i.test(texto)) return false;
  if (/\bmembros?\b/i.test(texto) && /\bvisitantes?\b/i.test(texto)) return false;
  if (/\bl[ií]deres?\b/i.test(texto) && /\bmembros?\b/i.test(texto)) return false;
  if (/\blista filtrada\b/i.test(texto)) return false;
  if (/\btotal atual\b/i.test(texto)) return false;
  return true;
}

export function aplicarRegrasPersona(texto: string, maxPalavras = 80): string {
  let out = removerMarkdownExcessivo(texto.trim());
  out = limitarEmoji(out, 3);
  out = truncarPalavras(out, maxPalavras);
  return out;
}

/**
 * Guarda pós-LLM — ordem SARA:
 * 1. vazamento de prompt → fallback
 * 2. tom robótico (membro/pastoral) → fallback
 * 3. contagem sem evidência (gerencial) → fallback
 * 4. persona (palavras, emoji, markdown)
 */
export function guardOutputWhatsApp(texto: string, opts: GuardOutputOpts = {}): GuardOutputResult {
  if (!texto || typeof texto !== 'string') {
    return { texto: '', violacoes: [], substituido: false };
  }

  const contexto = opts.contexto ?? 'geral';
  const maxPalavras = opts.maxPalavras ?? (contexto === 'gerencial' ? 400 : 80);
  const violacoes: string[] = [];
  let substituido = false;
  let out = texto;

  const leak = validarVazamentoPrompt(out);
  if (!leak.safe) {
    violacoes.push(...leak.violacoes);
    console.warn(`[OUTPUT_GUARD] vazamento ${opts.telefone ? `***${opts.telefone.slice(-4)}` : ''}: ${leak.violacoes.join(',')}`);
    return { texto: FALLBACK_SEGURO, violacoes, substituido: true };
  }

  if (contexto === 'membro' || contexto === 'pastoral') {
    const tom = validarTomRobótico(out);
    if (!tom.safe) {
      violacoes.push(...tom.violacoes);
      substituido = true;
      out = FALLBACK_SEGURO;
    }
  }

  if (opts.exigirGrounding && !substituido && pareceContagemSemEvidencia(out)) {
    violacoes.push('contagem_sem_evidencia');
    substituido = true;
    out = 'Não consegui confirmar esse número agora. Pode reformular a pergunta ou pedir a lista completa?';
  }

  if (!substituido) {
    out = aplicarRegrasPersona(out, maxPalavras);
  }

  return { texto: out, violacoes, substituido };
}
