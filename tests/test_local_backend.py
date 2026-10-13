import hashlib
import io
import os

import pytest

import flask_storage as fs

from flask_storage.backends.local import LocalBackend
from flask_storage.storage import Config

from .test_backend_mixin import BackendTestCase


class LocalBackendTest(BackendTestCase):
    def expected_checksum(self, content):
        return "sha1:{0}".format(hashlib.sha1(content).hexdigest())

    @pytest.fixture(autouse=True)
    def setup(self, tmpdir):
        self.test_dir = tmpdir
        self.config = Config(
            {
                "root": str(tmpdir),
            }
        )
        self.backend = LocalBackend("test", self.config)

    def filename(self, filename):
        return str(self.test_dir.join(filename))

    def put_file(self, filename, content):
        filename = self.filename(filename)
        parent = os.path.dirname(filename)
        if not os.path.exists(parent):
            os.makedirs(parent)
        with open(filename, "wb") as f:
            f.write(self.b(content))

    def get_file(self, filename):
        with open(self.filename(filename), "rb") as f:
            return f.read()

    def file_exists(self, filename):
        return self.test_dir.join(filename).exists()

    def test_root(self):
        assert self.backend.root == str(self.test_dir)

    def test_default_root(self, app):
        app.config["FS_ROOT"] = str(self.test_dir)
        root = self.test_dir.join("default")
        backend = LocalBackend("default", Config({}))
        assert backend.root == root

    def test_backend_root(self, app):
        app.config["FS_LOCAL_ROOT"] = str(self.test_dir)
        root = self.test_dir.join("default")
        backend = LocalBackend("default", Config({}))
        assert backend.root == root

    def test_relative_root_is_made_absolute(self, app, monkeypatch, tmpdir):
        monkeypatch.chdir(tmpdir)
        app.config["FS_ROOT"] = "relative"
        backend = LocalBackend("default", Config({}))
        assert backend.root == os.path.join(str(tmpdir), "relative", "default")
        assert os.path.isabs(backend.root)

    def test_serve_with_relative_root(self, app, monkeypatch, tmpdir, faker):
        # A relative FS_ROOT must anchor to the process CWD for every code path:
        # write paths resolve it at syscall time, while Flask's send_from_directory
        # would resolve it against the app package dir, serving 404s.
        monkeypatch.chdir(tmpdir)
        app.config["FS_ROOT"] = "relative"
        storage = fs.Storage("test")
        app.configure(storage)
        content = self.b(faker.sentence())
        storage.backend.save(io.BytesIO(content), "test.txt")

        file_url = storage.url("test.txt")
        response = app.test_client().get(file_url)

        assert response.status_code == 200
        assert response.data == content
