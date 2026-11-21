"""Detection power of the validator: every known violation in tests/mutations.py must produce a message.

Mutations the validator does not catch yet are marked expectedFailure with the v0.7.0 phase that fixes them; when a
phase lands, delete its entries from ``mutations.PENDING`` (an unexpected success fails the run as a reminder).
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations  # noqa: E402


class TestMutationDetection(unittest.TestCase):
    def test_golden_example_is_clean(self) -> None:
        self.assertEqual(mutations.baseline(), [])


def _make(name: str):
    def test(self: unittest.TestCase) -> None:
        msgs = mutations.run_mutation(name)
        self.assertTrue(
            mutations.caught(name, msgs), msg=f"{name} ({mutations.MUTATIONS[name][0]}) was not detected: {msgs}"
        )

    test.__name__ = f"test_{name.lower()}_{mutations.MUTATIONS[name][1].__name__[4:]}"
    test.__doc__ = f"{name}: {mutations.MUTATIONS[name][0]}"
    return unittest.expectedFailure(test) if name in mutations.PENDING else test


for _name in mutations.MUTATIONS:
    _t = _make(_name)
    setattr(TestMutationDetection, _t.__name__, _t)


if __name__ == "__main__":
    unittest.main()
