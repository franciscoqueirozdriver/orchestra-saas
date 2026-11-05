"""Metadata only. Does not open source files, upload, transcribe or index content."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path


def inventory(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Fonte deve ser uma pasta local existente, sem symlink na raiz")
    formats, depths = Counter(), Counter()
    files = size = folders = symlinks = 0
    for current, directories, names in os.walk(root, followlinks=False):
        parent = Path(current)
        directories[:] = [d for d in directories if not (parent / d).is_symlink()]
        folders += len(directories)
        for name in names:
            path = parent / name
            if path.is_symlink():
                symlinks += 1
                continue
            stat = path.stat()
            files += 1
            size += stat.st_size
            formats[path.suffix.lower() or '(sem extensão)'] += 1
            depths[str(len(path.relative_to(root).parts) - 1)] += 1
    return {'files': files, 'bytes': size, 'folders': folders, 'formats': dict(sorted(formats.items())),
            'file_depths': dict(sorted(depths.items())), 'skipped_symlink_files': symlinks,
            'content_read': False, 'names_recorded': False, 'uploaded': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--output', type=Path, required=True, help='Arquivo privado fora do repositório')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    out = args.output.absolute()
    if repo == out or repo in out.resolve().parents:
        parser.error('Inventário deve ficar fora do repositório')
    os.umask(0o077)
    out.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    # Exclusive creation protects an existing inventory; refuse symlink overwrite.
    with out.open('x', encoding='utf-8') as f:
        json.dump(inventory(args.root), f, ensure_ascii=False, indent=2)
    print('Inventário somente de metadados salvo privadamente; conteúdo não lido.')


if __name__ == '__main__':
    main()
