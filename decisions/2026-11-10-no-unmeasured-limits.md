# Install no limit without a source

Decided: 2026-11-10

Rule: A cap, budget, threshold, timeout, pace or stop condition goes into a config, a prompt or an
      instruction for another agent only with its source beside it: the system's own limit looked up, a
      measurement, or a ruling. With no source, leave it out. An agent that believes a limit is needed
      proposes it and does not install it silently. An inherited limit is evidence to check: find its
      source or remove it.

Reason: Limits were being added as a precaution without a source; they caused failures later, often for
        another agent, while they seemed protective.

Reopen when: A recorded incident shows harm that a default limit without a source would have prevented
             and that a measured limit could not.

Effect: Configs and briefs carry fewer limits, each with its source; reviews remove limits whose source
        cannot be found.
