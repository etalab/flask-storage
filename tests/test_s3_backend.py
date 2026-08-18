import base64
import hashlib
import io
import logging
import zlib

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
    def expected_checksum(self, content):
        return "crc32:{0}".format(format(zlib.crc32(content), "08x"))

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

    def test_open_write_sets_content_type(self, faker):
        # S3 serves back the content type stored with the object, so every
        # write path has to set it, not just `save()`.
        with self.backend.open("test.csv", "w") as f:
            f.write(faker.sentence())

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

    def test_metadata_checksum_does_not_depend_on_the_number_of_parts(self):
        # The point of asking S3 for a full-object checksum: the same content
        # gets the same checksum whether it was stored whole or in parts. The
        # ETag, which digests the parts' digests, does not have this property.
        content = b"0123456789" * (1024 * 1024)

        self.backend.save(io.BytesIO(content), "multipart.bin")
        self.bucket.put_object(Key="whole.bin", Body=content, ChecksumAlgorithm="CRC32")

        assert "-" in self.bucket.Object("multipart.bin").e_tag  # took the multipart path
        assert "-" not in self.bucket.Object("whole.bin").e_tag
        assert self.backend.metadata("multipart.bin")["checksum"] == self.expected_checksum(content)
        assert self.backend.metadata("whole.bin")["checksum"] == self.expected_checksum(content)

    def test_metadata_checksum_of_an_object_stored_without_one(self):
        # Objects written before a full-object checksum was asked for only have
        # their ETag to offer, and it only digests the content of an object
        # stored in one part.
        client = self.session.client(
            "s3",
            config=boto3.session.Config(
                signature_version="s3v4", request_checksum_calculation="when_required"
            ),
            endpoint_url=S3_SERVER,
            region_name=S3_REGION,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
        )
        client.put_object(Bucket=self.bucket.name, Key="legacy.bin", Body=b"abcd")

        assert self.backend.metadata("legacy.bin")["checksum"] == (
            "md5:e2fc714c4727ee9395f324cd2e7f331f"
        )

    def test_metadata_checksum_of_an_object_migrated_by_rclone(self):
        # rclone attaches the MD5 of the whole file under this header when it
        # uploads in parts, precisely because the ETag stops being one. It is
        # what keeps a usable checksum on the objects migrated from the local
        # storage, which nothing else can digest short of downloading them.
        content = b"0123456789" * (1024 * 1024)
        digest = hashlib.md5(content).digest()
        client = self.backend.client
        upload = client.create_multipart_upload(
            Bucket=self.bucket.name,
            Key="migrated.bin",
            Metadata={"md5chksum": base64.b64encode(digest).decode()},
        )
        part = client.upload_part(
            Bucket=self.bucket.name,
            Key="migrated.bin",
            UploadId=upload["UploadId"],
            PartNumber=1,
            Body=content,
        )
        client.complete_multipart_upload(
            Bucket=self.bucket.name,
            Key="migrated.bin",
            UploadId=upload["UploadId"],
            MultipartUpload={"Parts": [{"PartNumber": 1, "ETag": part["ETag"]}]},
        )

        assert "-" in self.bucket.Object("migrated.bin").e_tag
        assert self.backend.metadata("migrated.bin")["checksum"] == "md5:{0}".format(
            digest.hex()
        )

    def test_a_corrupted_part_is_rejected_rather_than_stored(self):
        # What makes the stored checksum worth reporting: S3 digests what it
        # receives on its side and refuses the upload when it does not match.
        client = self.backend.client
        upload = client.create_multipart_upload(
            Bucket=self.bucket.name,
            Key="corrupt.bin",
            ChecksumAlgorithm="CRC32",
            ChecksumType="FULL_OBJECT",
        )

        with pytest.raises(ClientError) as excinfo:
            client.upload_part(
                Bucket=self.bucket.name,
                Key="corrupt.bin",
                UploadId=upload["UploadId"],
                PartNumber=1,
                Body=b"0123456789",
                ChecksumCRC32=base64.b64encode(b"\x00\x00\x00\x00").decode(),
            )

        assert excinfo.value.response["Error"]["Code"] == "BadDigest"

    # def test_root(self):
    #     self.assertEqual(self.backend.root, self.test_dir)

    # def test_default_root(self):
    #     self.app.config['FS_ROOT'] = self.test_dir
    #     root = self.filename('default')
    #     backend = LocalBackend('default', Config({}))
    #     with self.app.app_context():
    #         self.assertEqual(backend.root, root)
