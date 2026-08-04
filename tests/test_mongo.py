import copy

import pytest

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
