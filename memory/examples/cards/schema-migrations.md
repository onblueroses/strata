---
name: Reversible Schema Migrations
description: Apply compatible database changes in stages
type: project
importance: 6
---
Use an expand-and-contract sequence. Add compatible fields, deploy readers and
writers, verify the migrated data, and remove obsolete fields only after every
consumer has moved.
