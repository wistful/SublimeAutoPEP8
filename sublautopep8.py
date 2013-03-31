# coding=utf-8
import os
import sys
from collections import namedtuple
import re
import difflib

from Queue import Queue
import threading

import sublime
import sublime_plugin

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

try:
    import sublimeautopep8lib.autopep8 as autopep8
except ImportError:
    import AutoPEP8.sublimeautopep8lib.autopep8 as autopep8

plugin_path = os.path.split(os.path.abspath(__file__))[0]
pycoding = re.compile("coding[:=]\s*([-\w.]+)")
if sublime.platform() == 'windows':
    BASE_NAME = 'AutoPep8 (Windows).sublime-settings'
else:
    BASE_NAME = 'AutoPep8.sublime-settings'

ViewState = namedtuple('ViewState', ['row', 'col', 'vector'])


class AutoPep8Thread(threading.Thread):
    """docstring for AutoPep8Thread"""
    def __init__(self, queue):
        super(AutoPep8Thread, self).__init__()
        self.queue = queue
        self.result = []

    def run(self):
        while True:
            args = self.queue.get()
            if args is None:
                break
            new = autopep8.fix_string(args['source'], args['pep8_params'], args['stdoutput'])
            if args['preview']:
                new = difflib.unified_diff(
                    StringIO(args['source']).readlines(), StringIO(new).readlines(),
                    'original:' + args['filename'],
                    'fixed:' + args['filename'])
                
                # fix issue with join two last lines
                lines = [item for item in new]
                if len(lines) >= 4 and lines[-2][-1] != '\n':
                    lines[-2] += '\n'

                new = ''.join(lines)
            args['new'] = new
            self.result.append(args)


def save_state(view):
    # save cursor position
    row, col = view.rowcol(view.sel()[0].begin())
    # save viewport
    vector = view.text_to_layout(view.visible_region().begin())
    return ViewState(row, col, vector)


def restore_state(view, state):
    # restore cursor position
    sel = view.sel()
    if len(sel) == 1 and sel[0].a == sel[0].b:
        point = view.text_point(state.row, state.col)
        sel.subtract(sel[0])
        sel.add(sublime.Region(point, point))

    # restore viewport
    # magic, next line doesn't work without it
    view.set_viewport_position((0.0, 0.0))
    view.set_viewport_position(state.vector)


def new_view(encoding, text):
    view = sublime.active_window().new_file()
    view.set_encoding(encoding)
    view.set_syntax_file("Packages/Diff/Diff.tmLanguage")
    view.run_command("auto_pep8_output", {"text": text})
    view.set_scratch(True)


def handle_threads(threads, preview, preview_output='', panel_output=None):
    print("hello from handle_threads: ", threads)
    new_threads = []
    panel_output = panel_output or {}
    for th in threads:
        if th.is_alive():
            new_threads.append(th)
            continue
        if th.result is None:
            continue
        for args in th.result:
            # out_data = self.format_text(substr, stdoutput)s
            out_data = args['new']
            if not out_data or out_data == args['source'] or (args['preview'] and len(out_data.split('\n')) < 3):
                continue
            filename = args['filename']
            panel_output[filename] = args['stdoutput'].getvalue()
            if not args['preview']:
                state = save_state(args['view'])
                args['view'].replace(args['edit'], args['region'], out_data)
                restore_state(args['view'], state)
            else:
                preview_output += args['new']


    if len(new_threads) > 0:
        sublime.set_timeout(lambda: handle_threads(new_threads, preview, preview_output, panel_output), 100)
    elif preview:
        new_view('utf-8', preview_output)



class AutoPep8(object):

    """AutoPep8 Formatter"""

    def pep8_params(self):
        params = ['-d']  # args for preview

        # read settings
        settings = sublime.load_settings(BASE_NAME)
        for opt in ("ignore", "select", "max-line-length"):
            params.append("--{0}={1}".format(opt, settings.get(opt, "")))

        if settings.get("list-fixes", None):
            params.append("--{0}={1}".format(opt, settings.get(opt)))

        for opt in ("verbose", "aggressive"):
            opt_count = settings.get(opt, 0)
            params.extend(["--" + opt] * opt_count)

        # autopep8.parse_args raises exception without it
        params.append('fake-arg')
        return autopep8.parse_args(params)[0]

    def std_message(self, std):
        return '{0}'.format(std.getvalue())

    def _get_diff(self, old, new, filename):
        diff = difflib.unified_diff(
            StringIO(old).readlines(), StringIO(new).readlines(),
            'original:' + filename,
            'fixed:' + filename)
        return ''.join(diff)

    def format_text(self, text, stdoutput):
        pep8_params = self.pep8_params()
        if pep8_params.verbose > 4:
            print("pep8 options: {0}".format(pep8_params))

        return autopep8.fix_string(text, pep8_params, stdoutput)

    def update_status_message(self, has_changes):
        if has_changes:
            sublime.status_message('AutoPEP8: Issues fixed')
        else:
            sublime.status_message('AutoPEP8: No issues to fix')

    def new_view(self, encoding, text):
        view = sublime.active_window().new_file()
        view.set_encoding(encoding)
        view.set_syntax_file("Packages/Diff/Diff.tmLanguage")
        view.run_command("auto_pep8_output", {"text": text})
        view.set_scratch(True)

    def panel(self, text):
        if not sublime.load_settings(BASE_NAME).get('show_output_panel', False):
            print(text)
            return
        view = sublime.active_window().get_output_panel("autopep8")
        view.set_read_only(False)
        view.run_command("auto_pep8_output", {"text": text})
        view.set_read_only(True)
        sublime.active_window().run_command(
            "show_panel", {"panel": "output.autopep8"})


class AutoPep8Command(sublime_plugin.TextCommand, AutoPep8):

    def sel(self):
        sels = self.view.sel()
        if len(sels) == 1 and sels[0].a == sels[0].b:
            sels = [namedtuple('sel', ['a', 'b'])(0, self.view.size())]

        for sel in sels:
            region = sublime.Region(sel.a, sel.b)
            yield region, self.view.substr(region)

    def save_state(self):
        # save cursor position
        self.cur_row, self.cur_col = self.view.rowcol(
            self.view.sel()[0].begin())
        # save viewport
        self.vector = self.view.text_to_layout(
            self.view.visible_region().begin())

    def restore_state(self):
        # restore cursor position
        sel = self.view.sel()
        if len(sel) == 1 and sel[0].a == sel[0].b:
            cur_point = self.view.text_point(self.cur_row, self.cur_col)
            sel.subtract(sel[0])
            sel.add(sublime.Region(cur_point, cur_point))

        # restore viewport
        # magic, next line doesn't work without it
        self.view.set_viewport_position((0.0, 0.0))
        self.view.set_viewport_position(self.vector)

    def run(self, edit, preview=True):
        std_message = preview_output = ''
        has_changes = False
        pep8_params = self.pep8_params()
        threads = []

        self.save_state()

        queue = Queue()
        stdoutput = StringIO()
        for region, substr in self.sel():
            args = {'pep8_params': pep8_params, 'view': self.view, 
                    'filename': self.view.file_name(),
                    'source': substr, 'preview': preview, 'stdoutput': stdoutput,
                    'edit': edit, 'region': region}
            queue.put(args)
            # th = threading.Thread(target=format_text, args=(queue, ))
            th = AutoPep8Thread(queue)
            th.start()
            threads.append(th)
            continue

            out_data = self.format_text(substr, stdoutput)
            if not out_data or out_data == substr or (preview and len(out_data.split('\n')) < 3):
                continue

            has_changes = True
            if not preview:
                self.view.replace(edit, region, out_data)
            else:
                preview_output += self._get_diff(
                    substr, out_data, self.view.file_name())

        for _ in range(len(threads)):
            queue.put(None)
        if len(threads) > 0:
            sublime.set_timeout(lambda: handle_threads(threads, preview), 100)
        return
        std_message = self.std_message(stdoutput)
        self.update_status_message(has_changes)

        self.panel(std_message)
        if has_changes and preview_output:
            self.new_view('utf-8', preview_output)
            return

        self.restore_state()

    def is_visible(self, *args):
        view_syntax = self.view.settings().get('syntax')
        syntax_list = sublime.load_settings(BASE_NAME).get('syntax_list', ["Python"])
        return os.path.splitext(os.path.basename(view_syntax))[0] in syntax_list


class AutoPep8OutputCommand(sublime_plugin.TextCommand, AutoPep8):

    def run(self, edit, text):
        self.view.insert(edit, 0, text)
        self.view.end_edit(edit)

    def is_visible(self, *args):
        return False


class AutoPep8FileCommand(sublime_plugin.WindowCommand, AutoPep8):

    file_names = None

    def run(self, paths=None, preview=True):
        if not paths:
            return

        has_changes = False
        preview_output = std_message = ''

        for path in self.file_names:
            print(path)

        stdoutput = StringIO()
        for path in self.file_names:
            in_data = open(path, 'r').read()
            out_data = self.format_text(in_data, stdoutput)
            sublime.status_message(
                "autopep8: formatting {path}".format(path=path))

            if not out_data \
                or out_data == in_data \
                    or (preview and len(out_data.split('\n')) < 3):
                continue

            has_changes = True
            if not preview:
                open(path, 'w').write(out_data)
            else:
                preview_output += self._get_diff(in_data, out_data, path)
            std_message = "{0}\n{1}:\n{2}".format(std_message,
                                                  path,
                                                  self.std_message(stdoutput))
            stdoutput.truncate(0)

        self.update_status_message(has_changes)

        if has_changes and preview_output:
            self.new_view('utf-8', preview_output)
            self.panel(std_message)

    def files(self, path):
        result = []
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                if filename.endswith('py'):
                    result.append(os.path.join(dirpath, filename))
        return result

    def is_visible(self, *args, **kwd):
        paths = kwd.get('paths')
        if not paths:
            return False
        files = []
        for path in paths:
            if os.path.isdir(path):
                files.extend(self.files(path))
            if os.path.isfile(path) and path.endswith('py'):
                files.append(path)
        if not (files and filter(lambda item: item.endswith('py'), files)):
            return False
        self.file_names = files
        return True


class AutoPep8Listener(sublime_plugin.EventListener, AutoPep8):

    def on_pre_save_async(self, view):
        if not view.settings().get('syntax') == "Packages/Python/Python.tmLanguage" \
                or not sublime.load_settings(BASE_NAME).get('format_on_save', False):
            return

        view.run_command("auto_pep8", {"preview": False})

    def on_pre_save(self, view):
        if sublime.version() < '3000':
            self.on_pre_save_async(view)
