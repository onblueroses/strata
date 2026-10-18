# Skills

These skills define reusable methods for session work. Each runtime discovers or links the applicable directories through its own skill mechanism. Configure the portable interfaces in [config.example](config.example) for local use.

| Runtime | Skill class | Methods |
|---|---|---|
| Claude Code | Session lifecycle and deployment | [context-save](context-save/SKILL.md), [end](end/SKILL.md), [deploy](deploy/SKILL.md) |
| Claude Code | Research mapping | [big-research](big-research/SKILL.md), [topic-atlas](topic-atlas/SKILL.md), [discourse-atlas](discourse-atlas/SKILL.md) |
| Claude Code and Codex | Outreach, visuals, routing, and web builds | [outreach-atlas](outreach-atlas/SKILL.md), [cold-email](cold-email/SKILL.md), [research-viz](research-viz/SKILL.md), [triage](triage/SKILL.md), [obscured-site](obscured-site/SKILL.md) |
| Codex | Native session lifecycle | [codex/skills](../codex/skills) |
| Claude Code and Codex peer sessions | Bridge method | [agent-bridge](agent-bridge/README.md) |

DeepSeek and Kimi can adopt these methods through their own runtime instructions. A skill is a method, not authority to publish, message people, spend money, or change production.
