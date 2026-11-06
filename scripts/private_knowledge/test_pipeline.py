import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline import classify_authors, connect, export_learning_corpus, identify_message_phones, ingest, link_author, normalize_whatsapp_phone, parse_vcards, transcribe_all


class ConversationAuthorTests(unittest.TestCase):
    def test_phone_normalization_requires_a_complete_brazilian_number(self):
        self.assertEqual(normalize_whatsapp_phone('+55 (11) 91234-5678'), '5511912345678')
        self.assertEqual(normalize_whatsapp_phone('11 3234-5678'), '551132345678')
        self.assertIsNone(normalize_whatsapp_phone('450 m'))
        self.assertIsNone(normalize_whatsapp_phone('2026-11-05'))

    def test_vcard_name_and_phone_are_parsed_for_exact_identity_candidates(self):
        cards=parse_vcards('BEGIN:VCARD\nVERSION:3.0\nFN:Cliente Exemplo\nTEL;TYPE=CELL:+55 11 91234-5678\nEND:VCARD\n')
        self.assertEqual(cards,[{'name':'Cliente Exemplo','phones':{'5511912345678'}}])

    def test_author_identity_stays_per_conversation_and_phone_is_only_identified(self):
        with tempfile.TemporaryDirectory(prefix='orchestra-private-authors-') as folder:
            folder = Path(folder)
            source = folder / 'exports'
            source.mkdir()
            (source / 'one.txt').write_text(
                '[05/11/2026, 10:00] +55 11 91234-5678: Olá\n'
                '[05/11/2026, 10:01] Atendimento: Meu número é 5511987654321\n',
                encoding='utf-8')
            (source / 'two.txt').write_text(
                '[05/11/2026, 11:00] Atendimento: Olá\n', encoding='utf-8')
            (source / 'contact.vcf').write_text(
                'BEGIN:VCARD\nVERSION:3.0\nFN:Cliente Exemplo\n'
                'TEL;TYPE=CELL:+55 11 91234-5678\nEND:VCARD\n',encoding='utf-8')

            db_path = folder / 'staging.sqlite'
            db = connect(db_path)
            company = 'tenant-test'
            ingest(db, source, company, max_exports=100)
            authors = db.execute('''SELECT a.id,a.display_name,a.link_status,a.phone_e164,
                count(m.id) messages FROM conversation_authors a
                LEFT JOIN messages m ON m.author_id=a.id WHERE a.company=?
                GROUP BY a.id ORDER BY a.display_name''', (company,)).fetchall()
            phone_author = next(a for a in authors if a['display_name'].startswith('+55'))
            self.assertEqual(phone_author['link_status'], 'phone_identified')
            self.assertEqual(phone_author['phone_e164'], '5511912345678')
            self.assertIsNone(db.execute('''SELECT whatsapp_contact_key FROM conversation_authors
                WHERE id=?''', (phone_author['id'],)).fetchone()[0])
            with self.assertRaises(ValueError):
                link_author(db,company,phone_author['id'],'5511912345678@c.us')
            link_author(db,company,phone_author['id'],'5511912345678@c.us',confirm_match=True)
            linked=db.execute('SELECT link_status,whatsapp_contact_key FROM conversation_authors WHERE id=?',(phone_author['id'],)).fetchone()
            self.assertEqual(tuple(linked),('linked','5511912345678@c.us'))
            same_name = [a for a in authors if a['display_name'] == 'Atendimento']
            self.assertEqual(len(same_name), 2)
            self.assertNotEqual(same_name[0]['id'], same_name[1]['id'])
            self.assertTrue(all(a['link_status'] == 'unresolved' for a in same_name))
            self.assertEqual(db.execute('''SELECT count(*) FROM author_contact_candidates x
                JOIN conversation_authors a ON a.id=x.author_id
                WHERE a.company=? AND x.match_method='exact_phone' AND x.status='confirmed' ''',
                (company,)).fetchone()[0],1)
            roles = classify_authors(db, company, 'Atendimento')
            self.assertEqual(roles, {'staff_authors':2,'customer_authors':1,'unresolved_authors':0})

            # Reopening applies migrations idempotently and backfills without duplicates.
            db.close()
            db = connect(db_path)
            self.assertEqual(db.execute('SELECT count(*) FROM conversation_authors').fetchone()[0], 3)
            self.assertEqual(db.execute('SELECT count(*) FROM messages WHERE author_id IS NULL AND author IS NOT NULL').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT max(version) FROM schema_version').fetchone()[0], 4)
            self.assertEqual(db.execute("SELECT count(*) FROM conversation_authors WHERE speaker_role='customer'").fetchone()[0],1)
            db.close()

    def test_transcribe_all_empty_company_does_not_load_model(self):
        with tempfile.TemporaryDirectory(prefix='orchestra-private-empty-transcription-') as folder:
            folder=Path(folder); db=connect(folder/'staging.sqlite'); model=folder/'model';model.mkdir()
            with patch('pipeline._transcription_recipe',return_value='test-recipe'):
                result=transcribe_all(db,'empty-company',model)
            self.assertEqual(result,{'total':0,'done':0,'reused':0,'errors':0})
            db.close()

    def test_unique_message_phone_links_only_the_classified_customer(self):
        with tempfile.TemporaryDirectory(prefix='orchestra-private-phone-link-') as folder:
            folder=Path(folder); source=folder/'exports';source.mkdir()
            (source/'chat.txt').write_text(
                '[05/11/2026, 10:00] Atendimento: Pode falar neste telefone 5511991234567\n'
                '[05/11/2026, 10:01] Cliente: Obrigado\n',encoding='utf-8')
            db=connect(folder/'staging.sqlite');ingest(db,source,'tenant-a',max_exports=10)
            classify_authors(db,'tenant-a','Atendimento')
            result=identify_message_phones(db,'tenant-a')
            self.assertEqual(result,{'confirmed_phone_links':1,'pending_phone_candidates':0})
            customer=db.execute("SELECT id,phone_e164,link_status FROM conversation_authors WHERE speaker_role='customer'").fetchone()
            self.assertEqual(customer['phone_e164'],'5511991234567')
            evidence=db.execute("SELECT author_id,status,evidence_type FROM author_phone_evidence WHERE evidence_type='message_body'").fetchone()
            self.assertEqual(tuple(evidence),(customer['id'],'confirmed','message_body'))
            output=folder/'learning-copy'
            summary=export_learning_corpus(db,'tenant-a',output)
            self.assertEqual(summary['messages'],2)
            corpus='\n'.join(p.read_text() for p in output.glob('*.md'))
            self.assertIn('Equipe',corpus)
            self.assertIn('Cliente',corpus)
            self.assertNotIn('5511991234567',corpus)
            self.assertEqual(next(output.glob('*.md')).stat().st_mode & 0o777,0o600)
            db.close()

    def test_import_attachment_is_linked_and_resume_is_idempotent_per_company(self):
        with tempfile.TemporaryDirectory(prefix='orchestra-private-resume-') as folder:
            folder=Path(folder); source=folder/'exports';source.mkdir()
            (source/'image.jpg').write_bytes(b'fixture-media')
            (source/'chat.txt').write_text(
                '[05/11/2026, 10:00] Cliente: Veja image.jpg (arquivo anexado)\n',encoding='utf-8')
            (source/'voice.opus').write_bytes(b'fixture-audio')
            db=connect(folder/'staging.sqlite'); ingest(db,source,'tenant-a',max_exports=20)
            message=db.execute("SELECT id FROM messages WHERE body LIKE '%image.jpg%' AND source_id IN (SELECT id FROM sources WHERE company='tenant-a')").fetchone()
            link=db.execute('SELECT status FROM attachments WHERE message_id=?',(message['id'],)).fetchone()
            self.assertEqual(link['status'],'linked')
            audio_id=db.execute("SELECT id FROM sources WHERE company='tenant-a' AND kind='audio'").fetchone()[0]
            db.execute("INSERT INTO transcriptions(source_id,recipe,status) VALUES(?,?,'done')",(audio_id,'test-recipe'))
            db.commit()
            ingest(db,source,'tenant-a',max_exports=20)
            ingest(db,source,'tenant-b',max_exports=20)
            self.assertEqual(db.execute("SELECT count(*) FROM messages m JOIN sources s ON s.id=m.source_id WHERE s.company='tenant-a'").fetchone()[0],1)
            self.assertEqual(db.execute("SELECT count(*) FROM messages m JOIN sources s ON s.id=m.source_id WHERE s.company='tenant-b'").fetchone()[0],1)
            with patch('pipeline._transcription_recipe',return_value='test-recipe'):
                result=transcribe_all(db,'tenant-a',folder)
            self.assertEqual(result,{'total':1,'done':1,'reused':1,'errors':0})
            self.assertEqual(db.execute("SELECT count(*) FROM transcriptions WHERE source_id=?",(audio_id,)).fetchone()[0],1)
            db.close()


if __name__ == '__main__':
    unittest.main()
