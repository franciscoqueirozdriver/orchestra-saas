/**
 * Proteção contra alucinação quando há conversa ativa e o usuário muda de assunto.
 * Em vez de forçar a mensagem no fluxo aberto (ex.: "boa tarde" → endereço),
 * abre gate CONTINUAR / NOVA (mesma UX do gate de ociosidade).
 */

import {
  mensagemPareceInteracaoRoteiro,
  mensagemParecePerguntaForaDoRoteiro,
  pareceAssuntoCadastroPessoal,
  pareceConsultaStatusCadastroPessoal,
  parecePedidoAtualizacaoCadastral,
} from './conversationEscape.ts';
import { descreverTemaConversa, type ConversaEstadoRow } from './conversaIdleGate.ts';
import { identificarCampoCadastroFromTexto } from './cadastroPessoal.ts';
import { montarRespostaSaudacaoSimples, pareceSaudacaoSemPergunta } from './mensagemDebounce.ts';
import {
  pareceConsultaGerencialCurta,
  pareceConviteRoteiro,
  parecePerguntaAbertaGerencial,
} from './router.ts';
import { pareceIniciarRelatorios, parecePedidoRelatorioNoFluxo } from './fluxoRelatorios.ts';

export type AcaoProtecaoMudancaAssunto = 'seguir_fluxo' | 'gate' | 'auto_nova';

export interface AvaliacaoMudancaAssunto {
  acao: AcaoProtecaoMudancaAssunto;
  motivo: string;
}

export interface EntradaProtecaoMudancaAssunto {
  conversa: ConversaEstadoRow;
  textoRecebido: string;
  textoNorm: string;
  autorizadoGerencial?: boolean;
}

const TOKENS_FLUXO_CURTO = /^(SIM|S|NAO|NÃO|N|OK|PODE|CLARO|CANCELAR?|CANCELA)($|\s|[!.?,])/i;

function pareceValorCampoCadastro(campo: string | null | undefined, textoRecebido: string, textoNorm: string): boolean {
  if (!campo) return false;
  if (campo === 'cep' && /\d{5}-?\d{3}/.test(textoRecebido)) return true;
  if (campo === 'data_nascimento' && /\d{1,2}\/\d{1,2}/.test(textoRecebido)) return true;
  if (campo === 'telefone' && /\d{10,11}/.test(textoRecebido.replace(/\D/g, ''))) return true;
  if (campo === 'endereco' && (
    /\b(RUA|AVENIDA|AV |TRAVESSA|ALAMEDA|RODOVIA|NUMERO|COMPLEMENTO|APTO)\b/.test(textoNorm) ||
    /,\s*\d/.test(textoRecebido) ||
    /\d{5}-?\d{3}/.test(textoRecebido)
  )) return true;
  if (['bairro', 'estado_civil'].includes(campo) && textoRecebido.trim().length >= 2) {
    return !pareceSaudacaoSemPergunta(textoNorm) && !textoRecebido.includes('?');
  }
  return false;
}

/** Mensagem coerente com a etapa atual do fluxo — pode seguir sem gate. */
export function mensagemValidaParaFluxoAtivo(input: EntradaProtecaoMudancaAssunto): boolean {
  const { conversa, textoRecebido, textoNorm } = input;
  const ctx = (conversa.contexto_json || {}) as Record<string, unknown>;
  const etapa = conversa.etapa_atual;
  const fluxo = conversa.fluxo_ativo;

  if (fluxo === 'relatorios') {
    return parecePedidoRelatorioNoFluxo(textoNorm, etapa);
  }

  if (fluxo === 'interpretacao_capacidade') {
    return true; // SIM/NÃO ou reformulação — o handler decide
  }

  if (TOKENS_FLUXO_CURTO.test(textoNorm.trim())) return true;

  if (fluxo === 'roteiro_estudo') {
    return mensagemPareceInteracaoRoteiro(textoNorm, textoRecebido);
  }

  if (fluxo !== 'atualizacao_cadastral') return true;

  if (pareceConsultaStatusCadastroPessoal(textoNorm)) return true;
  if (identificarCampoCadastroFromTexto(textoNorm)) return true;
  if (parecePedidoAtualizacaoCadastral(textoNorm)) return true;

  if (etapa === 'aguardando_horario' || etapa === 'agendado') return textoRecebido.trim().length >= 2;

  if (etapa === 'aguardando_ajuda_endereco') {
    return TOKENS_FLUXO_CURTO.test(textoNorm.trim()) ||
      /\b(RUA|AVENIDA|AV |CEP|NUMERO|COMPLEMENTO)\b/.test(textoNorm) ||
      /\d{5}-?\d{3}/.test(textoRecebido);
  }

  if (etapa === 'escolhendo_campo') {
    return Boolean(identificarCampoCadastroFromTexto(textoNorm)) ||
      parecePedidoAtualizacaoCadastral(textoNorm) ||
      pareceValorCampoCadastro(String(ctx.campo_atual || ''), textoRecebido, textoNorm);
  }

  if (etapa === 'perguntando_campo') {
    return pareceValorCampoCadastro(String(ctx.campo_atual || ''), textoRecebido, textoNorm);
  }

  if (etapa === 'confirmando_campo') {
    return TOKENS_FLUXO_CURTO.test(textoNorm.trim()) ||
      pareceValorCampoCadastro(String(ctx.campo_atual || ''), textoRecebido, textoNorm);
  }

  return false;
}

/** Assunto claramente externo ao fluxo aberto. */
export function pareceAssuntoExternoAoFluxo(input: EntradaProtecaoMudancaAssunto): boolean {
  const { conversa, textoRecebido, textoNorm, autorizadoGerencial } = input;

  if (pareceSaudacaoSemPergunta(textoNorm)) return true;

  if (pareceIniciarRelatorios(textoNorm) && conversa.fluxo_ativo !== 'relatorios') return true;

  if (conversa.fluxo_ativo === 'relatorios') {
    if (parecePedidoRelatorioNoFluxo(textoNorm, conversa.etapa_atual)) return false;
    if (autorizadoGerencial && (
      textoRecebido.includes('?') ||
      /\b(QUEM|QUAL|QUAIS|QUANTOS|QUANTAS|LIDER|MESA|ROTEIRO|BRIEFING|KPI)\b/.test(textoNorm)
    )) {
      return true;
    }
  }

  if (conversa.fluxo_ativo === 'roteiro_estudo') {
    return mensagemParecePerguntaForaDoRoteiro(textoNorm, textoRecebido);
  }

  if (conversa.fluxo_ativo === 'atualizacao_cadastral') {
    if (mensagemParecePerguntaForaDoRoteiro(textoNorm, textoRecebido)) return true;
    if (pareceAssuntoCadastroPessoal(textoNorm) && pareceConsultaStatusCadastroPessoal(textoNorm)) return false;
    if (pareceAssuntoCadastroPessoal(textoNorm) && parecePedidoAtualizacaoCadastral(textoNorm)) return false;
  }

  if (autorizadoGerencial) {
    if (pareceConsultaGerencialCurta(textoNorm, textoRecebido)) return true;
    if (parecePerguntaAbertaGerencial(textoNorm, textoRecebido)) return true;
    if (pareceConviteRoteiro(textoRecebido, textoNorm)) return true;
  }

  return false;
}

export function mensagemGateMudancaAssunto(conversa: ConversaEstadoRow): string {
  const tema = descreverTemaConversa(conversa);
  if (conversa.fluxo_ativo === 'relatorios') {
    return `A gente estava em ${tema}, mas isso parece outra coisa. Quer seguir nos relatórios ou prefere outro assunto?`;
  }
  return (
    `Ainda estou no assunto *${tema}*, mas sua mensagem parece ser outra coisa.\n\n` +
    'Quer *CONTINUAR* esse assunto ou tratar como pergunta *NOVA*?\n\n' +
    'Responda CONTINUAR ou NOVA.'
  );
}

/** Resposta imediata para saudação durante fluxo — usada só se gate não for preferido. */
export function respostaSaudacaoDuranteFluxo(tratamento?: string | null): string {
  return `${montarRespostaSaudacaoSimples(tratamento)} (Se quiser sair do assunto anterior, responda NOVA.)`;
}

/**
 * Decide: seguir fluxo, abrir gate, ou abandonar e tratar como assunto novo.
 * Gate evita alucinação no cron (processar-conversa).
 */
export function avaliarProtecaoMudancaAssunto(input: EntradaProtecaoMudancaAssunto): AvaliacaoMudancaAssunto {
  const { conversa } = input;

  if (!conversa?.fluxo_ativo || conversa.etapa_atual === 'aguardando_retomada_ociosa') {
    return { acao: 'seguir_fluxo', motivo: 'sem_fluxo_ou_ja_no_gate' };
  }

  if (pareceConsultaStatusCadastroPessoal(input.textoNorm) && conversa.fluxo_ativo === 'atualizacao_cadastral') {
    return { acao: 'auto_nova', motivo: 'reconsulta_status_cadastro' };
  }

  if (mensagemValidaParaFluxoAtivo(input)) {
    return { acao: 'seguir_fluxo', motivo: 'mensagem_valida_fluxo' };
  }

  if (pareceAssuntoExternoAoFluxo(input)) {
    return { acao: 'gate', motivo: 'assunto_externo_detectado' };
  }

  if (conversa.fluxo_ativo === 'relatorios') {
    return { acao: 'seguir_fluxo', motivo: 'pedido_aberto_relatorios' };
  }

  // Texto ambíguo durante coleta de campo — gate em vez de inventar interpretação
  if (conversa.fluxo_ativo === 'atualizacao_cadastral' &&
    ['escolhendo_campo', 'perguntando_campo', 'confirmando_campo'].includes(conversa.etapa_atual)) {
    return { acao: 'gate', motivo: 'texto_ambiguo_coleta_campo' };
  }

  return { acao: 'seguir_fluxo', motivo: 'fallback_fluxo' };
}
