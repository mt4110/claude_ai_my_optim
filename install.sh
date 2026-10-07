#!/usr/bin/env bash
# 個人用の基本指示だけを導入する。権限設定・スキルは変更しない。
set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' '導入にはPython 3が必要です。設定は変更していません。' >&2
  exit 1
fi
INSTALL_SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
exec python3 - "$INSTALL_SOURCE_DIR" "$@" <<'PY'
import argparse
import datetime
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys


class InstallError(Exception):
    pass


def fail(message):
    raise InstallError(message)


def check_path(path, directory=False):
    if path.is_symlink():
        fail(f'リンク先を変更しないため停止しました: {path}')
    if not path.exists():
        return
    mode = path.stat()
    if directory:
        if not stat.S_ISDIR(mode.st_mode):
            fail(f'ディレクトリではありません: {path}')
    elif not stat.S_ISREG(mode.st_mode) or mode.st_nlink != 1:
        fail(f'通常の独立したファイルではありません: {path}')


def read(path):
    check_path(path)
    return path.read_bytes() if path.exists() else None


def merged_block(original, body, begin, end, path):
    raw = original or b''
    try:
        raw.decode('utf-8')
    except UnicodeError:
        fail(f'UTF-8のテキストではないため停止しました: {path}')
    block = begin + b'\n' + body + b'\n' + end + b'\n'
    if begin in raw or end in raw:
        if raw.count(begin) != 1 or raw.count(end) != 1 or block not in raw:
            fail(f'既存の導入部分が変更されています。上書きしません: {path}')
        return raw
    separator = b'' if not raw or raw.endswith(b'\n') else b'\n'
    return raw + separator + block


def main():
    parser = argparse.ArgumentParser(
        prog='install.sh', description='現在のプロジェクトへ基本指示と個人設定を導入します。')
    parser.add_argument('target', nargs='?', default='.', help='対象プロジェクト。省略時は現在地')
    parser.add_argument('--dry-run', action='store_true', help='変更予定だけを表示。ファイルは作成しません')
    args = parser.parse_args(sys.argv[2:])
    source = Path(sys.argv[1])
    try:
        target = Path(args.target).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        fail('対象ディレクトリが存在しないか、解決できません。')
    if not target.is_dir() or any(c in str(target) for c in '\r\n'):
        fail('対象には改行を含まないディレクトリを指定してください。')

    local = target / '.claude/local'
    history = local / '.install-history'
    lock = local / '.install-lock'
    for directory in [target / '.claude', local, history]:
        check_path(directory, directory=True)
    if lock.exists() or lock.is_symlink():
        fail(f'別の導入または中断した導入があります。確認してください: {lock}')

    # Gitの呼び出しへ、別リポジトリ向けの環境設定を引き継がない。
    git_env = dict(os.environ)
    for key in ['GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR']:
        git_env.pop(key, None)

    def git(*arguments):
        return subprocess.run(['git', '-C', str(target), *arguments],
                              env=git_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    in_git = False
    git_marker = any((directory / '.git').exists() or (directory / '.git').is_symlink()
                     for directory in [target, *target.parents])
    if shutil.which('git'):
        root_result = git('rev-parse', '--show-toplevel')
        if root_result.returncode == 0:
            git_root = Path(os.fsdecode(root_result.stdout).rstrip('\n')).resolve()
            if git_root != target:
                fail(f'Gitプロジェクトの直下で実行してください: {git_root}')
            in_git = True
            tracked = git('ls-files', '-z', '--', 'CLAUDE.local.md', '.claude/local')
            if tracked.returncode != 0:
                fail('Gitの追跡状態を確認できません。設定は変更していません。')
            if tracked.stdout:
                fail('個人用の配置先にGit追跡済みファイルがあります。先に人が公開範囲を確認してください。')
        elif git_marker:
            fail('Gitリポジトリが見つかりましたが状態を確認できません。設定は変更していません。')
    elif git_marker:
        fail('Gitリポジトリへの導入にはGitコマンドが必要です。設定は変更していません。')

    # local指示の追加で、従来のAGENTS.md読み込みが失われないよう確認する。
    hierarchy = [target, *target.parents]
    existing_claude = any((directory / name).exists()
                          for directory in hierarchy
                          for name in ['CLAUDE.md', 'CLAUDE.local.md', '.claude/CLAUDE.md'])
    if not existing_claude:
        for directory in target.parents:
            if any((directory / name).exists() for name in ['AGENTS.md', '.claude/AGENTS.md']):
                fail('親ディレクトリのAGENTS.mdがあります。読み込みを変えないため、既存指示の統合を確認してから導入してください。')

    imports = []
    for name in ['AGENTS.md', '.claude/AGENTS.md']:
        path = target / name
        if path.exists() or path.is_symlink():
            check_path(path)
            imports.append('@' + name)
    imports.extend(['@.claude/local/BASE.md', '@.claude/local/PERSONAL.md'])

    payloads = [
        (local / 'BASE.md', source / 'kit/CLAUDE.md'),
        (local / 'PERSONAL.md', source / 'personalization/owner/PERSONAL.md'),
    ]
    original = {}
    desired = {}
    for destination, origin in payloads:
        check_path(origin)
        if not origin.is_file():
            fail(f'配布元のファイルがありません: {origin}')
        data = origin.read_bytes()
        current = read(destination)
        if current is not None and current != data:
            fail(f'既存の個人用ファイルが異なります。上書きしません: {destination}')
        original[destination], desired[destination] = current, data

    entry = target / 'CLAUDE.local.md'
    ignore = target / '.gitignore'
    original[entry], original[ignore] = read(entry), read(ignore)
    desired[entry] = merged_block(
        original[entry], '\n'.join(imports).encode(),
        b'<!-- BEGIN claude-development-kit local -->',
        b'<!-- END claude-development-kit local -->', entry)
    desired[ignore] = merged_block(
        original[ignore], b'/CLAUDE.local.md\n/.claude/local/',
        b'# BEGIN claude-development-kit local', b'# END claude-development-kit local', ignore)

    changed = [path for path in desired if original[path] != desired[path]]
    print(f'対象: {target}')
    for path in desired:
        action = '追加' if original[path] is None else '追記' if path in changed else '変更なし'
        print(f'{action}: {path.relative_to(target)}')
    if args.dry_run:
        print('変更予定の表示だけで終了しました。')
        return

    def verify_ignore():
        if in_git:
            for name in ['CLAUDE.local.md', '.claude/local/BASE.md', '.claude/local/PERSONAL.md']:
                if git('check-ignore', '-q', '--no-index', '--', name).returncode != 0:
                    fail(f'Gitの除外が有効ではありません。私的ファイルの配置を停止しました: {name}')

    if not changed:
        verify_ignore()
        print('導入済みです。変更はありません。')
        return

    if ignore not in changed:
        verify_ignore()

    # 同時に実行するinstaller同士を排他。一般のエディタ操作とは排他できない。
    local.mkdir(parents=True, exist_ok=True)
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError:
        fail('別の導入が開始されたため停止しました。')
    os.chmod(lock, 0o700)
    committed = []
    run = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ') + f'-{os.getpid()}'
    archived = history / run
    try:
        for path in desired:
            if read(path) != original[path]:
                fail('確認後に対象ファイルが変わりました。再度確認してください。')
        def prepare(index, path):
            before = original[path]
            if before is not None:
                shutil.copy2(path, lock / f'{index}.before')
            stage = lock / f'{index}.next'
            with stage.open('xb') as stream:
                stream.write(desired[path])
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(stage, stat.S_IMODE(path.stat().st_mode) if before is not None else 0o600)
        (lock / 'changes.txt').write_text(
            '\n'.join(f'{index}: {path.relative_to(target)}' for index, path in enumerate(changed)) + '\n')
        # 除外を先に反映し、Gitが実際に除外することを確認してから私的ファイルを置く。
        order = [ignore] + [path for path in changed if path != ignore]
        for path in order:
            if path not in changed:
                continue
            if read(path) != original[path]:
                fail(f'書き込み前に対象が変わりました: {path}')
            index = changed.index(path)
            prepare(index, path)
            os.replace(lock / f'{index}.next', path)
            committed.append(str(path.relative_to(target)))
            if path == ignore:
                verify_ignore()
        verify_ignore()
        print('導入が完了しました。Claude Codeの新しい会話で/contextを確認してください。')
    finally:
        (lock / 'applied.txt').write_text('\n'.join(committed) + '\n')
        check_path(history, directory=True)
        history.mkdir(mode=0o700, exist_ok=True)
        lock.rename(archived)
        print(f'変更前の記録: {archived}')


try:
    main()
except (InstallError, OSError) as error:
    print(f'停止: {error}', file=sys.stderr)
    print('途中の変更は自動で削除・復元しません。記録が表示された場合は確認してください。', file=sys.stderr)
    sys.exit(1)
PY
