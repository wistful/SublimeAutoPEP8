import os
import re
import sys

import sublime

if sublime.version() < '3000':
    from Queue import Queue
    from StringIO import StringIO

    PLUGIN_PATH = os.path.abspath(os.path.split(os.path.dirname(__file__))[0])
else:
    from io import StringIO
    from queue import Queue

    PLUGIN_PATH = os.path.abspath(os.path.dirname(__file__))


DEFAULT_FILE_MENU_BEHAVIOUR = 'ifneed'
DEFAULT_SEARCH_DEPTH = 3
PYCODING = re.compile("coding[:=]\s*([-\w.]+)")

if sublime.platform() == 'windows':
    USER_CONFIG_NAME = 'AutoPep8 (Windows).sublime-settings'
else:
    USER_CONFIG_NAME = 'AutoPep8.sublime-settings'


def update_syspath():
    plugin_path = os.path.split(os.path.abspath(__file__))[0]
    if sublime.version() < '3000':
        sys.path.insert(0, os.path.join(PLUGIN_PATH, "packages_py2"))
    else:
        sys.path.insert(0, os.path.join(PLUGIN_PATH, "packages_py3"))


update_syspath()
