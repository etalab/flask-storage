import copy

import pytest

import flask_storage as fs
from flask_storage.mongo import FileField, ImageField


@pytest.fixture(params=[FileField, ImageField])
def field(request, app, mock_backend):
    storage = fs.Storage("test")
    app.configure(storage)
    return request.param(fs=storage)


def test_deepcopy_shares_the_storage(field):
    # Mongoengine deep-copies a document's fields whenever auto-dereferencing
    # is off. The storage — and the backend it owns, which holds network
    # clients on S3 — must be shared with the copy, never copied.
    copied = copy.deepcopy(field)

    assert copied.fs is field.fs
    assert copied.fs.backend is field.fs.backend


def test_deepcopy_is_a_distinct_field(field):
    # Turning dereferencing off is done by mutating the copy, so the copy must
    # not be the class-level field itself: that would leak across documents.
    copied = copy.deepcopy(field)
    copied.set_auto_dereferencing(False)

    assert copied is not field
    assert field._auto_dereference
