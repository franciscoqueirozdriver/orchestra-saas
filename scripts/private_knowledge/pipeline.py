"""Private offline WhatsApp staging. No application database, HTTP, embeddings or publish path."""
import argparse
import csv
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
import unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

VERSION = 'whatsapp-local-v1'
REPO = Path(__file__).resolve().parents[2]
AUDIO = {'.opus', '.ogg', '.mp3', '.m4a', '.wav', '.aac', '.flac'}
VIDEO = {'.mp4', '.mov', '.mkv', '.webm', '.3gp', '.avi'}
IMAGE = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic'}
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
    version = db.execute('SELECT max(version) FROM schema_version').fetchone()[0] or 1
    if version < 2:
        db.executescript((Path(__file__).parent / 'migrations/0002_conversation_authors.sql').read_text())
        db.execute('INSERT OR IGNORE INTO schema_version VALUES(2)')
        db.commit()
        version = 2
    if version < 3:
        db.executescript((Path(__file__).parent / 'migrations/0003_author_roles.sql').read_text())
        db.execute('INSERT OR IGNORE INTO schema_version VALUES(3)')
        db.commit()
        version = 3
    if version < 4:
        db.executescript((Path(__file__).parent / 'migrations/0004_author_phone_evidence.sql').read_text())
        db.execute('INSERT OR IGNORE INTO schema_version VALUES(4)')
        db.commit()
    register_authors(db)
    register_contacts(db)
    register_author_contact_candidates(db)
    return db


def normalize_whatsapp_phone(value):
    digits = re.sub(r'\D', '', value or '')
    if len(digits) in {10, 11}:
        digits = '55' + digits
    if not digits.startswith('55') or len(digits) not in {12, 13}:
        return None
    ddd = int(digits[2:4])
    if not 11 <= ddd <= 99:
        return None
    return digits


def normalize_person_name(value):
    value = unicodedata.normalize('NFKD', value or '').encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '', value)


WHATSAPP_DATE_FORMATS = (
    '%d/%m/%Y, %H:%M:%S', '%d/%m/%Y %H:%M:%S',
    '%d/%m/%Y, %H:%M', '%d/%m/%Y %H:%M',
    '%d/%m/%y, %H:%M:%S', '%d/%m/%y %H:%M:%S',
    '%d/%m/%y, %H:%M', '%d/%m/%y %H:%M',
    '%d/%m/%y, %I:%M:%S %p', '%d/%m/%Y, %I:%M:%S %p',
    '%d/%m/%y %I:%M:%S %p', '%d/%m/%Y %I:%M:%S %p',
)


def parse_whatsapp_datetime(value, timezone_name):
    """Convert the original local wall time without dropping its source text."""
    zone = ZoneInfo(timezone_name)
    for pattern in WHATSAPP_DATE_FORMATS:
        try:
            local = datetime.strptime((value or '').strip(), pattern).replace(tzinfo=zone)
            return local.astimezone(timezone.utc)
        except ValueError:
            continue
    raise ValueError('Data de exportação sem formato reconhecido')


def parse_vcards(text):
    unfolded = re.sub(r'\r?\n[ \t]', '', text)
    cards=[]; current=None
    for line in unfolded.splitlines():
        line=line.strip()
        if line.upper() == 'BEGIN:VCARD':
            current={'name':'','phones':set()}
        elif line.upper() == 'END:VCARD':
            if current and current['name']:
                cards.append(current)
            current=None
        elif current is not None and ':' in line:
            prop,value=line.split(':',1)
            field=prop.split(';',1)[0].split('.')[-1].upper()
            value=re.sub(r'\\([\\,;nN])',lambda m: {'n':'\n','N':'\n'}.get(m.group(1),m.group(1)),value).strip()
            if field=='FN' and value:
                current['name']=value
            elif field=='TEL':
                phone=normalize_whatsapp_phone(value.replace('tel:',''))
                if phone: current['phones'].add(phone)
    return cards


def register_authors(db, source_id=None):
    """Give each raw author a stable ID within its source conversation.

    A matching display name in another export is deliberately not merged: names
    alone do not establish that two records are the same WhatsApp contact.
    """
    where = 'WHERE s.kind = ?'
    params = ['text']
    if source_id is not None:
        where += ' AND s.id = ?'
        params.append(source_id)
    rows = db.execute(f'''SELECT DISTINCT s.company, s.id source_id, m.author
        FROM sources s JOIN messages m ON m.source_id=s.id
        {where} AND m.author IS NOT NULL AND trim(m.author) != '' ''', params).fetchall()
    for row in rows:
        db.execute('''INSERT OR IGNORE INTO conversation_authors
            (company,source_id,display_name,link_status)
            VALUES(?,?,?,'unresolved')''',
            (row['company'], row['source_id'], row['author']))
    # A phone used as the WhatsApp export's author label identifies that sender
    # directly. Phone numbers merely mentioned in message text are not auto-linked.
    authors = db.execute("SELECT id,display_name FROM conversation_authors WHERE link_status='unresolved'").fetchall()
    for author in authors:
        phone = normalize_whatsapp_phone(author['display_name'])
        if phone:
            db.execute("UPDATE conversation_authors SET link_status='phone_identified',phone_e164=? WHERE id=?",
                       (phone, author['id']))
    identified=db.execute('''SELECT id,company,source_id,phone_e164 FROM conversation_authors
        WHERE phone_e164 IS NOT NULL''').fetchall()
    for author in identified:
        db.execute('''INSERT OR IGNORE INTO author_phone_evidence
            (company,source_id,author_id,message_id,phone_e164,evidence_type,status)
            VALUES(?,?,?,NULL,?,'author_label','confirmed')''',
            (author['company'],author['source_id'],author['id'],author['phone_e164']))
    db.execute('''UPDATE messages SET author_id=(
        SELECT a.id FROM conversation_authors a
        WHERE a.source_id=messages.source_id AND a.display_name=messages.author)
        WHERE author IS NOT NULL AND author_id IS NULL''')
    db.commit()
    return len(rows)


def register_contacts(db, company=None):
    """Import address-book cards into private staging, never into the app or Git."""
    query="SELECT id,company,root,relative_path,sha256 FROM sources WHERE lower(relative_path) LIKE '%.vcf'"
    params=[]
    if company is not None:
        query+=' AND company=?';params.append(company)
    for source in db.execute(query,params).fetchall():
        root=Path(source['root']).absolute()
        relative=Path(source['relative_path'])
        path=root/relative
        components=[root]
        for part in relative.parts:
            components.append(components[-1]/part)
        if relative.is_absolute() or '..' in relative.parts or any(p.is_symlink() for p in components):
            continue
        if not path.is_file() or file_hash(path)!=source['sha256']:
            continue
        try: cards=parse_vcards(path.read_text(encoding='utf-8-sig',errors='strict'))
        except (UnicodeError,OSError): continue
        for card in cards:
            phones=card['phones'] or {None}
            for phone in phones:
                key=hashlib.sha256((normalize_person_name(card['name'])+'|'+(phone or '')).encode()).hexdigest()
                db.execute('''INSERT OR IGNORE INTO contact_cards
                    (company,source_id,card_key,display_name,phone_e164)
                    VALUES(?,?,?,?,?)''',
                    (source['company'],source['id'],key,card['name'],phone))
    db.commit()


def register_author_contact_candidates(db, company=None):
    query='''SELECT a.id author_id,a.display_name,a.phone_e164,a.company,
        c.id contact_id,c.display_name contact_name,c.phone_e164 contact_phone
        FROM conversation_authors a JOIN contact_cards c ON c.company=a.company'''
    params=[]
    if company is not None:
        query+=' WHERE a.company=?';params.append(company)
    inserted=0
    for row in db.execute(query,params).fetchall():
        method=None
        if row['phone_e164'] and row['phone_e164']==row['contact_phone']:
            method='exact_phone'
        elif normalize_person_name(row['display_name']) and normalize_person_name(row['display_name'])==normalize_person_name(row['contact_name']):
            method='exact_name'
        if method:
            status='confirmed' if method=='exact_phone' else 'pending_review'
            cursor=db.execute('''INSERT OR IGNORE INTO author_contact_candidates
                (author_id,contact_card_id,match_method,status) VALUES(?,?,?,?)''',
                (row['author_id'],row['contact_id'],method,status))
            inserted+=cursor.rowcount
    db.commit()
    return inserted


def identify_message_phones(db, company):
    """Link a single explicit phone in a 1:1 export to its classified customer.

    Multiple phones, unidentified roles, or a conflicting phone stay pending.
    Each candidate retains the exact source message as evidence.
    """
    phone_pattern=re.compile(r'(?<!\d)(?:\+?55[ .()-]?)?\(?\d{2}\)?[ .-]?9?\d{4}[ .-]?\d{4}(?!\d)')
    sources=db.execute('SELECT id FROM sources WHERE company=? AND kind=\'text\'',(company,)).fetchall()
    confirmed=pending=0
    for source in sources:
        occurrences={}
        for message in db.execute('SELECT id,body FROM messages WHERE source_id=? AND system=0',(source['id'],)):
            for match in phone_pattern.finditer(message['body'] or ''):
                phone=normalize_whatsapp_phone(match.group())
                if phone:occurrences.setdefault(phone,set()).add(message['id'])
        if not occurrences:continue
        customers=db.execute("SELECT id,phone_e164 FROM conversation_authors WHERE source_id=? AND speaker_role='customer'",(source['id'],)).fetchall()
        customer=customers[0] if len(customers)==1 else None
        for phone,message_ids in occurrences.items():
            clear=len(occurrences)==1 and customer is not None and customer['phone_e164'] in {None,phone}
            status='confirmed' if clear else 'pending_review'
            with db:
                for message_id in message_ids:
                    db.execute('''INSERT OR IGNORE INTO author_phone_evidence
                        (company,source_id,author_id,message_id,phone_e164,evidence_type,status)
                        VALUES(?,?,?,?,?,'message_body',?)''',
                        (company,source['id'],customer['id'] if customer else None,message_id,phone,status))
                if clear:
                    db.execute("UPDATE conversation_authors SET phone_e164=?,link_status='phone_identified' WHERE id=? AND link_status IN ('unresolved','phone_identified')",
                               (phone,customer['id']))
            if clear:confirmed+=1
            else:pending+=1
    register_author_contact_candidates(db,company)
    return {'confirmed_phone_links':confirmed,'pending_phone_candidates':pending}


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
    return 'audio' if ext in AUDIO else 'video' if ext in VIDEO else 'image' if ext in IMAGE else 'text' if ext in TEXT else 'attachment'


def attachment_references(body, source_rows):
    """Resolve an export marker only to a filename literally present in the same archive."""
    refs=set()
    names={Path(row['relative_path']).name for row in source_rows if row['kind']!='text'}
    for match in MEDIA.finditer(body or ''):
        raw=next((v.strip().strip('\u200e\u200f\u202a\u202c').strip() for v in match.groups() if v), '')
        if not raw:continue
        if raw in names:
            refs.add(raw);continue
        suffix_matches={name for name in names if raw.endswith(name)}
        refs.add(next(iter(suffix_matches)) if len(suffix_matches)==1 else raw)
    return refs


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
                    refs = attachment_references(message['body'],current)
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
    register_authors(db)
    register_contacts(db, company)
    register_author_contact_candidates(db, company)
    return {'sources':len(current),'exports_selected':imported}


def link_author(db, company, author_id, contact_key, confirm_match=False):
    """Record a human-confirmed author-to-WhatsApp identity mapping."""
    if not confirm_match:
        raise ValueError('Confirme que este autor corresponde a este contato do WhatsApp')
    contact_key = contact_key.strip()
    if not contact_key or len(contact_key) > 180:
        raise ValueError('Identificador de contato inválido')
    row = db.execute('SELECT id FROM conversation_authors WHERE id=? AND company=?',
                     (author_id, company)).fetchone()
    if row is None:
        raise ValueError('Autor inexistente nesta empresa')
    with db:
        db.execute("UPDATE conversation_authors SET link_status='linked',whatsapp_contact_key=? WHERE id=?",
                   (contact_key, author_id))
    return {'author_id':author_id,'link_status':'linked'}


def classify_authors(db, company, staff_name):
    """Mark a user-confirmed staff author and the other speaker in 1:1 chats."""
    normalized_staff=normalize_person_name(staff_name)
    if not normalized_staff:
        raise ValueError('Nome da equipe inválido')
    exports=db.execute('''SELECT DISTINCT s.id source_id FROM sources s
        JOIN conversation_authors a ON a.source_id=s.id WHERE s.company=?''',(company,)).fetchall()
    staff_count=customer_count=unresolved_count=0
    for export in exports:
        authors=db.execute('SELECT id,display_name FROM conversation_authors WHERE source_id=?',(export['source_id'],)).fetchall()
        matches=[a for a in authors if normalize_person_name(a['display_name'])==normalized_staff]
        if len(matches)!=1:
            unresolved_count+=len(authors)
            continue
        team=matches[0]
        with db:
            db.execute("UPDATE conversation_authors SET speaker_role='staff' WHERE id=?",(team['id'],))
        staff_count+=1
        counterparts=[a for a in authors if a['id']!=team['id']]
        if len(authors)==2 and len(counterparts)==1:
            with db:
                db.execute("UPDATE conversation_authors SET speaker_role='customer' WHERE id=?",(counterparts[0]['id'],))
            customer_count+=1
        else:
            unresolved_count+=len(counterparts)
    # An exact name match to a staff contact is not evidence that the card is a customer.
    with db:
        db.execute('''UPDATE author_contact_candidates SET status='rejected'
            WHERE match_method='exact_name' AND author_id IN
            (SELECT id FROM conversation_authors WHERE company=? AND speaker_role='staff')''',(company,))
    return {'staff_authors':staff_count,'customer_authors':customer_count,'unresolved_authors':unresolved_count}


def export_authors(db, company, output):
    output = private_path(output)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    rows = db.execute('''SELECT a.id author_id,s.relative_path,a.display_name,a.speaker_role,a.link_status,
        a.phone_e164,a.whatsapp_contact_key,count(m.id) message_count
        FROM conversation_authors a JOIN sources s ON s.id=a.source_id
        LEFT JOIN messages m ON m.author_id=a.id
        WHERE a.company=? GROUP BY a.id ORDER BY s.relative_path,a.display_name''', (company,)).fetchall()
    with output.open('x', encoding='utf-8', newline='') as stream:
        os.chmod(output, 0o600)
        writer = csv.writer(stream)
        writer.writerow(['author_id','conversation_source','author','speaker_role','link_status','phone_e164','whatsapp_contact_key','message_count'])
        writer.writerows([tuple(row) for row in rows])
    return {'saved_private':True,'author_records':len(rows)}


def transcribe(db, source_id, company, model_path, model_name='tiny', threads=2):
    # Single local writer survives crashes via OS lock; no stale lease or double inference.
    lock_path = private_path(db.execute('PRAGMA database_list').fetchone()[2]).with_suffix('.lock')
    with lock_path.open('a') as lock:
        os.chmod(lock_path, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _transcribe(db, source_id, company, model_path, model_name, threads)


def _transcription_recipe(model_path, model_name):
    ffmpeg_version = subprocess.check_output(['ffmpeg','-version'],text=True).splitlines()[0]
    model_files = [p for p in paths(model_path) if '.cache' not in p.relative_to(model_path).parts]
    model_hash = hashlib.sha256(''.join(str(p.relative_to(model_path))+file_hash(p) for p in model_files).encode()).hexdigest()
    import importlib.metadata
    return f'{VERSION}:faster-whisper-{importlib.metadata.version("faster-whisper")}:{model_name}:{model_hash}:cpu:int8:pt:beam1:vad0:ffmpeg16k:{ffmpeg_version}'


def transcribe_all(db, company, model_path, model_name='tiny', threads=2, progress=None):
    """Transcribe every audio/video source for one company, loading the local model once."""
    lock_path=private_path(db.execute('PRAGMA database_list').fetchone()[2]).with_suffix('.lock')
    with lock_path.open('a') as lock:
        os.chmod(lock_path,0o600)
        fcntl.flock(lock,fcntl.LOCK_EX)
        model_path=private_path(model_path)
        if not model_path.is_dir():raise ValueError('Modelo local ausente')
        ids=[r[0] for r in db.execute("SELECT id FROM sources WHERE company=? AND kind IN ('audio','video') ORDER BY id",(company,))]
        recipe=_transcription_recipe(model_path,model_name)
        pending=[]
        for source_id in ids:
            db.execute('INSERT OR IGNORE INTO transcriptions(source_id,recipe,status) VALUES(?,?,?)',(source_id,recipe,'pending'))
            job=db.execute('SELECT status FROM transcriptions WHERE source_id=? AND recipe=?',(source_id,recipe)).fetchone()
            if job['status']!='done':pending.append(source_id)
        db.commit()
        if not pending:return {'total':len(ids),'done':len(ids),'reused':len(ids),'errors':0}
        try:
            os.environ['HF_HUB_OFFLINE']='1';os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
            from faster_whisper import WhisperModel
            model=WhisperModel(str(model_path),device='cpu',compute_type='int8',cpu_threads=threads,num_workers=1,local_files_only=True)
        except Exception as exc:
            return {'total':len(ids),'done':len(ids)-len(pending),'errors':len(pending),'model_error_class':type(exc).__name__}
        counts={'done':0,'reused':0,'errors':0}; started=time.monotonic()
        for index,source_id in enumerate(pending,1):
            result=_transcribe(db,source_id,company,model_path,model_name,threads,model=model,recipe=recipe)
            key='errors' if result['status']=='error' else result['status']
            counts[key]=counts.get(key,0)+1
            if progress and (index % 10==0 or index==len(pending)):
                progress({'processed':index,'pending':len(pending),'elapsed_seconds':round(time.monotonic()-started,1),'errors':counts['errors']})
        already_done=len(ids)-len(pending)
        return {'total':len(ids),'done':already_done+counts['done']+counts['reused'],
            'reused':already_done+counts['reused'],'errors':counts['errors'],
            'elapsed_seconds':round(time.monotonic()-started,1)}


def _transcribe(db, source_id, company, model_path, model_name='tiny', threads=2, model=None, recipe=None):
    row = db.execute('SELECT * FROM sources WHERE id=? AND company=?',(source_id,company)).fetchone()
    if not row or row['kind'] not in {'audio','video'}:
        raise ValueError('Mídia inexistente nesta empresa')
    source = Path(row['root'])/row['relative_path']
    root=Path(row['root']).absolute();relative=Path(row['relative_path']);components=[root]
    for part in relative.parts:components.append(components[-1]/part)
    if relative.is_absolute() or '..' in relative.parts or any(p.is_symlink() for p in components) or not source.is_file() or file_hash(source) != row['sha256']:
        raise ValueError('Fonte alterada ou insegura; reinvente antes')
    model_path = private_path(model_path)
    if not model_path.is_dir():
        raise ValueError('Modelo local ausente')
    recipe=recipe or _transcription_recipe(model_path,model_name)
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
        with tempfile.TemporaryDirectory(prefix='orchestra-audio-', dir=str(private_path(db.execute('PRAGMA database_list').fetchone()[2]).parent)) as folder:
            wav=Path(folder)/'audio.wav'
            subprocess.run(['ffmpeg','-nostdin','-v','error','-protocol_whitelist','file,pipe','-i',str(source),'-vn','-ac','1','-ar','16000',str(wav)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=600)
            if model is None:
                from faster_whisper import WhisperModel
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
    for message in db.execute('''SELECT m.*,a.speaker_role,a.display_name author_identity,
        a.phone_e164,a.whatsapp_contact_key,a.link_status identity_link_status FROM messages m
        JOIN sources s ON s.id=m.source_id LEFT JOIN conversation_authors a ON a.id=m.author_id
        WHERE s.company=? ORDER BY m.source_id,m.ordinal''',(company,)):
        item=dict(message); item['attachments']=[];item['author_contact_candidates']=[]
        if message['author_id']:
            item['author_contact_candidates']=[dict(r) for r in db.execute('''SELECT c.display_name,c.phone_e164,x.match_method,x.status
                FROM author_contact_candidates x JOIN contact_cards c ON c.id=x.contact_card_id
                WHERE x.author_id=? ORDER BY x.match_method,c.display_name''',(message['author_id'],))]
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
              (r'(?<!\d)(?:\+?55[\s().-]*)?\(?[1-9]\d\)?[\s().-]?(?:9?\d{4})[\s.-]?\d{4}(?!\d)','[TELEFONE]'),
              (r'(?<!\d)(?:\d{3}\.?\d{3}\.?\d{3}-?\d{2}|\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})(?!\d)','[DOCUMENTO]'),
              (r'\b(?:Rua|R\.|Avenida|Av\.|Travessa|Alameda|Rodovia|Estrada)\s+[^,;\n]{2,70}','[ENDEREÇO]')]
    for pattern,replacement in patterns:
        text=re.sub(pattern,replacement,text)
    return text


def export_learning_corpus(db, company, output_dir, max_chars=300000):
    """Write a private, role-labeled and redacted copy for human review before indexing."""
    if not 10000 <= max_chars <= 330000:
        raise ValueError('O tamanho precisa caber no limite de trechos da busca')
    output_dir=private_path(output_dir)
    output_dir.mkdir(mode=0o700,parents=True,exist_ok=True)
    names={r[0] for r in db.execute('SELECT display_name FROM conversation_authors WHERE company=?',(company,))}
    names.update(r[0] for r in db.execute('SELECT display_name FROM contact_cards WHERE company=?',(company,)))
    names={name for name in names if name}
    header=['# Exemplos históricos de conversas','','Material derivado do histórico privado. Use para exemplos de estilo e contexto, nunca como regra, preço, estoque ou política atual. Revisão humana de privacidade e qualidade obrigatória antes de indexar.','','Áudios foram transcritos localmente e ainda podem conter erros. Transcrição de vídeo não interpreta imagens. Anexos sem extração permanecem marcadores.','']
    # Exact duplicate exports are retained in staging for provenance but included once
    # in the derived corpus, avoiding repeated conversational examples in retrieval.
    source_rows=db.execute('''SELECT min(s.id) id,s.sha256 FROM sources s WHERE s.company=? AND s.kind='text'
        AND EXISTS(SELECT 1 FROM messages m WHERE m.source_id=s.id)
        GROUP BY s.sha256 ORDER BY min(s.relative_path),min(s.id)''',(company,)).fetchall()
    blocks=[];message_count=0
    for source in source_rows:
        rows=db.execute('''SELECT m.id,m.ordinal,m.date_raw,m.author,m.author_id,m.body,m.system,a.speaker_role
            FROM messages m LEFT JOIN conversation_authors a ON a.id=m.author_id
            WHERE m.source_id=? ORDER BY m.ordinal''',(source['id'],)).fetchall()
        if not any(not r['system'] for r in rows):continue
        block=['## Conversa '+source['sha256'][:10]];author_labels={}
        for row in rows:
            if row['system']:continue
            role=row['speaker_role'] or 'unresolved'
            if role=='staff':label='Equipe'
            elif role=='customer':label='Cliente'
            else:
                key=row['author_id'] or row['author'] or 'desconhecido'
                if key not in author_labels:author_labels[key]=f'Autor {len(author_labels)+1}'
                label=author_labels[key]
            body=row['body'] or '[mensagem sem texto]'
            attachments=db.execute('''SELECT a.reference,a.status,a.source_id,s.kind FROM attachments a
                LEFT JOIN sources s ON s.id=a.source_id WHERE a.message_id=?''',(row['id'],)).fetchall()
            media_notes=[]
            for attachment in attachments:
                reference=attachment['reference'] or ''
                filename=Path(reference).name
                for token in {reference,filename}:
                    if token and token not in {'[media omitted]'}:
                        body=re.sub(re.escape(token), '[ANEXO]',body,flags=re.I)
                body=re.sub(r'\s*\((?:arquivo anexado|file attached)\)','',body,flags=re.I)
                if attachment['status']!='linked' or not attachment['source_id']:
                    media_notes.append('[Anexo sem associação confirmada]');continue
                kind=attachment['kind']
                if kind in {'audio','video'}:
                    job=db.execute("SELECT id FROM transcriptions WHERE source_id=? AND status='done' ORDER BY id DESC LIMIT 1",(attachment['source_id'],)).fetchone()
                    if job:
                        segments=db.execute('SELECT start,end,text FROM segments WHERE transcription_id=? ORDER BY ordinal',(job['id'],)).fetchall()
                        if segments:
                            media_notes.append(f'[Transcrição local de anexo enviado por {label}; falante não identificado, revisar] '+ ' '.join(
                                f"({int(s['start']//60):02d}:{s['start']%60:05.2f}) {redact(s['text'],names)}" for s in segments))
                        else:media_notes.append('[Mídia transcrita sem segmentos]')
                    else:media_notes.append('[Áudio/vídeo sem transcrição]')
                elif kind=='attachment':media_notes.append('[Anexo sem extração textual]')
            body=redact(body,names)
            if '<Mídia oculta>' in body or '<Media omitted>' in body:
                body=re.sub(r'<(?:Mídia oculta|Media omitted)>','[Anexo não disponível]',body,flags=re.I)
            date=redact(row['date_raw'] or 'data não registrada',names)
            block.append(f'- {date} | {label}: {body} '+ ' '.join(media_notes))
            message_count+=1
        blocks.append('\n'.join(block)+'\n')
    batches=[];current='\n'.join(header)+'\n'
    for block in blocks:
        if len(current)+len(block)>max_chars and len(current)>len('\n'.join(header)):
            batches.append(current);current='\n'.join(header)+'\n'
        if len(current)+len(block)>max_chars:
            raise ValueError('Uma conversa excede o limite de exportação; divida-a com revisão')
        current+=block
    if current.strip():batches.append(current)
    for index,content in enumerate(batches,1):
        target=output_dir/f'conversas-atendimento-{index:02d}.md'
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as stream:stream.write(content)
    return {'saved_private':True,'conversations':len(blocks),'messages':message_count,'files':len(batches)}


def export_history_for_application(db, company, tenant_id, instance_id, timezone_name, output):
    """Create a private JSONL transfer package for an explicit tenant/instance."""
    if company != tenant_id or company == 'unassigned':
        raise ValueError('A empresa de staging precisa ser o ID do tenant de destino')
    if not re.fullmatch(r'[0-9a-fA-F-]{36}', instance_id):
        raise ValueError('ID da instância inválido')
    ZoneInfo(timezone_name)
    output=private_path(output)
    output.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    sources=db.execute('''SELECT min(id) id,sha256,min(version) version FROM sources
        WHERE company=? AND kind='text' AND EXISTS(SELECT 1 FROM messages m WHERE m.source_id=sources.id)
        GROUP BY sha256 ORDER BY min(id)''',(company,)).fetchall()
    author_rows={}
    for source in sources:
        author_rows[source['id']]=db.execute('''SELECT id,display_name,speaker_role,phone_e164
            FROM conversation_authors WHERE source_id=? ORDER BY id''',(source['id'],)).fetchall()
    # No path, basename or conversation body is emitted to progress/stdout.
    fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    total=0; known_contacts=set(); unresolved=0
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            for source in sources:
                authors=author_rows[source['id']]
                customers=[a for a in authors if a['speaker_role']=='customer']
                customer=customers[0] if len(customers)==1 else None
                phone=customer['phone_e164'] if customer else None
                display_name=None
                if phone:
                    names={r[0] for r in db.execute('''SELECT DISTINCT display_name FROM contact_cards
                        WHERE company=? AND phone_e164=? AND display_name!='' ''',(company,phone))}
                    if len(names)==1:display_name=next(iter(names))
                    known_contacts.add(phone)
                if not display_name and customer:display_name=customer['display_name']
                if not display_name:display_name='Histórico sem contato confirmado'
                contact_key=phone or 'history:'+source['sha256']
                rows=db.execute('''SELECT m.*,a.display_name author_name,a.speaker_role
                    FROM messages m LEFT JOIN conversation_authors a ON a.id=m.author_id
                    WHERE m.source_id=? ORDER BY m.ordinal''',(source['id'],)).fetchall()
                # One exported system-only line has no source date. Preserve the
                # line and its ordinal, borrow the nearest dated row only for
                # chronological display, and keep the original date empty so UI
                # never presents that borrowed timestamp as an observed fact.
                parsed_dates=[]
                for row_index,row in enumerate(rows):
                    try: parsed_dates.append(parse_whatsapp_datetime(row['date_raw'],timezone_name))
                    except ValueError:
                        if (row['date_raw'] or '').strip(): raise
                        parsed_dates.append(None)
                for index,value in enumerate(parsed_dates):
                    if value is None:
                        parsed_dates[index]=next((x for x in parsed_dates[index+1:] if x is not None),None)
                        if parsed_dates[index] is None:
                            parsed_dates[index]=next((x for x in reversed(parsed_dates[:index]) if x is not None),None)
                        if parsed_dates[index] is None:
                            raise ValueError('Origem sem nenhuma data para ordenar')
                for row_index,row in enumerate(rows):
                    if row['system']:
                        direction='historical';author_kind='system';author_name='Sistema WhatsApp'
                    elif row['speaker_role']=='staff':
                        direction='outgoing';author_kind='operator';author_name=row['author_name'] or row['author']
                    elif row['speaker_role']=='customer':
                        direction='incoming';author_kind='user';author_name=row['author_name'] or row['author']
                    else:
                        direction='historical';author_kind='legacy';author_name=row['author_name'] or row['author'] or 'Autor não identificado'
                        unresolved+=1
                    content=row['body'] or ''
                    attachments=db.execute('''SELECT a.status,a.source_id,s.kind FROM attachments a
                        LEFT JOIN sources s ON s.id=a.source_id WHERE a.message_id=? ORDER BY a.reference''',(row['id'],)).fetchall()
                    for attachment in attachments:
                        if attachment['status']!='linked' or not attachment['source_id']:
                            content+='\n[Anexo histórico sem arquivo associado]';continue
                        media_kind=attachment['kind']
                        if media_kind in {'audio','video'}:
                            job=db.execute("SELECT id FROM transcriptions WHERE source_id=? AND status='done' ORDER BY id DESC LIMIT 1",(attachment['source_id'],)).fetchone()
                            segments=db.execute('SELECT start,end,text FROM segments WHERE transcription_id=? ORDER BY ordinal',(job['id'],)).fetchall() if job else []
                            if segments:
                                transcript=' '.join(f"({int(seg['start']//60):02d}:{seg['start']%60:05.2f}) {seg['text']}" for seg in segments)
                                marker='Áudio' if media_kind=='audio' else 'Áudio extraído do vídeo; imagem não analisada'
                                content+=f'\n[{marker}; transcrição local automática, falante não identificado, revisão pendente] {transcript}'
                            elif media_kind=='video':content+='\n[Vídeo sem faixa de áudio; imagem não analisada]'
                            else:content+='\n[Áudio sem transcrição]'
                        elif media_kind=='image':content+='\n[Imagem anexada; conteúdo visual não analisado]'
                        elif media_kind=='attachment':content+='\n[Documento anexado; conteúdo não extraído]'
                        else:content+='\n[Anexo histórico]'
                    created=parsed_dates[row_index]
                    item={'tenant_id':tenant_id,'instance_id':instance_id,'source_sha256':source['sha256'],
                        'source_version':source['version'],'source_timezone':timezone_name,
                        'contact_key':contact_key,'contact_name':display_name,'ordinal':row['ordinal'],
                        'original_timestamp_text':row['date_raw'] or '','created_at':created.isoformat(),
                        'direction':direction,'author_kind':author_kind,'author_name':author_name,
                        'kind':'system' if row['system'] else 'text','content':content,'status':'historical'}
                    stream.write(json.dumps(item,ensure_ascii=False,separators=(',',':'))+'\n')
                    total+=1
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return {'saved_private':True,'source_hashes':len(sources),'messages':total,
        'known_contacts':len(known_contacts),'unresolved_author_messages':unresolved}


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
    p=sub.add_parser('transcribe-all');p.add_argument('--model-path',type=Path,required=True);p.add_argument('--model-name',default='tiny');p.add_argument('--threads',type=int,default=2)
    p=sub.add_parser('propose');p.add_argument('--message-id',action='append',type=int,required=True);p.add_argument('--kind',choices=['fact','example'],required=True);p.add_argument('--text-file',type=Path,required=True)
    p=sub.add_parser('approve');p.add_argument('--proposal-id',type=int,required=True);p.add_argument('--reviewer',required=True);p.add_argument('--confirm-personal-and-factual-review',action='store_true');p.add_argument('--valid-until')
    p=sub.add_parser('reconstruct');p.add_argument('--output',type=Path,required=True)
    p=sub.add_parser('authors');p.add_argument('--output',type=Path,required=True)
    p=sub.add_parser('link-author');p.add_argument('--author-id',type=int,required=True);p.add_argument('--contact-key',required=True);p.add_argument('--confirm-contact-match',action='store_true')
    p=sub.add_parser('classify-authors');p.add_argument('--staff-name',required=True)
    sub.add_parser('identify-phones')
    p=sub.add_parser('export-learning-corpus');p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--max-chars',type=int,default=300000)
    p=sub.add_parser('export-history-for-application');p.add_argument('--tenant-id',required=True);p.add_argument('--instance-id',required=True);p.add_argument('--timezone',default='America/Sao_Paulo');p.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();os.umask(0o077)
    with connect(args.db) as db:
        if args.command=='ingest':
            if args.max_exports < 1: parser.error('Limite positivo obrigatório')
            result=ingest(db,args.root,args.company,args.max_exports,args.export_relative)
        elif args.command=='transcribe':result=transcribe(db,args.source_id,args.company,args.model_path)
        elif args.command=='transcribe-all':
            result=transcribe_all(db,args.company,args.model_path,args.model_name,args.threads,
                progress=lambda item: print(json.dumps({'progress':item}),flush=True))
        elif args.command=='propose':
            result={'proposal_id':propose(db,args.company,args.message_id,args.kind,private_path(args.text_file).read_text(encoding='utf-8')),'status':'pending_review'}
        elif args.command=='approve':
            approve(db,args.company,args.proposal_id,args.reviewer,args.confirm_personal_and_factual_review,args.valid_until)
            result={'status':'approved_local','indexed':False}
        elif args.command=='authors':result=export_authors(db,args.company,args.output)
        elif args.command=='link-author':result=link_author(db,args.company,args.author_id,args.contact_key,args.confirm_contact_match)
        elif args.command=='classify-authors':result=classify_authors(db,args.company,args.staff_name)
        elif args.command=='identify-phones':result=identify_message_phones(db,args.company)
        elif args.command=='export-learning-corpus':result=export_learning_corpus(db,args.company,args.output_dir,args.max_chars)
        elif args.command=='export-history-for-application':result=export_history_for_application(db,args.company,args.tenant_id,args.instance_id,args.timezone,args.output)
        else:
            out=private_path(args.output);out.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            with out.open('x',encoding='utf-8') as stream:json.dump(reconstruct(db,args.company),stream,ensure_ascii=False,indent=2)
            result={'saved_private':True}
    print(json.dumps(result))

if __name__=='__main__':main()
