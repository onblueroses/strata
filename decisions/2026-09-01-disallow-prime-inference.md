# Exclude the prohibited inference provider

Decided: 2026-09

Rule: Never launch the `prime-inference` provider or its selectors. Check the resolved
      provider before dispatch and refuse an unavailable allowed route instead of falling
      back.

Reason: The operator excluded this provider from the permitted routes; the instruction
        records no triggering incident. A fallback could silently cross that boundary when
        an allowed route is exhausted or missing.

Reopen when: The operator expressly changes the provider boundary and the dispatch path proves
             it cannot switch providers silently.

Effect: The resolver fails closed on an unapproved route.
