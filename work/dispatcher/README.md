# Dispatcher

The dispatcher is the only program that claims tickets. It starts the work the [Linear Steward](../../stewards/README.md)
orders, honours the `laptop` and `vps` pins, and starts one fresh worker for each ticket (Codex on either machine,
Claude Code with the operator's browser on the laptop, DeepSeek on the server). It talks to Linear, to the Linear
Steward and to the workers. It guarantees that a ticket has one claimer at a time and that a ticket counts as done
only when its worker's signed outcome is on it. Its code and configuration are private. See [the work system](../README.md).
