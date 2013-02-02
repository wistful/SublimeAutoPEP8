## coding=utf-8
import os
from collections import namedtuple
import re
import difflib
from StringIO import StringIO

import sublime
import sublime_plugin
import autopep8

plugin_path = os.path.split(os.path.abspath(__file__))[0]
pycoding = re.compile("coding[:=]\s*([-\w.]+)")
base_name = sublime.platform() == 'windows' and 'AutoPep8 (Windows).sublime-settings' or 'AutoPep8.sublime-settings'


class AutoPep8(object):
    """AutoPep8 Formatter"""

    def pep8_params(self):
        params = ['-d', '-vv']  # args for preview

        # read settings
        settings = sublime.load_settings(base_name)
        if settings.get("ignore"):
            params.append("--ignore=" + settings.get("ignore"))
        if settings.get("select"):
            params.append("--select=" + settings.get("select"))

        params.append('fake-arg')  # autopep8.parse_args raises exception without it
        return autopep8.parse_args(params)[0]

    def _get_diff(self, old, new, filename):
        diff = difflib.unified_diff(
            StringIO(old).readlines(), StringIO(new).readlines(),
            'original:' + filename,
            'fixed:' + filename)
        return ''.join(diff)

    def format_text(self, text):
        print "pep8_params: ", self.pep8_params()
        return autopep8.fix_string(text, self.pep8_params())

    def update_status_message(self, has_changes):
        if has_changes:
            sublime.status_message('AutoPEP8: Issues fixed')
        else:
            sublime.status_message('AutoPEP8: No issues to fix')

    def new_view(self, encoding, text):
        view = sublime.active_window().new_file()
        view.set_encoding(encoding)
        view.set_syntax_file("Packages/Diff/Diff.tmLanguage")
        edit = view.begin_edit()
        view.insert(edit, 0, text)
        view.end_edit(edit)
        view.set_scratch(1)


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
        self.cur_row, self.cur_col = self.view.rowcol(self.view.sel()[0].begin())
        # save viewport
        self.vector = self.view.text_to_layout(self.view.visible_region().begin())

    def restore_state(self):
        # restore cursor position
        sel = self.view.sel()
        if len(sel) == 1 and sel[0].a == sel[0].b:
            cur_point = self.view.text_point(self.cur_row, self.cur_col)
            sel.subtract(sel[0])
            sel.add(sublime.Region(cur_point, cur_point))

        # restore viewport
        self.view.set_viewport_position(
            (0.0, 0.0))  # magic, next line doesn't work without it
        self.view.set_viewport_position(self.vector)

    def run(self, edit, preview=True):
        preview_output = ''
        has_changes = False

        self.save_state()

        for region, substr in self.sel():
            out_data = self.format_text(substr)
            if not out_data or out_data == substr or (preview and len(out_data.split('\n')) < 3):
                continue

            has_changes = True
            if not preview:
                self.view.replace(edit, region, out_data)
            else:
                preview_output += self._get_diff(substr, out_data, self.view.file_name())

        self.update_status_message(has_changes)

        if has_changes and preview_output:
            self.new_view('utf-8', preview_output)
            return

        self.restore_state()

    def is_visible(self, *args):
        return self.view.settings().get('syntax') == "Packages/Python/Python.tmLanguage"


class AutoPep8FileCommand(sublime_plugin.WindowCommand, AutoPep8):

    file_names = None

    def run(self, paths=None, preview=True):
        if not paths:
            return

        has_changes = False
        preview_output = ''

        for path in self.file_names:
            in_data = open(path, 'r').read()
            out_data = self.format_text(in_data)
            sublime.status_message(
                "autopep8: formatting {path}".format(path=path))

            if not out_data or out_data == in_data or (preview and len(out_data.split('\n')) < 3):
                continue

            has_changes = True
            if not preview:
                open(path, 'w').write(out_data)
            else:
                preview_output += self._get_diff(in_data, out_data, path)

        self.update_status_message(has_changes)

        if has_changes and preview_output:
            self.new_view('utf-8', preview_output)

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

    def on_pre_save(self, view):
        if not view.settings().get('syntax') == "Packages/Python/Python.tmLanguage" \
                or not sublime.load_settings(base_name).get('format_on_save', False):
            return
        # save cursor position
        cur_row, cur_col = view.rowcol(view.sel()[0].begin())

        # save viewport
        vector = view.text_to_layout(view.visible_region().begin())

        region = sublime.Region(0, view.size())
        source = view.substr(region)
        out_data = self.format_text(source)
        if out_data != source:
            edit = view.begin_edit()
            view.replace(edit, region, out_data)
            view.end_edit(edit)

            # restore cursor position
            sel = view.sel()
            if len(sel) == 1 and sel[0].a == sel[0].b:
                cur_point = view.text_point(cur_row, cur_col)
                sel.subtract(sel[0])
                sel.add(sublime.Region(cur_point, cur_point))

            # restore viewport
            view.set_viewport_position(
                (0.0, 0.0))  # magic, next line doesn't work without it
            view.set_viewport_position(vector)
