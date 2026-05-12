# Handoff

> Stop re-explaining your project every time you switch AI coding agents.

![Handoff Demo](demo/handoff-demo.gif)

[中文](./README_zh.md)

## What is this?

You use Claude Code for backend. You use Cursor for frontend. Every time you switch, the new agent knows nothing — you re-explain your project, your decisions, your progress.

Handoff fixes that. One command extracts what you did in Claude Code and injects it into Cursor's rules. Cursor starts the conversation already informed.

## Install

```bash
# Run directly (no install needed)
python3 handoff.py sync

# Or add to PATH
chmod +x handoff.py
ln -s $(pwd)/handoff.py /usr/local/bin/handoff
```

## Usage

```bash
# Sync in current project directory
handoff sync

# Specify project path
handoff sync --project /path/to/project

# Sync last 10 sessions
handoff sync --recent 10

# View current memory
handoff show

# Clear memory
handoff clear
```

## How it works

```
Claude Code session logs (~/.claude/projects/*//*.jsonl)
    ↓ Parse JSONL
    ↓ Extract: titles, file changes, tool calls, user tasks
    ↓ Format as markdown
    ↓
~/.handoff/<project>/context.md          (shared storage)
    ↓ Inject
    ↓
.cursor/rules/handoff-context.mdc        (Cursor auto-reads)
```

### What gets extracted

| Content | Source |
|---------|--------|
| Session title | Claude Code's auto-generated `ai-title` |
| User task | The user's prompt |
| Files changed | File paths from Edit/Write/Read tool calls |
| Tool call stats | Tool names and call counts |

**No LLM needed. Pure rule-based extraction. Zero cost.**

## What happens after

Run `handoff sync`, then open Cursor. Its Agent automatically reads `.cursor/rules/handoff-context.mdc` and knows:

- What tasks you did in Claude Code
- Which files you changed
- What tools you used
- Where you left off

**No re-explaining. Just start working.**

## Requirements

- Python 3.9+
- No external dependencies (stdlib only)

## Roadmap

- [x] Claude Code → Cursor sync
- [ ] Claude Code → Codex sync
- [ ] Codex → Cursor sync
- [ ] Auto-sync on session end
- [ ] Gemini CLI / Windsurf support

## Why "Handoff"?

It's a relay race. One agent runs, passes the baton, the next agent picks up without stopping.

## License

MIT
