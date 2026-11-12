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


def generate_with_fallback(db, agent, conversation, instructions, history, *, client=complete, revision=None,
                           response_validator=None):
    revision = conversation.revision if revision is None else revision
    serialized = json.dumps({"instructions":instructions,"history":history},ensure_ascii=False,sort_keys=True,separators=(",",":"))
    fingerprint = sha256(serialized.encode()).hexdigest()
    run = db.query(ModelRun).filter(ModelRun.tenant_id==agent.tenant_id,ModelRun.conversation_id==conversation.id,ModelRun.revision==revision).order_by(ModelRun.created_at.desc()).first()
    if run is None:
        run = ModelRun(tenant_id=agent.tenant_id,conversation_id=conversation.id,agent_id=agent.id,revision=revision,context_hash=fingerprint,context_snapshot_encrypted=encrypt_secret(serialized),attempts=[],status="running")
        db.add(run); db.commit()
    if run.agent_id != agent.id or run.context_hash != fingerprint:
        raise LLMError("Contexto ou agente mudou; aguarde nova revisão", category="stale_context")
    snapshot = json.loads(decrypt_secret(run.context_snapshot_encrypted))
    invalid_cached_config = None
    invalid_response_seen = False
    if run.status=="succeeded" and run.response_encrypted:
        cached_response = decrypt_secret(run.response_encrypted)
        try:
            if response_validator:
                response_validator(cached_response)
        except LLMError as exc:
            if not exc.permits_fallback:
                raise
            invalid_response_seen = True
            invalid_cached_config = run.selected_config_id
            attempts = list(run.attempts or [])
            for index in range(len(attempts)-1, -1, -1):
                previous_attempt = attempts[index]
                if previous_attempt.get("config_id") == invalid_cached_config and previous_attempt.get("result") == "succeeded":
                    attempts[index] = {**previous_attempt,"result":exc.category,"failure_stage":"response_validation"}
                    break
            run.attempts = attempts
            run.status = "trying_alternatives"
            db.commit()
        else:
            return cached_response
    # Never silently replace the snapshot during a retry or model switch.
    candidates = candidate_configs(db,agent)
    if not candidates: raise LLMError("Configure ao menos uma conexão de IA habilitada",category="configuration")
    for config in candidates:
        if config.id == invalid_cached_config:
            continue
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
            if exc.category == "invalid_response":
                invalid_response_seen = True
            config.last_error_category=exc.category
            if exc.category in {"quota","authentication","rate_limit","unavailable"}:
                base = {"quota":3600,"authentication":3600,"rate_limit":60,"unavailable":30}[exc.category]
                config.cooldown_until = now+timedelta(seconds=max(base,exc.retry_after))
            run.attempts = (run.attempts or [])+[attempt]
            run.status="trying_alternatives" if exc.permits_fallback else "failed"
            db.commit()
            if not exc.permits_fallback: raise
            continue
        if response_validator:
            try:
                response_validator(answer)
            except LLMError as exc:
                attempt["result"] = exc.category
                attempt["failure_stage"] = "response_validation"
                run.attempts = (run.attempts or [])+[attempt]
                run.status = "trying_alternatives"
                db.commit()
                if not exc.permits_fallback:
                    run.status = "failed"
                    db.commit()
                    raise
                invalid_response_seen = True
                continue
        attempt["result"]="succeeded"
        run.attempts=(run.attempts or [])+[attempt]
        run.selected_config_id=config.id;run.status="succeeded"
        run.response_encrypted=encrypt_secret(answer)
        config.last_error_category=None;config.cooldown_until=None
        db.commit()
        return answer
    run.status="exhausted";db.commit()
    if invalid_response_seen:
        raise LLMError("Nenhum modelo retornou uma resposta válida para o contrato da conversa",category="invalid_response")
    raise LLMError("Nenhum modelo da cadeia está disponível; contexto preservado para nova tentativa",category="unavailable")
