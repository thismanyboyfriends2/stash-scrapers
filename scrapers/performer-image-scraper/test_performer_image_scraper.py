#!/usr/bin/env python3
"""
Black-box tests for the Performer Image Scraper.

Runs the scraper as Stash would — a subprocess with the image fragment on
stdin, a working dir inside `<config dir>/scrapers/`, and py_common on
PYTHONPATH — against a fake Stash GraphQL server.

    python3 -m unittest test_performer_image_scraper.py
"""
import base64
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRAPER = Path(__file__).with_name("performer-image-scraper.py")

# 1x1 transparent PNG
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

STUB_LOG = '''
import sys
def _log(level, msg):
    print(f"{level}: {msg}", file=sys.stderr)
def debug(msg): _log("DEBUG", msg)
def info(msg): _log("INFO", msg)
def warning(msg): _log("WARNING", msg)
def error(msg): _log("ERROR", msg)
'''


class FakeStash:
    """A minimal Stash: findImage, performerUpdate, and image bytes."""

    def __init__(self, api_key=None, performers=None, image_exists=True, tls=None, graphql_html=False):
        self.api_key = api_key
        self.performers = [{"id": "7", "name": "Jane Doe"}] if performers is None else performers
        self.image_exists = image_exists
        self.graphql_html = graphql_html
        self.performer_updates = []
        self.api_keys_seen = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):  # noqa: A002 - keep quiet
                pass

            def _authorised(self):
                fake.api_keys_seen.append(self.headers.get("ApiKey"))
                if fake.api_key and self.headers.get("ApiKey") != fake.api_key:
                    self.send_response(401)
                    self.end_headers()
                    return False
                return True

            def _json(self, payload):
                body = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if not self._authorised():
                    return
                if self.path.startswith("/image/"):
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.end_headers()
                    self.wfile.write(PNG)
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self):
                if not self._authorised():
                    return
                if fake.graphql_html:
                    # e.g. a reverse proxy's login page
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"<html><body>Please log in</body></html>")
                    return
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                query = body["query"]
                if "findImage" in query:
                    image_id = body["variables"]["image_id"]
                    image = None
                    if fake.image_exists:
                        image = {
                            "id": image_id,
                            # Stash reports whatever host it believes it has;
                            # the scraper must not depend on it.
                            "paths": {"image": f"http://stash.example.invalid/image/{image_id}/image?t=1"},
                            "performers": fake.performers,
                        }
                    self._json({"data": {"findImage": image}})
                elif "performerUpdate" in query:
                    update = body["variables"]["input"]
                    fake.performer_updates.append(update)
                    self._json({"data": {"performerUpdate": {"id": update["id"], "name": "Jane Doe"}}})
                else:
                    self._json({"errors": [{"message": "unknown query"}]})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        if tls:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(*tls)
            self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class ScraperTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        # Stash config dir with the scraper installed under scrapers/
        self.config_dir = self.tmp / "stash-config"
        self.scraper_dir = self.config_dir / "scrapers" / "performer-image-scraper"
        self.scraper_dir.mkdir(parents=True)
        shutil.copy(SCRAPER, self.scraper_dir)
        # py_common stub, as installed from the CommunityScrapers source
        self.py_common = self.tmp / "community" / "py_common"
        self.py_common.mkdir(parents=True)
        (self.py_common / "__init__.py").write_text("")
        (self.py_common / "log.py").write_text(STUB_LOG)
        # isolated home, so ~/.stash never leaks in from the real machine
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(self.home),
            "PYTHONPATH": str(self.py_common.parent),
        }

    def start_stash(self, **kwargs):
        stash = FakeStash(**kwargs)
        self.addCleanup(stash.close)
        return stash

    def write_config(self, path, **values):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(f"{k}: {v}\n" for k, v in values.items()))
        return path

    def run_scraper(self, image_id="3091701", expect_exit=0, stdin=None):
        """Run the scraper; 0 means it worked, 69 tells Stash the scrape failed."""
        result = subprocess.run(
            [sys.executable, SCRAPER.name],
            input=json.dumps({"id": image_id}) if stdin is None else stdin,
            cwd=self.scraper_dir,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, expect_exit, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        if expect_exit == 0:
            self.assertEqual(json.loads(result.stdout), {})
        return result.stderr


class TestPerformerImageScraper(ScraperTestCase):
    def test_sets_performer_image_using_key_from_stash_config_file_env(self):
        stash = self.start_stash(api_key="secret-key")
        config = self.write_config(
            self.tmp / "elsewhere" / "config.yml", api_key="secret-key", port=stash.port
        )
        self.env["STASH_CONFIG_FILE"] = str(config)
        self.assertNotEqual(stash.port, 9999, "must prove the configured port is honoured")

        log = self.run_scraper()

        self.assertEqual(len(stash.performer_updates), 1, log)
        update = stash.performer_updates[0]
        self.assertEqual(update["id"], "7")
        self.assertEqual(update["image"], "data:image/png;base64," + base64.b64encode(PNG).decode())
        self.assertIn("Jane Doe", log)
        self.assertNotIn("secret-key", log)

    def test_finds_config_in_parent_of_scrapers_dir_without_env(self):
        stash = self.start_stash(api_key="secret-key")
        self.write_config(self.config_dir / "config.yml", api_key="secret-key", port=stash.port)

        log = self.run_scraper()

        self.assertEqual(len(stash.performer_updates), 1, log)

    def test_falls_back_to_home_stash_config(self):
        stash = self.start_stash(api_key="secret-key")
        self.write_config(self.home / ".stash" / "config.yml", api_key="secret-key", port=stash.port)

        log = self.run_scraper()

        self.assertEqual(len(stash.performer_updates), 1, log)

    def test_falls_back_to_py_common_config_ini_when_config_yml_has_no_key(self):
        stash = self.start_stash(api_key="ini-key")
        self.write_config(self.config_dir / "config.yml", port=stash.port)
        (self.py_common / "config.ini").write_text(
            "# URL for your local Stash server\nurl = http://localhost:9999\n\napi_key = ini-key\n"
        )

        log = self.run_scraper()

        self.assertEqual(len(stash.performer_updates), 1, log)

    def test_config_ini_fallback_works_when_py_common_is_a_namespace_package(self):
        stash = self.start_stash(api_key="ini-key")
        self.write_config(self.config_dir / "config.yml", port=stash.port)
        (self.py_common / "__init__.py").unlink()
        (self.py_common / "config.ini").write_text("api_key = ini-key\n")

        log = self.run_scraper()

        self.assertEqual(len(stash.performer_updates), 1, log)

    def test_sends_no_api_key_when_stash_has_no_auth(self):
        stash = self.start_stash(api_key=None)
        self.write_config(self.config_dir / "config.yml", port=stash.port)

        log = self.run_scraper()

        self.assertEqual(len(stash.performer_updates), 1, log)
        self.assertEqual(set(stash.api_keys_seen), {None})


class TestErrorsNameTheRealCause(ScraperTestCase):
    def test_auth_enabled_but_no_key_anywhere_says_to_generate_one(self):
        stash = self.start_stash(api_key="secret-key")
        self.write_config(self.config_dir / "config.yml", port=stash.port)

        log = self.run_scraper(expect_exit=69)

        self.assertEqual(stash.performer_updates, [])
        self.assertIn("authentication enabled but no API key was found", log)
        self.assertIn("Settings → Security", log)
        self.assertNotIn("not found in Stash", log)

    def test_rejected_key_says_so_and_names_its_source(self):
        stash = self.start_stash(api_key="current-key")
        config = self.write_config(self.config_dir / "config.yml", api_key="stale-key", port=stash.port)

        log = self.run_scraper(expect_exit=69)

        self.assertEqual(stash.performer_updates, [])
        self.assertIn("rejected the API key", log)
        self.assertIn(str(config), log)
        self.assertNotIn("stale-key", log)
        self.assertNotIn("not found in Stash", log)

    def test_unreachable_stash_names_the_url_tried(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            free_port = s.getsockname()[1]
        self.write_config(self.config_dir / "config.yml", port=free_port)

        log = self.run_scraper(expect_exit=69)

        self.assertIn(f"Could not connect to Stash at http://localhost:{free_port}", log)
        self.assertNotIn("not found in Stash", log)

    def test_missing_image_says_not_found(self):
        stash = self.start_stash(image_exists=False)
        self.write_config(self.config_dir / "config.yml", port=stash.port)

        log = self.run_scraper(expect_exit=69)

        self.assertIn("Image 3091701 not found in Stash", log)

    def test_image_without_performers_says_so(self):
        stash = self.start_stash(performers=[])
        self.write_config(self.config_dir / "config.yml", port=stash.port)

        log = self.run_scraper(expect_exit=69)

        self.assertEqual(stash.performer_updates, [])
        self.assertIn("has no performers attached", log)

    def test_image_with_several_performers_names_them(self):
        stash = self.start_stash(performers=[{"id": "1", "name": "Ann"}, {"id": "2", "name": "Bea"}])
        self.write_config(self.config_dir / "config.yml", port=stash.port)

        log = self.run_scraper(expect_exit=69)

        self.assertEqual(stash.performer_updates, [])
        self.assertIn("multiple performers: Ann, Bea", log)
        self.assertIn("exactly one", log)

    def test_non_json_response_says_stash_did_not_answer_graphql(self):
        stash = self.start_stash(graphql_html=True)
        self.write_config(self.config_dir / "config.yml", port=stash.port)

        log = self.run_scraper(expect_exit=69)

        self.assertIn("did not return JSON", log)

    def test_malformed_fragment_is_reported(self):
        log = self.run_scraper(expect_exit=69, stdin="not json")

        self.assertIn("Could not read the fragment", log)


@unittest.skipUnless(shutil.which("openssl"), "openssl needed to make a self-signed cert")
class TestHttps(ScraperTestCase):
    def make_cert(self, directory, cert_name, key_name):
        directory.mkdir(parents=True, exist_ok=True)
        cert, key = directory / cert_name, directory / key_name
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
             "-subj", "/CN=localhost", "-keyout", str(key), "-out", str(cert)],
            check=True, capture_output=True,
        )
        return cert, key

    def test_uses_https_when_config_sets_cert_paths(self):
        cert, key = self.make_cert(self.tmp / "certs", "my.crt", "my.key")
        stash = self.start_stash(api_key="secret-key", tls=(cert, key))
        self.write_config(
            self.config_dir / "config.yml",
            api_key="secret-key", port=stash.port, ssl_cert_path=cert, ssl_key_path=key,
        )

        log = self.run_scraper()

        self.assertEqual(len(stash.performer_updates), 1, log)

    def test_uses_https_when_default_cert_files_sit_in_config_dir(self):
        cert, key = self.make_cert(self.config_dir, "stash.crt", "stash.key")
        stash = self.start_stash(api_key="secret-key", tls=(cert, key))
        self.write_config(self.config_dir / "config.yml", api_key="secret-key", port=stash.port)

        log = self.run_scraper()

        self.assertEqual(len(stash.performer_updates), 1, log)


if __name__ == "__main__":
    unittest.main()
