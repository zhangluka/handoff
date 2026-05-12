# Handoff

> 每次切换 AI 编程工具，都要重新解释一遍项目上下文？不需要了。

[English](./README.md)

## 这是什么？

你用 Claude Code 写后端，用 Cursor 写前端。每次切换，新 Agent 什么都不知道——你得重新解释项目结构、技术决策、当前进度。

Handoff 解决这个问题。一条命令，自动从 Claude Code 的 session 日志中提取关键信息，注入到 Cursor 的规则文件里。Cursor 开口就知道你之前做了什么。

## 安装

```bash
# 直接运行（无需安装）
python3 handoff.py sync

# 或者添加到 PATH
chmod +x handoff.py
ln -s $(pwd)/handoff.py /usr/local/bin/handoff
```

## 使用

```bash
# 在项目目录下运行
handoff sync

# 指定项目路径
handoff sync --project /path/to/project

# 同步最近 10 个 session
handoff sync --recent 10

# 查看当前记忆
handoff show

# 清除记忆
handoff clear
```

## 工作原理

```
Claude Code session 日志 (~/.claude/projects/*//*.jsonl)
    ↓ 解析 JSONL
    ↓ 提取：标题、文件变更、工具调用、用户任务
    ↓ 格式化为 markdown
    ↓
~/.handoff/<project>/context.md          (共享存储)
    ↓ 同步注入
    ↓
.cursor/rules/handoff-context.mdc        (Cursor 自动读取)
```

### 提取内容

| 内容 | 来源 |
|------|------|
| Session 标题 | Claude Code 自动生成的 `ai-title` |
| 用户任务 | 用户输入的 prompt |
| 修改的文件 | Edit/Write/Read 等工具调用中的文件路径 |
| 工具调用统计 | 所有工具调用的名称和次数 |

**不需要 LLM，纯规则提取，零成本。**

## 效果

运行 `handoff sync` 后，打开 Cursor，它的 Agent 会自动读取 `.cursor/rules/handoff-context.mdc`，知道：

- 你最近在 Claude Code 里做了什么任务
- 修改了哪些文件
- 用了哪些工具
- 项目当前的状态

**不用重新解释，直接开始工作。**

## 要求

- Python 3.9+
- 无外部依赖（只用标准库）

## 路线图

- [x] Claude Code → Cursor 同步
- [ ] Claude Code → Codex 同步
- [ ] Codex → Cursor 同步
- [ ] 自动监听 session 结束并同步
- [ ] 支持 Gemini CLI / Windsurf

## 为什么叫 Handoff？

接力赛。一个 Agent 跑完，把棒递出去，下一个 Agent 接住继续跑，中间不停。

## License

MIT
