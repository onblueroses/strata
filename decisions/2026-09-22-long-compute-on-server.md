# Move long compute to the server

Decided: 2026-09-22

Rule: Run CPU-heavy work or jobs expected to exceed five minutes on the server by default;
      keep only quick jobs on the laptop.

Reason: Long local runs compete with interactive work and depend on laptop uptime. The remote
        machine provides the intended durable compute path.

Reopen when: A measured workload completes more reliably or efficiently on the laptop without
             harming interactive use.

Effect: Long remote work keeps its completion chain off the laptop.
