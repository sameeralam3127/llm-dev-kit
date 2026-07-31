# Project skills

Shared Claude Code skills for LLM Dev Kit. Invoke with `/<name>` or let
Claude pick them up automatically from their descriptions.

| Skill | Use it to |
| --- | --- |
| `/roadmap` | See where the project is, pick and plan the next learning increment |
| `/add-provider` | Connect a new LLM host behind the `ChatProvider` seam (Phase 2) |
| `/add-feature` | Land any web/ feature through the standard six-layer pattern |
| `/smoke-test` | Prove the chat path end-to-end, including failure paths |

## Why only four?

Skills encode *repeatable workflows that exist today*. The roadmap's later
phases (memory, agents, voice, enterprise…) get their skills when their code
and workflow actually exist — a skill for unwritten code is documentation
that is born stale. `/roadmap` is the exception: its job is precisely to
plan phases that don't exist yet, and to spawn a new skill when a phase
develops a repeatable workflow.

## Local-only skills

Personal experiments and machine-specific skills go in `local/` — it is
gitignored, so nothing you put there is ever committed or pushed:

```
.claude/skills/local/my-experiment/SKILL.md
```

Same format as the shared ones. If a local skill proves broadly useful,
promote it by moving it up a level and committing it.
