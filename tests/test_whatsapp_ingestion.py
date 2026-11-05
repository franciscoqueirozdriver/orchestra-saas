import importlib.util
from pathlib import Path
import sqlite3
import pytest

spec=importlib.util.spec_from_file_location('pipeline',Path(__file__).resolve().parents[1]/'scripts/private_knowledge/pipeline.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

@pytest.fixture
def db(tmp_path):
    connection=p.connect(tmp_path/'private'/'staging.sqlite')
    yield connection
    connection.close()


def export(root):
    root.mkdir()
    (root/'chat.txt').write_text('01/11/2026 10:01 - Pessoa fictícia: Olá\ncontinuação\n[01/11/2026, 10:02:04] Outra pessoa: <anexado: audio.opus>\n01/11/2026 10:03 - Outra pessoa: \u200eclip.mp4 (arquivo anexado)\n01/11/2026 10:04 - aviso sem autor\n01/11/2026 10:05 - Outra pessoa: <anexado: ausente.jpg>')
    (root/'audio.opus').write_bytes(b'fake')
    (root/'clip.mp4').write_bytes(b'fake-video')
    return root


def test_parser_preserves_multiline_order_author_and_dates():
    rows=p.parse_export('\ufeff[01/11/2026, 10:02:04] Nome: Olá\nmais\n01/11/2026 10:03 - aviso')
    assert rows[0]=={'date_raw':'01/11/2026, 10:02:04','author':'Nome','body':'Olá\nmais','system':0}
    assert rows[1]['author'] is None
    assert rows[1]['date_raw']=='01/11/2026 10:03'


def test_ingest_links_resume_and_company_isolation(db,tmp_path):
    root=export(tmp_path/'exports')
    p.ingest(db,root,'company-a')
    before=[db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('sources','messages','attachments')]
    p.ingest(db,root,'company-a')
    assert before==[db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('sources','messages','attachments')]
    assert before==[3,5,3]
    assert [r[0] for r in db.execute('SELECT status FROM attachments ORDER BY message_id')]==['linked','linked','missing']
    assert not p.reconstruct(db,'company-b')
    p.ingest(db,root,'company-b')
    mid=db.execute("SELECT m.id FROM messages m JOIN sources s ON s.id=m.source_id WHERE s.company='company-a'").fetchone()[0]
    with pytest.raises(ValueError):p.propose(db,'company-b',[mid],'fact','Teste')


def test_changed_source_retains_old_revision_and_no_duplicate(db,tmp_path):
    root=export(tmp_path/'exports');p.ingest(db,root,'a')
    (root/'chat.txt').write_text('02/11/2026 09:00 - Pessoa: Versão nova')
    p.ingest(db,root,'a');p.ingest(db,root,'a')
    assert db.execute("SELECT count(*) FROM sources WHERE kind='text'").fetchone()[0]==2
    assert db.execute('SELECT count(*) FROM messages').fetchone()[0]==6


def test_no_temporal_guessing_and_missing_link(db,tmp_path):
    root=export(tmp_path/'exports');(root/'other.opus').write_bytes(b'x')
    p.ingest(db,root,'a')
    assert db.execute("SELECT count(*) FROM attachments WHERE reference='other.opus'").fetchone()[0]==0
    assert db.execute("SELECT source_id FROM attachments WHERE status='missing'").fetchone()[0] is None


def test_ambiguous_versions_are_not_linked(db,tmp_path):
    root=export(tmp_path/'exports');p.ingest(db,root,'a')
    # Identical basename elsewhere must not be borrowed into the chat folder.
    sub=root/'elsewhere';sub.mkdir();(sub/'ausente.jpg').write_bytes(b'x')
    p.ingest(db,root,'b')
    assert all(r[0] is None for r in db.execute("SELECT source_id FROM attachments WHERE reference='ausente.jpg'"))


def test_reconstructed_transcript_keeps_origin_timestamps(db,tmp_path):
    root=export(tmp_path/'exports');p.ingest(db,root,'a')
    sid=db.execute("SELECT id FROM sources WHERE kind='audio'").fetchone()[0]
    jid=db.execute("INSERT INTO transcriptions(source_id,recipe,status) VALUES(?,'synthetic','done')",(sid,)).lastrowid
    db.execute('INSERT INTO segments VALUES(?,0,1.0,2.5,?,NULL,NULL)',(jid,'fala sintética'))
    rows=p.reconstruct(db,'a');a=rows[1]['attachments'][0]
    assert a['segments'][0]['start']==1.0 and a['segments'][0]['end']==2.5
    assert a['segments'][0]['text']=='fala sintética'
    assert a['visual_interpretation'] is False
    assert rows[1]['author']=='Outra pessoa'


def test_proposal_redaction_pending_review_and_no_publish(db,tmp_path):
    p.ingest(db,export(tmp_path/'exports'),'a')
    mid=db.execute('SELECT id FROM messages ORDER BY id').fetchone()[0]
    pid=p.propose(db,'a',[mid],'example','Pessoa fictícia: teste@example.com +55 (11) 99999-8888 https://example.com')
    row=db.execute('SELECT * FROM proposals WHERE id=?',(pid,)).fetchone()
    assert row['status']=='pending_review'
    assert 'Pessoa fictícia' not in row['text'] and 'example.com' not in row['text']
    with pytest.raises(ValueError):p.approve(db,'a',pid,'Reviewer',False)
    p.approve(db,'a',pid,'Reviewer',True)
    assert db.execute('SELECT status FROM proposals WHERE id=?',(pid,)).fetchone()[0]=='approved_local'
    assert not db.execute("SELECT name FROM sqlite_master WHERE name='knowledge_chunks'").fetchall()


def test_unassigned_and_stale_facts_cannot_be_approved(db,tmp_path):
    root=export(tmp_path/'exports')
    for company in ('unassigned','a'):
        p.ingest(db,root,company)
        mid=db.execute('SELECT m.id FROM messages m JOIN sources s ON m.source_id=s.id WHERE s.company=?',(company,)).fetchone()[0]
        pid=p.propose(db,company,[mid],'fact','Preço histórico a revisar')
        with pytest.raises(ValueError):p.approve(db,company,pid,'Reviewer',True,'2000-01-01')


def test_private_destination_and_symlink_rejected(tmp_path):
    with pytest.raises(ValueError):p.connect(p.REPO/'private.sqlite')
    target=tmp_path/'target';target.mkdir();link=tmp_path/'link';link.symlink_to(target)
    with pytest.raises(ValueError):list(p.paths(link))
    with pytest.raises(ValueError):p.connect(link/'db.sqlite')


def test_transcription_resume_segments_and_failure_are_private(db,tmp_path,monkeypatch):
    import types,sys,importlib.metadata
    root=export(tmp_path/'exports');p.ingest(db,root,'a')
    sid=db.execute("SELECT id FROM sources WHERE kind='audio'").fetchone()[0]
    model=tmp_path/'model';model.mkdir();(model/'config.json').write_text('{}')
    calls=[]
    class Model:
        def __init__(self,*a,**kw):
            assert kw['local_files_only'] and kw['device']=='cpu' and kw['compute_type']=='int8'
        def transcribe(self,*a,**kw):
            calls.append(1)
            seg=types.SimpleNamespace(start=0.2,end=1.4,text='ficção',avg_logprob=-0.4,no_speech_prob=0.1)
            return iter([seg]),types.SimpleNamespace(duration=2.0,language='pt')
    monkeypatch.setitem(sys.modules,'faster_whisper',types.SimpleNamespace(WhisperModel=Model))
    monkeypatch.setattr(importlib.metadata,'version',lambda _: 'synthetic')
    monkeypatch.setattr(p.subprocess,'run',lambda *a,**kw:None)
    monkeypatch.setattr(p.subprocess,'check_output',lambda *a,**kw:'ffmpeg synthetic\n')
    assert p.transcribe(db,sid,'a',model)['status']=='done'
    assert p.transcribe(db,sid,'a',model)['status']=='reused'
    assert len(calls)==1
    assert db.execute('SELECT count(*) FROM segments').fetchone()[0]==1
    with pytest.raises(ValueError):p.transcribe(db,sid,'b',model)
    def fail(*a,**kw):raise RuntimeError('private path or secret in stderr')
    monkeypatch.setattr(p.subprocess,'run',fail)
    (model/'config.json').write_text('{"new":true}')
    assert p.transcribe(db,sid,'a',model)['status']=='error'
    assert db.execute("SELECT error FROM transcriptions WHERE status='error'").fetchone()[0]=='RuntimeError'
    assert db.execute('SELECT count(*) FROM segments').fetchone()[0]==1


def test_ambiguous_external_basename_not_guessed(db,tmp_path):
    root=export(tmp_path/'exports')
    for name in ('first','second'):
        folder=root/name;folder.mkdir();(folder/'ausente.jpg').write_bytes(b'fake')
    p.ingest(db,root,'a')
    row=db.execute("SELECT * FROM attachments WHERE reference='ausente.jpg'").fetchone()
    assert row['status']=='ambiguous' and row['source_id'] is None


def test_unlabeled_media_and_filename_in_prose_not_guessed(db,tmp_path):
    root=export(tmp_path/'exports')
    with (root/'chat.txt').open('a') as f:
        f.write('\n01/11/2026 11:00 - Pessoa: <Mídia oculta>\n01/11/2026 11:01 - Pessoa: será que audio.opus está disponível?')
    p.ingest(db,root,'a')
    assert db.execute("SELECT count(*) FROM attachments WHERE status='omitted'").fetchone()[0]==1
    last=db.execute('SELECT max(id) FROM messages').fetchone()[0]
    assert db.execute('SELECT count(*) FROM attachments WHERE message_id=?',(last,)).fetchone()[0]==0


def test_new_origins_invalidate_existing_approval(db,tmp_path):
    p.ingest(db,export(tmp_path/'exports'),'a')
    mids=[r[0] for r in db.execute('SELECT id FROM messages ORDER BY id')]
    pid=p.propose(db,'a',[mids[0]],'example','Texto revisável')
    p.approve(db,'a',pid,'Reviewer',True)
    assert p.propose(db,'a',[mids[1]],'example','Texto revisável')==pid
    row=db.execute('SELECT status,reviewer FROM proposals WHERE id=?',(pid,)).fetchone()
    assert tuple(row)==('pending_review',None)
