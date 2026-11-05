-- Migration 0008: banco de perguntas não respondidas pelo bot WhatsApp
-- Captura automática quando o bot envia fallback "não consegui responder".
-- Revisão humana + sugestão IA no painel (Comunicação).

CREATE TABLE IF NOT EXISTS whatsapp_perguntas_nao_respondidas (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  telefone TEXT NOT NULL,
  pessoa_id TEXT REFERENCES pessoas(id) ON DELETE SET NULL,
  pessoa_nome TEXT,
  pergunta TEXT NOT NULL,
  resposta_bot TEXT NOT NULL,
  resposta_bruta TEXT,
  motivo TEXT NOT NULL DEFAULT 'fallback_bot',
  intent_router TEXT,
  contexto TEXT CHECK (contexto IS NULL OR contexto IN ('gerencial', 'membro', 'pastoral', 'geral')),
  detalhes_json JSONB NOT NULL DEFAULT '{}',
  sugestao_ia TEXT,
  sugestao_ia_gerada_em TIMESTAMPTZ,
  resposta_editada TEXT,
  status TEXT NOT NULL DEFAULT 'pendente' CHECK (status IN ('pendente', 'sugestao_gerada', 'revisado', 'arquivado')),
  revisado_por TEXT,
  revisado_em TIMESTAMPTZ,
  notas_revisor TEXT
);

CREATE INDEX IF NOT EXISTS idx_whatsapp_perguntas_nr_status
  ON whatsapp_perguntas_nao_respondidas (status, criado_em DESC);

CREATE INDEX IF NOT EXISTS idx_whatsapp_perguntas_nr_telefone
  ON whatsapp_perguntas_nao_respondidas (telefone, criado_em DESC);

ALTER TABLE whatsapp_perguntas_nao_respondidas ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated_full_access" ON whatsapp_perguntas_nao_respondidas
  FOR ALL
  USING (auth.role() = 'authenticated')
  WITH CHECK (auth.role() = 'authenticated');

COMMENT ON TABLE whatsapp_perguntas_nao_respondidas IS
  'Perguntas ao bot WhatsApp que receberam resposta de fallback; fila de revisão com sugestão IA e correção humana.';
