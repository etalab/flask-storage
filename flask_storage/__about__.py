'''
Flask storage
'''

import os

tag = os.environ.get('CIRCLE_TAG')
build_num = os.environ.get('CIRCLE_BUILD_NUM')

__version__ = '0.6.2.dev' + (str(build_num) if not tag and build_num else '')
__description__ = 'Simple and easy file storages for Flask'
