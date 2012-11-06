## coding=utf-8
import sublime
import sublime_plugin
import tempfile
import subprocess
import os
from collections import namedtuple
import re
import locale

plugin_path = os.path.split(os.path.abspath(__file__))[0]
pycoding = re.compile("coding[:=]\s*([-\w.]+)")
base_name = sublime.platform() == 'windows' and 'AutoPep8 (Windows).sublime-settings' or 'AutoPep8.sublime-settings'


class AutoPep8(object):
    """AutoPep8 Formatter"""

    def pep8_params(self, preview=True):
        params = ['-d', '-vv']  # args for preview
        if not preview:
            params = ['-i']  # args for format

        # read settings
        settings = sublime.load_settings(base_name)
        if settings.get("ignore"):
            params.append("--ignore=" + settings.get("ignore"))
        if settings.get("select"):
            params.append("--select=" + settings.get("select"))
        return params

    def format_file(self, in_file, out_file, preview=True, encoding='utf-8'):
        """format/diff code from in_file using autopep8
        and save output in out_file"""

             # in_file doesn't change
        open(out_file, 'w').write(open(in_file, 'r').read())
        settings = sublime.load_settings(base_name)
        params = [settings.get("python", "python"), settings.get(
            "autopep8", "autopep8.py"), out_file]
        params.extend(self.pep8_params(preview))
        print 'autopep8:', repr(params)
        p = subprocess.Popen(params, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, cwd=plugin_path)
        if preview:
            # write diff to out_file
            l_encoding = locale.getpreferredencoding()
            output = p.stdout.read().decode(l_encoding)
            output = output.replace(out_file, in_file)
            open(out_file, 'w').write(output.encode('utf-8'))
        for line in p.stderr:
            print line

    def format_text(self, text, encoding, preview=True):
        fd1, in_path = tempfile.mkstemp(text=True)
        fd2, out_path = tempfile.mkstemp(text=True)
        fd_in, fd_out = os.fdopen(fd1, 'w'), os.fdopen(fd2)
        open(in_path, 'w').write(text.encode(encoding))
        self.format_file(in_path, out_path, preview, encoding)
        out_data = fd_out.read().decode(encoding)
        os.remove(in_path)
        os.remove(out_path)
        return out_data


class AutoPep8Command(sublime_plugin.TextCommand, AutoPep8):

    def sel(self):
        sels = self.view.sel()
        if len(sels) == 1 and sels[0].a == sels[0].b:
            sels = [namedtuple('sel', ['a', 'b'])(0, self.view.size())]

        for sel in sels:
            region = sublime.Region(sel.a, sel.b)
            yield region, self.view.substr(region)

    def get_encoding(self):
        encoding = self.view.encoding()
        if encoding and encoding != 'Undefined':
            return encoding
        try:
            return pycoding.search(self.view.substr(sublime.Region(0, self.view.size()))).group(1)
        except (AttributeError, IndexError):
            return sublime.load_settings('Preferences.sublime-settings').get('default_encoding', 'utf-8')

    def new_view(self, edit, encoding, text):
        view = sublime.active_window().new_file()
        view.set_encoding(encoding)
        view.set_syntax_file("Packages/Diff/Diff.tmLanguage")
        view.insert(edit, 0, text)
        view.set_scratch(1)

    def run(self, edit, preview=True):
        encoding = self.get_encoding()
        preview_output = ''

        has_changes = False

        # save cursor position
        cur_row, cur_col = self.view.rowcol(self.view.sel()[0].begin())

        # save viewport
        vector = self.view.text_to_layout(self.view.visible_region().begin())

        for region, substr in self.sel():
            out_data = self.format_text(substr, encoding, preview)
            if not out_data or out_data == substr or (preview and len(out_data.split('\n')) < 6):
                continue

            has_changes = True
            if not preview:
                self.view.replace(edit, region, out_data)
            else:
                preview_output += out_data

        if has_changes and preview_output:
            self.new_view(edit, 'utf-8', preview_output)

        # restore cursor position
        sel = self.view.sel()
        if len(sel) == 1 and sel[0].a == sel[0].b:
            cur_point = self.view.text_point(cur_row, cur_col)
            sel.subtract(sel[0])
            sel.add(sublime.Region(cur_point, cur_point))

        # restore viewport
        self.view.set_viewport_position(
            (0.0, 0.0))  # magic, next line doesn't work without it
        self.view.set_viewport_position(vector)

        if not has_changes:
            sublime.message_dialog("0 issues to fix")

    def is_visible(self, *args):
        return self.view.settings().get('syntax') == "Packages/Python/Python.tmLanguage"


class AutoPep8FileCommand(sublime_plugin.WindowCommand, AutoPep8):

    file_names = None
    default_encoding = 'utf-8'

    def get_encoding(self, path):
        try:
            with open(path, 'r') as f:
                file_head = f.readline() + f.readline()
            return pycoding.search(file_head).group(1)
        except (AttributeError, IndexError, IOError):
            return sublime.load_settings('Preferences.sublime-settings').get('default_encoding', 'utf-8')

    def new_view(self, encoding, text):
        view = sublime.active_window().new_file()
        view.set_encoding(encoding)
        view.set_syntax_file("Packages/Diff/Diff.tmLanguage")
        edit = view.begin_edit()
        view.insert(edit, 0, text)
        view.end_edit(edit)
        view.set_scratch(1)

    def run(self, paths=None, preview=True):
        if not paths:
            return

        has_changes = False
        preview_output = ''

        for path in self.file_names:
            encoding = self.get_encoding(path)
            fd2, out_path = tempfile.mkstemp(text=True)
            sublime.status_message(
                "autopep8: formatting {path}".format(path=path))
            self.format_file(
                path, out_path, preview=preview, encoding=encoding)
            in_data = open(path).read()
            out_data = open(out_path, 'r').read()
            os.remove(out_path)
            if not out_data or out_data == in_data or (preview and len(out_data.split('\n')) < 6):
                continue

            has_changes = True
            if not preview:
                open(path, 'w').write(out_data)
            else:
                preview_output += out_data.decode('utf-8')

        sublime.status_message("")
        if has_changes and preview_output:
            self.new_view('utf-8', preview_output)
        if not has_changes:
            sublime.message_dialog("0 issues to fix")

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

    def get_encoding(self, view):
        encoding = view.encoding()
        if encoding and encoding != 'Undefined':
            return encoding
        try:
            return pycoding.search(view.substr(sublime.Region(0, view.size()))).group(1)
        except (AttributeError, IndexError):
            return sublime.load_settings('Preferences.sublime-settings').get('default_encoding', 'utf-8')

    def on_pre_save(self, view):
        if not view.settings().get('syntax') == "Packages/Python/Python.tmLanguage" \
                or not sublime.load_settings(base_name).get('format_on_save', False):
            return

        # save cursor position
        cur_row, cur_col = view.rowcol(view.sel()[0].begin())

        # save viewport
        vector = view.text_to_layout(view.visible_region().begin())

        encoding = self.get_encoding(view)
        region = sublime.Region(0, view.size())
        source = view.substr(region)
        out_data = self.format_text(source, encoding, preview=False)
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
