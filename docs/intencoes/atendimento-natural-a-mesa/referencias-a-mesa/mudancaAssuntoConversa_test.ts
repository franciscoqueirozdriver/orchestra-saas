/// <reference lib="deno.ns" />
import { assert, assertEquals } from 'https://deno.land/std@0.224.0/assert/mod.ts';
import {
  avaliarProtecaoMudancaAssunto,
  mensagemValidaParaFluxoAtivo,
  pareceAssuntoExternoAoFluxo,
} from './mudancaAssuntoConversa.ts';

const CONV_CADASTRO_ESCOLHENDO = {
  id: 'c1',
  fluxo_ativo: 'atualizacao_cadastral',
  etapa_atual: 'escolhendo_campo',
  contexto_json: { aguardando_alteracao: true, nome: 'Francisco' },
  atualizado_em: new Date().toISOString(),
};

const CONV_CADASTRO_ENDERECO = {
  id: 'c2',
  fluxo_ativo: 'atualizacao_cadastral',
  etapa_atual: 'perguntando_campo',
  contexto_json: { campo_atual: 'endereco', nome: 'Francisco' },
  atualizado_em: new Date().toISOString(),
};

Deno.test('G29: boa tarde durante cadastro → gate, não valor de campo', () => {
  const input = {
    conversa: CONV_CADASTRO_ESCOLHENDO,
    textoRecebido: 'boa tarde!',
    textoNorm: 'BOA TARDE',
    autorizadoGerencial: true,
  };
  assertEquals(mensagemValidaParaFluxoAtivo(input), false);
  assert(pareceAssuntoExternoAoFluxo(input));
  assertEquals(avaliarProtecaoMudancaAssunto(input).acao, 'gate');
});

Deno.test('G29b: mudar endereço durante escolhendo_campo → segue fluxo', () => {
  const input = {
    conversa: CONV_CADASTRO_ESCOLHENDO,
    textoRecebido: 'quero mudar meu endereço',
    textoNorm: 'QUERO MUDAR MEU ENDERECO',
    autorizadoGerencial: false,
  };
  assertEquals(mensagemValidaParaFluxoAtivo(input), true);
  assertEquals(avaliarProtecaoMudancaAssunto(input).acao, 'seguir_fluxo');
});

Deno.test('G29c: consulta gerencial autorizada durante cadastro → gate', () => {
  const input = {
    conversa: CONV_CADASTRO_ESCOLHENDO,
    textoRecebido: 'quantas mulheres temos?',
    textoNorm: 'QUANTAS MULHERES TEMOS?',
    autorizadoGerencial: true,
  };
  assert(pareceAssuntoExternoAoFluxo(input));
  assertEquals(avaliarProtecaoMudancaAssunto(input).acao, 'gate');
});

Deno.test('G29d: endereço real durante perguntando_campo → segue fluxo', () => {
  const input = {
    conversa: CONV_CADASTRO_ENDERECO,
    textoRecebido: 'Rua Nova, 123',
    textoNorm: 'RUA NOVA, 123',
    autorizadoGerencial: false,
  };
  assertEquals(mensagemValidaParaFluxoAtivo(input), true);
  assertEquals(avaliarProtecaoMudancaAssunto(input).acao, 'seguir_fluxo');
});

Deno.test('G29e: reconsulta status cadastro → auto_nova', () => {
  const input = {
    conversa: CONV_CADASTRO_ESCOLHENDO,
    textoRecebido: 'verifique se meu cadastro está atualizado',
    textoNorm: 'VERIFIQUE SE MEU CADASTRO ESTA ATUALIZADO',
    autorizadoGerencial: true,
  };
  assertEquals(avaliarProtecaoMudancaAssunto(input).acao, 'auto_nova');
});

const CONV_RELATORIOS = {
  id: 'r1',
  fluxo_ativo: 'relatorios',
  etapa_atual: 'aguardando_pedido',
  contexto_json: { nome: 'Alessandra' },
  atualizado_em: new Date().toISOString(),
};

Deno.test('relatórios: pedido em linguagem natural segue o fluxo', () => {
  const input = {
    conversa: CONV_RELATORIOS,
    textoRecebido: 'contatos dos membros',
    textoNorm: 'CONTATOS DOS MEMBROS',
    autorizadoGerencial: true,
  };
  assertEquals(mensagemValidaParaFluxoAtivo(input), true);
  assertEquals(avaliarProtecaoMudancaAssunto(input).acao, 'seguir_fluxo');
});

Deno.test('relatórios: catálogo "quais você tem" segue o fluxo (não gate)', () => {
  const input = {
    conversa: CONV_RELATORIOS,
    textoRecebido: 'Quais você tem?',
    textoNorm: 'QUAIS VOCE TEM',
    autorizadoGerencial: true,
  };
  assertEquals(mensagemValidaParaFluxoAtivo(input), true);
  assertEquals(avaliarProtecaoMudancaAssunto(input).acao, 'seguir_fluxo');
});

Deno.test('relatórios: pessoas por mesa segue o fluxo', () => {
  const input = {
    conversa: CONV_RELATORIOS,
    textoRecebido: 'Relatório de pessoas por mesa',
    textoNorm: 'RELATORIO DE PESSOAS POR MESA',
    autorizadoGerencial: true,
  };
  assertEquals(mensagemValidaParaFluxoAtivo(input), true);
  assertEquals(avaliarProtecaoMudancaAssunto(input).acao, 'seguir_fluxo');
});

Deno.test('relatórios: pergunta fora do menu → gate CONTINUAR/NOVA', () => {
  const input = {
    conversa: CONV_RELATORIOS,
    textoRecebido: 'quem é o líder da Mesa Betim?',
    textoNorm: 'QUEM E O LIDER DA MESA BETIM?',
    autorizadoGerencial: true,
  };
  assertEquals(mensagemValidaParaFluxoAtivo(input), false);
  assertEquals(avaliarProtecaoMudancaAssunto(input).acao, 'gate');
});

Deno.test('relatórios: saudação fora do menu → gate', () => {
  const input = {
    conversa: CONV_RELATORIOS,
    textoRecebido: 'boa tarde',
    textoNorm: 'BOA TARDE',
    autorizadoGerencial: true,
  };
  assertEquals(avaliarProtecaoMudancaAssunto(input).acao, 'gate');
});

Deno.test('Iniciar Relatórios durante cadastro → gate (não mistura fluxos)', () => {
  const input = {
    conversa: CONV_CADASTRO_ESCOLHENDO,
    textoRecebido: 'Iniciar Relatórios',
    textoNorm: 'INICIAR RELATORIOS',
    autorizadoGerencial: true,
  };
  assert(pareceAssuntoExternoAoFluxo(input));
  assertEquals(avaliarProtecaoMudancaAssunto(input).acao, 'gate');
});
