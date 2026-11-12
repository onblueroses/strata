# Linear webhook receiver

The receiver takes Linear's change notifications for tickets, comments and labels, checks that they come from
Linear, and writes each one to a durable event log. The dispatcher and the [Linear Steward](../../stewards/README.md)
read that log. It guarantees that every accepted event is kept; it decides nothing about work. Its code and
configuration are private. See [the work system](../README.md).
