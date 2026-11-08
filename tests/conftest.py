import pytest


def _program(rng, lines=None):
    """A random equation file with reassignments, constants and 0 to 5 inputs."""
    pool = [rng.choice("ABCDE") for _ in range(rng.randint(0, 5))]
    out = []
    for k in range(lines or rng.randint(1, 20)):
        dst = rng.choice(pool) if pool and rng.random() < 0.25 else rng.choice(["X", "Y", "Z", f"T{k}"])

        def operand():
            if pool and rng.random() < 0.85:
                return rng.choice(pool)
            return str(rng.choice([0, 1, 2, 255, 65535, rng.randint(0, 65535)]))
        out.append(f"{dst} = {operand()} {rng.choice('+-*')} {operand()}")
        pool.append(dst)
    return "\n".join(out) + "\n"


@pytest.fixture
def random_program():
    return _program
