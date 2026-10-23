# -*- coding: utf-8 -*-
"""Синхронизация конфигов Z Code с Claude Code в репозитории.

Источник истины — конфиги Claude Code: CLAUDE.md, .claude/skills/, .mcp.json.
Порождаемые зеркала: AGENTS.md, .zcode/skills/, .zcode/config.json (mcp.servers).

Запуск:
    python sync_claude_configs.py [--repo ПУТЬ] [--check]
--check — только проверить расхождение, ничего не писать (код 1, если есть расхождения).
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

# Замены CLAUDE.md -> AGENTS.md. Новый устойчивый контекст — добавь шаблон сюда,
# а не правь AGENTS.md руками: файл целиком перегенерируется.
REPLACEMENTS = [
    ("# CLAUDE.md", "# AGENTS.md"),
    (
        "This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.",
        "This file provides guidance to Z Code when working with code in this repository.",
    ),
    ("из Claude Code", "из Z Code"),
    (".claude/skills/", ".zcode/skills/"),
]

# Ключи строгой схемы MCP ZCode: неизвестный ключ = сервер молча отбрасывается.
ZCODE_MCP_KEYS = ("type", "command", "args", "cwd", "env", "url", "headers", "enabled", "timeoutMs")


def build_agents_md(claude_md_path):
    """AGENTS.md, который должен получиться из текущего CLAUDE.md."""
    text = claude_md_path.read_text(encoding="utf-8", newline="")
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    return text


def sync_instructions(repo, check):
    lines, changed = [], False
    claude_md = repo / "CLAUDE.md"
    agents_md = repo / "AGENTS.md"
    if not claude_md.exists():
        return ["CLAUDE.md не найден — инструкции не синхронизированы"], False
    expected = build_agents_md(claude_md)
    if agents_md.exists() and agents_md.read_text(encoding="utf-8", newline="") == expected:
        lines.append("AGENTS.md: уже синхронизирован")
        return lines, False
    changed = True
    action = "разошёлся с CLAUDE.md" if agents_md.exists() else "не существует"
    if not check:
        with open(agents_md, "w", encoding="utf-8", newline="") as f:
            f.write(expected)
        action = "переписан из CLAUDE.md"
    # Упоминания Claude Code, не покрытые REPLACEMENTS: решает агент по смыслу.
    for i, line in enumerate(expected.splitlines(), 1):
        if "Claude Code" in line:
            lines.append(f"  осталось «Claude Code», строка {i}: {line.strip()[:90]}")
    lines.insert(0, f"AGENTS.md: {action}")
    return lines, changed


def dir_files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def sync_skills(repo, check):
    lines, changed = [], False
    src = repo / ".claude" / "skills"
    dst = repo / ".zcode" / "skills"
    if not src.exists():
        return [".claude/skills не найден — скиллы не синхронизированы"], False
    sources = {d.name: d for d in src.iterdir() if d.is_dir() and (d / "SKILL.md").exists()}
    if not dst.exists():
        changed = len(sources) > 0
        if not check:
            dst.mkdir(parents=True)
    for name, s in sorted(sources.items()):
        d = dst / name
        if d.exists() and dir_files(d) == dir_files(s):
            continue
        changed = True
        existed = d.exists()
        if not check:
            if existed:
                shutil.rmtree(d)
            shutil.copytree(s, d)
        lines.append(f"скилл {name}: {'обновлён' if existed else 'скопирован'}"
                     if not check else f"скилл {name}: отличается от .claude/skills")
    if dst.exists():
        for d in sorted(dst.iterdir()):
            if d.is_dir() and d.name not in sources:
                lines.append(f"скилл {d.name}: есть только в .zcode/skills (оставлен, удали вручную, если не нужен)")
    if not lines:
        lines.append("скиллы: уже синхронизированы")
    return lines, changed


def canonical_server(name, server):
    """Каноническая запись ZCode: допустимые ключи, type выводится, лишнее отбрасывается."""
    out = {k: server[k] for k in ZCODE_MCP_KEYS if k in server}
    if "type" not in out:
        out["type"] = "stdio" if "command" in out else "http"
    ordered = {"type": out.pop("type")}
    ordered.update(out)
    dropped = set(server) - set(ZCODE_MCP_KEYS)
    if "command" in server and "url" in server:
        print(f"  предупреждение: сервер {name}: и command, и url — в ZCode нужен ровно один")
    for k in sorted(dropped):
        print(f"  предупреждение: сервер {name}: ключ «{k}» не входит в схему ZCode и отброшен")
    return ordered


def sync_mcp(repo, check):
    lines, changed = [], False
    mcp_json = repo / ".mcp.json"
    config = repo / ".zcode" / "config.json"
    if not mcp_json.exists():
        return [".mcp.json не найден — MCP не синхронизирован"], False
    servers = {n: canonical_server(n, s) for n, s in json.loads(mcp_json.read_text(encoding="utf-8")).get("mcpServers", {}).items()}
    cfg = {}
    if config.exists():
        try:
            cfg = json.loads(config.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            lines.append(f".zcode/config.json: битый JSON ({e}) — будет переписан")
            changed = True
    old = cfg.get("mcp", {}).get("servers", {})
    if old == servers:
        lines.append("MCP: уже синхронизирован")
        return lines, changed
    changed = True
    for n in sorted(set(old) - set(servers)):
        lines.append(f"  сервер {n}: был только в .zcode/config.json — удаляется (был и в .mcp.json?)")
    cfg["mcp"] = {"servers": servers}
    if not check:
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines.insert(0, ".zcode/config.json: mcp.servers " + ("переписан из .mcp.json" if not check else "расходится с .mcp.json"))
    return lines, changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".", help="корень репозитория (по умолчанию текущая папка)")
    ap.add_argument("--check", action="store_true", help="только проверить, ничего не менять")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    all_lines, any_changed = [], False
    for step in (sync_instructions, sync_skills, sync_mcp):
        lines, changed = step(repo, args.check)
        all_lines += lines
        any_changed = any_changed or changed
    if args.check:
        mode = "ПРОВЕРКА: расхождения есть" if any_changed else "ПРОВЕРКА: всё синхронизировано"
    else:
        mode = "СИНХРОНИЗАЦИЯ ВЫПОЛНЕНА" if any_changed else "СИНХРОНИЗАЦИЯ: изменений не было"
    print("\n".join(all_lines))
    print(f"\n{mode}")
    sys.exit(1 if args.check and any_changed else 0)


if __name__ == "__main__":
    main()
