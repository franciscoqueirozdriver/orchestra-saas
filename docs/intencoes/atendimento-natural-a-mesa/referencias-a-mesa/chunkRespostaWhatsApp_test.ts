/// <reference lib="deno.ns" />
import { assert, assertEquals } from 'https://deno.land/std@0.224.0/assert/mod.ts';
import { dividirRespostaWhatsApp } from './chunkRespostaWhatsApp.ts';

Deno.test('chunk: prefere quebra por linha, não no meio do nome', () => {
  const linhas = [
    'Temos:',
    '• 7 membros Kids I:',
    '• Laís Lourenço Souza, 3a — Pai: Victor Souza',
    '• Lívia Lourenço Souza, 11a — Pai: Victor Souza',
    '• 11 membros Kids II:',
    '• Maria Alice Jacinto Maciel, 9a — Pai: Eugenito',
  ];
  const texto = linhas.join('\n');
  const partes = dividirRespostaWhatsApp(texto, 120);
  assert(partes.length >= 2);
  for (const p of partes) {
    assert(!p.endsWith('Souz'), `parte cortou nome: ${p.slice(-40)}`);
    assert(!/^a, \d+a/.test(p.trim()), `parte começa com resto de nome: ${p.slice(0, 30)}`);
  }
});

Deno.test('chunk: parágrafos de faixa tendem a ficar em partes separadas', () => {
  const kidsI = '7 membros Kids I (3 a 6 anos):\n\n' + '• Criança, 5a — Pai: Fulano\n'.repeat(7);
  const kidsII = '11 membros Kids II (7 a 12 anos):\n\n' + '• Criança, 9a — Pai: Fulano\n'.repeat(11);
  const texto = `Temos:\n\n${kidsI}\n\n${kidsII}\n\n(125 sem data de nascimento não entraram nesse recorte.)`;
  const partes = dividirRespostaWhatsApp(texto, 400);
  assert(partes.length >= 2);
  assert(partes[0].includes('Kids I'));
  assert(partes.some((p) => p.includes('sem data de nascimento')));
  assert(!partes[0].includes('sem data de nascimento'), 'aviso no rodapé, não na parte 1');
});
