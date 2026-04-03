# Debug

Systematic approach to finding and fixing bugs. Follow the steps in order -
skipping steps is the #1 cause of wasted debugging time.

## Steps

1. **Reproduce** - Get a reliable reproduction before touching code. Write down
   the exact steps, inputs, and expected vs actual output.
2. **Hypothesize** - Form a specific, testable hypothesis about the cause.
   "Something is wrong with auth" is not a hypothesis. "The JWT expiry check
   uses seconds but the token stores milliseconds" is.
3. **Isolate** - Narrow the problem to the smallest possible scope. Binary search
   through the call stack. Comment out code. Use minimal inputs.
4. **Fix** - Change one thing at a time. If the fix is more than a few lines,
   you probably haven't isolated enough.
5. **Verify** - Confirm the original reproduction now passes. Check for
   regressions. Write a test that would have caught this.

## Anti-Examples

| Bad | Why | Better |
|-----|-----|--------|
| Print statements everywhere | Generates noise, doesn't narrow scope | Binary search: one print at the midpoint |
| Fixing the symptom | Creates recurring bugs | Trace to root cause |
| "Works on my machine" | Environment diff is a clue | Document exact env diff, test in failing env |
| Changing multiple things | Can't tell which change fixed it | One change, one test, then next |
| Debugging in production | Risk of data corruption | Reproduce locally first |

## Concrete Tests

- Can you reproduce the bug with a single command or test case?
- Can you explain the root cause in one sentence without using "somehow"?
- Does your fix have a corresponding test that fails without it?
- Did you check for the same bug pattern elsewhere in the codebase?

## Quality Self-Check

Before reporting the bug fixed:
1. Original reproduction case passes?
2. New test written that catches this specific bug?
3. Root cause identified and explained (not just symptom patched)?
4. Checked for same pattern in related code?
5. No debug artifacts left (print statements, temporary comments)?
