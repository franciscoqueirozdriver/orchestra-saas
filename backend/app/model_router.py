"""Retry alternate models using one immutable, encrypted context snapshot per revision."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from app.llm_client import LLMError, complete
from app.models import LLMConfig, ModelRun
from app.security import decrypt_secret, encrypt_secret


def candidate_configs(db, agent):
    primary = agent.llm_config_id
    if not primary:
        default = db.query(LLMConfig).filter(LLMConfig.tenant_id==agent.tenant_id,LLMConfig.is_default.is_(True)).first()
        primary = default.id if default else None
    ids = list(dict.fromkeys(([primary] if primary else []) + (agent.fallback_config_ids or [])))
    rows = db.query(LLMConfig).filter(LLMConfig.tenant_id==agent.tenant_id, LLMConfig.id.in_(ids)).all() if ids else []
    by_id = {x.id:x for x in rows}
    return [by_id[x] for x in ids if x in by_id and by_id[x].enabled]


def generate_with_fallback(db, agent, conversation, instructions, history, *, client=complete):
    serialized = json.dumps({"instructions":instructions,"history":history},ensure_ascii=False,sort_keys=True,separators=(",",":"))
    fingerprint = sha256(serialized.encode()).hexdigest()
    run = db.query(ModelRun).filter(ModelRun.tenant_id==agent.tenant_id,ModelRun.conversation_id==conversation.id,ModelRun.revision==conversation.revision).order_by(ModelRun.created_at.desc()).first()
    if run is None:
        run = ModelRun(tenant_id=agent.tenant_id,conversation_id=conversation.id,agent_id=agent.id,revision=conversation.revision,context_hash=fingerprint,context_snapshot_encrypted=encrypt_secret(serialized),attempts=[],status="running")
        db.add(run); db.commit()
    snapshot = json.loads(decrypt_secret(run.context_snapshot_encrypted))
    if run.status=="succeeded" and run.response_encrypted:
        return decrypt_secret(run.response_encrypted)
    # Never silently replace the snapshot during a retry or model switch.
    candidates = candidate_configs(db,agent)
    if not candidates: raise LLMError("Configure ao menos uma conexão de IA habilitada",category="configuration")
    for config in candidates:
        now = datetime.now(timezone.utc)
        cooldown = config.cooldown_until
        if cooldown and cooldown.tzinfo is None: cooldown = cooldown.replace(tzinfo=timezone.utc)
        attempt = {"config_id":config.id,"provider":config.provider,"model":config.model,"context_hash":run.context_hash,"at":now.isoformat()}
        if cooldown and cooldown>now:
            attempt["result"]="cooldown"
            run.attempts = (run.attempts or [])+[attempt];db.commit()
            continue
        try:
            answer = client(config.provider,config.base_url,config.model,decrypt_secret(config.api_key_encrypted) or "",snapshot["instructions"],[dict(x) for x in snapshot["history"]],protocol=config.protocol,max_output_tokens=config.max_output_tokens)
        except LLMError as exc:
            attempt["result"]=exc.category
            attempt["http_status"]=exc.status_code
            config.last_error_category=exc.category
            if exc.category in {"quota","authentication","rate_limit","unavailable"}:
                base = {"quota":3600,"authentication":3600,"rate_limit":60,"unavailable":30}[exc.category]
                config.cooldown_until = now+timedelta(seconds=max(base,exc.retry_after))
            run.attempts = (run.attempts or [])+[attempt]
            run.status="trying_alternatives" if exc.permits_fallback else "failed"
            db.commit()
            if not exc.permits_fallback: raise
            continue
        attempt["result"]="succeeded"
        run.attempts=(run.attempts or [])+[attempt]
        run.selected_config_id=config.id;run.status="succeeded"
        run.response_encrypted=encrypt_secret(answer)
        config.last_error_category=None;config.cooldown_until=None
        db.commit()
        return answer
    run.status="exhausted";db.commit()
    raise LLMError("Nenhum modelo da cadeia está disponível; contexto preservado para nova tentativa",category="unavailable")
