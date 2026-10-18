# Keep raw private runtime registries out of Git

Decided: 2026-08-13

Rule: Keep registries containing private evaluation inputs in the backup tier rather than
      tracking raw copies in a repository.

Reason: A proposed recovery aid would have made private probe text durable in Git. No
        privacy-safe derived representation had been established.

Reopen when: A derived representation is shown to exclude private inputs and provides recovery
             value the backup tier does not.

Effect: Runtime recovery does not publish the private probes.
