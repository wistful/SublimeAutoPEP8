# coding=utf-8
import os
import sys
from collections import namedtuple
import re
import glob
try:
    from Queue import Queue
except ImportError:
    from queue import Queue

import sublime
import sublime_plugin

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO


try:
    sys.path.insert(0,
                    os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                 "packages_py2")))
    import sublimeautopep8lib.autopep8 as autopep8
    from sublimeautopep8lib.common import AutoPep8Thread, handle_threads
except ImportError:
    sys.path.insert(0,
                    os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                 "packages_py3")))
    import AutoPEP8.sublimeautopep8lib.autopep8 as autopep8
    from AutoPEP8.sublimeautopep8lib.common import AutoPep8Thread
    from AutoPEP8.sublimeautopep8lib.common import handle_threads


plugin_path = os.path.split(os.path.abspath(__file__))[0]
pycoding = re.compile("coding[:=]\s*([-\w.]+)")
if sublime.platform() == 'windows':
    BASE_NAME = 'AutoPep8 (Windows).sublime-settings'
else:
    BASE_NAME = 'AutoPep8.sublime-settings'

DEFAULT_SEARCH_DEPTH = 3
DEFAULT_FILE_MENU_BEHAVIOUR = 'ifneed'


def _next(iter_obj):
    try:
        return iter_obj.next()
    except AttributeError:
        return iter_obj.__next__()


def Settings(name, default):
    view = sublime.active_window().active_view()
    project_config = view.settings().get('sublimeautopep8', {})
    global_config = sublime.load_settings(BASE_NAME)
    return project_config.get(name, global_config.get(name, default))


def pep8_params():
    params = ['-d']  # args for preview

    # read settings
    for opt in ("ignore", "select", "max-line-length"):
        params.append("--{0}={1}".format(opt, Settings(opt, "")))

    if Settings("list-fixes", None):
        params.append("--{0}={1}".format(opt, Settings(opt)))

    for opt in ("aggressive",):
        opt_count = Settings(opt, 0)
        params.extend(["--" + opt] * opt_count)

    # use verbose==2 to catch non-fixed issues
    params.extend(["--" + "verbose"] * 2)

    # autopep8.parse_args requirea at least one positional argument
    params.append('fake-file')
    return autopep8.parse_args(params)[0]


class AutoPep8Command(sublime_plugin.TextCommand):

    def sel(self):
        sels = self.view.sel()
        if len(sels) == 1 and sels[0].a == sels[0].b:
            sels = [namedtuple('sel', ['a', 'b'])(0, self.view.size())]

        for sel in sels:
            region = sublime.Region(sel.a, sel.b)
            yield region, self.view.substr(region)

    def run(self, edit, preview=True):
        max_threads = Settings('max-threads', 5)
        threads = []
        queue = Queue()
        stdoutput = StringIO()

        for region, substr in self.sel():
            args = {
                'pep8_params': pep8_params(), 'view': self.view,
                'filename': self.view.file_name(),
                'source': substr,
                'preview': preview,
                'stdoutput': stdoutput,
                'edit': edit, 'region': region
            }
            queue.put(args)
            if len(threads) < max_threads:
                th = AutoPep8Thread(queue)
                th.start()
                threads.append(th)

        for _ in range(len(threads)):
            queue.put(None)
        if len(threads) > 0:
            sublime.set_timeout(lambda: handle_threads(threads, preview), 100)

    def is_visible(self, *args):
        view_syntax = self.view.settings().get('syntax')
        syntax_list = Settings('syntax_list', ["Python"])
        filename = os.path.basename(view_syntax)
        return os.path.splitext(filename)[0] in syntax_list


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
        max_threads = Settings('max-threads', 5)
        threads = []
        queue = Queue()

        for path in self.files(paths):
            stdoutput = StringIO()
            in_data = open(path, 'r').read()

            args = {
                'pep8_params': pep8_params(), 'filename': path,
                'source': in_data, 'preview': preview,
                'stdoutput': stdoutput
            }

            queue.put(args)
            if len(threads) < max_threads:
                th = AutoPep8Thread(queue)
                th.start()
                threads.append(th)

        for _ in range(len(threads)):
            queue.put(None)
        if len(threads) > 0:
            sublime.set_timeout(lambda: handle_threads(threads, preview), 100)

    def files(self, paths):
        for path in paths:
            if os.path.isfile(path) and path.endswith('.py'):
                yield path
                continue
            if os.path.isdir(path):
                for dirpath, dirnames, filenames in os.walk(path):
                    for filename in filenames:
                        if filename.endswith('.py'):
                            yield os.path.join(dirpath, filename)

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
        depth = Settings('file_menu_search_depth', DEFAULT_SEARCH_DEPTH)
        for path in paths:
            if os.path.isdir(path) and self.has_pyfiles(path, depth):
                return True
            elif os.path.isfile(path) and path.endswith('.py'):
                return True
        return False

    def is_visible(self, *args, **kwd):
        behaviour = Settings('file_menu_behaviour',
                             DEFAULT_FILE_MENU_BEHAVIOUR)
        if behaviour == 'always':
            return True
        elif behaviour == 'never':
            return False
        else:
            # ifneed behaviour
            return self.check_paths(kwd.get('paths'))


class AutoPep8Listener(sublime_plugin.EventListener):

    def on_pre_save_async(self, view):
        if not Settings('format_on_save', False):
            return
        view_syntax = view.settings().get('syntax')
        syntax_list = Settings('syntax_list', ["Python"])
        if os.path.splitext(os.path.basename(view_syntax))[0] in syntax_list:
            view.run_command("auto_pep8", {"preview": False})

    def on_pre_save(self, view):
        if not Settings('format_on_save', False):
            return
        if sublime.version() < '3000':
            self.on_pre_save_async(view)
