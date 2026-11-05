// Módulo de Humanização e Proteção de Respostas via WhatsApp
// - Pausa de leitura: conversacional (~400ms–1s) ou campanha (~1.5s–4s)
// - Emissão de status "composing" (digitando...) contínuo via Z-API
// - Divisão de mensagens longas em blocos por parágrafos
// - Guard pós-resposta anti-alucinação com bloqueio e resposta fallback

import { ZapiCredentials, sleep } from "./whatsappCore.ts";

export async function enviarComposingContinuo(
  zapi: ZapiCredentials,
  targetPhone: string,
  durationMs: number,
  isSandbox: boolean
) {
  if (isSandbox || !zapi) {
    console.log(`[HUMANIZE_SANDBOX] Simulando status "composing" (digitando...) para ${targetPhone} por ${durationMs}ms`);
    await sleep(Math.min(2000, durationMs));
    return;
  }

  const endpointUrl = `${zapi.baseUrl}/send-presence`;
  const intervalMs = 2000;
  const startTime = Date.now();

  while (Date.now() - startTime < durationMs) {
    try {
      await fetch(endpointUrl, {
        method: 'POST',
        headers: zapi.headers,
        body: JSON.stringify({
          phone: targetPhone,
          presence: 'composing',
        }),
      }).catch(() => {});
    } catch {
      // Ignora falhas temporárias de presença
    }
    const rem = durationMs - (Date.now() - startTime);
    if (rem <= 0) break;
    await sleep(Math.min(intervalMs, rem));
  }
}

export type ModoPausaLeitura = 'campanha' | 'conversacional';

export function calcularPausaLeitura(texto: string, modo: ModoPausaLeitura = 'campanha'): number {
  if (!texto) return modo === 'conversacional' ? 600 : 1500;

  if (modo === 'conversacional') {
    // Resposta a quem iniciou — só um sinal breve de digitação (~400ms–1s)
    const baseMs = texto.length * 12;
    return Math.min(1000, Math.max(400, baseMs));
  }

  // Campanhas / lotes — pausa mais longa (~1.5s–4s)
  const baseMs = texto.length * 40;
  return Math.min(4000, Math.max(1500, baseMs));
}

export function dividirMensagemEmBlocos(texto: string, maxChars: number = 500): string[] {
  if (!texto || texto.length <= maxChars) return [texto];

  const paragrafos = texto.split(/\n\n+/);
  const blocos: string[] = [];
  let blocoAtual = '';

  for (const p of paragrafos) {
    if ((blocoAtual + '\n\n' + p).trim().length <= maxChars) {
      blocoAtual = blocoAtual ? blocoAtual + '\n\n' + p : p;
    } else {
      if (blocoAtual) blocos.push(blocoAtual.trim());
      if (p.length > maxChars) {
        const frases = p.split(/(?<=[.!?])\s+/);
        let subBloco = '';
        for (const f of frases) {
          if ((subBloco + ' ' + f).trim().length <= maxChars) {
            subBloco = subBloco ? subBloco + ' ' + f : f;
          } else {
            if (subBloco) blocos.push(subBloco.trim());
            subBloco = f;
          }
        }
        if (subBloco) blocoAtual = subBloco;
      } else {
        blocoAtual = p;
      }
    }
  }

  if (blocoAtual) blocos.push(blocoAtual.trim());
  return blocos.filter(Boolean);
}

export interface GroundingData {
  nomesPermitidos?: string[];
}

export interface GuardResult {
  seguro: boolean;
  motivo?: string;
  respostaValidada: string;
}

export function validarGuardAntiAlucinacao(textoResposta: string, grounding?: GroundingData): GuardResult {
  if (!textoResposta) {
    return { seguro: true, respostaValidada: textoResposta };
  }

  // Se grounding com nomes autorizados for passado, valida se menções a nomes próprios foram inventadas
  if (grounding?.nomesPermitidos && grounding.nomesPermitidos.length > 0) {
    const nomesEncontrados = textoResposta.match(/\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]{2,}\b/g) || [];
    const nomesPermitidosNorm = grounding.nomesPermitidos.map(n => n.toLowerCase());
    
    const stopwords = [
      'de', 'da', 'do', 'em', 'para', 'com', 'igreja', 'mesa', 'roteiro', 'deus', 'jesus',
      'senhor', 'bíblia', 'domingo', 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado',
      'pode', 'sim', 'não', 'bairro', 'rua', 'cep', 'estado', 'paz', 'olá', 'tudo', 'bem', 'graça'
    ];
    
    for (const nome of nomesEncontrados) {
      const lower = nome.toLowerCase();
      if (stopwords.includes(lower)) continue;
      const presente = nomesPermitidosNorm.some(p => p.includes(lower) || lower.includes(p));
      if (!presente) {
        console.warn(`[GUARD_ANTI_ALUCINACAO_BLOCK] Nome não autorizado detectado na resposta do Gemini: "${nome}"`);
        return {
          seguro: false,
          motivo: `Nome não autorizado detectado: "${nome}"`,
          respostaValidada: 'Desculpe, não consegui confirmar essa informação com precisão. Um líder da nossa comunidade vai falar com você em breve! 🙏',
        };
      }
    }
  }

  return { seguro: true, respostaValidada: textoResposta };
}
