import copy
import filecmp
import os

import mongoengine
import pytest
from PIL import Image

import flask_storage as fs
from flask_storage.mongo import FileField, ImageField


@pytest.fixture(params=[FileField, ImageField])
def field(request):
    return request.param(fs=fs.Storage("test"))


def test_deepcopy_of_a_field_shares_the_storage(field):
    # Mongoengine deep-copies a document's fields whenever auto-dereferencing
    # is off, and every field points at the application storage.
    copied = copy.deepcopy(field)

    assert copied.fs is field.fs


def test_deepcopy_of_a_file_reference_shares_the_storage(field):
    # The proxies stored in `document._data` hold the storage too, so deep
    # copying a document must not duplicate it either.
    reference = field.proxy(filename="file.test")

    copied = copy.deepcopy(reference)

    assert copied.fs is field.fs


class FieldTestCase:
    # No database: reloading a document from `to_mongo()` with `_from_son` goes
    # through the same `to_python` as a document read from MongoDB.
    @pytest.fixture(autouse=True)
    def storage(self, app, tmpdir):
        app.instance_path = str(tmpdir)
        storage = fs.Storage("test", fs.ALL)
        fs.init_app(app, storage)
        return storage


class FileFieldTest(FieldTestCase):
    def test_default_validate(self, storage):
        class Tester(mongoengine.Document):
            file = FileField(fs=storage)

        tester = Tester()

        assert tester.validate() is None

        assert not tester.file
        assert str(tester.file) == ""
        assert tester.to_mongo() == {}
        assert tester.file.filename is None

    def test_set_filename(self, storage):
        class Tester(mongoengine.Document):
            file = FileField(fs=storage)

        filename = "file.test"

        tester = Tester()
        tester.file = filename

        assert tester.validate() is None

        assert tester.file
        assert tester.file.filename == filename
        assert tester.to_mongo() == {"file": {"filename": filename}}

        tester = Tester._from_son(tester.to_mongo())
        assert tester.file.filename == filename

    def test_save_from_file(self, storage, binfile):
        class Tester(mongoengine.Document):
            file = FileField(fs=storage)

        filename = "test.png"

        tester = Tester()
        with open(binfile, "rb") as f:
            tester.file.save(f, filename)
        tester.validate()

        assert tester.file
        assert str(tester.file) == tester.file.url
        assert tester.file.filename == filename
        assert tester.to_mongo() == {"file": {"filename": filename}}
        assert filename in storage
        assert filecmp.cmp(storage.path(filename), binfile)

        tester = Tester._from_son(tester.to_mongo())
        assert tester.file.filename == filename

    def test_save_from_filestorage(self, storage, utils):
        class Tester(mongoengine.Document):
            file = FileField(fs=storage)

        filename = "test.txt"

        tester = Tester()
        tester.file.save(utils.filestorage(filename, "this is a test"))
        tester.validate()

        assert tester.file
        assert str(tester.file) == tester.file.url
        assert tester.file.filename == filename
        assert tester.to_mongo() == {"file": {"filename": filename}}
        assert filename in storage

        tester = Tester._from_son(tester.to_mongo())
        assert tester.file.filename == filename

    def test_save_with_upload_to(self, storage, utils):
        upload_to = "prefix"

        class Tester(mongoengine.Document):
            file = FileField(fs=storage, upload_to=upload_to)

        filename = "test.txt"

        tester = Tester()
        tester.file.save(utils.filestorage(filename, "this is a test"))
        tester.validate()

        expected_filename = "/".join([upload_to, filename])
        assert tester.file
        assert tester.file.filename == expected_filename
        assert expected_filename in storage
        assert tester.to_mongo() == {"file": {"filename": expected_filename}}

        tester = Tester._from_son(tester.to_mongo())
        assert tester.file.filename == expected_filename

    def test_save_with_callable_upload_to(self, storage, utils):
        upload_to = "prefix"

        class Tester(mongoengine.Document):
            file = FileField(fs=storage, upload_to=lambda o: upload_to)

        filename = "test.txt"

        tester = Tester()
        tester.file.save(utils.filestorage(filename, "this is a test"))
        tester.validate()

        expected_filename = "/".join([upload_to, filename])
        assert tester.file
        assert tester.file.filename == expected_filename
        assert expected_filename in storage
        assert tester.to_mongo() == {"file": {"filename": expected_filename}}

        tester = Tester._from_son(tester.to_mongo())
        assert tester.file.filename == expected_filename

    def test_save_with_callable_basename(self, storage, utils):
        class Tester(mongoengine.Document):
            file = FileField(fs=storage, basename=lambda o: "prefix/filename")

        tester = Tester()
        tester.file.save(utils.filestorage("test.txt", "this is a test"))
        tester.validate()

        expected_filename = "prefix/filename.txt"
        assert tester.file
        assert tester.file.filename == expected_filename
        assert expected_filename in storage
        assert tester.to_mongo() == {"file": {"filename": expected_filename}}

        tester = Tester._from_son(tester.to_mongo())
        assert tester.file.filename == expected_filename

    def test_save_with_callable_basename_override(self, storage, utils):
        class Tester(mongoengine.Document):
            file = FileField(fs=storage, basename=lambda o: "prefix/filename")

        expected_filename = "other.txt"

        tester = Tester()
        tester.file.save(utils.filestorage("test.txt", "this is a test"), expected_filename)
        tester.validate()

        assert tester.file
        assert tester.file.filename == expected_filename
        assert expected_filename in storage
        assert tester.to_mongo() == {"file": {"filename": expected_filename}}

        tester = Tester._from_son(tester.to_mongo())
        assert tester.file.filename == expected_filename


class ImageFieldTestMixin(FieldTestCase):
    @pytest.fixture
    def resource(self, utils, image):
        return utils.filestorage(f"flask.{self.ext}", image)

    def test_default_validate(self, storage):
        class Tester(mongoengine.Document):
            image = ImageField(fs=storage)

        tester = Tester()
        assert tester.validate() is None

        assert not tester.image
        assert str(tester.image) == ""
        assert tester.to_mongo() == {}
        assert tester.image.filename is None
        assert tester.image.original is None

    def test_save_file(self, storage, image):
        class Tester(mongoengine.Document):
            image = ImageField(fs=storage)

        filename = f"test.{self.ext}"

        tester = Tester()
        tester.image.save(image, filename)
        tester.validate()

        assert tester.image
        assert str(tester.image) == tester.image.url
        assert tester.image.filename == filename
        assert tester.image.original == filename
        assert filename in storage
        assert tester.to_mongo() == {"image": {"filename": filename}}

        tester = Tester._from_son(tester.to_mongo())
        assert tester.image.filename == filename

        with open(storage.path(filename), "rb") as f_stored:
            assert Image.open(f_stored).size == Image.open(image).size

    def test_save_filestorage(self, storage, resource, image):
        class Tester(mongoengine.Document):
            image = ImageField(fs=storage)

        filename = f"flask.{self.ext}"

        tester = Tester()
        tester.image.save(resource)
        tester.validate()

        assert tester.image
        assert str(tester.image) == tester.image.url
        assert tester.image.filename == filename
        assert tester.image.original == filename
        assert filename in storage
        assert tester.to_mongo() == {"image": {"filename": filename}}

        tester = Tester._from_son(tester.to_mongo())
        assert tester.image.filename == filename

        with open(storage.path(filename), "rb") as f_stored:
            assert Image.open(f_stored).size == Image.open(image).size

    def assert_optimized(self, storage, image, filename, filename_original):
        path_original = storage.path(filename_original)
        path_optimized = storage.path(filename)

        with open(path_original, "rb") as f_orig, open(path_optimized, "rb") as f_optimized:
            source = Image.open(image)
            assert Image.open(f_orig).size == source.size
            assert Image.open(f_optimized).size == source.size
        assert os.stat(path_optimized).st_size < os.stat(path_original).st_size

    def test_save_optimize_settings(self, app, storage, resource, image):
        app.config["FS_IMAGES_OPTIMIZE"] = True

        class Tester(mongoengine.Document):
            image = ImageField(fs=storage)

        filename = f"flask.{self.ext}"
        filename_original = f"flask-original.{self.ext}"

        tester = Tester()
        tester.image.save(resource)
        tester.validate()

        assert tester.image
        assert str(tester.image) == tester.image.url
        assert tester.image.filename == filename
        assert tester.image.original == filename_original
        assert filename in storage
        assert tester.to_mongo() == {"image": {"filename": filename, "original": filename_original}}

        tester = Tester._from_son(tester.to_mongo())
        assert tester.image.filename == filename
        assert tester.image.original == filename_original

        self.assert_optimized(storage, image, filename, filename_original)

    def test_save_optimize_attribute(self, storage, resource, image):
        class Tester(mongoengine.Document):
            image = ImageField(fs=storage, optimize=True)

        filename = f"flask.{self.ext}"
        filename_original = f"flask-original.{self.ext}"

        tester = Tester()
        tester.image.save(resource)
        tester.validate()

        assert tester.image
        assert str(tester.image) == tester.image.url
        assert tester.image.filename == filename
        assert tester.image.original == filename_original
        assert filename in storage
        assert tester.to_mongo() == {"image": {"filename": filename, "original": filename_original}}

        tester = Tester._from_son(tester.to_mongo())
        assert tester.image.filename == filename
        assert tester.image.original == filename_original

        self.assert_optimized(storage, image, filename, filename_original)

    def test_save_max_size(self, storage, resource, image):
        max_size = 150

        class Tester(mongoengine.Document):
            image = ImageField(fs=storage, max_size=max_size)

        filename = f"flask.{self.ext}"
        filename_original = f"flask-original.{self.ext}"

        tester = Tester()
        tester.image.save(resource)
        tester.validate()

        assert tester.image
        assert str(tester.image) == tester.image.url
        assert tester.image.filename == filename
        assert tester.image.original == filename_original
        assert filename in storage
        assert tester.to_mongo() == {"image": {"filename": filename, "original": filename_original}}

        tester = Tester._from_son(tester.to_mongo())
        assert tester.image.filename == filename
        assert tester.image.original == filename_original

        with open(storage.path(filename_original), "rb") as f_orig:
            with open(storage.path(filename), "rb") as f_resized:
                source = Image.open(image)
                resized = Image.open(f_resized)
                assert Image.open(f_orig).size == source.size
                assert max(resized.size) <= max_size < max(source.size)
                assert resized.size[0] / resized.size[1] == pytest.approx(
                    source.size[0] / source.size[1], rel=0.02
                )

    def assert_thumbnails(self, storage, image, filename, filename_32, filename_150):
        with open(storage.path(filename), "rb") as f_orig:
            with open(storage.path(filename_32), "rb") as f_32:
                with open(storage.path(filename_150), "rb") as f_150:
                    assert Image.open(f_orig).size == Image.open(image).size
                    assert Image.open(f_32).size == (32, 32)
                    assert Image.open(f_150).size == (150, 150)

    def test_save_thumbnails(self, storage, image, resource):
        sizes = [150, 32]

        class Tester(mongoengine.Document):
            image = ImageField(fs=storage, thumbnails=sizes)

        filename = f"flask.{self.ext}"
        filename_150 = f"flask-150.{self.ext}"
        filename_32 = f"flask-32.{self.ext}"

        tester = Tester()
        tester.image.save(resource)
        tester.validate()

        assert tester.image
        assert str(tester.image) == tester.image.url
        assert tester.image.filename == filename
        assert tester.image.original == filename
        assert tester.image.thumbnail(32) == filename_32
        assert tester.image.thumbnail(150) == filename_150
        with pytest.raises(ValueError):
            tester.image.thumbnail(200)

        assert filename in storage
        assert filename_32 in storage
        assert filename_150 in storage
        assert tester.to_mongo() == {
            "image": {
                "filename": filename,
                "thumbnails": {"32": filename_32, "150": filename_150},
            }
        }

        tester = Tester._from_son(tester.to_mongo())
        assert tester.image.filename == filename
        assert tester.image.original == filename
        assert tester.image.thumbnail(32) == filename_32
        assert tester.image.thumbnail(150) == filename_150

        self.assert_thumbnails(storage, image, filename, filename_32, filename_150)

    def test_save_thumbnails_with_bbox(self, storage, resource, image):
        sizes = [150, 32]
        bbox = (10, 10, 100, 100)

        filename = f"flask.{self.ext}"
        filename_150 = f"flask-150.{self.ext}"
        filename_32 = f"flask-32.{self.ext}"

        class Tester(mongoengine.Document):
            image = ImageField(fs=storage, thumbnails=sizes)

        tester = Tester()
        tester.image.save(resource, bbox=bbox)
        tester.validate()

        assert tester.image
        assert str(tester.image) == tester.image.url
        assert tester.image.filename == filename
        assert tester.image.original == filename
        assert tester.image.thumbnail(32) == filename_32
        assert tester.image.thumbnail(150) == filename_150
        assert tester.image.bbox == bbox
        with pytest.raises(ValueError):
            tester.image.thumbnail(200)

        assert filename in storage
        assert filename_32 in storage
        assert filename_150 in storage
        assert tester.to_mongo() == {
            "image": {
                "filename": filename,
                "bbox": (10, 10, 100, 100),
                "thumbnails": {"32": filename_32, "150": filename_150},
            }
        }

        tester = Tester._from_son(tester.to_mongo())
        assert tester.image.filename == filename
        assert tester.image.original == filename
        assert tester.image.thumbnail(32) == filename_32
        assert tester.image.thumbnail(150) == filename_150
        assert tuple(tester.image.bbox) == bbox

        self.assert_thumbnails(storage, image, filename, filename_32, filename_150)

    def test_save_with_two_fields(self, storage, resource):
        sizes = [32]
        bbox = (10, 10, 100, 100)

        filename = f"flask.{self.ext}"
        filename_32 = f"flask-32.{self.ext}"
        filename2 = f"flask2.{self.ext}"

        class Tester(mongoengine.Document):
            image = ImageField(fs=storage, thumbnails=sizes)
            image2 = ImageField(fs=storage)

        tester = Tester()
        tester.image.save(resource, bbox=bbox)
        tester.image2.save(resource, filename=filename2)
        tester.validate()

        assert tester.image
        assert str(tester.image) == tester.image.url
        assert tester.image.filename == filename
        assert tester.image.thumbnail(32) == filename_32
        assert tuple(tester.image.bbox) == bbox

        assert tester.image2
        assert str(tester.image2) == tester.image2.url
        assert tester.image2.filename == filename2
        assert tester.image2.bbox is None

        assert filename in storage
        assert filename_32 in storage
        assert filename2 in storage
        assert tester.to_mongo() == {
            "image": {
                "filename": filename,
                "bbox": (10, 10, 100, 100),
                "thumbnails": {"32": filename_32},
            },
            "image2": {"filename": filename2},
        }

    def test_save_and_update(self, storage, resource):
        sizes = [150, 32]
        bbox = (10, 10, 100, 100)

        filename = f"flask.{self.ext}"
        filename_150 = f"flask-150.{self.ext}"
        filename_32 = f"flask-32.{self.ext}"

        class Tester(mongoengine.Document):
            image = ImageField(fs=storage, thumbnails=sizes)

        # A document loaded from the database, so only actual changes are tracked.
        tester = Tester._from_son({})

        tester.image.save(resource, bbox=bbox)

        assert tester._changed_fields == ["image"]

        tester = Tester._from_son(tester.to_mongo())
        assert tester.image.filename == filename
        assert tester.image.original == filename
        assert tester.image.thumbnail(32) == filename_32
        assert tester.image.thumbnail(150) == filename_150
        assert tuple(tester.image.bbox) == bbox

    def test_best_match(self, storage, resource):
        sizes = [150, 32]

        filename_150 = f"flask-150.{self.ext}"
        filename_32 = f"flask-32.{self.ext}"
        filename2 = f"flask2.{self.ext}"

        class Tester(mongoengine.Document):
            image = ImageField(fs=storage, thumbnails=sizes)
            image2 = ImageField(fs=storage)

        tester = Tester()

        assert tester.image(150) is None
        assert tester.image.best_url() is None

        tester.image.save(resource)
        tester.image2.save(resource, filename2)

        assert tester.image.best_url(150) == storage.url(filename_150)
        assert tester.image.best_url(140) == storage.url(filename_150)
        assert tester.image.best_url(100) == storage.url(filename_150)
        assert tester.image.best_url(32) == storage.url(filename_32)
        assert tester.image.best_url(30) == storage.url(filename_32)
        assert tester.image.best_url(160) == storage.url(filename_150)
        assert tester.image.best_url() == storage.url(filename_150)

        assert tester.image(150) == storage.url(filename_150)
        assert tester.image(140) == storage.url(filename_150)
        assert tester.image(160) == storage.url(filename_150)

        assert tester.image2.best_url(150) == storage.url(filename2)
        assert tester.image2.best_url() == storage.url(filename2)

    def test_full(self, storage, resource):
        class Tester(mongoengine.Document):
            image = ImageField(fs=storage, max_size=150)

        filename = f"flask.{self.ext}"

        tester = Tester()

        assert tester.image.full() is None
        assert tester.image.full(external=True) is None

        tester.image.save(resource)

        assert tester.image.full() == storage.url(filename)
        assert tester.image.full(external=True) == storage.url(filename, external=True)

    def test_save_with_upload_to(self, storage, resource):
        upload_to = "prefix"

        class Tester(mongoengine.Document):
            image = ImageField(fs=storage, upload_to=upload_to)

        tester = Tester()
        tester.image.save(resource)
        tester.validate()

        expected_filename = "/".join([upload_to, f"flask.{self.ext}"])
        assert tester.image
        assert tester.image.filename == expected_filename
        assert expected_filename in storage
        assert tester.to_mongo() == {"image": {"filename": expected_filename}}

        tester = Tester._from_son(tester.to_mongo())
        assert tester.image.filename == expected_filename

    def test_save_with_callable_upload_to(self, storage, resource):
        upload_to = "prefix"

        class Tester(mongoengine.Document):
            image = ImageField(fs=storage, upload_to=lambda o: upload_to)

        tester = Tester()
        tester.image.save(resource)
        tester.validate()

        expected_filename = "/".join([upload_to, f"flask.{self.ext}"])
        assert tester.image
        assert tester.image.filename == expected_filename
        assert expected_filename in storage
        assert tester.to_mongo() == {"image": {"filename": expected_filename}}

        tester = Tester._from_son(tester.to_mongo())
        assert tester.image.filename == expected_filename

    def test_save_with_callable_basename(self, storage, resource):
        class Tester(mongoengine.Document):
            image = ImageField(fs=storage, basename=lambda o: "prefix/filename")

        tester = Tester()
        tester.image.save(resource)
        tester.validate()

        expected_filename = f"prefix/filename.{self.ext}"
        assert tester.image
        assert tester.image.filename == expected_filename
        assert expected_filename in storage
        assert tester.to_mongo() == {"image": {"filename": expected_filename}}

        tester = Tester._from_son(tester.to_mongo())
        assert tester.image.filename == expected_filename

    def test_save_with_callable_basename_override(self, storage, resource):
        class Tester(mongoengine.Document):
            image = ImageField(fs=storage, basename=lambda o: "prefix/filename")

        expected_filename = f"other.{self.ext}"

        tester = Tester()
        tester.image.save(resource, expected_filename)
        tester.validate()

        assert tester.image
        assert tester.image.filename == expected_filename
        assert expected_filename in storage
        assert tester.to_mongo() == {"image": {"filename": expected_filename}}

        tester = Tester._from_son(tester.to_mongo())
        assert tester.image.filename == expected_filename

    def test_rerender(self, storage, image):
        class Tester(mongoengine.Document):
            image = ImageField(fs=storage, optimize=True)

        filename = f"flask.{self.ext}"
        filename_original = f"flask-original.{self.ext}"

        storage.write(filename, image)

        tester = Tester()
        tester.image.filename = filename
        assert tester.to_mongo() == {"image": {"filename": filename}}

        tester.image.rerender()
        tester = Tester._from_son(tester.to_mongo())

        assert tester.image
        assert str(tester.image) == tester.image.url
        assert tester.image.filename == filename
        assert tester.image.original == filename_original
        assert filename in storage
        assert tester.to_mongo() == {
            "image": {"filename": filename, "original": filename_original},
        }

        self.assert_optimized(storage, image, filename, filename_original)

    def test_rerender_multiple(self, storage, image):
        class Tester(mongoengine.Document):
            image = ImageField(fs=storage, max_size=100, optimize=True)

        filename = f"flask.{self.ext}"
        filename_original = f"flask-original.{self.ext}"

        storage.write(filename_original, image)

        tester = Tester()
        tester.image.original = filename_original
        tester.image.filename = filename
        assert tester.to_mongo() == {"image": {"original": filename_original, "filename": filename}}

        tester.image.rerender()
        tester = Tester._from_son(tester.to_mongo())

        assert tester.image
        assert str(tester.image) == tester.image.url
        assert tester.image.filename == filename
        assert tester.image.original == filename_original
        assert filename in storage
        assert tester.to_mongo() == {
            "image": {"filename": filename, "original": filename_original},
        }

        path_original = storage.path(filename_original)
        path_resized = storage.path(filename)

        with open(path_original, "rb") as f_orig, open(path_resized, "rb") as f_resized:
            assert Image.open(f_orig).size == Image.open(image).size
            assert Image.open(f_resized).size[0] == 100
        assert os.stat(path_resized).st_size < os.stat(path_original).st_size


class ImageFieldPngTest(ImageFieldTestMixin):
    ext = "png"

    @pytest.fixture
    def image(self, pngfile):
        with open(pngfile, "rb") as f:
            yield f


class ImageFieldJpgTest(ImageFieldTestMixin):
    ext = "jpg"

    @pytest.fixture
    def image(self, jpgfile):
        with open(jpgfile, "rb") as f:
            yield f
