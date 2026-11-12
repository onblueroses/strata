# Operator wrapper

A narrow helper that lets a worker restart a listed service and read its status for a ticket, and nothing more.
It talks to the service manager and writes one log line per call. It guarantees that a worker can do only the
listed actions on the listed services. Its code and configuration are private. See [the work system](../README.md).
