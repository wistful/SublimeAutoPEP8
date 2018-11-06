# coding=utf-8
"""SublimeAutoPEP8 plugin."""

import glob
import logging
import os
import sys

import sublime
import sublime_plugin

from AutoPEP8.sublimeautopep8lib import autopep8
from AutoPEP8.sublimeautopep8lib import common

VERSION = '2.1.0'

logger = logging.getLogger('SublimeAutoPEP8')


AUTOPEP8_OPTIONS = (
    'global-config',
    'ignore-local-config',
    'ignore',
    'select',
    'max-line-length',
    'indent-size',
    'exclude',
    'hang-closing',
)


def get_user_settings():
    """Return user settings related to the plugin."""
    return sublime.load_settings(common.USER_CONFIG_NAME)


def _setup_logger():
    """Setup logging for the plugin."""
    user_settings = get_user_settings()

    if not user_settings.get('debug', False):
        return

    logger = logging.getLogger('SublimeAutoPEP8')
    logger.handlers = []
    # Set level.
    logger.setLevel(logging.DEBUG)

    # Init handler.
    if user_settings.get('logfile', ''):
        handler = logging.FileHandler(user_settings.get('logfile', ''),
                                      encoding='utf8')
        logger.propagate = False
    else:
        logger.propagate = True
        handler = logging.StreamHandler(sys.stdout)

    # Set formatter.
    handler.setFormatter(
        logging.Formatter(
            '%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s'))
    logger.addHandler(handler)


def _print_debug_info():
    """Print debug info into the sublime console."""
    user_settings = get_user_settings()

    message = (
        '\n'
        'AutoPEP8:'
        '\n\tsublime:'
        '\n\t    version=%(subl_version)s'
        '\n\t    platform=%(subl_platform)s'
        '\n\t    arch=%(subl_arch)s'
        '\n\t    packages_path=%(subl_packages)s'
        '\n\t    installed_packages_path=%(subl_installed_packages)s'
        '\n\tplugin:'
        '\n\t    version=%(plugin_version)s'
        '\n\t    config: %(config)s'
        '\n'
    )

    plugin_keys = (
        'format_on_save',
        'syntax_list',
        'file_menu_search_depth',
        'avoid_new_line_in_select_mode',
        'debug',
        'logfile',
    )
    config = {
        key: user_settings.get(key, None)
        for key in AUTOPEP8_OPTIONS + plugin_keys
    }

    message_values = {
        'plugin_version': VERSION,
        'subl_version': sublime.version(),
        'subl_platform': sublime.platform(),
        'subl_arch': sublime.arch(),
        'subl_packages': sublime.packages_path(),
        'subl_installed_packages': sublime.installed_packages_path(),
        'config': config
    }
    logger.info(message, message_values)
    print_message = any([
        user_settings.get('logfile', ''),
        not user_settings.get('debug', False)
    ])
    if print_message:
        # Print config information to the console even if there is a logfile.
        print(message % message_values)


def pep8_params():
    """Return params for the autopep8 module."""
    user_settings = get_user_settings()
    env_vars = sublime.active_window().extract_variables()

    params = ['-d']  # args for preview
    # read settings
    for opt in AUTOPEP8_OPTIONS:
        opt_value = user_settings.get(opt, '')
        if opt_value == '' or opt_value is None:
            continue
        if opt_value and opt in ('exclude', 'global-config'):
            opt_value = sublime.expand_variables(opt_value, env_vars)

        if opt in ('exclude', 'global-config'):
            if opt_value:
                opt_value = sublime.expand_variables(opt_value, env_vars)
                params.append('--{0}={1}'.format(opt, opt_value))
        elif opt in ('ignore', 'select'):
            # remove white spaces as autopep8 does not trim them
            opt_value = ','.join(param.strip()
                                 for param in opt_value.split(','))
            params.append('--{0}={1}'.format(opt, opt_value))
        elif opt in ('ignore-local-config', 'hang-closing'):
            if opt_value:
                params.append('--{0}'.format(opt))
        else:
            params.append('--{0}={1}'.format(opt, opt_value))

    # use verbose==2 to catch non-fixed issues
    params.extend(['--verbose'] * 2)

    # autopep8.parse_args required at least one positional argument,
    # fake-file parent folder is used as location for local configs.
    params.append(sublime.expand_variables('${folder}/fake-file', env_vars))

    logger.info('pep8_params: %s', params)
    args = autopep8.parse_args(params, apply_config=True)
    return args


class AutoPep8Command(sublime_plugin.TextCommand):

    def get_selection(self, skip_selected):
        region = self.view.sel()[0]
        # select all view if there is no selected region.
        if region.a == region.b or skip_selected:
            region = sublime.Region(0, self.view.size())

        return region, self.view.substr(region), self.view.encoding()

    def run(self, edit, preview=True, skip_selected=False):
        queue = common.Queue()
        region, source, encoding = self.get_selection(skip_selected)
        if not isinstance(source, str) and hasattr('decode'):
            source = source.decode(encoding)

        queue.put((source, self.view.file_name(), self.view, region, encoding))
        sublime.set_timeout_async(
            lambda: common.worker(queue, preview, pep8_params()),
            common.WORKER_START_TIMEOUT)

    def is_enabled(self, *args):
        view_syntax = self.view.settings().get('syntax')
        syntax_list = get_user_settings().get('syntax_list', ["Python"])
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
        user_settings = get_user_settings()
        region = sublime.Region(int(a), int(b))
        remove_last_line = user_settings.get('avoid_new_line_in_select_mode',
                                             False)
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

        for path in self.files(paths, pep8_params().exclude):
            with open(path, 'r') as fd:
                source = fd.read()

            encoding = common.get_pyencoding(source)
            if not isinstance(source, str) and hasattr(source, 'decode'):
                source = source.decode(encoding)

            queue.put((source, path, None, None, encoding))

        sublime.set_timeout_async(
            lambda: common.worker(queue, preview, pep8_params()),
            common.WORKER_START_TIMEOUT)

    def files(self, paths, exclude=None):
        for path in autopep8.find_files(paths, recursive=True, exclude=exclude):
            if path.endswith('.py'):
                yield path

    def has_pyfiles(self, path, depth):
        for step in range(depth):
            depth_path = '*/' * step + '*.py'
            search_path = os.path.join(path, depth_path)
            try:
                next(glob.iglob(search_path))
                return True
            except StopIteration:
                pass
        return False

    def check_paths(self, paths):
        if not paths:
            return False
        depth = get_user_settings().get('file_menu_search_depth',
                                        common.DEFAULT_SEARCH_DEPTH)
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
        user_settings = get_user_settings()
        skip_format = view.settings().get(common.VIEW_SKIP_FORMAT, False)
        if not user_settings.get('format_on_save', False) or skip_format:
            view.settings().erase(common.VIEW_SKIP_FORMAT)
            view.settings().erase(common.VIEW_AUTOSAVE)
            return
        view_syntax = view.settings().get('syntax')
        syntax_list = user_settings.get('syntax_list', ['Python'])
        if os.path.splitext(os.path.basename(view_syntax))[0] in syntax_list:
            view.settings().set(common.VIEW_AUTOSAVE, True)
            view.run_command('auto_pep8',
                             {'preview': False, 'skip_selected': True})


def on_ready():
    """Run code once plugin is loaded."""
    _setup_logger()
    _print_debug_info()


# Timeout is required for ST3
# as plugin_host loading asynchronously
# and it is not possible to use sublime API at import time.
sublime.set_timeout_async(on_ready, 0)
