## Laptop specifics

- You run as the operator's user on the laptop, inside one headless run; the machine can sleep, which ends
  the run (the dispatcher then hands the ticket back once; while the laptop is asleep nothing is dispatched
  to it and approvals wait). Leave working trees in a state a later run can pick up, and put what it needs
  on the ticket.
- This user holds a root SSH route to the VPS (`ssh vps`, uid 0 there). Use it for
  what the ticket asks: the operator's request covers writes on the VPS over it too, except the four gates above.
- The laptop holds local repositories, a lore store, the company vault and OptMem. Read each repository or vault `AGENTS.md` before changing it.
- Browser: only the official @Chrome integration, never Playwright, CDP or another browser. Codex reaches
  Chrome through the bundled chrome plugin (`mcp__node_repl__js` browser client); Claude Code through its
  `mcp__claude-in-chrome__*` tools. The browser is the operator's live session: read and navigate freely, but anything
  that pays, or sends or posts as the operator to other people, is one of the four gates (see above).
