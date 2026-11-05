#!/usr/bin/env python3
"""Publish a reviewed full commit. Default: checks only, no service changes.

Run on the VPS. Never copies changes from the VPS back to GitHub.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def run(root, *args):
    return subprocess.check_output(args, cwd=root, text=True).strip()


def ensure_clean(root):
    if run(root, 'git', 'status', '--porcelain', '--untracked-files=all'):
        raise RuntimeError('VPS com alterações pendentes. Preserve e revise fora do fluxo de publicação; nada será sincronizado automaticamente.')


def validate_target(root, commit):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise RuntimeError('Informe o SHA completo de 40 caracteres do commit validado.')
    if run(root, 'git', 'cat-file', '-t', commit) != 'commit':
        raise RuntimeError('Destino não é um commit.')
    subprocess.run(['git', 'merge-base', '--is-ancestor', commit, 'refs/remotes/origin/main'], cwd=root, check=True)
    previous = run(root, 'git', 'rev-parse', 'HEAD')
    subprocess.run(['git', 'merge-base', '--is-ancestor', previous, commit], cwd=root, check=True)
    return previous


def image_inventory(root):
    result = {}
    for service in ('api', 'worker', 'web', 'db', 'redis', 'scheduler'):
        container = run(root, 'docker', 'compose', 'ps', '-q', service)
        if not container and service == 'scheduler':
            continue
        if not container:
            raise RuntimeError('Serviço ausente: ' + service + '. Primeiro bootstrap exige procedimento próprio.')
        image = run(root, 'docker', 'inspect', '--format', '{{.Image}}', container)
        result[service] = {'container_id': container, 'image_id': image}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('commit')
    parser.add_argument('--checkout-root', type=Path, help='Checkout alvo, para executar uma cópia revisada da ferramenta fora do repositório.')
    parser.add_argument('--allow-outbound', action='store_true', help='Somente para piloto de envio explicitamente autorizado; respeita OUTBOUND_ENABLED configurado.')
    parser.add_argument('--apply', action='store_true', help='Autoriza publicação e execução do deploy, incluindo as migrations do commit.')
    parser.add_argument('--expected-db-revision', help='Obrigatório no apply; recusa revisão atual diferente da revisada.')
    parser.add_argument('--allow-schema-change', action='store_true', help='Confirma revisão do plano de migrations e rollback.')
    args = parser.parse_args()
    root = (args.checkout_root or Path(__file__).resolve().parents[1]).resolve()
    # Check before fetch, Docker, filesystem receipts or backup.
    ensure_clean(root)
    subprocess.run(['git', 'fetch', '--no-tags', 'origin', 'main'], cwd=root, check=True)
    previous = validate_target(root, args.commit)
    changed = run(root, 'git', 'diff', '--name-only', previous, args.commit).splitlines()
    schema_change = any(p.startswith('backend/migrations/') for p in changed)
    images = image_inventory(root)
    revision = run(root, 'docker', 'compose', 'exec', '-T', 'db', 'sh', '-c',
                   'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "BEGIN READ ONLY; SELECT version_num FROM public.alembic_version; COMMIT;"')
    revisions = [s for s in revision.splitlines() if s not in ('BEGIN', 'COMMIT')]
    revision = ','.join(revisions)
    print('Origem:', previous, '\nDestino:', args.commit, '\nBanco:', revision,
          '\nAlteração de migrations:', schema_change, flush=True)
    if not args.apply:
        print('Somente conferência concluída. Nenhum serviço alterado.')
        return
    if not args.expected_db_revision or args.expected_db_revision != revision:
        raise RuntimeError('Revisão do banco não corresponde à revisão explicitamente autorizada.')
    if schema_change and not args.allow_schema_change:
        raise RuntimeError('Revise as migrations antes de autorizar --allow-schema-change.')
    ensure_clean(root)
    os.umask(0o077)
    release_dir = Path.home() / 'orchestra-releases' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    release_dir.mkdir(parents=True, mode=0o700)
    receipt = {'previous_commit': previous, 'target_commit': args.commit, 'previous_db_revision': revision, 'images': images, 'status': 'prepared'}
    (release_dir / 'receipt.json').write_text(json.dumps(receipt, indent=2))
    # Backup helper already requires a protected passphrase; do not bypass failure.
    subprocess.run(['bash', 'scripts/backup.sh'], cwd=root, check=True)
    for service in ('api', 'worker', 'web'):
        tag = 'orquestra-' + service + ':rollback-' + release_dir.name.lower()
        subprocess.run(['docker', 'image', 'tag', images[service]['image_id'], tag], check=True)
        images[service]['rollback_tag'] = tag
    (release_dir / 'receipt.json').write_text(json.dumps(receipt, indent=2))
    # Check again to catch operator edits made during backup. Requires an exclusive
    # maintenance window; Git cannot lock humans editing source outside this process.
    ensure_clean(root)
    subprocess.run(['git', 'checkout', '--detach', args.commit], cwd=root, check=True)
    env = dict(os.environ, ORCHESTRA_EXPECTED_COMMIT=args.commit, ORCHESTRA_ALLOW_OUTBOUND_DEPLOY='yes' if args.allow_outbound else 'no')
    if not args.allow_outbound:
        env['OUTBOUND_ENABLED'] = 'false'
    try:
        subprocess.run(['bash', 'scripts/deploy.sh'], cwd=root, env=env, check=True)
        # Caddyfile is bind-mounted: recreate explicitly so new inode/config is used.
        subprocess.run(['docker', 'compose', 'up', '-d', '--no-deps', '--force-recreate', 'web'], cwd=root, check=True)
    except subprocess.CalledProcessError:
        receipt['status'] = 'failed_review_required'
        (release_dir / 'receipt.json').write_text(json.dumps(receipt, indent=2))
        raise
    receipt['outbound_pilot_requested'] = args.allow_outbound
    receipt['status'] = 'started_external_checks_pending'
    (release_dir / 'receipt.json').write_text(json.dumps(receipt, indent=2))
    print('Recibo privado:', release_dir, '\nValide HTTPS, worker e sites adicionais. Não há rollback automático do banco.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print('Publicação interrompida:', exc, file=sys.stderr)
        sys.exit(1)
