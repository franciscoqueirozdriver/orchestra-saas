-- Buffer de debounce inbound WhatsApp — agrupa mensagens rápidas do mesmo telefone entre instâncias Edge.
-- PO OK 30/08/2026

CREATE TABLE IF NOT EXISTS whatsapp_debounce_inbound (
  telefone TEXT PRIMARY KEY,
  partes JSONB NOT NULL DEFAULT '[]'::jsonb,
  flush_at TIMESTAMPTZ NOT NULL,
  atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_whatsapp_debounce_flush
  ON whatsapp_debounce_inbound (flush_at);

ALTER TABLE whatsapp_debounce_inbound ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_full_access_debounce_inbound"
  ON whatsapp_debounce_inbound FOR ALL
  USING (true) WITH CHECK (true);

-- Append atômico + estende janela
CREATE OR REPLACE FUNCTION public.whatsapp_debounce_acumular(
  p_telefone text,
  p_texto text,
  p_janela_ms integer DEFAULT 2500
) RETURNS timestamptz
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_flush timestamptz := now() + make_interval(secs => p_janela_ms / 1000.0);
BEGIN
  INSERT INTO whatsapp_debounce_inbound (telefone, partes, flush_at)
  VALUES (p_telefone, jsonb_build_array(p_texto), v_flush)
  ON CONFLICT (telefone) DO UPDATE SET
    partes = whatsapp_debounce_inbound.partes || jsonb_build_array(p_texto),
    flush_at = GREATEST(whatsapp_debounce_inbound.flush_at, v_flush),
    atualizado_em = now();
  RETURN (SELECT flush_at FROM whatsapp_debounce_inbound WHERE telefone = p_telefone);
END;
$$;

-- Claim atômico após janela — retorna partes ou null se ainda não expirou / outra instância ganhou
CREATE OR REPLACE FUNCTION public.whatsapp_debounce_claim(
  p_telefone text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_partes jsonb;
BEGIN
  DELETE FROM whatsapp_debounce_inbound
  WHERE telefone = p_telefone AND flush_at <= now()
  RETURNING partes INTO v_partes;
  IF v_partes IS NULL THEN
    RETURN NULL;
  END IF;
  RETURN jsonb_build_object('partes', v_partes);
END;
$$;
