// Divisão de respostas longas para WhatsApp (referência: gpt-chatbot-boilerplate chunking)

const MAX_CHARS_PADRAO = Number(Deno.env.get('WHATSAPP_REPLY_CHUNK_SIZE') || '1500');

function dividirLinhaLonga(linha: string, maxChars: number): string[] {
  if (linha.length <= maxChars) return [linha];
  const partes: string[] = [];
  let resto = linha;
  while (resto.length > maxChars) {
    let corte = resto.lastIndexOf(' ', maxChars);
    if (corte <= 0) corte = maxChars;
    partes.push(resto.slice(0, corte).trim());
    resto = resto.slice(corte).trimStart();
  }
  if (resto) partes.push(resto);
  return partes;
}

function empacotarLinhas(linhas: string[], maxChars: number): string[] {
  const blocos: string[] = [];
  let atual = '';
  for (const linha of linhas) {
    const candidato = atual ? `${atual}\n${linha}` : linha;
    if (candidato.length <= maxChars) {
      atual = candidato;
      continue;
    }
    if (atual) blocos.push(atual.trim());
    if (linha.length <= maxChars) {
      atual = linha;
    } else {
      blocos.push(...dividirLinhaLonga(linha, maxChars));
      atual = '';
    }
  }
  if (atual.trim()) blocos.push(atual.trim());
  return blocos;
}

export function dividirRespostaWhatsApp(texto: string, maxChars = MAX_CHARS_PADRAO): string[] {
  if (!texto?.trim()) return [];
  const t = texto.trim();
  if (t.length <= maxChars) return [t];

  const paragrafos = t.split(/\n\n+/);
  const blocos: string[] = [];
  let atual = '';

  for (const p of paragrafos) {
    const candidato = atual ? `${atual}\n\n${p}` : p;
    if (candidato.length <= maxChars) {
      atual = candidato;
      continue;
    }
    if (atual) blocos.push(atual.trim());
    if (p.length <= maxChars) {
      atual = p;
      continue;
    }
    const linhas = p.split('\n');
    if (linhas.length > 1) {
      blocos.push(...empacotarLinhas(linhas, maxChars));
      atual = '';
      continue;
    }
    blocos.push(...dividirLinhaLonga(p, maxChars));
    atual = '';
  }
  if (atual.trim()) blocos.push(atual.trim());
  return blocos.filter(Boolean);
}

export function aplicarCabecalhoPartes(partes: string[]): string[] {
  if (partes.length <= 1) return partes;
  return partes.map((p, i) => `(Parte ${i + 1}/${partes.length})\n\n${p}`);
}

export function prepararPartesRespostaWhatsApp(texto: string, maxChars = MAX_CHARS_PADRAO): string[] {
  return aplicarCabecalhoPartes(dividirRespostaWhatsApp(texto, maxChars));
}

/** Intervalo humanizado entre bolhas — uniforme entre min e max (default 4–8s). */
export function calcularIntervaloEntrePartesWhatsApp(): number {
  const minMs = Number(Deno.env.get('WHATSAPP_CHUNK_PART_DELAY_MIN_MS') || '4000');
  const maxMs = Number(Deno.env.get('WHATSAPP_CHUNK_PART_DELAY_MAX_MS') || '8000');
  const lo = Math.min(minMs, maxMs);
  const hi = Math.max(minMs, maxMs);
  if (lo === hi) return lo;
  return lo + Math.floor(Math.random() * (hi - lo + 1));
}

/** Acumula atrasos aleatórios por parte (1ª parte = imediata). */
export function agendarHorariosPartesWhatsApp(totalPartes: number, inicioMs = Date.now()): Date[] {
  if (totalPartes <= 0) return [];
  const horarios: Date[] = [new Date(inicioMs)];
  let acumulado = inicioMs;
  for (let i = 1; i < totalPartes; i++) {
    acumulado += calcularIntervaloEntrePartesWhatsApp();
    horarios.push(new Date(acumulado));
  }
  return horarios;
}

const LIMITE_LINHAS_POR_PARTE = 15;

/** Lista longa → várias mensagens "(Parte i/n)" com N linhas cada. */
export function formatarListaEmPartes(
  cabecalho: string,
  linhas: string[],
  rodape?: string,
  limitePorParte = LIMITE_LINHAS_POR_PARTE,
): string[] {
  if (linhas.length === 0) {
    let msg = cabecalho;
    if (rodape) msg += `\n\n${rodape}`;
    return [msg];
  }
  if (linhas.length <= limitePorParte) {
    let msg = `${cabecalho}\n\n${linhas.join('\n')}`;
    if (rodape) msg += `\n\n${rodape}`;
    return [msg];
  }
  const nPartes = Math.ceil(linhas.length / limitePorParte);
  const partes: string[] = [];
  for (let i = 0; i < nPartes; i++) {
    const slice = linhas.slice(i * limitePorParte, (i + 1) * limitePorParte);
    let msg = `(Parte ${i + 1}/${nPartes})\n\n${cabecalho}\n\n${slice.join('\n')}`;
    if (i === nPartes - 1 && rodape) msg += `\n\n${rodape}`;
    partes.push(msg);
  }
  return partes;
}
