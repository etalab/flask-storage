# Contributing

Flask-Storage is open-source and very open to contributions.

## Submitting issues

Issues are contributions in a way so don't hesitate
to submit reports on the [official bugtracker](https://github.com/etalab/flask-storage/issues)

Provide as much informations as possible to specify the issues:

- the flask-fs version used
- a stacktrace
- installed applications list
- a code sample to reproduce the issue
- ...


## Submitting patches (bugfix, features, ...)

If you want to contribute some code:

1. fork the [official Flask-FS repository](https://github.com/etalab/flask-storage)
2. create a branch with an explicit name (like ``my-new-feature`` or ``issue-XX``)
3. do your work in it
4. rebase it on the master branch from the official repository (cleanup your history by performing an interactive rebase)
5. submit your pull-request

There are some rules to follow:

- your contribution should be documented (if needed)
- your contribution should be tested and the test suite should pass successfully
- your code should be mostly PEP8 compatible with a 120 characters line length

You need to install some dependencies to develop on Flask-Storage:

.. code-block:: console

    $ pip install -e .[dev]

A ``Makefile`` is provided to simplify the common tasks


