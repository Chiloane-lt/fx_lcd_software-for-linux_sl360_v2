
"""Safe tests for fx-lcd runtime helpers; no USB hardware access."""

import ast
import fcntl
import os
import tempfile
import unittest
import subprocess

from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = PROJECT_ROOT / "main.py"

HELPER_NAMES = {
    "_read_managed_pid",
    "_acquire_runtime_lock",
    "_remove_pid_file_if_matches",
    "_write_pid_file",
    "_is_managed_process",
    "_remove_own_pid_file",
    "_terminate_process",
}


def load_runtime_helpers(namespace):
    """Compile only selected helper definitions from main.py."""
    source = MAIN_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(MAIN_PATH))

    selected = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in HELPER_NAMES
    ]

    found = {node.name for node in selected}
    if found != HELPER_NAMES:
        raise AssertionError(
            f"Missing runtime helpers: {sorted(HELPER_NAMES - found)}"
        )

    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace["__file__"] = str(MAIN_PATH)
    exec(compile(module, str(MAIN_PATH), "exec"), namespace)


class RuntimeHelperTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.runtime_dir = Path(self.temp_dir.name) / "runtime"
        self.runtime_dir.mkdir(parents=True)
        self.pid_file = self.runtime_dir / "fx-lcd.pid"
        self.lock_file = self.runtime_dir / "fx-lcd.lock"

        self.helpers = {
            "os": os,
            "fcntl": fcntl,
            "_RUNTIME_DIR": str(self.runtime_dir),
            "_PID_FILE": str(self.pid_file),
            "_LOCK_FILE": str(self.lock_file),
            "subprocess": subprocess,
        }
        load_runtime_helpers(self.helpers)

    def test_current_test_process_is_not_managed_playback(self):
        # The unittest process is not running main.py with the managed flag.
        self.assertFalse(
            self.helpers["_is_managed_process"](os.getpid())
        )

    def test_missing_process_is_not_managed(self):
        # A very large, unlikely-to-exist PID should not be managed.
        self.assertFalse(
            self.helpers["_is_managed_process"](2**30)
        )

    def test_remove_own_pid_file_only_when_pid_matches(self):
        own_pid = os.getpid()
        self.helpers["_write_pid_file"](own_pid)

        self.helpers["_remove_own_pid_file"]()
        self.assertFalse(self.pid_file.exists())

    def test_remove_own_pid_file_preserves_another_pid(self):
        self.helpers["_write_pid_file"](12345)

        self.helpers["_remove_own_pid_file"]()
        self.assertTrue(self.pid_file.exists())
        self.assertEqual(
            self.helpers["_read_managed_pid"](),
            12345,
        )

    def test_missing_pid_file_returns_none(self):
        self.assertIsNone(self.helpers["_read_managed_pid"]())

    def test_invalid_pid_file_returns_none(self):
        self.pid_file.write_text("not-a-pid\n", encoding="utf-8")

        self.assertIsNone(self.helpers["_read_managed_pid"]())

    def test_pid_must_be_greater_than_one(self):
        for value in ("-1", "0", "1"):
            with self.subTest(value=value):
                self.pid_file.write_text(value, encoding="utf-8")
                self.assertIsNone(self.helpers["_read_managed_pid"]())

    def test_write_and_read_pid(self):
        self.helpers["_write_pid_file"](12345)

        self.assertEqual(self.helpers["_read_managed_pid"](), 12345)
        self.assertEqual(self.pid_file.read_text(encoding="utf-8"), "12345\n")

    def test_remove_pid_only_when_it_matches(self):
        self.helpers["_write_pid_file"](12345)

        self.helpers["_remove_pid_file_if_matches"](54321)
        self.assertTrue(self.pid_file.exists())
        self.assertEqual(self.helpers["_read_managed_pid"](), 12345)

        self.helpers["_remove_pid_file_if_matches"](12345)
        self.assertFalse(self.pid_file.exists())

    def test_write_pid_replaces_previous_value(self):
        self.helpers["_write_pid_file"](12345)
        self.helpers["_write_pid_file"](23456)

        self.assertEqual(self.helpers["_read_managed_pid"](), 23456)
        self.assertEqual(
            list(self.runtime_dir.glob("*.tmp")),
            [],
            "Temporary PID files should be cleaned up.",
        )

    def test_lock_creates_runtime_directory_and_lock_file(self):
        lock = self.helpers["_acquire_runtime_lock"]
        lock_file = lock()

        try:
            self.assertTrue(self.runtime_dir.is_dir())
            self.assertTrue(self.lock_file.is_file())
        finally:
            lock_file.close()

    def test_lock_can_be_reacquired_after_close(self):
        acquire_lock = self.helpers["_acquire_runtime_lock"]

        first_lock = acquire_lock()
        first_lock.close()

        second_lock = acquire_lock()
        try:
            self.assertTrue(second_lock.closed is False)
        finally:
            second_lock.close()

    def test_terminate_process_waits_for_normal_exit(self):
        class FakeProcess:
            def __init__(self):
                self.terminated = False
                self.killed = False

            def terminate(self):
                self.terminated = True

            def wait(self, timeout):
                return 0

            def kill(self):
                self.killed = True

        process = FakeProcess()
        result = self.helpers["_terminate_process"](process, timeout=0.01)

        self.assertTrue(result)
        self.assertTrue(process.terminated)
        self.assertFalse(process.killed)

    def test_failed_start_cleanup_terminates_child_and_removes_own_pid(self):
        class FakeProcess:
            pid = 12345

            def __init__(self):
                self.terminated = False
                self.killed = False
                self.wait_calls = 0

            def terminate(self):
                self.terminated = True

            def wait(self, timeout):
                self.wait_calls += 1
                return 0

            def kill(self):
                self.killed = True

        process = FakeProcess()
        self.helpers["_write_pid_file"](process.pid)

        terminated = self.helpers["_terminate_process"](process)
        self.helpers["_remove_pid_file_if_matches"](process.pid)

        self.assertTrue(terminated)
        self.assertTrue(process.terminated)
        self.assertFalse(process.killed)
        self.assertEqual(process.wait_calls, 1)
        self.assertFalse(self.pid_file.exists())

    def test_terminate_process_kills_after_timeout(self):
        class FakeProcess:
            def __init__(self):
                self.terminated = False
                self.killed = False
                self.wait_calls = 0

            def terminate(self):
                self.terminated = True

            def wait(self, timeout):
                self.wait_calls += 1
                if self.wait_calls == 1:
                    raise subprocess.TimeoutExpired("fake-process", timeout)
                return 0

            def kill(self):
                self.killed = True

        process = FakeProcess()
        result = self.helpers["_terminate_process"](process, timeout=0.01)

        self.assertTrue(result)
        self.assertTrue(process.terminated)
        self.assertTrue(process.killed)
        self.assertEqual(process.wait_calls, 2)

    def test_terminate_process_reports_if_child_will_not_exit(self):
        class FakeProcess:
            def terminate(self):
                pass

            def wait(self, timeout):
                raise subprocess.TimeoutExpired("fake-process", timeout)

            def kill(self):
                pass

        process = FakeProcess()
        result = self.helpers["_terminate_process"](process, timeout=0.01)

        self.assertFalse(result)

if __name__ == "__main__":
    unittest.main()
