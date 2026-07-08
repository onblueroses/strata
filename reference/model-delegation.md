<!-- keywords: delegate, delegation, dispatch, sub-model, sub-agent, lane, strong, fast, grader, breadth, orchestrator, hand off, handoff, offload, second opinion, parallel review, review panel, tool-use loop, working directory, fallback, quota, rate limit, cache no-op, exit code, wrapper, model-map, routing, background job, long-running -->
# Model Delegation

How to delegate sub-tasks to other models from this Claude Code session.

The lanes are bash wrappers at `$STRATA_HOME/bin/` (`strong`, `fast`, `grader`, `breadth`). Each wrapper resolves its lane name from the executable shim, reads the concrete model id from `[lanes]` in `config/model-map.toml`, dispatches through `bin/lib/agent.py`, returns text on stdout, and reports failures by exit code.

Each lane runs the same multi-provider agent in the current working directory. The agent has tools to read and write files, run shell commands, list directories, and search with ripgrep. The wrappers expose only the flags listed below; change directories before invoking when a task should run from another tree.

## Quick Nav

| Task | Section |
|------|---------|
| Pick which lane for a task | Tier Sketch |
| See command flag reference | Wrapper Reference |
| Chain lanes on quota | Fallback Chain |
| Read failure exit codes | Exit Code Contract |
| Write a self-contained prompt | Prompt Template |
| Long-running jobs (>10 min) | Long-Running Jobs |

## Tier Sketch

Pick the lane by what the task actually needs. The model bound to each lane lives in `config/model-map.toml`.

```
fast      DEFAULT FOR CODE. Fast, cheap, and useful for parallel scouting.
strong    DEEPER. Load-bearing logic, security review, hardest debugging,
          architecture decisions.
grader    CHEAP + FAST. Summaries, simple fixes, review panels, and filtering.
breadth   FALLBACK + VERBOSE. Use when primary lanes are exhausted or when a
          different model voice is useful.
```

## Wrapper Reference

All four lane wrappers share the same interface. Each takes a self-contained prompt by argument, `--file`, or stdin.

```bash
grader "prompt"
grader --file prompt.md
echo "prompt" | grader
```

Implemented flags:

```
--file PATH       Read prompt from file
--system TEXT     Override the default system prompt
--timeout SECS    Max wall time (default 1800 = 30 min)
```

Accepted compatibility flags:

```
--effort VALUE
--reasoning VALUE
--cache VALUE
--max-tokens VALUE
--raw
```

The compatibility flags are parsed for older skill bodies but do not change behavior. The value-taking compatibility flags still require an operand and fail with a controlled usage error when the operand is missing. `--raw` is accepted without an operand.

Prompt parsing details:

- First positional argument captures the rest of the command line as one prompt string.
- `--` stops flag parsing and captures the remaining words as the prompt.
- With no argument prompt and no `--file`, the agent reads stdin when stdin is piped.

## Exit Code Contract

```
0   Success; read stdout for content
1   Usage, setup, model-map, placeholder, or wrapper-side input error
2   API / model error
3   Quota / rate limit; shell timeout 124 is remapped to 3
4   Auth error
5   Empty content from the model after one re-prompt attempt
```

React to exit code, not message text. The contract is stable across all four lanes.

## Fallback Chain

Sequential, not parallel. On exit 3, drop one lane:

```bash
strong       exit 3   ->   try fast
fast         exit 3   ->   try breadth
breadth      exit 3   ->   try grader
grader       exit 3   ->   surface to user; all lanes are exhausted
```

Do not fan the same logical request out to all four lanes in parallel; that wastes tokens and creates ambiguous results.

## Prompt Template

Sub-models start fresh: no conversation memory and no shared context beyond files they read themselves. Every prompt should be self-contained and open with an outcome block.

```
Goal: <one sentence describing the result>

Success means:
  - <checkable output element>
  - <checkable output element>
  - <format or length constraint>

Stop when: <explicit stopping condition>

CONTEXT:
<embedded code, file paths, command output, or prior findings>

TASK:
<directional instructions that name the work to perform>

OUTPUT FORMAT:
<exact response shape>
```

## Long-Running Jobs

Wrappers support 30-minute timeouts via `--timeout`. For jobs that may exceed the foreground Bash tool limit, invoke the wrapper in the background through the surrounding harness and read the captured stdout when the completion notification arrives.

Examples:

```bash
cat my_function.py | grader \
  "Find any bugs in the code below. Output: bug list, then fixed code. Terse."
```

```bash
strong --file design-prompt.md
```

```bash
strong --file prompt.md
if [ $? -eq 3 ]; then fast --file prompt.md; fi
if [ $? -eq 3 ]; then breadth --file prompt.md; fi
if [ $? -eq 3 ]; then grader --file prompt.md; fi
```
