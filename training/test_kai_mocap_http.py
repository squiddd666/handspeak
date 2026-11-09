"""Exercise Kai's public assets through the real handler, without touching a DB."""
import hashlib
import json
from pathlib import Path
import threading
import unittest
import urllib.error
import urllib.request

import server as app


class QuietHandler(app.HandSpeakHandler):
    def log_message(self, *args):
        pass


class KaiMocapHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Static requests never initialize the database or create account state.
        cls.server = app.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def get(self, path, method="GET"):
        request = urllib.request.Request(self.base + path, method=method)
        try:
            response = urllib.request.urlopen(request, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.headers, response.read()

    def test_model_and_mocap_are_served_with_binary_gltf_mime(self):
        root = Path(app.ROOT)
        index_path = "media/avatar/clips/index.json"
        status, headers, raw = self.get("/" + index_path)
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "application/json")
        index = json.loads(raw)
        assets = {"media/avatar/signer.glb": None}
        assets.update({"media/avatar/clips/" + entry["file"]: entry for entry in index["signs"].values()})
        status, headers, raw = self.get("/media/avatar/reference/index.json")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "application/json")
        references = json.loads(raw)
        self.assertEqual(len(references["signs"]), 40)
        assets.update({"media/avatar/reference/" + entry["file"]: entry for entry in references["signs"].values()})
        for path, entry in assets.items():
            with self.subTest(path=path):
                status, headers, body = self.get("/" + path + "?v=20261105-studio-galt-4")
                self.assertEqual(status, 200)
                self.assertEqual(headers.get_content_type(), "model/gltf-binary")
                self.assertEqual(body, (root / path).read_bytes())
                if entry:
                    self.assertEqual(hashlib.sha256(body).hexdigest(), entry["sha256"])
                status, headers, body = self.get("/" + path, "HEAD")
                self.assertEqual(status, 200)
                self.assertEqual(headers.get_content_type(), "model/gltf-binary")
                self.assertEqual(body, b"")

    def test_glb_allowlist_does_not_expose_private_files_or_source_inputs(self):
        for path in ["/server.py", "/handspeak.db", "/.git/config", "/training/",
                     "/reports/", "/scripts/retarget_studio_galt.py",
                     "/scripts/author_kai_practice.py",
                     "/scripts/extract_reference_motion.py", "/scripts/retarget_reference_motion.py",
                     "/scripts/kai-reference-corrections.json",
                     "/asl-cache/kai-reference/hello.json",
                     "/media/avatar/clips/hello.fbx"]:
            for method in ["GET", "HEAD"]:
                with self.subTest(path=path, method=method):
                    self.assertEqual(self.get(path, method)[0], 404)


if __name__ == "__main__":
    unittest.main()
