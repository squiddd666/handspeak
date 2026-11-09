"""Inventory, provenance, real HTTP playback, and local-use restriction checks."""
from __future__ import annotations

from collections import Counter
from email.message import Message
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

import server as app
import beginner_asl
import capstone_asl_v3
from experience import ExperienceStore
from scripts.build_local_research_videos import recognition_labels

ROOT = Path(app.ROOT)
MANIFEST = json.loads((ROOT / "models/recognition-videos.json").read_text(encoding="utf-8"))


class QuietHandler(app.HandSpeakHandler):
    def log_message(self, *args):
        pass


class ResearchVideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Static-only tests do not initialize or change any application database.
        cls.server = app.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        cls.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def request(self, path, method="GET", headers=None):
        request = urllib.request.Request(self.base + path, method=method, headers=headers or {})
        try:
            response = self.opener.open(request, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.headers, response.read()

    def test_exact_198_label_union_and_all_catalog_entries(self):
        modes, glosses = recognition_labels()
        self.assertEqual(set(modes), {item["label"] for item in MANIFEST["items"]})
        self.assertEqual(Counter(mode for values in modes.values() for mode in values),
                         Counter({"capstone-full": 100, "beginner": 79, "default": 6, "extra": 7,
                                  "daily": 5, "category": 5, "capstone-core": 7, "capstone-extended": 19}))
        self.assertEqual(MANIFEST["counts"], {"labels": 198, "existingLocal": 51, "researchLocal": 147})
        catalog = json.loads((ROOT / "models/motion-vocabulary.json").read_text(encoding="utf-8"))
        by_label = {item["label"]: item for item in catalog["items"]}
        self.assertEqual(len(catalog["items"]), 347)
        self.assertEqual(len({item["id"] for item in catalog["items"]}), 347)
        for item in MANIFEST["items"]:
            self.assertEqual(by_label[item["label"]]["id"], item["id"])
            self.assertEqual(by_label[item["label"]]["video"], item["video"])

    def test_catalog_reader_uses_utf8_with_a_legacy_windows_default(self):
        note = "Practice the \u201cREADY\u201d sign slowly."
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "models").mkdir()
            (root / "models/motion-vocabulary.json").write_text(
                json.dumps({"items": [{"id": "ready", "label": "READY", "note": note}]},
                           ensure_ascii=False), encoding="utf-8")
            original_read_text = Path.read_text

            def legacy_default_read_text(path, encoding=None, errors=None):
                return original_read_text(path, encoding=encoding or "cp1252", errors=errors)

            with patch.object(Path, "read_text", legacy_default_read_text):
                store = ExperienceStore(None, root, ValueError, lambda: "")
                self.assertEqual(store.catalog()[0]["note"], note)

    def test_all_198_references_get_and_head_succeed_with_correct_content(self):
        for item in MANIFEST["items"]:
            with self.subTest(label=item["label"]):
                expected = (ROOT / item["video"]).read_bytes()
                code, headers, body = self.request("/" + item["video"])
                self.assertEqual(code, 200)
                self.assertEqual(headers.get_content_type(), "video/mp4")
                self.assertEqual(body, expected)
                code, headers, body = self.request("/" + item["video"], "HEAD")
                self.assertEqual(code, 200)
                self.assertEqual(int(headers["Content-Length"]), len(expected))
                self.assertEqual(body, b"")
                if item["localResearchOnly"]:
                    self.assertEqual(headers["X-Local-Research-Only"], "true")
                    self.assertEqual(headers["Cache-Control"], "private, no-store")

    def test_all_147_research_clips_support_bounded_video_range_requests(self):
        for item in MANIFEST["items"]:
            if not item["localResearchOnly"]:
                continue
            with self.subTest(label=item["label"]):
                code, headers, body = self.request("/" + item["video"], headers={"Range": "bytes=0-1023"})
                self.assertEqual(code, 206)
                self.assertEqual(len(body), 1024)
                self.assertEqual(body, (ROOT / item["video"]).read_bytes()[:1024])
                self.assertEqual(headers["Accept-Ranges"], "bytes")

    def test_suffix_ranges_and_invalid_ranges(self):
        path = "/media/research-signs/name.mp4"
        expected = (ROOT / path.lstrip("/")).read_bytes()
        code, headers, body = self.request(path, headers={"Range": "bytes=-32"})
        self.assertEqual(code, 206)
        self.assertEqual(body, expected[-32:])
        for value in ["bytes=-0", "bytes=999999999999-", "bytes=20-10", "bytes=0-1,4-5", "garbage", "bytes=" + "9" * 400 + "-"]:
            self.assertEqual(self.request(path, headers={"Range": value})[0], 416)

    def test_public_hosts_origins_and_proxy_headers_are_rejected_for_get_and_head(self):
        path = "/media/research-signs/name.mp4"
        for headers in [{"Host": "public.example.com"}, {"Host": "localhost.evil.example"},
                        {"Host": "localhost:bad"}, {"X-Forwarded-For": "127.0.0.1"},
                        {"X-Forwarded-Host": "public.example.com"}, {"Forwarded": "for=127.0.0.1"},
                        {"Via": "1.1 public-proxy"}, {"X-Real-IP": "127.0.0.1"},
                        {"Origin": "https://public.example.com"}, {"Referer": "https://public.example.com/"}]:
            for method in ["GET", "HEAD"]:
                with self.subTest(headers=headers, method=method):
                    self.assertEqual(self.request(path, method, headers)[0], 403)
        self.assertEqual(self.request(path, headers={"Host": "localhost:8000", "Origin": "http://localhost:8000"})[0], 200)
        # The restriction does not break existing unrestricted reference routes.
        self.assertEqual(self.request("/media/signs/hello.mp4", headers={"Host": "public.example.com"})[0], 200)

    def test_loopback_host_check_rejects_remote_clients_and_duplicate_hosts(self):
        headers = Message()
        headers["Host"] = "localhost:8000"
        self.assertTrue(app.local_research_request("127.0.0.1", headers))
        self.assertTrue(app.local_research_request("::1", headers))
        self.assertTrue(app.local_research_request("::ffff:127.0.0.1", headers))
        self.assertFalse(app.local_research_request("192.168.1.5", headers))
        headers["Host"] = "public.example.com"
        self.assertFalse(app.local_research_request("127.0.0.1", headers))

    def test_provenance_output_hashes_and_original_40_reconstructions(self):
        for item in MANIFEST["items"]:
            if not item["localResearchOnly"]:
                continue
            self.assertTrue(item["referenceOnly"])
            self.assertGreaterEqual(item["duration"], 0.97)
            self.assertEqual(item["videoSha256"], hashlib.sha256((ROOT / item["video"]).read_bytes()).hexdigest())
            for row in item["sources"]:
                self.assertEqual(row["split"], "test")
                self.assertGreaterEqual(row["duration"], 1.0)
                self.assertTrue(row["lexCode"])
                self.assertEqual(len(row["sha256"]), 64)
        index = json.loads((ROOT / "media/avatar/reference/index.json").read_text(encoding="utf-8"))
        self.assertEqual(len(index["signs"]), 40)
        for item in index["signs"].values():
            self.assertEqual(item["reference"]["sha256"], hashlib.sha256((ROOT / item["referenceVideo"]).read_bytes()).hexdigest())

    def test_research_media_is_git_ignored(self):
        result = subprocess.run(["git", "check-ignore", "media/research-signs/name.mp4"], cwd=ROOT,
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0)

    def test_runtime_statuses_cannot_claim_ready_when_model_loading_fails(self):
        with patch.object(capstone_asl_v3, "_load", side_effect=ImportError("missing torch")):
            result = capstone_asl_v3.status()
            self.assertFalse(result["available"])
            self.assertFalse(result["runtimeReady"])
        with patch.object(beginner_asl, "_load", side_effect=ImportError("missing torch")), patch.object(beginner_asl, "labels", return_value=["TEST"]):
            result = beginner_asl.status()
            self.assertFalse(result["available"])
            self.assertFalse(result["runtimeReady"])


if __name__ == "__main__":
    unittest.main()
