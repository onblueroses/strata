# Learn - Mid-Session Pattern Capture

Capture a pattern, gotcha, or insight right now before it's forgotten.

## Steps

1. Ask the user what they learned using AskUserQuestion:
   - Question: "What did you just learn or notice?"
   - Options:
     - "Gotcha / workaround" - Something that broke and how to fix it
     - "Tool/tech pattern" - A technique or command that works well
     - "Architecture decision" - A choice with reasoning worth preserving

2. Based on their response, ask a follow-up: "Which section of MEMORY.md?" with options:
   - "Gotchas" - Traps, bugs, workarounds
   - "Tech" - Tools, configs, commands
   - "Key Decisions" - Choices with reasoning
   - "Projects" - Project-specific knowledge

3. Read the MEMORY.md file (located at `.claude/memory/MEMORY.md` or the path shown in your project's memory config)

4. Check for duplicates - search for key terms from the user's input. If a similar entry exists, update it instead of adding a new one.

5. Format the entry as a concise bullet point matching the existing style in that section:
   - Terse, specific, include file paths and command syntax
   - Bold the key term: `- **Thing**: explanation`
   - Max 2-3 lines per entry
   - No session-specific context (task details, temp state)

6. Use Edit to append the entry to the correct section of MEMORY.md.

7. Confirm exactly what was added and where.

## Rules
- Match existing MEMORY.md style exactly (look at nearby entries)
- Never duplicate - update existing entries if the topic already exists
- Don't add things that belong in entity summaries (project state) or daily notes (session events)
- This is for cross-session knowledge only
