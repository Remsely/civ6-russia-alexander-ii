# -*- coding: utf-8 -*-
"""Mirror project skills from Codex to Claude Code and Z Code.

python sync_claude_configs.py [--repo PATH] [--check] [--mcp]
--check is read-only and returns 1 for skill or requested MCP drift.
--mcp separately enables the legacy .mcp.json -> .zcode/config.json sync.
AGENTS.md, CLAUDE.md, Codex settings and mirror-only files are never removed.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

MCP_KEYS = ("type", "command", "args", "cwd", "env", "url", "headers", "enabled", "timeoutMs")


def inside(repo, path):
    if not path.resolve().is_relative_to(repo):
        raise ValueError(f"Путь выходит за пределы проекта: {path}")


def skill_files(folder):
    files = {}
    for path in folder.rglob('*'):
        if path.is_symlink():
            raise ValueError(f"Ссылки внутри скиллов не поддерживаются: {path}")
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            files[path.relative_to(folder)] = path.read_bytes()
    return files


def sync_skills(repo, check):
    source = repo / '.agents' / 'skills'
    inside(repo, source)
    if not source.is_dir():
        raise ValueError('Нет источника .agents/skills')
    skills = sorted(p for p in source.iterdir() if p.is_dir() and (p / 'SKILL.md').is_file())
    if not skills:
        raise ValueError('В .agents/skills не найдено ни одного скилла')
    changed = False
    for rootname in ('.claude', '.zcode'):
        target_root = repo / rootname / 'skills'
        inside(repo, target_root)
        for skill in skills:
            inside(repo, skill)
            target = target_root / skill.name
            inside(repo, target)
            src = skill_files(skill)
            dst = skill_files(target) if target.exists() else {}
            updates = [name for name, contents in src.items() if dst.get(name) != contents]
            extra = sorted(set(dst) - set(src))
            if updates or extra:
                changed = True
                print(f'{rootname}/skills/{skill.name}: обновить {len(updates)}, лишних файлов {len(extra)}')
            if not check:
                for name in updates:
                    dest = target / name
                    inside(repo, dest)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(skill / name, dest)
            for name in extra:
                print(f'  сохранён лишний файл: {target / name}')
        if target_root.exists():
            for folder in sorted(target_root.iterdir()):
                if folder.is_dir() and folder.name not in {s.name for s in skills}:
                    print(f'  сохранён скилл только в {rootname}: {folder.name}')
    if not changed:
        print('Скиллы Codex и зеркала совпадают')
    return changed


def sync_mcp(repo, check):
    source = repo / '.mcp.json'
    target = repo / '.zcode' / 'config.json'
    inside(repo, source)
    inside(repo, target)
    if not source.exists():
        print('.mcp.json не найден — MCP не изменён')
        return False
    servers = {}
    for name, value in json.loads(source.read_text(encoding='utf8')).get('mcpServers', {}).items():
        canonical = {k: value[k] for k in MCP_KEYS if k in value}
        canonical.setdefault('type', 'stdio' if 'command' in value else 'http')
        servers[name] = canonical
        for key in sorted(set(value) - set(MCP_KEYS)):
            print(f'  MCP {name}: отброшен неподдерживаемый ключ {key}')
    cfg = json.loads(target.read_text(encoding='utf8')) if target.exists() else {}
    if cfg.get('mcp', {}).get('servers', {}) == servers:
        print('MCP уже синхронизирован')
        return False
    print('MCP Z Code расходится с .mcp.json')
    if not check:
        cfg.setdefault('mcp', {})['servers'] = servers
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + '\n', encoding='utf8')
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', default='.')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--mcp', action='store_true')
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    try:
        changed = sync_skills(repo, args.check)
        if args.mcp:
            changed = sync_mcp(repo, args.check) or changed
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f'Ошибка синхронизации: {exc}', file=sys.stderr)
        return 1
    print('AGENTS.md, CLAUDE.md и настройки MCP не изменены' if not args.mcp else 'AGENTS.md и CLAUDE.md не изменены')
    return int(args.check and changed)


if __name__ == '__main__':
    sys.exit(main())
