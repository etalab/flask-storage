'''
Flask storage
'''


import os
from os.path import join

try:
    from flask import current_app

    from .backends import BaseBackend, DEFAULT_BACKEND  # noqa: Facade pattern
    from .errors import *  # noqa: Facade pattern
    from .files import *  # noqa: Facade pattern
    from .storage import Storage  # noqa: Facade pattern

except ImportError as e:
    print(e)


tag = os.environ.get('CIRCLE_TAG')
build_num = os.environ.get('CIRCLE_BUILD_NUM')

__version__ = '0.6.2.dev' + (str(build_num) if not tag and build_num else '')
__description__ = 'Simple and easy file storages for Flask'


def by_name(name):
    '''Get a storage by its name'''
    return current_app.extensions['fs'].get(name)


def init_app(app, *storages):
    '''
    Initialize Storages configuration
    Register blueprint if necessary.

    :param app: The `~flask.Flask` instance to get the configuration from.
    :param storages: A  `Storage` instance list to register and configure.
    '''

    # Set default configuration
    app.config.setdefault('FS_SERVE', app.config.get('DEBUG', False))
    app.config.setdefault('FS_ROOT', join(app.instance_path, 'fs'))
    app.config.setdefault('FS_PREFIX', None)
    app.config.setdefault('FS_URL', None)
    app.config.setdefault('FS_BACKEND', DEFAULT_BACKEND)
    app.config.setdefault('FS_IMAGES_OPTIMIZE', False)

    state = app.extensions['fs'] = app.extensions.get('fs', {})
    for storage in storages:
        storage.configure(app)
        state[storage.name] = storage

    from .views import bp
    app.register_blueprint(bp, url_prefix=app.config['FS_PREFIX'])
