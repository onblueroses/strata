# Alarms and phone channels

When a service fails, an alarm reaches the operator's phone, and the [Infrastructure Steward](../../stewards/README.md)
works on the same alarm beside it. Each failure has one owner that sends its alarm and its recovery, so the phone
sees one coherent lifecycle.

Phone pushes use three channels, chosen by what the operator must do: **approve** for a waiting tap, **alarm** for
a broken system, **fyi** for a completion that needs no action. Pushes carry no ticket text. The units and helpers
are private. See [the work system](../README.md).
