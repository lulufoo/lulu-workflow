import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from workflow_common import session_base_dir, write_md_state

HOOK = Path(__file__).parent / "hook_guard.py"


class TestProductHookPathGuard(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.conv = "hook-test-conv"

    def tearDown(self):
        self._tmp.cleanup()

    def _run_hook(self, rel_path: str, conv_id: str) -> dict:
        event = {
            "tool_name": "Write",
            "conversation_id": conv_id,
            "tool_input": {"path": str(self.root / rel_path), "content": "x"},
        }
        proc = subprocess.run(
            ["python3", str(HOOK)],
            input=json.dumps(event),
            text=True,
            capture_output=True,
            cwd=str(self.root),
        )
        return json.loads(proc.stdout)

    def test_blocks_src_write_when_active(self):
        state = self.root / session_base_dir(self.conv) / "revision1" / "workflow-state.md"
        write_md_state(state, "Drafting")
        result = self._run_hook("src/foo.ts", self.conv)
        self.assertEqual(result["permission"], "deny")

    def test_allows_cache_write_when_active(self):
        state = self.root / session_base_dir(self.conv) / "revision1" / "workflow-state.md"
        write_md_state(state, "Drafting")
        cache_path = (
            f".cache/lulu-dev-workflow/product/{self.conv}/revision1/product-doc.md"
        )
        result = self._run_hook(cache_path, self.conv)
        self.assertEqual(result["permission"], "allow")

    def test_allows_src_when_delivered(self):
        state = self.root / session_base_dir(self.conv) / "revision1" / "workflow-state.md"
        write_md_state(state, "Delivered")
        result = self._run_hook("src/foo.ts", self.conv)
        self.assertEqual(result["permission"], "allow")


if __name__ == "__main__":
    unittest.main()
