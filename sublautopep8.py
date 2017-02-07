# coding=utf-8
import glob
import logging
import os
import sys

import sublime
import sublime_plugin

if sublime.version() < '3000':
    from sublimeautopep8lib import autopep8
    from sublimeautopep8lib import common
else:
    from AutoPEP8.sublimeautopep8lib import autopep8
    from AutoPEP8.sublimeautopep8lib import common

try:
    unicode
except NameError:
    unicode = str

VERSION = '1.3.3'

logger = logging.getLogger('SublimeAutoPEP8')
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.INFO)


def _next(iter_obj):
    """Retrieve the next item from the iter_obj."""
    try:
        return iter_obj.next()
    except AttributeError:
        return iter_obj.__next__()


def _PrintDebugInfo():
    """Prints debug info into the sublime console."""
    if not is_debug():
        return
    message = (
        'AutoPEP8:'
        '\n\tsublime: version=%(subl_version)s, platform=%(subl_platform)s,'
        ' arch=%(subl_arch)s,'
        ' packages_path=%(subl_packages)s\n,'
        ' installed_packages_path=%(subl_installed_packages)s'
        '\n\tplugin: version=%(plugin_version)s'
        '\n\tconfig: %(config)s'
    )
    config_keys = (
        'max-line-length', 'list-fixes', 'ignore', 'select', 'aggressive',
        'indent-size', 'format_on_save', 'syntax_list',
        'file_menu_search_depth', 'avoid_new_line_in_select_mode', 'debug',
    )
    config = {}
    for key in config_keys:
        config[key] = Settings(key, None)

    message_values = {
        'plugin_version': VERSION,
        'subl_version': sublime.version(),
        'subl_platform': sublime.platform(),
        'subl_arch': sublime.arch(),
        'subl_packages': sublime.packages_path(),
        'subl_installed_packages': sublime.installed_packages_path(),
        'config': config
    }
    get_logger().debug(message, message_values)


def Settings(name, default):  # flake8: noqa
    """Return value by name from user settings."""
    config = sublime.load_settings(common.USER_CONFIG_NAME)
    return config.get(name, default)


def is_debug():
    """Returns whether debug mode is enable or not."""
    return Settings('debug', False)


def get_logger():
    """Sets required log level and returns logger."""
    if is_debug():
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    return logger


def pep8_params():
    """Return params for the autopep8 module."""
    params = ['-d']  # args for preview

    # read settings
    for opt in ("ignore", "select", "max-line-length", "indent-size"):
        opt_value = Settings(opt, "")
        # remove white spaces as autopep8 does not trim them
        if opt in ("ignore", "select"):
            opt_value = ','.join(param.strip()
                                 for param in opt_value.split(','))
        params.append("--{0}={1}".format(opt, opt_value))

    if Settings("list-fixes", None):
        params.append("--list-fixes")

    for opt in ("aggressive",):
        opt_count = Settings(opt, 0)
        params.extend(["--" + opt] * opt_count)

    # use verbose==2 to catch non-fixed issues
    params.extend(["--" + "verbose"] * 2)

    # autopep8.parse_args requirea at least one positional argument
    params.append('fake-file')

    parsed_params = autopep8.parse_args(params)
    get_logger().debug('autopep8.params: %s', parsed_params)
    return parsed_params


class AutoPep8Command(sublime_plugin.TextCommand):

    def sel(self, skip_selected):
        region = self.view.sel()[0]
        # select all view if there is no selected region.
        if region.a == region.b or skip_selected:
            region = sublime.Region(0, self.view.size())

        return region, self.view.substr(region), self.view.encoding()

    def run(self, edit, preview=True, skip_selected=False):
        queue = common.Queue()
        region, source, encoding = self.sel(skip_selected)
        if not isinstance(source, unicode) and hasattr('decode'):
            source = source.decode(encoding)

        queue.put((source, self.view.file_name(), self.view, region, encoding))
        common.set_timeout(
            lambda: common.worker(queue, preview, pep8_params()),
            common.WORKER_START_TIMEOUT)

    def is_enabled(self, *args):
        view_syntax = self.view.settings().get('syntax')
        syntax_list = Settings('syntax_list', ["Python"])
        filename = os.path.basename(view_syntax)
        return os.path.splitext(filename)[0] in syntax_list

    def is_visible(self, *args):
        return True


class AutoPep8OutputCommand(sublime_plugin.TextCommand):

    def run(self, edit, text):
        self.view.insert(edit, 0, text)
        self.view.end_edit(edit)

    def is_visible(self, *args):
        return False


class AutoPep8ReplaceCommand(sublime_plugin.TextCommand):

    def run(self, edit, text, a, b):
        region = sublime.Region(int(a), int(b))
        remove_last_line = Settings('avoid_new_line_in_select_mode', False)
        if region.b - region.a < self.view.size() and remove_last_line:
            lines = text.split('\n')
            if not lines[-1]:
                text = '\n'.join(lines[:-1])
        self.view.replace(edit, region, text)

    def is_visible(self, *args):
        return False


class AutoPep8FileCommand(sublime_plugin.WindowCommand):

    def run(self, paths=None, preview=True):
        if not paths:
            return
        queue = common.Queue()

        for path in self.files(paths):
            with open(path, 'r') as fd:
                source = fd.read()

            encoding = common.get_pyencoding(source)
            if not isinstance(source, unicode) and hasattr(source, 'decode'):
                source = source.decode(encoding)

            queue.put((source, path, None, None, encoding))

        common.set_timeout(
            lambda: common.worker(queue, preview, pep8_params()),
            common.WORKER_START_TIMEOUT)

    def py_files_from_dir(self, path):
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                if filename.endswith('.py'):
                    yield os.path.join(dirpath, filename)

    def files(self, paths):
        for path in paths:
            if os.path.isfile(path) and path.endswith('.py'):
                yield path
                continue
            if os.path.isdir(path):
                for file_path in self.py_files_from_dir(path):
                    yield file_path

    def has_pyfiles(self, path, depth):
        for step in range(depth):
            depth_path = '*/' * step + '*.py'
            search_path = os.path.join(path, depth_path)
            try:
                _next(glob.iglob(search_path))
                return True
            except StopIteration:
                pass
        return False

    def check_paths(self, paths):
        if not paths:
            return False
        depth = Settings('file_menu_search_depth', common.DEFAULT_SEARCH_DEPTH)
        for path in paths:
            if os.path.isdir(path) and self.has_pyfiles(path, depth):
                return True
            elif os.path.isfile(path) and path.endswith('.py'):
                return True
        return False

    def is_enabled(self, *args, **kwd):
        return self.check_paths(kwd.get('paths'))

    def is_visible(self, *args, **kwd):
        return True


class AutoPep8Listener(sublime_plugin.EventListener):

    def on_pre_save_async(self, view):
        skip_format = view.settings().get(common.VIEW_SKIP_FORMAT, False)
        if not Settings('format_on_save', False) or skip_format:
            view.settings().erase(common.VIEW_SKIP_FORMAT)
            view.settings().erase(common.VIEW_AUTOSAVE)
            return
        view_syntax = view.settings().get('syntax')
        syntax_list = Settings('syntax_list', ["Python"])
        if os.path.splitext(os.path.basename(view_syntax))[0] in syntax_list:
            view.settings().set(common.VIEW_AUTOSAVE, True)
            view.run_command("auto_pep8",
                             {"preview": False, "skip_selected": True})

    def on_pre_save(self, view):
        if sublime.version() < '3000':
            return self.on_pre_save_async(view)


if sublime.version() < '3000':
    _PrintDebugInfo()
else:
    # timeout is necessary for sublime3
    # because user settings is not loaded during importing plugin
    sublime.set_timeout(_PrintDebugInfo, 1000)
