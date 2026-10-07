"""導入先は合成の一時プロジェクトだけ。確認用ファイルは削除せず残す。"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'install.sh'


class InstallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / '.work').mkdir(exist_ok=True)
        cls.artifacts = Path(tempfile.mkdtemp(prefix='install-tests-', dir=ROOT / '.work'))
        print(f'確認用プロジェクト（保全）: {cls.artifacts}', flush=True)

    def project(self, label='project'):
        path = self.artifacts / self._testMethodName / label
        path.mkdir(parents=True)
        subprocess.run(['git', 'init', '-q', str(path)], check=True)
        return path

    def install(self, path, *args, script=SCRIPT):
        return subprocess.run(['bash', str(script), *args], cwd=path,
                              capture_output=True, text=True)

    def snapshot(self, path):
        return {str(p.relative_to(path)): p.read_bytes()
                for p in path.rglob('*') if p.is_file() and '.git' not in p.parts}

    def assert_installed(self, path):
        self.assertEqual((path / '.claude/local/BASE.md').read_bytes(),
                         (ROOT / 'kit/CLAUDE.md').read_bytes())
        self.assertEqual((path / '.claude/local/PERSONAL.md').read_bytes(),
                         (ROOT / 'personalization/owner/PERSONAL.md').read_bytes())
        for name in ['CLAUDE.local.md', '.claude/local/BASE.md', '.claude/local/PERSONAL.md']:
            result = subprocess.run(['git', '-C', str(path), 'check-ignore', '-q', '--', name])
            self.assertEqual(result.returncode, 0, name)

    def test_fresh_install_and_ignore(self):
        path = self.project()
        result = self.install(path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed(path)
        self.assertFalse((path / 'CLAUDE.md').exists())
        self.assertFalse((path / '.claude/settings.json').exists())
        self.assertFalse((path / '.claude/local/.install-lock').exists())

    def test_second_run_has_no_changes(self):
        path = self.project()
        self.assertEqual(self.install(path).returncode, 0)
        before = self.snapshot(path)
        result = self.install(path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, self.snapshot(path))

    def test_dry_run_does_not_create_files(self):
        path = self.project()
        before = self.snapshot(path)
        result = self.install(path, '--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, self.snapshot(path))
        self.assertFalse((path / '.claude').exists())

    def test_preserves_team_local_ignore_and_permissions(self):
        path = self.project()
        team = b'# team\n'
        local = '# 個人の既存設定\r\n末尾改行なし'.encode()
        ignore = b'dist/\r\n'
        (path / 'CLAUDE.md').write_bytes(team)
        (path / 'CLAUDE.local.md').write_bytes(local)
        (path / 'CLAUDE.local.md').chmod(0o640)
        (path / '.gitignore').write_bytes(ignore)
        result = self.install(path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((path / 'CLAUDE.md').read_bytes(), team)
        self.assertTrue((path / 'CLAUDE.local.md').read_bytes().startswith(local + b'\n'))
        self.assertTrue((path / '.gitignore').read_bytes().startswith(ignore))
        self.assertEqual((path / 'CLAUDE.local.md').stat().st_mode & 0o777, 0o640)
        backups = list((path / '.claude/local/.install-history').glob('*/[0-9]*.before'))
        self.assertIn(local, [p.read_bytes() for p in backups])
        self.assertIn(ignore, [p.read_bytes() for p in backups])

    def test_conflicting_personal_stops_before_writes(self):
        path = self.project()
        (path / '.claude/local').mkdir(parents=True)
        (path / '.claude/local/PERSONAL.md').write_text('自分で変更した設定')
        before = self.snapshot(path)
        result = self.install(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(before, self.snapshot(path))
        self.assertFalse((path / '.gitignore').exists())

    def test_root_agents_is_preserved(self):
        path = self.project()
        (path / 'AGENTS.md').write_text('プロジェクトの指示')
        result = self.install(path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('@AGENTS.md\n', (path / 'CLAUDE.local.md').read_text())
        self.assertEqual((path / 'AGENTS.md').read_text(), 'プロジェクトの指示')
        self.assertEqual(self.install(path).returncode, 0)

    def test_parent_agents_requires_manual_integration(self):
        path = self.project()
        (path.parent / 'AGENTS.md').write_text('親の指示')
        result = self.install(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((path / '.claude').exists())

    def test_tracked_personal_file_is_not_modified(self):
        path = self.project()
        (path / 'CLAUDE.local.md').write_text('追跡済み')
        subprocess.run(['git', '-C', str(path), 'add', 'CLAUDE.local.md'], check=True)
        before = self.snapshot(path)
        result = self.install(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(before, self.snapshot(path))

    def test_symlink_directory_is_not_followed(self):
        path = self.project()
        outside = path.parent / 'outside'
        outside.mkdir()
        (path / '.claude').symlink_to(outside, target_is_directory=True)
        result = self.install(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((path / '.gitignore').exists())

    def test_symlink_entry_is_not_followed(self):
        path = self.project()
        outside = path.parent / 'outside.txt'
        outside.write_text('保全する内容')
        (path / 'CLAUDE.local.md').symlink_to(outside)
        result = self.install(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(outside.read_text(), '保全する内容')
        self.assertFalse((path / '.claude').exists())

    def test_modified_managed_block_stops(self):
        path = self.project()
        self.assertEqual(self.install(path).returncode, 0)
        entry = path / 'CLAUDE.local.md'
        entry.write_text(entry.read_text().replace('@.claude/local/BASE.md', '# 内容を変更'))
        before = self.snapshot(path)
        result = self.install(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(before, self.snapshot(path))

    def test_subdirectory_is_not_targeted_by_accident(self):
        path = self.project()
        child = path / 'src'
        child.mkdir()
        result = self.install(child)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((child / '.claude').exists())

    def test_spaces_japanese_quotes_and_source_location(self):
        path = self.project("日本語 project's folder")
        source = path.parent / "配布 kit's folder"
        (source / 'kit').mkdir(parents=True)
        (source / 'personalization/owner').mkdir(parents=True)
        for name in ['install.sh', 'kit/CLAUDE.md', 'personalization/owner/PERSONAL.md']:
            shutil.copyfile(ROOT / name, source / name)
        result = self.install(path, script=source / 'install.sh')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed(path)

    def test_existing_lock_stops_without_changes(self):
        path = self.project()
        (path / '.claude/local/.install-lock').mkdir(parents=True)
        before = self.snapshot(path)
        result = self.install(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(before, self.snapshot(path))

    def test_ignore_override_stops_before_personal_payload(self):
        path = self.project()
        (path / '.claude').mkdir()
        (path / '.claude/.gitignore').write_text('!local/\n!local/**\n')
        result = self.install(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((path / '.claude/local/PERSONAL.md').exists())
        self.assertFalse((path / '.claude/local/BASE.md').exists())
        self.assertTrue((path / '.claude/local/.install-history').is_dir())
        self.assertFalse(list((path / '.claude/local/.install-history').glob('*/[0-9]*.next')))

    def test_explicit_target_from_another_directory(self):
        path = self.project('explicit target')
        result = self.install(path.parent, str(path))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed(path)
        self.assertFalse((path.parent / '.claude').exists())

    def test_hardlinked_entry_is_not_replaced(self):
        import os
        path = self.project()
        outside = path.parent / 'original.txt'
        outside.write_text('変更しない内容')
        os.link(outside, path / 'CLAUDE.local.md')
        result = self.install(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(outside.read_text(), '変更しない内容')
        self.assertFalse((path / '.claude').exists())

    def test_non_utf8_entry_stops_before_writes(self):
        path = self.project()
        (path / 'CLAUDE.local.md').write_bytes(b'\xff\x00')
        result = self.install(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((path / 'CLAUDE.local.md').read_bytes(), b'\xff\x00')
        self.assertFalse((path / '.claude').exists())

    def test_broken_git_is_not_treated_as_untracked_project(self):
        path = self.artifacts / self._testMethodName / 'broken'
        path.mkdir(parents=True)
        (path / '.git').write_text('gitdir: /not-existing-install-test-git')
        result = self.install(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((path / '.claude').exists())


if __name__ == '__main__':
    unittest.main()
