.. _api:

API
===

Core
----

.. automodule:: flask_storage
    :members:

.. autoclass:: flask_storage.Storage
    :members:


File types
----------

.. autodata:: flask_storage.TEXT
.. autodata:: flask_storage.DOCUMENTS
.. autodata:: flask_storage.IMAGES
.. autodata:: flask_storage.AUDIO
.. autodata:: flask_storage.DATA
.. autodata:: flask_storage.SCRIPTS
.. autodata:: flask_storage.ARCHIVES
.. autodata:: flask_storage.EXECUTABLES
.. autodata:: flask_storage.DEFAULTS
.. autodata:: flask_storage.ALL

.. autoclass:: flask_storage.All
.. autoclass:: flask_storage.AllExcept

.. .. automodule:: flask_storage.files
..     :members:


.. automodule:: flask_storage.images
    :members:


Backends
--------

.. automodule:: flask_storage.backends
    :members:


.. autoclass:: flask_storage.backends.local.LocalBackend
    :members:


.. autoclass:: flask_storage.backends.s3.S3Backend
    :members:


.. autoclass:: flask_storage.backends.swift.SwiftBackend
    :members:


.. autoclass:: flask_storage.backends.gridfs.GridFsBackend
    :members:


Mongo
-----

.. automodule:: flask_storage.mongo
    :members:



Errors
------

These are all errors used accross this extensions.

.. automodule:: flask_storage.errors
    :members:


Internals
---------

These are internal classes or helpers.
Most of the time you shouldn't have to deal directly with them.


.. autoclass:: flask_storage.storage.Config
