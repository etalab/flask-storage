import io
import logging

import boto3
import pytest
from botocore.exceptions import ClientError

from flask_storage.backends.s3 import S3Backend
from flask_storage.storage import Config

from .test_backend_mixin import BackendTestCase

# Hide over verbose boto3 logging
logging.getLogger("boto3").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)


class ReadOnlyStream(io.RawIOBase):
    """A stream that can only be read forward, like a reassembled chunked upload."""

    def __init__(self, content):
        self.content = io.BytesIO(content)

    def readable(self):
        return True

    def readinto(self, target):
        return self.content.readinto(target)


S3_SERVER = "http://localhost:9000"
S3_REGION = "us-east-1"
S3_ACCESS_KEY = "ABCDEFGHIJKLMNOQRSTU"
S3_SECRET_KEY = "abcdefghiklmnoqrstuvwxyz1234567890abcdef"


class S3BackendTest(BackendTestCase):
    hasher = "md5"

    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = boto3.session.Session()
        self.config = boto3.session.Config(signature_version="s3v4")

        self.s3 = self.session.resource(
            "s3",
            config=self.config,
            endpoint_url=S3_SERVER,
            region_name=S3_REGION,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
        )
        self.bucket = self.s3.Bucket("test")

        self.config = Config(
            endpoint=S3_SERVER, region=S3_REGION, access_key=S3_ACCESS_KEY, secret_key=S3_SECRET_KEY
        )
        self.backend = S3Backend("test", self.config)
        yield
        for obj in self.bucket.objects.all():
            obj.delete()
        self.bucket.delete()

    def put_file(self, filename, content):
        self.bucket.put_object(Key=filename, Body=content)

    def get_file(self, filename):
        obj = self.bucket.Object(filename).get()
        return obj["Body"].read()

    def file_exists(self, filename):
        try:
            self.bucket.Object(filename).load()
            return True
        except ClientError:
            return False

    def test_save_sets_content_type(self, faker, utils):
        self.backend.save(utils.file(faker.binary()), "test.csv")

        assert self.bucket.Object("test.csv").content_type == "text/csv"

    def test_save_large_file(self):
        # Over the 8MB multipart threshold of boto3.
        content = b"0123456789" * (1024 * 1024)

        self.backend.save(io.BytesIO(content), "large.bin")

        self.assert_bin_equal("large.bin", content)
        # A multipart ETag is a digest of digests suffixed with the part count.
        # Without this, nothing would tell the upload took the multipart path
        # rather than being buffered into a single PUT.
        assert "-" in self.bucket.Object("large.bin").e_tag

    def test_save_stream_that_cannot_seek(self, faker):
        content = faker.binary()

        self.backend.save(ReadOnlyStream(content), "stream.bin")

        self.assert_bin_equal("stream.bin", content)

    def test_save_leaves_the_file_open(self, faker, utils):
        # ImageField stores the same file object several times, seeking back to
        # its start in between (flask_storage/mongo.py:143-155): a save that
        # consumed the caller's file would break thumbnail generation.
        content = faker.binary()
        f = utils.file(content)

        self.backend.save(f, "first.bin")
        f.seek(0)
        self.backend.save(f, "second.bin")

        assert not f.closed
        self.assert_bin_equal("first.bin", content)
        self.assert_bin_equal("second.bin", content)

    def test_metadata_of_a_multipart_upload_has_no_checksum(self):
        # The ETag of a multipart object digests the parts' digests, not the
        # content: there is no MD5 to report, and reporting the ETag as one
        # would hand out a checksum that does not match the file.
        self.backend.save(io.BytesIO(b"0123456789" * (1024 * 1024)), "large.bin")

        assert self.backend.metadata("large.bin")["checksum"] is None

    # def test_root(self):
    #     self.assertEqual(self.backend.root, self.test_dir)

    # def test_default_root(self):
    #     self.app.config['FS_ROOT'] = self.test_dir
    #     root = self.filename('default')
    #     backend = LocalBackend('default', Config({}))
    #     with self.app.app_context():
    #         self.assertEqual(backend.root, root)
