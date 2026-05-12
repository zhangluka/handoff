#!/usr/bin/env python3
"""
Handoff - Pass context between AI coding agents.

Syncs context from Claude Code sessions to Cursor rules,
so Cursor automatically knows what you did in Claude Code.

Usage:
    handoff sync [--project PATH] [--recent N]
    handoff show [--project PATH]
    handoff clear [--project PATH]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# ============================================================
# Constants
# ============================================================

CLAUDE_DIR = Path.home() / ".claude" / "projects"
AGENT_MEMORY_DIR = Path.home() / ".handoff"


# ============================================================
# Claude Code JSONL Parser
# ============================================================

def encode_project_path(path: str) -> str:
    """Convert /Users/bobby/project to -Users-bobby-project"""
    # Claude Code encodes paths by replacing / with -
    # Leading / becomes a leading -
    return path.replace("/", "-").rstrip("-")


def find_claude_sessions(project_path: str, recent_n: int = 5) -> list[dict]:
    """Find recent Claude Code session JSONL files for a project."""
    encoded = encode_project_path(project_path)
    project_dir = CLAUDE_DIR / encoded

    if not project_dir.exists():
        return []

    jsonl_files = sorted(
        project_dir.glob("*.jsonl"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    sessions = []
    for f in jsonl_files[:recent_n]:
        sessions.append({
            "path": str(f),
            "name": f.stem,  # session UUID
            "modified": datetime.fromtimestamp(f.stat().st_mtime),
            "size": f.stat().st_size,
        })

    return sessions


def parse_session_jsonl(jsonl_path: str) -> dict:
    """Parse a Claude Code session JSONL file and extract key info."""
    title = ""
    user_prompts = []
    files_changed = set()
    tool_calls = {}
    assistant_texts = []
    last_prompt = ""
    timestamp_start = None
    timestamp_end = None

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            record_type = record.get("type")

            # Session title
            if record_type == "ai-title":
                title = record.get("ai-title", "")

            # Last prompt marker
            elif record_type == "last-prompt":
                last_prompt = record.get("lastPrompt", "")

            # User messages (prompts, not tool results)
            elif record_type == "user":
                msg = record.get("message", {})
                content = msg.get("content", "")
                if isinstance(content, str) and content.strip():
                    user_prompts.append(content.strip()[:200])
                ts = record.get("timestamp")
                if ts:
                    if timestamp_start is None:
                        timestamp_start = ts
                    timestamp_end = ts

            # Assistant messages
            elif record_type == "assistant":
                msg = record.get("message", {})
                content_blocks = msg.get("content", [])
                if isinstance(content_blocks, list):
                    for block in content_blocks:
                        block_type = block.get("type")

                        # Tool use - extract file paths and tool names
                        if block_type == "tool_use":
                            tool_name = block.get("name", "")
                            tool_calls[tool_name] = tool_calls.get(tool_name, 0) + 1
                            tool_input = block.get("input", {})

                            # Extract file paths from common tools
                            if tool_name in ("Edit", "Write", "Read", "NotebookEdit"):
                                fp = tool_input.get("file_path", "")
                                if fp:
                                    files_changed.add(fp)
                            elif tool_name == "Bash":
                                cmd = tool_input.get("command", "")
                                # Try to extract file paths from common commands
                                for word in cmd.split():
                                    if "/" in word and not word.startswith("-"):
                                        # Heuristic: looks like a path
                                        p = Path(word)
                                        if p.suffix and len(p.suffix) <= 5:
                                            files_changed.add(word)

                        # Text content
                        elif block_type == "text":
                            text = block.get("text", "")
                            if text.strip():
                                assistant_texts.append(text.strip()[:500])

    return {
        "title": title,
        "user_prompts": user_prompts[:5],  # first 5 prompts
        "files_changed": sorted(files_changed),
        "tool_calls": tool_calls,
        "assistant_texts": assistant_texts[-3:],  # last 3 text blocks
        "last_prompt": last_prompt,
        "timestamp_start": timestamp_start,
        "timestamp_end": timestamp_end,
    }


def extract_context(project_path: str, recent_n: int = 5) -> dict:
    """Extract context from recent Claude Code sessions."""
    sessions = find_claude_sessions(project_path, recent_n)

    if not sessions:
        return {"sessions": [], "error": f"No sessions found for {project_path}"}

    parsed = []
    all_files = set()

    for session in sessions:
        info = parse_session_jsonl(session["path"])
        info["session_id"] = session["name"]
        info["modified"] = session["modified"].isoformat()
        parsed.append(info)
        all_files.update(info["files_changed"])

    return {
        "project": project_path,
        "sessions": parsed,
        "all_files_changed": sorted(all_files),
        "synced_at": datetime.now().isoformat(),
    }


# ============================================================
# Markdown Formatter
# ============================================================

def format_context_markdown(context: dict) -> str:
    """Format extracted context as markdown."""
    if context.get("error"):
        return f"# Agent Memory\n\n> {context['error']}\n"

    lines = [
        "# Agent Memory Sync",
        "",
        f"**Project**: `{context['project']}`",
        f"**Synced at**: {context['synced_at']}",
        "",
        "---",
        "",
        "## Recent Claude Code Sessions",
        "",
    ]

    for i, session in enumerate(context["sessions"], 1):
        title = session["title"] or f"Session {session['session_id'][:8]}"
        lines.append(f"### {i}. {title}")
        lines.append("")

        # Time
        if session["modified"]:
            lines.append(f"- **Time**: {session['modified']}")

        # User task (first prompt)
        if session["user_prompts"]:
            task = session["user_prompts"][0]
            lines.append(f"- **Task**: {task}")

        # Files changed
        if session["files_changed"]:
            files = ", ".join(f"`{Path(f).name}`" for f in session["files_changed"][:10])
            lines.append(f"- **Files**: {files}")

        # Tool calls summary
        if session["tool_calls"]:
            tools = ", ".join(f"{k}({v})" for k, v in sorted(session["tool_calls"].items()))
            lines.append(f"- **Tools**: {tools}")

        lines.append("")

    # All files changed section
    if context["all_files_changed"]:
        lines.append("---")
        lines.append("")
        lines.append("## All Files Changed")
        lines.append("")
        for f in context["all_files_changed"][:30]:
            lines.append(f"- `{f}`")
        lines.append("")

    return "\n".join(lines)


# ============================================================
# Storage: ~/.agent-memory/
# ============================================================

def get_project_name(project_path: str) -> str:
    """Get a clean project name from a path."""
    return Path(project_path).name


def get_memory_dir(project_path: str) -> Path:
    """Get the memory directory for a project."""
    name = get_project_name(project_path)
    return AGENT_MEMORY_DIR / name


def save_context(project_path: str, markdown: str):
    """Save context to ~/.agent-memory/<project>/context.md"""
    mem_dir = get_memory_dir(project_path)
    mem_dir.mkdir(parents=True, exist_ok=True)
    context_file = mem_dir / "context.md"
    context_file.write_text(markdown, encoding="utf-8")
    return context_file


def load_context(project_path: str) -> Optional[str]:
    """Load context from ~/.agent-memory/<project>/context.md"""
    context_file = get_memory_dir(project_path) / "context.md"
    if context_file.exists():
        return context_file.read_text(encoding="utf-8")
    return None


def clear_context(project_path: str):
    """Clear context for a project."""
    context_file = get_memory_dir(project_path) / "context.md"
    if context_file.exists():
        context_file.unlink()
        return True
    return False


# ============================================================
# Cursor Writer
# ============================================================

CURSOR_RULE_TEMPLATE = """---
description: Handoff context from Claude Code
globs: ["**/*"]
alwaysApply: true
---

{content}
"""


def write_to_cursor(project_path: str, markdown_content: str):
    """Write context to .cursor/rules/handoff-context.mdc"""
    cursor_rules_dir = Path(project_path) / ".cursor" / "rules"
    cursor_rules_dir.mkdir(parents=True, exist_ok=True)

    rule_file = cursor_rules_dir / "handoff-context.mdc"
    rule_content = CURSOR_RULE_TEMPLATE.format(content=markdown_content)
    rule_file.write_text(rule_content, encoding="utf-8")
    return rule_file


# ============================================================
# CLI Commands
# ============================================================

def cmd_sync(args):
    """Sync context from Claude Code to Cursor."""
    project_path = args.project

    if not Path(project_path).exists():
        print(f"Error: Project path does not exist: {project_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Syncing context for: {project_path}")
    print()

    # Extract from Claude Code
    context = extract_context(project_path, args.recent)

    if context.get("error"):
        print(f"Warning: {context['error']}", file=sys.stderr)
        sys.exit(1)

    # Format as markdown
    markdown = format_context_markdown(context)

    # Save to shared storage
    shared_file = save_context(project_path, markdown)
    print(f"  Saved to: {shared_file}")

    # Write to Cursor rules
    cursor_file = write_to_cursor(project_path, markdown)
    print(f"  Cursor:   {cursor_file}")

    # Summary
    total_sessions = len(context["sessions"])
    total_files = len(context["all_files_changed"])
    print()
    print(f"Synced {total_sessions} sessions, {total_files} files changed.")
    print()
    print("Open Cursor to use the synced context.")


def cmd_show(args):
    """Show current shared memory."""
    markdown = load_context(args.project)
    if markdown:
        print(markdown)
    else:
        print(f"No memory found for: {args.project}")
        print(f"Run 'agent-memory sync --project {args.project}' first.")


def cmd_clear(args):
    """Clear shared memory."""
    if clear_context(args.project):
        print(f"Cleared memory for: {args.project}")
    else:
        print(f"No memory found for: {args.project}")

    # Also clear Cursor rules
    cursor_rule = Path(args.project) / ".cursor" / "rules" / "handoff-context.mdc"
    if cursor_rule.exists():
        cursor_rule.unlink()
        print(f"Removed: {cursor_rule}")


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        prog="handoff",
        description="Pass context between AI coding agents.",
    )

    subparsers = parser.add_subparsers(dest="command")

    # sync
    sync_parser = subparsers.add_parser("sync", help="Sync context from Claude Code to Cursor")
    sync_parser.add_argument("--project", "-p", default=os.getcwd(), help="Project path (default: current directory)")
    sync_parser.add_argument("--recent", "-n", type=int, default=5, help="Number of recent sessions (default: 5)")

    # show
    show_parser = subparsers.add_parser("show", help="Show current shared memory")
    show_parser.add_argument("--project", "-p", default=os.getcwd(), help="Project path (default: current directory)")

    # clear
    clear_parser = subparsers.add_parser("clear", help="Clear shared memory")
    clear_parser.add_argument("--project", "-p", default=os.getcwd(), help="Project path (default: current directory)")

    args = parser.parse_args()

    if args.command == "sync":
        cmd_sync(args)
    elif args.command == "show":
        cmd_show(args)
    elif args.command == "clear":
        cmd_clear(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
