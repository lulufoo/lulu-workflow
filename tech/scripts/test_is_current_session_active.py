import tempfile
import unittest
from pathlib import Path

from workflow_common import (
    is_current_session_active,
    session_base_dir,
    write_md_state,
)


class TestTechIsCurrentSessionActive(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.conv = "tech-conv"

    def tearDown(self):
        self._tmp.cleanup()

    def _state_path(self, revision: str, state: str) -> Path:
        path = self.root / session_base_dir(self.conv) / revision / "workflow-state.md"
        write_md_state(path, state)
        return path

    def test_drafting_returns_true(self):
        self._state_path("revision1", "Drafting")
        self.assertTrue(is_current_session_active(self.root, self.conv))

    def test_delivered_returns_false(self):
        self._state_path("revision1", "Delivered")
        self.assertFalse(is_current_session_active(self.root, self.conv))

    def test_missing_dir_returns_false(self):
        self.assertFalse(is_current_session_active(self.root, "missing"))

    def test_empty_conv_returns_false(self):
        self.assertFalse(is_current_session_active(self.root, ""))

    def test_mixed_revisions_one_active(self):
        self._state_path("revision1", "Delivered")
        self._state_path("revision2", "Evaluating")
        self.assertTrue(is_current_session_active(self.root, self.conv))


if __name__ == "__main__":
    unittest.main()
