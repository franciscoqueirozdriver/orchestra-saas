from pathlib import Path
import importlib.util
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('inventory', ROOT / 'scripts/private_knowledge/inventory.py')
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


def test_inventory_records_only_formats_and_counts_without_opening_content(tmp_path, monkeypatch):
    folder = tmp_path / 'synthetic'
    folder.mkdir()
    (folder / 'fictional-client.txt').write_text('sensitive-synthetic-text')
    (folder / 'recording.opus').write_bytes(b'synthetic bytes')
    def no_read(*_a, **_k):
        raise AssertionError('source content must not be read')
    monkeypatch.setattr(Path, 'read_text', no_read)
    monkeypatch.setattr(Path, 'read_bytes', no_read)
    data = inventory.inventory(tmp_path)
    assert data['files'] == 2
    assert data['formats'] == {'.opus': 1, '.txt': 1}
    assert 'fictional' not in str(data)
    assert data['content_read'] is False


def test_raw_exports_are_not_tracked_and_are_ignored_by_git_and_docker():
    assert not subprocess.check_output(['git', 'ls-files', '--', 'docs/Conversas'], cwd=ROOT)
    assert '/docs/Conversas/' in (ROOT / '.gitignore').read_text().splitlines()
    rules = (ROOT / '.dockerignore').read_text().splitlines()
    assert '/docs/Conversas/' in rules
    assert 'docs' in rules
    assert not any(x.startswith('!') and 'docs' in x for x in rules)
    dockerfile = (ROOT / 'Dockerfile').read_text()
    assert 'COPY backend/ /app/' in dockerfile
    assert 'COPY . ' not in dockerfile
