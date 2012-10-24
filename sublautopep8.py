## coding=utf-8
import sublime
import sublime_plugin
import tempfile
import subprocess
import os

plugin_path = os.path.split(os.path.abspath(__file__))[0]


class AutoPep8PreviewCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        settings = sublime.load_settings('AutoPep8.sublime-settings')
        file_path = sublime.active_window().active_view().file_name()
        params = [settings.get("python", "python"), settings.get("autopep8", "autopep8.py"), file_path, "-d", "-vv"]
        if settings.get("ignore"):
            params.append("--ignore=" + settings.get("ignore"))
        if settings.get("select"):
            params.append("--select=" + settings.get("select"))
        print 'autopep8:', params
        p = subprocess.Popen(params, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=plugin_path)
        encoding = sublime.active_window().active_view().encoding()
        diff = p.stdout.read().decode(encoding)
        for line in p.stderr:
            print line
        if len(diff) == 0:
            sublime.message_dialog("0 issues to fix")
        else:
            sublime.active_window().new_file()
            sublime.active_window().active_view().set_encoding(encoding)
            sublime.active_window().active_view().set_syntax_file("Packages/Diff/Diff.tmLanguage")
            sublime.active_window().active_view().insert(edit, 0, diff)


class AutoPep8Command(sublime_plugin.TextCommand):
    def run(self, edit):
        settings = sublime.load_settings('AutoPep8.sublime-settings')
        encoding = sublime.active_window().active_view().encoding()
        fd, tmp_path = tempfile.mkstemp()
        data = self.view.substr(sublime.Region(0, self.view.size()))
        open(tmp_path, 'w').write(data.encode(encoding))
        params = [settings.get("python", "python"), settings.get("autopep8", "autopep8.py"), tmp_path, "-i"]
        if settings.get("ignore"):
            params.append("--ignore=" + settings.get("ignore"))
        if settings.get("select"):
            params.append("--select=" + settings.get("select"))
        print 'autopep8:', params
        p = subprocess.Popen(params, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=plugin_path)
        for line in p.stderr:
            print line
        self.view.replace(edit, sublime.Region(0, self.view.size()), open(tmp_path, 'r').read().decode(encoding))
