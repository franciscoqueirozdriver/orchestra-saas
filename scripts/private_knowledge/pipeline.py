"""Private offline WhatsApp staging. No application database, HTTP, embeddings or publish path."""
import argparse
import hashlib
import fcntl
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
import time
from datetime import datetime, timezone

VERSION = 'whatsapp-local-v1'
REPO = Path(__file__).resolve().parents[2]
AUDIO = {'.opus', '.ogg', '.mp3', '.m4a', '.wav', '.aac', '.flac'}
VIDEO = {'.mp4', '.mov', '.mkv', '.webm', '.3gp', '.avi'}
TEXT = {'.txt', '.md'}
# Android and iOS exports, day-first date retained verbatim: no guessed timezone/year.
HEADER = re.compile(r'^\[?(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APap][Mm])?)\]?\s*(?:-\s*)?(.*)$')
MEDIA = re.compile(r'(?:<anexado:\s*([^>]+)>|<attached:\s*([^>]+)>|([^\n<>]+?)\s*\((?:arquivo anexado|file attached)\))', re.I)

def private_path(path):
    path = Path(path).expanduser().absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Symlinks não permitidos')
    resolved = path.resolve()
    if resolved == REPO or REPO in resolved.parents:
        raise ValueError('Resultados devem ficar fora do repositório')
    return resolved


def connect(path):
    path = private_path(path)
    os.umask(0o077)
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if path.exists() and path.stat().st_mode & 0o077:
        raise ValueError('Banco existente deve ter permissão 600')
    db = sqlite3.connect(path, timeout=30)
    os.chmod(path, 0o600)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript((Path(__file__).parent / 'migrations/0001_private.sql').read_text())
    return db


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def paths(root):
    root = Path(root).absolute()
    if any(p.is_symlink() for p in (root, *root.parents)) or not root.is_dir():
        raise ValueError('Fonte inválida')
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not (Path(directory)/d).is_symlink())
        for name in sorted(names):
            p = Path(directory)/name
            if not p.is_symlink() and p.is_file():
                yield p


def parse_export(text):
    messages, current = [], None
    for line in text.lstrip('\ufeff').splitlines():
        line = line.lstrip('\u200e\u200f')
        match = HEADER.match(line)
        if match:
            rest = match[2]
            author, sep, body = rest.partition(': ')
            current = {'date_raw': match[1], 'author': author if sep else None,
                       'body': body if sep else rest, 'system': int(not sep)}
            messages.append(current)
        elif current is not None:
            current['body'] += '\n' + line
        elif line.strip():
            # Keep preamble, do not assign it to a person or invent a date.
            current = {'date_raw': None, 'author': None, 'body': line, 'system': 1}
            messages.append(current)
    return messages


def kind(path):
    ext = path.suffix.lower()
    return 'audio' if ext in AUDIO else 'video' if ext in VIDEO else 'text' if ext in TEXT else 'attachment'


def ingest(db, root, company, max_exports=None, export_relative=None):
    if not company.strip():
        raise ValueError('Empresa obrigatória')
    root = Path(root).absolute()
    files = list(paths(root))
    for path in files:
        db.execute('INSERT OR IGNORE INTO sources(company,root,relative_path,sha256,version,kind,status) VALUES(?,?,?,?,?,?,?)',
                   (company,str(root),str(path.relative_to(root)),file_hash(path),VERSION,kind(path),'inventoried'))
    db.commit()
    rows = db.execute('SELECT * FROM sources WHERE company=? AND root=? AND version=? ORDER BY relative_path,id', (company,str(root),VERSION)).fetchall()
    # Only current file versions participate; historical revisions stay auditable.
    current = [r for r in rows if (root/r['relative_path']).is_file() and file_hash(root/r['relative_path']) == r['sha256']]
    imported = 0
    for source in current:
        if export_relative is not None and source['relative_path'] != export_relative:
            continue
        if source['kind'] != 'text' or Path(source['relative_path']).suffix.lower() != '.txt':
            continue
        if max_exports is not None and imported >= max_exports:
            break
        imported += 1
        if source['status'] == 'parsed':
            continue
        try:
            text = (root/source['relative_path']).read_text(encoding='utf-8-sig', errors='strict')
            parsed = parse_export(text)
            with db:
                for ordinal, message in enumerate(parsed):
                    db.execute('INSERT OR IGNORE INTO messages(source_id,ordinal,date_raw,author,body,system) VALUES(?,?,?,?,?,?)',
                        (source['id'],ordinal,message['date_raw'],message['author'],message['body'],message['system']))
                    message_id = db.execute('SELECT id FROM messages WHERE source_id=? AND ordinal=?',(source['id'],ordinal)).fetchone()[0]
                    refs = {next(v.strip().strip('\u200e\u200f\u202a\u202c').strip() for v in m.groups() if v) for m in MEDIA.finditer(message['body'])}
                    # Bare filenames only link when literally present, never from chronological proximity.
                    refs.update(Path(r['relative_path']).name for r in current if r['kind'] != 'text' and message['body'].strip() == Path(r['relative_path']).name)
                    if re.search(r'<(?:Mídia oculta|Media omitted)>',message['body'],re.I):
                        db.execute('INSERT OR IGNORE INTO attachments VALUES(?,NULL,?,?)',(message_id,'[media omitted]','omitted'))
                    for ref in refs:
                        candidates = [r for r in current if Path(r['relative_path']).name == ref and Path(r['relative_path']).parent == Path(source['relative_path']).parent]
                        elsewhere = [r for r in current if Path(r['relative_path']).name == ref]
                        state = 'linked' if len(candidates) == 1 else 'ambiguous' if len(candidates)>1 or len(elsewhere)>1 else 'missing'
                        db.execute('INSERT OR IGNORE INTO attachments VALUES(?,?,?,?)',(message_id,candidates[0]['id'] if len(candidates)==1 else None,ref,state))
                db.execute('UPDATE sources SET status=?,error=NULL WHERE id=?',('parsed',source['id']))
        except (UnicodeError, OSError):
            with db:
                db.execute('UPDATE sources SET status=?,error=? WHERE id=?',('error','text_decode_or_io',source['id']))
    return {'sources':len(current),'exports_selected':imported}


def transcribe(db, source_id, company, model_path, model_name='tiny', threads=2):
    # Single local writer survives crashes via OS lock; no stale lease or double inference.
    lock_path = private_path(db.execute('PRAGMA database_list').fetchone()[2]).with_suffix('.lock')
    with lock_path.open('a') as lock:
        os.chmod(lock_path, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _transcribe(db, source_id, company, model_path, model_name, threads)


def _transcribe(db, source_id, company, model_path, model_name='tiny', threads=2):
    row = db.execute('SELECT * FROM sources WHERE id=? AND company=?',(source_id,company)).fetchone()
    if not row or row['kind'] not in {'audio','video'}:
        raise ValueError('Mídia inexistente nesta empresa')
    source = Path(row['root'])/row['relative_path']
    if source not in list(paths(Path(row['root']))) or file_hash(source) != row['sha256']:
        raise ValueError('Fonte alterada ou insegura; reinvente antes')
    model_path = private_path(model_path)
    if not model_path.is_dir():
        raise ValueError('Modelo local ausente')
    # Cache identity includes every model artifact; changed weights cannot reuse old output.
    ffmpeg_version = subprocess.check_output(['ffmpeg','-version'],text=True).splitlines()[0]
    model_files = [p for p in paths(model_path) if '.cache' not in p.relative_to(model_path).parts]
    model_hash = hashlib.sha256(''.join(str(p.relative_to(model_path))+file_hash(p) for p in model_files).encode()).hexdigest()
    import importlib.metadata
    recipe = f'{VERSION}:faster-whisper-{importlib.metadata.version("faster-whisper")}:{model_name}:{model_hash}:cpu:int8:pt:beam1:vad0:ffmpeg16k:{ffmpeg_version}'
    with db:
        db.execute('INSERT OR IGNORE INTO transcriptions(source_id,recipe,status) VALUES(?,?,?)',(source_id,recipe,'pending'))
    job = db.execute('SELECT * FROM transcriptions WHERE source_id=? AND recipe=?',(source_id,recipe)).fetchone()
    if job['status']=='done':
        return {'status':'reused','id':job['id']}
    started=time.monotonic()
    with db:
        db.execute('UPDATE transcriptions SET status=?,error=NULL WHERE id=?',('processing',job['id']))
    try:
        os.environ['HF_HUB_OFFLINE']='1'
        os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
        from faster_whisper import WhisperModel
        with tempfile.TemporaryDirectory(prefix='orchestra-audio-', dir=str(private_path(db.execute('PRAGMA database_list').fetchone()[2]).parent)) as folder:
            wav=Path(folder)/'audio.wav'
            subprocess.run(['ffmpeg','-nostdin','-v','error','-protocol_whitelist','file,pipe','-i',str(source),'-vn','-ac','1','-ar','16000',str(wav)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=600)
            model=WhisperModel(str(model_path),device='cpu',compute_type='int8',cpu_threads=threads,num_workers=1,local_files_only=True)
            segments, info=model.transcribe(str(wav),language='pt',beam_size=1,vad_filter=False,condition_on_previous_text=False)
            with db:
                db.execute('DELETE FROM segments WHERE transcription_id=?',(job['id'],))
                for i,s in enumerate(segments):
                    db.execute('INSERT INTO segments VALUES(?,?,?,?,?,?,?)',(job['id'],i,s.start,s.end,s.text,s.avg_logprob,s.no_speech_prob))
                db.execute('UPDATE transcriptions SET status=?,duration=?,elapsed=?,language=? WHERE id=?',('done',info.duration,time.monotonic()-started,info.language,job['id']))
        return {'status':'done','id':job['id'],'elapsed':round(time.monotonic()-started,2)}
    except Exception as exc:
        # Persist a class, never ffmpeg stderr, transcript or source path in logs.
        with db:
            db.execute('UPDATE transcriptions SET status=?,error=?,elapsed=? WHERE id=?',('error',type(exc).__name__,time.monotonic()-started,job['id']))
        return {'status':'error','id':job['id'],'error_class':type(exc).__name__}


def reconstruct(db, company):
    result=[]
    for message in db.execute('SELECT m.* FROM messages m JOIN sources s ON s.id=m.source_id WHERE s.company=? ORDER BY m.source_id,m.ordinal',(company,)):
        item=dict(message); item['attachments']=[]
        for link in db.execute('SELECT * FROM attachments WHERE message_id=?',(message['id'],)):
            media=dict(link)
            job=db.execute("SELECT id,recipe FROM transcriptions WHERE source_id=? AND status='done' ORDER BY id DESC LIMIT 1",(link['source_id'],)).fetchone()
            media['segments']=[dict(s) for s in db.execute('SELECT start,end,text,avg_logprob,no_speech_prob FROM segments WHERE transcription_id=? ORDER BY ordinal',(job['id'],))] if job else []
            media['transcription_id']=job['id'] if job else None
            media['processing_recipe']=job['recipe'] if job else None
            media['human_review_required']=True
            media['low_confidence_segments']=sum(s['avg_logprob'] is not None and s['avg_logprob'] < -1 for s in media['segments'])
            media['visual_interpretation']=False
            item['attachments'].append(media)
        result.append(item)
    return result


def redact(text, names=()):
    # Conservative aids, not an anonymization guarantee. Human review still mandatory.
    for name in sorted(set(names),key=len,reverse=True):
        if name:
            text=re.sub(re.escape(name),'[PESSOA]',text,flags=re.I)
    patterns=[(r'https?://\S+','[LINK]'),(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}','[EMAIL]'),
              (r'\+?\d[\d\s()./-]{6,}\d','[NUMERO]')]
    for pattern,replacement in patterns:
        text=re.sub(pattern,replacement,text)
    return text


def propose(db, company, ids, category, text):
    if category not in {'fact','example'} or not ids or not text.strip():
        raise ValueError('Proposta exige categoria, texto e mensagens de origem')
    rows=db.execute('SELECT m.id,m.author FROM messages m JOIN sources s ON s.id=m.source_id WHERE s.company=? AND m.id IN ('+','.join('?' for _ in ids)+')',(company,*ids)).fetchall()
    if {r['id'] for r in rows} != set(ids):
        raise ValueError('Origem pertence a outra empresa ou não existe')
    names=[r[0] for r in db.execute('SELECT DISTINCT m.author FROM messages m JOIN sources s ON s.id=m.source_id WHERE s.company=? AND m.author IS NOT NULL',(company,))]
    clean=redact(text,names)
    with db:
        db.execute('INSERT OR IGNORE INTO proposals(company,kind,text,redaction_version) VALUES(?,?,?,?)',(company,category,clean,'regex-v1-human-review-required'))
        pid=db.execute('SELECT id FROM proposals WHERE company=? AND kind=? AND text=?',(company,category,clean)).fetchone()[0]
        existing={r[0] for r in db.execute('SELECT message_id FROM proposal_messages WHERE proposal_id=?',(pid,))}
        if set(ids)-existing:
            db.execute("UPDATE proposals SET status='pending_review',reviewer=NULL,reviewed_at=NULL,valid_until=NULL WHERE id=?",(pid,))
        db.executemany('INSERT OR IGNORE INTO proposal_messages VALUES(?,?)',[(pid,i) for i in ids])
    return pid


def approve(db, company, pid, reviewer, confirmed, valid_until=None):
    row=db.execute('SELECT * FROM proposals WHERE id=? AND company=?',(pid,company)).fetchone()
    if not row or company=='unassigned' or not reviewer.strip() or not confirmed:
        raise ValueError('Exige empresa atribuída, revisor e confirmação de revisão pessoal/factual')
    if row['kind']=='fact':
        if not valid_until or datetime.fromisoformat(valid_until).date() <= datetime.now(timezone.utc).date():
            raise ValueError('Conhecimento factual exige validade futura confirmada')
    with db:
        db.execute('UPDATE proposals SET status=?,reviewer=?,reviewed_at=?,valid_until=? WHERE id=?',('approved_local',reviewer,datetime.now(timezone.utc).isoformat(),valid_until,pid))
    # There is deliberately no bridge to KnowledgeChunk/indexed or to external APIs.


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',required=True,type=Path)
    parser.add_argument('--company',required=True)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('ingest');p.add_argument('root',type=Path);p.add_argument('--max-exports',type=int,default=1);p.add_argument('--export-relative')
    p=sub.add_parser('transcribe');p.add_argument('--source-id',type=int,required=True);p.add_argument('--model-path',type=Path,required=True)
    p=sub.add_parser('propose');p.add_argument('--message-id',action='append',type=int,required=True);p.add_argument('--kind',choices=['fact','example'],required=True);p.add_argument('--text-file',type=Path,required=True)
    p=sub.add_parser('approve');p.add_argument('--proposal-id',type=int,required=True);p.add_argument('--reviewer',required=True);p.add_argument('--confirm-personal-and-factual-review',action='store_true');p.add_argument('--valid-until')
    p=sub.add_parser('reconstruct');p.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();os.umask(0o077)
    with connect(args.db) as db:
        if args.command=='ingest':
            if args.max_exports < 1: parser.error('Limite positivo obrigatório')
            result=ingest(db,args.root,args.company,args.max_exports,args.export_relative)
        elif args.command=='transcribe':result=transcribe(db,args.source_id,args.company,args.model_path)
        elif args.command=='propose':
            result={'proposal_id':propose(db,args.company,args.message_id,args.kind,private_path(args.text_file).read_text(encoding='utf-8')),'status':'pending_review'}
        elif args.command=='approve':
            approve(db,args.company,args.proposal_id,args.reviewer,args.confirm_personal_and_factual_review,args.valid_until)
            result={'status':'approved_local','indexed':False}
        else:
            out=private_path(args.output);out.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            with out.open('x',encoding='utf-8') as stream:json.dump(reconstruct(db,args.company),stream,ensure_ascii=False,indent=2)
            result={'saved_private':True}
    print(json.dumps(result))

if __name__=='__main__':main()
