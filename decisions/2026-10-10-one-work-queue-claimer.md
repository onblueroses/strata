# Use one claimer for queued work

Decided: 2026-10-10

Rule: One dispatcher claims eligible work issues. Steering can set labels and priority, while
      workers execute only after the dispatcher claims.

Reason: Two keepers raced for the same issue. Parallel claim paths risked duplicate work
        and uncertain ownership.

Reopen when: A different claim protocol proves single ownership under concurrent deliveries
             and recovery, with no duplicate execution.

Effect: All eligible issues have one claim path.
