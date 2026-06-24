import codecs
import io
import logging
import mimetypes
from contextlib import contextmanager

import boto3
from botocore.exceptions import ClientError
from flask import send_file

from . import BaseBackend

log = logging.getLogger(__name__)


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
        obj = self.bucket.Object(filename)
        if "r" in mode:
            f = obj.get()["Body"]
            yield f if "b" in mode else codecs.getreader(encoding)(f)
        else:  # mode == 'w'
            f = io.BytesIO() if "b" in mode else io.StringIO()
            yield f
            obj.put(Body=f.getvalue(), **self.get_object_extra_args())

    def read(self, filename):
        obj = self.bucket.Object(filename).get()
        return obj["Body"].read()

    def write(self, filename, content):
        extra_args = self.get_object_extra_args()
        if content_type := mimetypes.guess_type(filename)[0]:
            extra_args["ContentType"] = content_type
        return self.bucket.put_object(Key=filename, Body=self.as_binary(content), **extra_args)

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
        obj = self.bucket.Object(filename)
        checksum = "md5:{0}".format(obj.e_tag[1:-1])
        mime = obj.content_type.split(";", 1)[0] if obj.content_type else None
        return {
            "checksum": checksum,
            "size": obj.content_length,
            "mime": mime,
            "modified": obj.last_modified,
        }

    def serve(self, filename):
        with self.open(filename, mode="rb") as f:
            return send_file(f, self.get_metadata(filename)["mime"])

    def get_object_extra_args(self):
        # Build extra args for options present in config
        return {
            arg_name: self.config[config_key]
            for config_key, arg_name in self._S3_OBJECT_OPTION_MAP.items()
            if config_key in self.config
        }
