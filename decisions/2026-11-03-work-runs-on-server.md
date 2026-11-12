# Run all heavy work on the server

Decided: 2026-11-03

Supersedes: [2026-09-22-long-compute-on-server.md](2026-09-22-long-compute-on-server.md)

Rule: Run full or slow test suites, test matrices, benchmarks, evals, builds, grids, training and any
      other CPU-heavy or long-running work on the server, never on the laptop. New work, repositories,
      data and services start there too. The laptop runs only quick, targeted checks: one test or file,
      a lint, a smoke run of seconds. When unsure, use the server.

Reason: The earlier ruling made the server the default and left a judgment call about job length,
        made run by run. Work on the laptop competes with interactive use and depends on the laptop's
        uptime. A rule with no length threshold removes the judgment call, and a single place for new
        work keeps repositories, data and services together.

Reopen when: A measured workload completes more reliably or efficiently on the laptop without harming
             interactive use.

Effect: Agents start heavy work over SSH on the server, and services are deployed there.
