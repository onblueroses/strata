# Approval gate

The approval gate is the operator's phone page for the four tap-only actions: spending money, messages sent as the
operator, disclosing secrets, and destruction that cannot be undone. A worker asks for one exact action on its
ticket; the operator's tap records an approval for that action, and the dispatcher passes it to the worker. It
talks to Linear, to the dispatcher and to the operator's phone. It guarantees that an approval belongs to one
exact ask and that text on a ticket is never an approval. Its code and configuration are private. See
[the work system](../README.md).
