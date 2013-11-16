import os
from collections import namedtuple
import re
import difflib
import threading

from contextlib import contextmanager
import sys

import sublime

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

PATTERN = re.compile(r"Not fixing (?P<code>[A-Z]{1}\d+) on line (?P<line>\d+)")


@contextmanager
def custom_stderr(stderr):
    try:
        _stderr = sys.stderr
        sys.stderr = stderr
        yield
    finally:
        sys.stderr = _stderr


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
            with custom_stderr(args['stdoutput']):
                new = autopep8.fix_code(args['source'], args['pep8_params'])
            if args['preview']:
                new = difflib.unified_diff(
                    StringIO(args['source']).readlines(),
                    StringIO(new).readlines(),
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


def show_panel(text, has_change):
    settings = sublime.load_settings(BASE_NAME)

    if not settings.get('show_output_panel', False):
        return

    if not text and not settings.get('show_empty_panel', False):
        return

    if text:
        text = "SublimeAutoPep8: some issue(s) not fixed:\n" + text
    elif has_change and not text:
        text = "SublimeAutoPep8: all issues were fixed."
    elif not has_change and not text:
        text = "SublimeAutoPep8: no issue(s) to fix."

    view = sublime.active_window().get_output_panel("autopep8")
    view.set_read_only(False)
    view.run_command("auto_pep8_output", {"text": text})
    view.set_read_only(True)
    sublime.active_window().run_command(
        "show_panel", {"panel": "output.autopep8"})


def find_not_fixing(text, filepath):
    result = ""
    last_to_fix = text.rfind("issue(s) to fix")
    if last_to_fix > 0:
        for code, line in PATTERN.findall(text[last_to_fix:]):
            message = 'File "{0}", line {1}: not fixing {2}\n'.format(filepath,
                                                                      line,
                                                                      code)
            result += message
    return result


def handle_threads(threads, preview, preview_output='',
                   panel_output="", has_changes=False):
    sublime.status_message('AutoPEP8: formatting ...')
    new_threads = []
    for th in threads:
        if th.is_alive():
            new_threads.append(th)
            continue
        if th.result is None:
            continue
        for args in th.result:
            out_data = args['new']
            view = args.get('view')
            filename = args['filename']
            panel_output += find_not_fixing(args['stdoutput'].getvalue(),
                                            filename)
            if not out_data or out_data == args['source'] \
                    or (args['preview'] and len(out_data.split('\n')) < 3):
                continue

            has_changes = True
            # preview file or view
            if preview:
                preview_output += out_data
            # format view
            elif not preview and view:
                state = save_state(view)
                view.run_command("auto_pep8_replace", {"text": out_data,
                                                       "a": args["region"].a,
                                                       "b": args["region"].b})
                restore_state(view, state)
            # format file
            elif not preview and not view:
                open(filename, 'w').write(out_data)

    if len(new_threads) > 0:
        sublime.set_timeout(
            lambda: handle_threads(new_threads, preview, preview_output,
                                   panel_output, has_changes),
            100)
    else:
        message = 'AutoPep8: No issues to fixed.'
        if has_changes:
            message = 'AutoPep8: Issues fixed.'
        sublime.status_message(message)
        show_panel(panel_output, has_changes)

        if preview and preview_output:
            new_view('utf-8', preview_output)
        sublime.set_timeout(lambda: sublime.status_message(''), 3000)
