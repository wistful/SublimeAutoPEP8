## coding=utf-8
import sublime
import sublime_plugin
import autopep8
import StringIO
import tempfile


class AutoPep8PreviewCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        output = StringIO.StringIO()
        params = [sublime.active_window().active_view().file_name(), "-d", "-v"]
        settings = sublime.load_settings('AutoPep8.sublime-settings')
        if settings.get("ignore"):
            params.append("--ignore=" + settings.get("ignore"))
        if settings.get("select"):
            params.append("--select=" + settings.get("select"))
        output.write(params)
        autopep8.main(params, output)
        output.read()
        sublime.active_window().new_file()
        sublime.active_window().active_view().insert(edit, 0, output.buf)


class AutoPep8Command(sublime_plugin.TextCommand):
    def run(self, edit):
        fd, tmp_path = tempfile.mkstemp()
        open(tmp_path, 'w').write(self.view.substr(sublime.Region(0, self.view.size())))
        params = [tmp_path, "-i", "-v"]
        settings = sublime.load_settings('AutoPep8.sublime-settings')
        if settings.get("ignore"):
            params.append("--ignore=" + settings.get("ignore"))
        if settings.get("select"):
            params.append("--select=" + settings.get("select"))
        autopep8.main(params)
        self.view.replace(edit, sublime.Region(0, self.view.size()), open(tmp_path, 'r').read())
