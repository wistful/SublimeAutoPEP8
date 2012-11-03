## coding=utf-8
import sublime
import sublime_plugin
import tempfile
import subprocess
import os
from collections import namedtuple

plugin_path = os.path.split(os.path.abspath(__file__))[0]


class AutoPep8(object):
    """AutoPep8 Formatter"""

    def pep8_params(self, preview=True):
        params = ['-d', '-vv']  # args for preview
        if not preview:
            params = ['-i']  # args for format

        # read settings
        settings = sublime.load_settings('AutoPep8.sublime-settings')
        if settings.get("ignore"):
            params.append("--ignore=" + settings.get("ignore"))
        if settings.get("select"):
            params.append("--select=" + settings.get("select"))
        return params

    def format(self, in_file, out_file, preview=True):
        """format/diff code from in_file using autopep8
        and save output in out_file"""
        open(out_file, 'w').write(open(in_file, 'r').read())
             # in_file doesn't change
        settings = sublime.load_settings('AutoPep8.sublime-settings')
        params = [settings.get("python", "python"), settings.get(
            "autopep8", "autopep8.py"), out_file]
        params.extend(self.pep8_params(preview))
        print 'autopep8:', repr(params)
        p = subprocess.Popen(params, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, cwd=plugin_path)
        p.wait()  # waiting while autpep8 finish
        if preview:
            # write diff to out_file
            open(out_file, 'w').write(p.stdout.read())
        for line in p.stderr:
            print line


class AutoPep8Command(sublime_plugin.TextCommand, AutoPep8):

    def sel(self):
        sels = sublime.active_window().active_view().sel()
        if len(sels) == 1 and sels[0].a == sels[0].b:
            sels = [namedtuple('sel', ['a', 'b'])(0, self.view.size())]

        for sel in sels:
            region = sublime.Region(sel.a, sel.b)
            yield region, sublime.active_window().active_view().substr(region)

    def new_view(self, edit, encoding, text):
        view = sublime.active_window().new_file()
        view.set_encoding(encoding)
        view.set_syntax_file("Packages/Diff/Diff.tmLanguage")
        view.insert(edit, 0, text)
        view.set_scratch(1)

    def run(self, edit, preview=True):
        encoding = sublime.active_window().active_view().encoding()
        if encoding == 'Undefined':
            encoding = sublime.load_settings('Preferences.sublime-settings').get('default_encoding', 'utf-8')
        preview_output = ''
        has_changes = False

        for region, substr in self.sel():
            fd1, in_path = tempfile.mkstemp(text=True)
            fd2, out_path = tempfile.mkstemp(text=True)
            fd_in, fd_out = os.fdopen(fd1, 'w+'), os.fdopen(fd2)
            fd_in.write(substr) and fd_in.flush()
            self.format(in_path, out_path, preview)
            out_data = fd_out.read().decode(encoding)
            if not out_data or out_data == substr or (preview and len(out_data.split('\n')) < 6):
                continue

            has_changes = True
            if not preview:
                self.view.replace(edit, region, out_data)
            else:
                preview_output += out_data

        if has_changes and preview_output:
            self.new_view(edit, encoding, preview_output)

        if not has_changes:
            sublime.message_dialog("0 issues to fix")


class AutoPep8FileCommand(sublime_plugin.WindowCommand, AutoPep8):

    file_names = None

    def run(self, paths=None):
        if not paths:
            return

        has_changes = False

        for path in self.file_names:
            fd2, out_path = tempfile.mkstemp(text=True)
            sublime.status_message("autopep8: formatting {path}".format(path=path))
            self.format(path, out_path, preview=False)
            in_data = open(path).read()
            out_data = open(out_path).read()
            if in_data != out_data:
                has_changes = True
                open(path, 'w').write(out_data)
        sublime.status_message("")
        if not has_changes:
            sublime.message_dialog("0 issues to fix")

    def files(self, path):
        result = []
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                if filename.endswith('py'):
                    result.append(os.path.join(dirpath, filename))
        return result

    def is_visible(self, paths=None):
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
