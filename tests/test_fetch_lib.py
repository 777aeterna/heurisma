"""v0.7.0 Phase 5: scripts/fetch_lib.py (retries with backoff, checksum, download_log, canonical attempts log)."""

import csv
import hashlib
import io
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills" / "heurisma" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import fetch_lib  # noqa: E402


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener_from(script):
    """script: list of bytes (success) or Exception (raised), consumed one per call."""
    calls = []

    def opener(req, timeout=None):
        calls.append((req.full_url, dict(req.header_items()), timeout))
        item = script[min(len(calls) - 1, len(script) - 1)]
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)

    opener.calls = calls
    return opener


def http_error(code):
    return urllib.error.HTTPError("https://x.org/f", code, f"HTTP {code}", {}, None)


def rows(path):
    with Path(path).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


class TestFetch(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.appendix = Path(self.tmp.name) / "appendix"
        self.sleeps = []
        self.sleep = self.sleeps.append

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def fetch(self, opener, **kw):
        return fetch_lib.fetch("Series X", "Agency API", "https://x.org/f.csv", "f.csv", self.appendix,
                               opener=opener, sleep=self.sleep, **kw)

    def test_success_writes_file_and_download_log_with_sha256(self) -> None:
        payload = b"a;b\n1;2\n"
        path = self.fetch(opener_from([payload]))
        self.assertEqual(path.resolve(), (self.appendix / "data" / "f.csv").resolve())
        self.assertEqual(path.read_bytes(), payload)
        log = rows(self.appendix / "download_log.csv")[0]
        self.assertEqual(log["file"], "f.csv")
        self.assertEqual(log["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(int(log["bytes"]), len(payload))
        self.assertRegex(log["retrieved_utc"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertFalse((self.appendix / "data_attempts.csv").exists())

    def test_server_errors_are_retried_with_exponential_backoff(self) -> None:
        op = opener_from([http_error(503), http_error(429), b"ok"])
        path = self.fetch(op, retries=3, backoff=1.0)
        self.assertIsNotNone(path)
        self.assertEqual(len(op.calls), 3)
        self.assertEqual(self.sleeps, [1.0, 2.0])

    def test_client_errors_are_not_retried_and_are_logged(self) -> None:
        op = opener_from([http_error(404)])
        self.assertIsNone(self.fetch(op, retries=3))
        self.assertEqual(len(op.calls), 1)
        attempt = rows(self.appendix / "data_attempts.csv")[0]
        self.assertEqual(attempt["outcome"], "HTTP 404")
        self.assertEqual(attempt["target_series"], "Series X")
        self.assertRegex(attempt["attempted_utc"], r"Z$")
        self.assertFalse((self.appendix / "download_log.csv").exists())

    def test_gives_up_after_the_retries_and_logs_the_last_error(self) -> None:
        op = opener_from([http_error(503)])
        self.assertIsNone(self.fetch(op, retries=2, backoff=0.5))
        self.assertEqual(len(op.calls), 3)  # first try + 2 retries
        self.assertEqual(rows(self.appendix / "data_attempts.csv")[0]["outcome"], "HTTP 503")

    def test_network_errors_are_retried(self) -> None:
        op = opener_from([urllib.error.URLError("temporary failure"), b"ok"])
        self.assertIsNotNone(self.fetch(op, retries=1))
        self.assertEqual(len(op.calls), 2)

    def test_user_agent_timeout_and_env_override(self) -> None:
        op = opener_from([b"x"])
        self.fetch(op, user_agent="MyAgent/1.0", timeout=7)
        _, headers, timeout = op.calls[0]
        self.assertEqual(headers.get("User-agent"), "MyAgent/1.0")
        self.assertEqual(timeout, 7)
        with mock.patch.dict(os.environ, {"HEURISMA_UA": "FromEnv/2"}):
            op2 = opener_from([b"x"])
            fetch_lib.fetch("S", "src", "https://x.org/g", "g", self.appendix, opener=op2, sleep=self.sleep)
            self.assertEqual(op2.calls[0][1].get("User-agent"), "FromEnv/2")

    def test_offline_mode_skips_the_network_and_logs(self) -> None:
        op = opener_from([b"never"])
        with mock.patch.dict(os.environ, {"HEURISMA_OFFLINE": "1"}):
            self.assertIsNone(self.fetch(op))
        self.assertEqual(op.calls, [])
        self.assertEqual(rows(self.appendix / "data_attempts.csv")[0]["outcome"], "offline mode")

    def test_expected_sha256_mismatch_is_rejected_and_not_saved(self) -> None:
        op = opener_from([b"payload"])
        self.assertIsNone(self.fetch(op, expected_sha256="0" * 64))
        self.assertFalse((self.appendix / "data" / "f.csv").exists())
        self.assertIn("checksum", rows(self.appendix / "data_attempts.csv")[0]["failure_reason"])

    def test_expected_sha256_match_is_accepted(self) -> None:
        payload = b"payload"
        self.assertIsNotNone(self.fetch(opener_from([payload]), expected_sha256=hashlib.sha256(payload).hexdigest()[:16]))

    def test_filename_cannot_escape_the_data_folder(self) -> None:
        with self.assertRaises(ValueError):
            fetch_lib.fetch("S", "src", "https://x.org/g", "../evil.csv", self.appendix, opener=opener_from([b"x"]), sleep=self.sleep)

    def test_only_http_and_https_urls_are_fetched(self) -> None:
        for url in ("file:///etc/passwd", "ftp://x.org/f", "javascript:alert(1)"):
            op = opener_from([b"x"])
            self.assertIsNone(fetch_lib.fetch("S", "src", url, "g", self.appendix, opener=op, sleep=self.sleep))
            self.assertEqual(op.calls, [])
        self.assertIn("unsupported URL scheme", rows(self.appendix / "data_attempts.csv")[0]["failure_reason"])

    def test_size_limit(self) -> None:
        big = b"x" * 2048
        self.assertIsNone(self.fetch(opener_from([big]), max_bytes=1024))
        self.assertIn("larger than", rows(self.appendix / "data_attempts.csv")[0]["failure_reason"])

    def test_fetch_lib_shares_the_package_version(self) -> None:
        import validate_report

        self.assertEqual(fetch_lib.__version__, validate_report.__version__)


if __name__ == "__main__":
    unittest.main()
