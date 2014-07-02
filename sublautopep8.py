# coding=utf-8
import glob
import os

import sublime
import sublime_plugin

if sublime.version() < '3000':
    from sublimeautopep8lib import autopep8
    from sublimeautopep8lib import common
else:
    from AutoPEP8.sublimeautopep8lib import autopep8
    from AutoPEP8.sublimeautopep8lib import common


def _next(iter_obj):
    """Retrieve the next item from the iter_obj."""
    try:
        return iter_obj.next()
    except AttributeError:
        return iter_obj.__next__()


def Settings(name, default):
    """Return value by name from user settings."""
    view = sublime.active_window().active_view()
    project_config = view.settings().get('sublimeautopep8', {})
    global_config = sublime.load_settings(common.USER_CONFIG_NAME)
    return project_config.get(name, global_config.get(name, default))


def pep8_params():
    """Return params for the autopep8 module."""
    params = ['-d']  # args for preview

    # read settings
    for opt in ("ignore", "select", "max-line-length", "indent-size"):
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
    return autopep8.parse_args(params)


class AutoPep8Command(sublime_plugin.TextCommand):

    def sel(self, skip_selected):
        region = self.view.sel()[0]
        # select all view if there is no selected region.
        if region.a == region.b or skip_selected:
            region = sublime.Region(0, self.view.size())
        return region, self.view.substr(region)

    def run(self, edit, preview=True, skip_selected=False):
        queue = common.Queue()
        region, source = self.sel(skip_selected)

        queue.put((source, self.view.file_name(), self.view, region))
        common.set_timeout(
            lambda: common.worker(queue, preview, pep8_params()),
            common.WORKER_START_TIMEOUT)

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
        queue = common.Queue()

        for path in self.files(paths):
            with open(path, 'r') as fd:
                source = fd.read()
            queue.put((source, path, None, None))

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

    def is_visible(self, *args, **kwd):
        behaviour = Settings('file_menu_behaviour',
                             common.DEFAULT_FILE_MENU_BEHAVIOUR)
        if behaviour == 'always':
            return True
        elif behaviour == 'never':
            return False
        else:
            # ifneed behaviour
            return self.check_paths(kwd.get('paths'))


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
        return self.on_pre_save_async(view)
