# Classify destruction by recoverability and scope

Decided: 2026-10-13

Rule: Allow undoable cleanup and deletion of a specifically named item without a second tap.
      Always require a tap for production data, backups, whole servers or accounts,
      shared-history force pushes, or anything without a backup path or outside the request.

Reason: A uniform deletion rule did not distinguish named, recoverable cleanup from losses
        that cannot be safely reversed. The latter can outlive a mistaken interpretation of a
        request.

Reopen when: A proposed tier change demonstrates a reliable recovery path and equivalent owner
             scope for the affected class.

Effect: A direct file-removal convention can remain stricter than the tap classification.
