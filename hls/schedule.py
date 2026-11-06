"""The five schedulers: asap, alap, casap, calap and custom."""


def schedule(dag, mode, limits=None, latency=None, cycles=None) -> list[int]:
    """Start step (1-based) of each op; raises ValueError with a user-facing message."""
    raise NotImplementedError("the schedulers are not written yet")
