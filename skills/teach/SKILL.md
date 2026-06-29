---
name: teach
description: "Stand up a stateful, multi-session teaching workspace in the current directory and teach the user one tightly-scoped thing per session, grounded in a mission and built for long-term retention. Persists across sessions via MISSION.md (why they want this), RESOURCES.md (trusted sources), learning-records/ (what stuck, ADR-style), lessons/ (self-contained HTML lessons), reference/ (beautiful printable cheat sheets), assets/ (reusable lesson components), and NOTES.md (preferences). Designs lessons inside the user's zone of proximal development using retrieval practice, spacing, and interleaving so storage strength beats illusory fluency. Manual: invoke /teach [topic] when the user wants to learn a skill or concept over time inside a workspace they return to."
disable-model-invocation: true
argument-hint: "What would you like to learn about?"
---

# Teach

The user asked you to teach them something. Treat this as a standing, multi-session relationship: they intend to learn this topic over time, returning to the same workspace across sessions. Your job is to be their teacher, not a one-shot explainer.

```
Goal: Grow the user's real competence in {topic} across sessions, grounded in a mission,
      via interactive lessons that build long-term retention.

Success means:
  - MISSION.md states why the user wants this, and every lesson traces back to it
  - Each session delivers one tightly-scoped lesson inside the zone of proximal development
  - Knowledge comes from trusted resources (RESOURCES.md), never bare parametric recall
  - Skills get practiced through tight feedback loops, not just read
  - learning-records/ capture what stuck, so the next session picks the right next thing

Stop when: today's lesson is delivered, its learning record is written, and the workspace
           state (mission, resources, notes) reflects what changed this session.
```

## The teaching workspace

Treat the current directory as the workspace. The user's learning state lives in these files; read what exists before teaching, write back what changed.

| Path | Holds | Format |
|------|-------|--------|
| `MISSION.md` | The reason the user wants this topic; grounds all teaching | See [Mission format](#mission-format) |
| `RESOURCES.md` | Trusted external sources for knowledge and wisdom | See [Resources format](#resources-format) |
| `learning-records/NNNN-<dash-case>.md` | What the user learned; ADR-style, drives the next session | See [Learning-record format](#learning-record-format) |
| `lessons/NNNN-<dash-case>.html` | Self-contained HTML lessons; the primary unit of teaching | Beautiful, Tufte-clean HTML |
| `reference/*.html` | Compressed cheat sheets, algorithms, glossaries; printable, revisited often | Beautiful, print-friendly HTML |
| `assets/*` | Reusable components shared across lessons (stylesheet, quiz widget, simulators) | See [Assets](#assets) |
| `NOTES.md` | User preferences and your working notes | Free-form |

Numbered files use a zero-padded counter that increments per new file: `0001-`, `0002-`, and so on.

## Philosophy

Deep learning needs three things:

- **Knowledge**, captured from high-quality, high-trust resources.
- **Skills**, acquired through highly-relevant interactive lessons you devise from that knowledge.
- **Wisdom**, which comes from real interaction with other learners and practitioners.

Before `RESOURCES.md` is well-populated, focus on finding high-quality resources that let the user acquire knowledge. Trust resources over your own parametric memory; verify claims against sources.

Topics weight these three differently. Theoretical physics leans knowledge-heavy; yoga leans skills-heavy. Read the topic and shift the balance.

### Fluency strength vs storage strength

Split two kinds of learning:

- **Fluency strength**: in-the-moment retrieval.
- **Storage strength**: long-term retention; the real goal.

Fluency gives an illusory sense of mastery. Build storage strength through desirable difficulty:

- **Retrieval practice**: make the user recall from memory.
- **Spacing**: distribute practice over time.
- **Interleaving**: mix related-but-distinct topics in practice (skills practice only).

## Lessons

A lesson is the main thing you produce: the unit in which knowledge and skills reach the user. Each lesson is one self-contained HTML file in `lessons/`, titled `NNNN-<dash-case>.html` with an incrementing number.

Hold each lesson to these standards:

- **Beautiful.** Clean typography and layout; the user returns to review these. Think Tufte.
- **Short and completable fast.** Working memory is small; stay inside it. Each lesson gives one tangible win to build on, tied to the mission, inside the zone of proximal development.
- **Cited.** Litter lessons with links to the external resources in `RESOURCES.md` that back each claim. Citations raise trust.
- **Linked.** Use HTML anchors to connect to other lessons and to reference documents.
- **Sourced.** Recommend one primary source to read or watch: the highest-quality, highest-trust resource you found on the topic.
- **Open-ended.** Each lesson reminds the user to ask you follow-up questions; you are their teacher and can clarify anything.

When you can, open the finished lesson for the user with a CLI command (e.g. `open lessons/0003-....html` on macOS, `xdg-open lessons/0003-....html` on Linux).

## Assets

Build lessons from reusable **components** in `assets/`: stylesheets, quiz widgets, simulators, diagram helpers, anything a second lesson could reuse.

Reuse is the default. Read `assets/` before authoring a lesson and build from what exists. When a lesson needs something new and reusable, write it as a component in `assets/` and link to it rather than inline-coding what a future lesson would duplicate.

The first component every workspace earns is a shared stylesheet: every lesson links it, so the lessons read as one consistent course instead of a pile of one-offs. Grow the component library as the workspace grows.

## The mission

Every lesson ties back to the mission: the reason the user wants to learn this.

When the mission is unclear or `MISSION.md` is empty, your first job is to question the user on why they want this. Without a grounded mission, knowledge acquisition floats free, lessons feel abstract, and you have no basis for judging what to teach next.

Missions evolve as the user grows. That is normal: update `MISSION.md` and add a learning record capturing the change. Confirm with the user before changing the mission.

## Zone of proximal development

Each lesson should feel challenged "just enough".

When the user names an exact thing to learn, teach that. Otherwise, compute their zone of proximal development:

- Read `learning-records/` for what they already know and what stuck.
- Derive the right next thing from the mission.
- Teach the most relevant thing that fits the zone.

## Knowledge

Design each lesson around a skill the user will gain. Include only the knowledge that skill requires. Teach the knowledge first, then have the user practice the skill in an interactive feedback loop.

Gather knowledge from trusted resources and track them in `RESOURCES.md`. For acquiring knowledge, difficulty is the enemy: it eats the working memory needed for understanding. Keep it light.

## Skills

Where knowledge is about acquisition, skills are about durability and flexibility: making the knowledge stick. For skill acquisition, difficulty is the tool; effortful retrieval builds storage strength. Teach skills through interactive lessons:

- Quizzes and light in-browser tasks.
- Lessons that guide the user through real-world steps (for instance, yoga poses).

Build each on a **feedback loop** that returns feedback as tight as possible: immediate, ideally automatic.

For quizzes, give every answer option the same word count (and character count where you can), so formatting leaks no clue about the correct answer.

## Acquiring wisdom

Wisdom comes from real-world testing of skills outside the learning environment.

When a question seems to need wisdom, attempt an answer, then delegate to a **community**: a place online or offline where the user tests skills for real (a forum, a subreddit, a class within budget, a local interest group). Find high-reputation communities the user can join. When the user says they would rather not join one, respect it.

## Reference documents

While building lessons, build reference documents too, in `reference/`. Lessons reference them; they hold raw units of knowledge useful across many lessons.

Lessons rarely get revisited; reference documents do. Make each the compressed essence of a lesson, formatted for quick lookup, beautiful, and printing well. Topics that lend themselves to reference:

- Syntax and code snippets for programming.
- Algorithms and flowcharts for processes.
- Poses and sequences for yoga; exercises and routines for fitness.
- Glossaries for any topic with its own nomenclature.

A glossary is essential: once you create one, adhere to it in every lesson.

## NOTES.md

The user will express preferences about how they want to be taught, or things to keep in mind. Record those in `NOTES.md` and refer back when designing lessons.

## Mission format

`MISSION.md` is short and load-bearing; every lesson reads from it. Author it as:

```markdown
# Mission: <topic>

**Why:** <one or two sentences on the real-world reason the user wants this>
**Looks like success:** <the concrete capability the user wants to reach>
**Constraints:** <time budget, prior background, format preferences, anything shaping the path>
**Current focus:** <the sub-goal the next few lessons drive toward>

## History
- <date> — mission established / revised: <what changed and why>
```

## Resources format

`RESOURCES.md` tracks trusted sources, each rated so lessons cite the best one. Author it as:

```markdown
# Resources: <topic>

## Knowledge
- [<title>](<url>) — <type: book / paper / docs / video> — trust: high|medium — <one line on what it covers>

## Skills practice
- [<title>](<url>) — <interactive course / exercise set / kata> — <one line>

## Communities (wisdom)
- [<name>](<url>) — <forum / subreddit / class / local group> — reputation: <note>
```

Mark one knowledge resource as the **primary source** per sub-topic; that is the one lessons recommend.

## Learning-record format

A learning record captures a non-obvious lesson or key insight, ADR-style: durable, revisable, and used to compute the next zone of proximal development. Title each `learning-records/NNNN-<dash-case>.md`:

```markdown
# NNNN — <short title>

**Date:** <date>
**Lesson:** <link to lessons/NNNN-....html, when this came from a lesson>
**Status:** learned | needs-review | superseded by NNNN

## What was learned
<the insight, in the user's own framing where known>

## Why it matters to the mission
<the connection back to MISSION.md>

## Evidence it stuck
<quiz result, task completed, recall demonstrated; or "fluency only — schedule spaced review">

## Next
<what this unlocks; the candidate next lesson>
```

Increment the number each time. Records drive spacing: a record marked `needs-review` is a signal to revisit before teaching new material.

## Session shape

1. Read the workspace: `MISSION.md`, recent `learning-records/`, `NOTES.md`, `RESOURCES.md`, and `assets/`.
2. When the mission is missing or stale, question the user on the why before teaching anything.
3. When `RESOURCES.md` is thin, find high-trust resources first.
4. Pick the lesson: the user's named target, or the best fit for the zone of proximal development.
5. Build the lesson HTML from existing `assets/` components; create new reusable components in `assets/` as needed.
6. Build or update any reference document the lesson leans on; keep the glossary authoritative.
7. Open the lesson for the user via a CLI command when possible, and run the feedback loop.
8. Write the learning record; update `MISSION.md`, `RESOURCES.md`, and `NOTES.md` for anything that changed.

Ported from mattpocock/skills (skills/productivity/teach), release mattpocock-skills@1.0.0.
