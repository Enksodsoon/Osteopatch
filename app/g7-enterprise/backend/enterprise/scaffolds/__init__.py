"""Gated scaffolds for E2–E6.

Each later phase is a DESIGN-COMPLETE stub: the public contract (functions,
inputs, outputs, the gate it needs) is encoded, but the body raises
GateNotApproved. This makes the later build a fill-in-the-body job and makes it
impossible to accidentally run an un-approved phase (no AWS mutation, no spend,
no training).
"""


class GateNotApproved(RuntimeError):
    """Raised when a gated phase is invoked before its gate is approved."""

    def __init__(self, phase: str, gate: str, note: str = ""):
        self.phase = phase
        self.gate = gate
        super().__init__(
            f"{phase} is gated behind {gate} and is NOT approved to run. {note}".strip()
        )
