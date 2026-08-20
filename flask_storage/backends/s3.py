import base64
import binascii
import codecs
import io
import logging
from contextlib import contextmanager, suppress

import boto3
from botocore.exceptions import ClientError
from flask import send_file

from flask_storage import files

from . import BaseBackend

log = logging.getLogger(__name__)


class NonClosingProxy:
    """Expose a file object to a consumer that must not close it.

    `upload_fileobj` closes the file object it is handed once the transfer is
    over, which would close the caller's file and break the contract of
    `BaseBackend.save`. Everything but `close` goes through, so whether the
    file can seek (which decides how the transfer reads it) is unchanged.
    """

    def __init__(self, fileobj):
        self.fileobj = fileobj

    def __getattr__(self, name):
        return getattr(self.fileobj, name)

    def close(self):
        pass


class S3Backend(BaseBackend):
    """
    An Amazon S3 Backend (compatible with any S3-like API)

    Expect the following settings:

    - `endpoint`: The S3 API endpoint
    - `region`: The region to work on.
    - `access_key`: The AWS credential access key
    - `secret_key`: The AWS credential secret key
    """

    _S3_OBJECT_OPTION_MAP = {
        "object_acl": "ACL",
        "object_storage_class": "StorageClass",
    }

    def __init__(self, name, config):
        super().__init__(name, config)

        self.session = boto3.session.Session()
        self.s3config = boto3.session.Config(signature_version="s3v4")

        self.s3 = self.session.resource(
            "s3",
            config=self.s3config,
            endpoint_url=config.endpoint,
            region_name=config.region,
            aws_access_key_id=config.access_key,
            aws_secret_access_key=config.secret_key,
        )
        self.client = self.s3.meta.client
        self.bucket = self.s3.Bucket(config.get("bucket_name") or name)

        if not self.bucket.creation_date:
            # The bucket does not exist, create it
            self.bucket.create()

    def exists(self, filename):
        try:
            self.bucket.Object(filename).load()
        except ClientError:
            return False
        return True

    @contextmanager
    def open(self, filename, mode="r", encoding="utf8"):
        if "r" in mode:
            f = self.bucket.Object(filename).get()["Body"]
            yield f if "b" in mode else codecs.getreader(encoding)(f)
        else:  # mode == 'w'
            f = io.BytesIO() if "b" in mode else io.StringIO()
            yield f
            self.write(filename, f.getvalue())

    def read(self, filename):
        obj = self.bucket.Object(filename).get()
        return obj["Body"].read()

    def write(self, filename, content):
        return self.bucket.put_object(
            Key=filename, Body=self.as_binary(content), **self.get_object_extra_args(filename)
        )

    def save(self, file_or_wfs, filename):
        # Unlike the base implementation, which reads the file into a single
        # `bytes` before a lone PUT, `upload_fileobj` consumes the file object
        # by blocks and switches to a multipart upload past its threshold: the
        # memory it holds is bounded by the parts in flight instead of growing
        # with the file, and the 5GB limit of a single PUT does not apply. The
        # file object only needs `read()`, so a stream that cannot seek back is
        # fine, whether it is reassembled, piped or wrapped by the caller.
        #
        # What it costs is the size of the parts: boto3 only sizes them when it
        # can measure the file, which it does by seeking. A stream it cannot
        # seek keeps them at the default 8MB, and S3 takes at most 10000 of
        # them, so such an upload tops out around 80GB. It is worth knowing
        # that a wrapper exposing nothing but `read()` around an otherwise
        # seekable file lowers that ceiling onto it.
        #
        # `ChecksumType` is set here rather than with the other write options
        # because `put_object` rejects it: it only means something to an upload
        # made of several parts, which by default gets a digest of its parts'
        # digests. `FULL_OBJECT` asks for a digest of the content instead, so a
        # file has the same checksum however many parts it travelled in.
        extra_args = self.get_object_extra_args(filename)
        extra_args["ChecksumType"] = "FULL_OBJECT"
        self.bucket.upload_fileobj(NonClosingProxy(file_or_wfs), filename, ExtraArgs=extra_args)
        return filename

    def delete(self, filename):
        # Delete the exact object...
        self.bucket.Object(filename).delete()
        # ...and, if it is a "directory", everything stored under it. The
        # trailing slash is required so deleting "foo/1" does not also wipe
        # sibling keys sharing the prefix ("foo/10", "foo/11", ...).
        for obj in self.bucket.objects.filter(Prefix=filename + "/"):
            obj.delete()

    def copy(self, filename, target):
        src = {
            "Bucket": self.bucket.name,
            "Key": filename,
        }
        self.bucket.copy(src, target)

    def list_files(self, prefix=None):
        objects = self.bucket.objects.filter(Prefix=prefix) if prefix else self.bucket.objects.all()
        for f in objects:
            yield f.key

    def get_metadata(self, filename):
        """Fetch all availabe metadata"""
        # `ChecksumMode` is what makes S3 hand back the checksum it stored with
        # the object; the resource layer never asks for it.
        head = self.client.head_object(
            Bucket=self.bucket.name, Key=filename, ChecksumMode="ENABLED"
        )
        content_type = head.get("ContentType")
        return {
            "checksum": self.get_checksum(head),
            "size": head["ContentLength"],
            "mime": content_type.split(";", 1)[0] if content_type else None,
            "modified": head["LastModified"],
        }

    @staticmethod
    def get_checksum(head):
        """Read a checksum describing the content out of a HeadObject response."""
        # A `FULL_OBJECT` checksum digests the content, whether the object was
        # stored whole or in a hundred parts. A `COMPOSITE` one digests the
        # parts' digests (like the ETag of a multipart object, suffixed with
        # the part count) and says nothing about the content, so it is worth
        # no more than no checksum at all.
        if head.get("ChecksumType") == "FULL_OBJECT" and (crc32 := head.get("ChecksumCRC32")):
            return "crc32:{0}".format(base64.b64decode(crc32).hex())
        # Objects written before a full-object checksum was asked for only have
        # their ETag, which digests the content when it was stored in one part.
        etag = head["ETag"].strip('"')
        if "-" not in etag:
            return "md5:{0}".format(etag)
        # A multipart ETag digests the parts' digests, so it describes how the
        # object was uploaded rather than what it contains. rclone stores the
        # MD5 of the whole file under this metadata key for exactly that reason,
        # so an object it copied still has a usable checksum. S3 knows nothing
        # about that key: it keeps it as-is, without computing or checking it,
        # so whatever comes out of it has to look like an MD5 before we report
        # it as one.
        if md5 := head.get("Metadata", {}).get("md5chksum"):
            with suppress(binascii.Error):
                digest = base64.b64decode(md5, validate=True)
                if len(digest) == 16:
                    return "md5:{0}".format(digest.hex())
        return None

    def serve(self, filename):
        with self.open(filename, mode="rb") as f:
            return send_file(f, self.get_metadata(filename)["mime"])

    def get_object_extra_args(self, filename):
        # Build extra args for options present in config
        extra_args = {
            arg_name: self.config[config_key]
            for config_key, arg_name in self._S3_OBJECT_OPTION_MAP.items()
            if config_key in self.config
        }
        # S3 stores the content type with the object and serves it back as-is,
        # so it has to be set at write time; it defaults to binary/octet-stream.
        if content_type := files.mime(filename):
            extra_args["ContentType"] = content_type
        # Have S3 checksum what it receives and store the result with the
        # object, so a corrupted transfer is rejected instead of being stored,
        # and `get_metadata` has a digest of the content to report. CRC32 is
        # not a cryptographic digest, but it is the widest algorithm S3 accepts
        # for a whole object: SHA-256 digests can only be combined part by part.
        extra_args["ChecksumAlgorithm"] = "CRC32"
        return extra_args
