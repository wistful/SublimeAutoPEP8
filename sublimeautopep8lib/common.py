from collections import namedtuple
from contextlib import contextmanager
import difflib
import os
import re
import sys

import sublime

if sublime.version() < '3000':
    from Queue import Queue  # NOQA
    from StringIO import StringIO

    from sublimeautopep8lib import autopep8

    PLUGIN_PATH = os.path.abspath(os.path.split(os.path.dirname(__file__))[0])
    sys.path.insert(0, os.path.join(PLUGIN_PATH, "packages_py2"))

else:
    from io import StringIO
    from queue import Queue  # NOQA

    from AutoPEP8.sublimeautopep8lib import autopep8

    PLUGIN_PATH = os.path.abspath(os.path.dirname(__file__))
    sys.path.insert(0, os.path.join(PLUGIN_PATH, "packages_py3"))


DEFAULT_FILE_MENU_BEHAVIOUR = 'ifneed'
DEFAULT_SEARCH_DEPTH = 3
PYCODING = re.compile("coding[:=]\s*([-\w.]+)")
VIEW_SKIP_FORMAT = 'autopep8_view_skip_format'
VIEW_AUTOSAVE = 'autopep8_view_autosave'

WORKER_TIMEOUT = 50 if sublime.version() < '3000' else 0
WORKER_START_TIMEOUT = 100
STATUS_MESSAGE_TIMEOUT = 3000

if sublime.platform() == 'windows':
    USER_CONFIG_NAME = 'AutoPep8 (Windows).sublime-settings'
else:
    USER_CONFIG_NAME = 'AutoPep8.sublime-settings'


ViewState = namedtuple('ViewState', ['row', 'col', 'vector'])

PATTERN = re.compile(r"Not fixing (?P<code>[A-Z]{1}\d+) on line (?P<line>\d+)")


@contextmanager
def custom_stderr(stderr=None):
    try:
        _stderr = sys.stderr
        sys.stderr = stderr or StringIO()
        yield sys.stderr
    finally:
        sys.stderr = _stderr


def set_timeout(func, delay):
    if sublime.version() < '3000':
        return sublime.set_timeout(func, delay)
    else:
        return sublime.set_timeout_async(func, delay)


def create_diff(source1, source2, filepath):
    result = difflib.unified_diff(
        StringIO(source1).readlines(),
        StringIO(source2).readlines(),
        'original:' + filepath,
        'fixed:' + filepath)

    # fix issue with join two last lines
    lines = [item for item in result]
    if len(lines) >= 4 and lines[-2][-1] != '\n':
        lines[-2] += '\n'

    return ''.join(lines) if len(lines) >= 3 else ''


def replace_text(view, region, text):
    state = save_state(view)
    view.run_command(
        "auto_pep8_replace", {"text": text, "a": region.a, "b": region.b})
    restore_state(view, state)


def show_result(result):
    diffs = []
    not_fixed = ""
    has_changes = False

    # merge diffs.
    for command_result in result:
        if 'diff' in command_result:
            diffs.append(command_result['diff'])
        not_fixed += command_result['not_fixed']
        has_changes = has_changes or command_result.get('has_changes')

    # show status message.
    message = 'AutoPep8: No issues to fix.'
    if has_changes:
        message = 'AutoPep8: Issues were fixed.'
    sublime.status_message(message)

    show_error_panel(not_fixed)

    # show diff.
    if diffs:
        new_view('utf-8', '\n'.join(diffs))

    set_timeout(lambda: sublime.status_message(''), STATUS_MESSAGE_TIMEOUT)


def format_source(formatted, filepath, view, region):
    if view:
        replace_text(view, region, formatted)
        if view.settings().get(VIEW_AUTOSAVE, False):
            # prevent double formatting.
            view.settings().set(VIEW_SKIP_FORMAT, True)
            view.run_command("save")
    else:
        with open(filepath, 'w') as fd:
            fd.write(formatted)


def worker(queue, preview, pep8_params, result=None):
    sublime.status_message('AutoPEP8: formatting ...')
    if queue.empty():
        return show_result(result)

    result = result or []
    command_result = {}
    source, filepath, view, region = queue.get()
    with custom_stderr() as stdoutput:
        # TODO(wistful): pass 'encoding' parameter to the 'fix_code' function.
        formatted = autopep8.fix_code(source, pep8_params)
        if preview:
            formatted = create_diff(source1=source, source2=formatted,
                                    filepath=filepath)

    command_result['not_fixed'] = find_not_fixed(stdoutput.getvalue(),
                                                 filepath)
    if formatted and formatted != source:
        if not preview:
            command_result['has_changes'] = True
            format_source(formatted, filepath, view, region)
        else:
            command_result['diff'] = formatted

    result.append(command_result)

    set_timeout(
        lambda: worker(queue, preview, pep8_params, result), WORKER_TIMEOUT)


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


def hide_error_panel():
    sublime.active_window().run_command(
        "hide_panel", {"panel": "output.autopep8"})


def show_error_panel(text):
    settings = sublime.load_settings(USER_CONFIG_NAME)
    has_errors = False
    if not (text and settings.get('show_output_panel', False)):
        text = "SublimeAutoPep8: There is no errors."
    else:
        text = "SublimeAutoPep8: some issue(s) not fixed:\n" + text
        has_errors = True

    view = sublime.active_window().get_output_panel("autopep8")
    view.set_read_only(False)
    view.run_command("auto_pep8_output", {"text": text})
    view.set_read_only(True)
    if has_errors:
        sublime.active_window().run_command(
            "show_panel", {"panel": "output.autopep8"})


def find_not_fixed(text, filepath):
    result = ""
    last_to_fix = text.rfind("issue(s) to fix")
    if last_to_fix > 0:
        for code, line in PATTERN.findall(text[last_to_fix:]):
            message = 'File "{0}", line {1}: not fixed {2}\n'
            result += message.format(filepath, line, code)
    return result
