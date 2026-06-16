Configuration
=============

Flask-FS expose both global and by storage settings.

Global configuration
--------------------

FS_SERVE
~~~~~~~~

**default**: ``DEBUG``

A boolean whether or not Flask-FS should serve files


FS_ROOT
~~~~~~~

**default**: ``{app.instance_path}/fs``

The global local storage root.
Each storage will have its own root as a subdirectory unless not local or overridden by configuration.

FS_PREFIX
~~~~~~~~~

**default**: ``None``

An optional URL path prefix under which the file-serving blueprint is mounted
(ex: ``'/fs'``).

This only affects the **HTTP route** used to serve files (when ``FS_SERVE`` is
enabled): a file otherwise served at ``/files/...`` becomes ``/fs/files/...``.
It is **not** a path inside the storage or bucket and does not change object
keys. To store a storage's files under a subfolder, use the per-storage
``PREFIX`` key (see `Storages configuration`_).


FS_URL
~~~~~~

**default**: ``None``

An optionnal URL on which the `FS_ROOT` is visible (ex: ``'https://static.mydomain.com/'``).


FS_BACKEND
~~~~~~~~~~

**default**: ``'local'``

The default backend used for storages.
Can be one of ``local``, ``s3``, ``gridfs`` or ``swift``

FS_IMAGES_OPTIMIZE
~~~~~~~~~~~~~~~~~~

**default**: ``False``

Whether or not image should be compressedd/optimized by default.


Storages configuration
----------------------

Each storage configuration can be overridden from the application configuration.
For a given ``KEY``, the value is resolved in the following order (most specific
first):

- ``{STORAGE_NAME}_FS_{KEY}`` (storage-specific configuration)
- ``FS_{BACKEND_NAME}_{KEY}`` (backend-wide configuration)
- the default value

.. warning::

    There is **no** generic ``FS_{KEY}`` global fallback: a plain ``FS_PREFIX``,
    for instance, does *not* propagate to storages. Only a few global settings
    are honored, each resolved on its own: ``FS_BACKEND`` (default backend),
    ``FS_URL`` (base URL) and ``FS_ROOT`` (local root).

Given a storage declared like this:

.. code-block:: python

    import flask_storage as fs

    avatars = fs.Storage('avatars', fs.IMAGES)

You can override its root with the following configuration:

.. code-block:: python

    AVATARS_FS_ROOT = '/somewhere/on/the/filesystem'

Or you can set a base URL to all storages for a given backend:

.. code-block:: python

    FS_S3_URL = 'https://s3.somewhere.com/'
    FS_S3_REGION = 'us-east-1'

Storage prefix
~~~~~~~~~~~~~~

The ``PREFIX`` key stores all of a storage's files under a subfolder of its
backend location. It is a *namespace* applied transparently to every operation:
it is prepended to the object key on every access (read, write, delete, ...),
but it **never** appears in the filename returned by ``save()``. Stored
references therefore stay prefix-agnostic, and ``list_files()`` only returns
this storage's own files, with the prefix stripped.

This is typically used to share a single S3 bucket between several storages,
each isolated under its own folder:

.. code-block:: python

    CHUNKS_FS_BUCKET_NAME = 'my-shared-bucket'
    CHUNKS_FS_PREFIX = 'chunks'   # objects stored under "chunks/..."

Leading and trailing slashes are ignored, so ``'chunks'`` and ``'chunks/'`` are
equivalent. You can also set it for a whole backend:

.. code-block:: python

    FS_S3_PREFIX = 'udata'        # every S3 storage stored under "udata/..."

.. note::

    This is unrelated to `FS_PREFIX`_, which mounts the file-serving HTTP route
    and does not change object keys.
