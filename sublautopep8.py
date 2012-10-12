## coding=utf-8
import sublime
import sublime_plugin
import tempfile
import subprocess
import os


class AutoPep8PreviewCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        plugin_path = os.path.join(sublime.packages_path(), "AutoPEP8")
        file_path = sublime.active_window().active_view().file_name()
        params = ["python", "autopep8.py", file_path, "-d", "-vv"]
        settings = sublime.load_settings('AutoPep8.sublime-settings')
        if settings.get("ignore"):
            params.append("--ignore=" + settings.get("ignore"))
        if settings.get("select"):
            params.append("--select=" + settings.get("select"))

        p = subprocess.Popen(params, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=plugin_path)
        diff = p.stdout.read()
        for line in p.stderr:
            print line
        if len(diff) == 0:
            sublime.message_dialog("0 issues to fix")
        else:
            sublime.active_window().new_file()
            sublime.active_window().active_view().set_syntax_file("Packages/Diff/Diff.tmLanguage")
            sublime.active_window().active_view().insert(edit, 0, diff)


class AutoPep8Command(sublime_plugin.TextCommand):
    def run(self, edit):
        plugin_path = os.path.join(sublime.packages_path(), "AutoPEP8")
        fd, tmp_path = tempfile.mkstemp()
        open(tmp_path, 'w').write(self.view.substr(sublime.Region(0, self.view.size())))
        params = ["python", "autopep8.py", tmp_path, "-i"]
        settings = sublime.load_settings('AutoPep8.sublime-settings')
        if settings.get("ignore"):
            params.append("--ignore=" + settings.get("ignore"))
        if settings.get("select"):
            params.append("--select=" + settings.get("select"))

        p = subprocess.Popen(params, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=plugin_path)
        for line in p.stderr:
            print line
        self.view.replace(edit, sublime.Region(0, self.view.size()), open(tmp_path, 'r').read())
