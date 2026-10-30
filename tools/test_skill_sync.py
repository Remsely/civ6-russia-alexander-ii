"""Regression checks for project skill mirroring; uses an isolated temporary repository."""
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / '.agents/skills/claude-config-sync/scripts/sync_claude_configs.py'
if len(sys.argv) > 1:
    SCRIPT = Path(sys.argv[1]).resolve()

with tempfile.TemporaryDirectory() as tmp:
    repo = Path(tmp)
    skill = repo / '.agents/skills/example'
    (skill / 'references').mkdir(parents=True)
    (skill / 'SKILL.md').write_text('source', encoding='utf8')
    (skill / 'references/context.md').write_text('context', encoding='utf8')
    (repo / 'AGENTS.md').write_text('codex', encoding='utf8')
    (repo / 'CLAUDE.md').write_text('claude', encoding='utf8')
    def run(*args):
        return subprocess.run([sys.executable, str(SCRIPT), '--repo', str(repo), *args],
                              capture_output=True, text=True, encoding='utf8')
    assert run('--check').returncode == 1
    assert not (repo / '.claude').exists(), 'check must be read-only'
    assert run().returncode == 0
    for agent in ('.claude', '.zcode'):
        target = repo / agent / 'skills/example'
        assert (target / 'SKILL.md').read_text(encoding='utf8') == 'source'
        assert (target / 'references/context.md').read_text(encoding='utf8') == 'context'
    assert run('--check').returncode == 0
    (repo / '.claude/skills/example/SKILL.md').write_text('drift', encoding='utf8')
    extra = repo / '.zcode/skills/example/custom.txt'
    extra.write_text('keep', encoding='utf8')
    assert run('--check').returncode == 1
    assert run().returncode == 0
    assert extra.read_text(encoding='utf8') == 'keep'
    assert run('--check').returncode == 1, 'extra files must remain visible as drift'
    assert (repo / 'AGENTS.md').read_text(encoding='utf8') == 'codex'
    assert (repo / 'CLAUDE.md').read_text(encoding='utf8') == 'claude'
    assert not (repo / '.zcode/config.json').exists(), 'MCP is opt-in'
    assert not run('--sync-agents').returncode == 0
print('OK: mirrors, drift, extra files, instructions and MCP isolation')
