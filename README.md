# Flask-Storage

Simple and easy file storages for Flask

Flask-Storage is a community driven fork of [Flask-FS](https://github.com/noirbizarre/flask-fs)


## Compatibility

Flask-Storage requires 3.11+ and Flask 1.1.4.

Amazon S3 support requires Boto3.


## Installation

You can install Flask-Storage with pip:

.. code-block:: console

    $ pip install flask-storage
    # or
    $ pip install flask-storage[s3]  # For Amazon S3 backend support


## Quick start

.. code-block:: python

    from flask import Flask
    import flask_storage as fs

    app = Flask(__name__)
    fs.init_app(app)

    images = fs.Storage('images')


    if __name__ == '__main__':
        app.run(debug=True)


## Documentation

The full documentation is hosted [on Read the Docs](http://flask-storage.readthedocs.org/en/latest/)
