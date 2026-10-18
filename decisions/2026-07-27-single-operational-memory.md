# Keep one operational memory store

Decided: 2026-07-27

Rule: Use OptMem as the operational memory authority; retire the parallel search-backed memory
      service and its timer.

Reason: The migration had moved the records and event path to OptMem. Keeping both systems
        live would leave two places capable of disagreeing about memory.

Reopen when: A missing need under OptMem is demonstrated, and a second service shows measured
             benefit greater than its drift and recovery cost.

Effect: Lookup and hooks converge on one store.
