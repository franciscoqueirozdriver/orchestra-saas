/// <reference lib="deno.ns" />
import {
  conversaRequerRespostaImediata,
  debounceMensagemInbound,
  deveAplicarDebounceInbound,
  montarRespostaSaudacaoSimples,
  pareceSaudacaoSemPergunta,
  concatenarPartesDebounce,
  limparBuffersDebounce,
} from './mensagemDebounce.ts';
import { assertEquals, assert, assertMatch } from 'https://deno.land/std@0.224.0/assert/mod.ts';

Deno.test('deveAplicarDebounceInbound: skip comandos e roteiro longo', () => {
  assertEquals(deveAplicarDebounceInbound('CANCELAR', 'CANCELAR'), false);
  assertEquals(deveAplicarDebounceInbound('VOLTA AI', 'VOLTA AI'), false);
  assert(deveAplicarDebounceInbound('bom dia', 'BOM DIA'));
  assert(deveAplicarDebounceInbound('quantos membros', 'QUANTOS MEMBROS'));
  assertEquals(deveAplicarDebounceInbound('x'.repeat(401), 'X'), false);
});

Deno.test('montarRespostaSaudacaoSimples — com e sem nome', () => {
  assertMatch(montarRespostaSaudacaoSimples('Francisco'), /Francisco/);
  assertMatch(montarRespostaSaudacaoSimples(null), /^Oi!/);
});

Deno.test('pareceSaudacaoSemPergunta: boa noite sim, pergunta não', () => {
  assert(pareceSaudacaoSemPergunta('BOA NOITE'));
  assert(pareceSaudacaoSemPergunta('BOM DIA'));
  assertEquals(pareceSaudacaoSemPergunta('QUANTOS MEMBROS SEM DATA'), false);
  assertEquals(pareceSaudacaoSemPergunta('BOA NOITE, QUANTOS MEMBROS'), false);
});

Deno.test('conversaRequerRespostaImediata: cadastro e roteiro confirmacao', () => {
  assert(conversaRequerRespostaImediata({ fluxo_ativo: 'atualizacao_cadastral', etapa_atual: 'perguntando_campo' }));
  assert(conversaRequerRespostaImediata({ fluxo_ativo: 'roteiro_estudo', etapa_atual: 'aguardando_confirmacao' }));
  assert(conversaRequerRespostaImediata({ fluxo_ativo: 'relatorios', etapa_atual: 'aguardando_pedido' }));
  assertEquals(conversaRequerRespostaImediata(null), false);
  assertEquals(conversaRequerRespostaImediata({ fluxo_ativo: 'roteiro_estudo', etapa_atual: 'aguardando_texto' }), false);
});

Deno.test('debounceMensagemInbound: concatena mensagens na janela', async () => {
  limparBuffersDebounce();
  const flushed: string[] = [];

  const p1 = debounceMensagemInbound('contato-ficticio-teste', 'Bom dia', 80, async (t) => {
    flushed.push(t);
    return 'ok1';
  });

  await new Promise((r) => setTimeout(r, 20));
  debounceMensagemInbound('contato-ficticio-teste', 'quantos no culto?', 80, async (t) => {
    flushed.push(t);
    return 'ok2';
  });

  await p1;

  assertEquals(flushed.length, 1);
  assertEquals(flushed[0], 'Bom dia\nquantos no culto?');
  limparBuffersDebounce();
});

Deno.test('concatenarPartesDebounce junta com newline', () => {
  assertEquals(concatenarPartesDebounce(['Boa noite', 'quantos membros']), 'Boa noite\nquantos membros');
});

Deno.test('debounceMensagemInbound: telefones isolados', async () => {
  limparBuffersDebounce();
  const a: string[] = [];
  const b: string[] = [];

  const pa = debounceMensagemInbound('111', 'msg A', 60, async (t) => { a.push(t); return 1; });
  const pb = debounceMensagemInbound('222', 'msg B', 60, async (t) => { b.push(t); return 2; });

  await Promise.all([pa, pb]);
  assertEquals(a, ['msg A']);
  assertEquals(b, ['msg B']);
  limparBuffersDebounce();
});
