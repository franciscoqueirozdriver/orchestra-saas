import importlib.util
from pathlib import Path
import subprocess

import pytest

spec = importlib.util.spec_from_file_location('release', Path(__file__).resolve().parents[1] / 'scripts/release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True).strip()


def repository(tmp_path):
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.email', 'synthetic@example.invalid')
    git(tmp_path, 'config', 'user.name', 'Synthetic test')
    (tmp_path / 'source.py').write_text('pass\n')
    git(tmp_path, 'add', 'source.py')
    git(tmp_path, 'commit', '-qm', 'synthetic baseline')
    head = git(tmp_path, 'rev-parse', 'HEAD')
    git(tmp_path, 'update-ref', 'refs/remotes/origin/main', head)
    return head


def test_release_refuses_new_or_modified_remote_source(tmp_path):
    repository(tmp_path)
    release.ensure_clean(tmp_path)
    (tmp_path / 'untracked.py').write_text('pass\n')
    with pytest.raises(RuntimeError, match='alterações pendentes'):
        release.ensure_clean(tmp_path)
    # Do not mutate production to test the guard; this repository is disposable.
    git(tmp_path, 'add', 'untracked.py')
    git(tmp_path, 'commit', '-qm', 'synthetic second')
    (tmp_path / 'source.py').write_text('changed\n')
    with pytest.raises(RuntimeError):
        release.ensure_clean(tmp_path)


def test_release_requires_full_reviewed_commit_reachable_from_main(tmp_path):
    head = repository(tmp_path)
    assert release.validate_target(tmp_path, head) == head
    with pytest.raises(RuntimeError, match='SHA completo'):
        release.validate_target(tmp_path, head[:7])
    (tmp_path / 'source.py').write_text('new work\n')
    git(tmp_path, 'add', 'source.py')
    git(tmp_path, 'commit', '-qm', 'not published')
    unpublished = git(tmp_path, 'rev-parse', 'HEAD')
    with pytest.raises(subprocess.CalledProcessError):
        release.validate_target(tmp_path, unpublished)
    with pytest.raises(subprocess.CalledProcessError):
        release.validate_target(tmp_path, head)  # would rewind current checkout


def test_low_level_deploy_refuses_dirty_checkout_before_docker(tmp_path):
    import os
    repository(tmp_path)
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    source = Path(__file__).resolve().parents[1] / 'scripts/deploy.sh'
    target = scripts / 'deploy.sh'
    target.write_text(source.read_text())
    git(tmp_path, 'add', 'scripts/deploy.sh')
    git(tmp_path, 'commit', '-qm', 'synthetic deploy helper')
    (tmp_path / 'source.py').write_text('pending work\n')
    tools = tmp_path.parent / 'fake-tools'
    tools.mkdir(exist_ok=True)
    docker = tools / 'docker'
    docker.write_text('#!/bin/sh\ntouch "$DOCKER_TEST_MARKER"\nexit 99\n')
    docker.chmod(0o700)
    marker = tmp_path.parent / 'docker-was-called'
    result = subprocess.run(['bash', str(target)], cwd=tmp_path, capture_output=True, text=True,
                            env=dict(os.environ, PATH=str(tools) + ':' + os.environ['PATH'], DOCKER_TEST_MARKER=str(marker)))
    assert result.returncode != 0
    assert 'alterações pendentes' in result.stderr
    assert not marker.exists()
