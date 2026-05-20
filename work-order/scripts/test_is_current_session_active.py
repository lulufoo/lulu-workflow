import tempfile
import unittest
from pathlib import Path

from workflow_common import (
    is_current_session_active,
    session_base_dir,
    write_md_state,
)


class TestWorkOrderIsCurrentSessionActive(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.conv = "wo-conv"

    def tearDown(self):
        self._tmp.cleanup()

    def _state_path(self, round_dir: str, state: str) -> Path:
        path = self.root / session_base_dir(self.conv) / round_dir / "workflow-state.md"
        write_md_state(path, state)
        return path

    def test_r_glob_drafting(self):
        self._state_path("r1", "Drafting")
        self.assertTrue(is_current_session_active(self.root, self.conv))

    def test_revision_glob_not_matched(self):
        path = self.root / session_base_dir(self.conv) / "revision1" / "workflow-state.md"
        write_md_state(path, "Drafting")
        self.assertFalse(is_current_session_active(self.root, self.conv))

    def test_all_delivered_false(self):
        self._state_path("r1", "Delivered")
        self.assertFalse(is_current_session_active(self.root, self.conv))


if __name__ == "__main__":
    unittest.main()
