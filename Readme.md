### Sublime Auto PEP8 Formatting

## About
Automatically formats Python code to conform to the PEP 8 style guide using [autopep8](https://github.com/hhatto/autopep8) library.

**Supports ST3 only**.

## Features
+ format / preview code according PEP8
+ format / preview selected text
+ format / preview all python modules in folder
+ side bar menu
+ format code while saving

## Installing
The easiest way to install AutoPEP8_2020 in through Package Control,
which can be found at this site: [http://wbond.net/sublime_packages/package_control](http://wbond.net/sublime_packages/package_control).

Once you install Package Control, restart ST3 and bring up the Command Palette (`Command+Shift+P` on OS X, `Control+Shift+P` on Linux/Windows). Select "Package Control: Install Package", wait while Package Control fetches the latest package list, then select AutoPEP8_2020 when the list appears.

## Pep8(pycodestyle) configuration
The extenstion supports both `--global-config` and `--ignore-local-config` options from the [autopep8](https://github.com/hhatto/autopep8).


## Settings
```javascript
{

    "max-line-length": 79,

    // Do not fix these errors / warnings(e.g. E4, W)
    "ignore": "",

    // Select errors / warnings(e.g. E4, W)
    "select": "",

    // Number of spaces per indent level
    "indent-size": 4,

    // Don't look for and apply local config files;
    // if false, defaults are updated with any config files in the project's root directory.
    "ignore-local-config": false,

    // Path to a global pep8 config file;
    // if this file doesnot exist then this is ignored.
    "global-config": "",

    // Hang closing bracket instead of matching indentation of opening bracket's line.
    "hang-closing": false,

    // Specifies whether or not format files once they saved.
    "format_on_save": false,

    // If true - open new output panel with format/preview results.
    "show_output_panel": false,

    // Format/Preview menu items only appear for views
    // with syntax from `syntax_list`
    // value is base filename of the .tmLanguage syntax files
    "syntax_list": ["Python"],

    // The value shows how deep the plugin should look for *.py files
    // before disabling "Preview" and "Format" items in the Side Bar "AutoPep8" Context Menu.
    "file_menu_search_depth": 3, // max depth to search python files

    // If value is false(default)
    // then formatter doesn't treat absence of bottom empty line as an error
    // and doesn't try to fix it.
    "avoid_new_line_in_select_mode": false,

    // For debug purporse only.
    "debug": false,
    "logfile": "/tmp/sublimeautopep8.log"  // File to store debug messages.
}
```

## Using

+ **SideBar** - right click on the file(s) or folder(s)
+ **Active view** - right click on the view
+ **Selected text** - right click on the selected text
+ **On Save** - provide by settings: option `format_on_save`
+ **Command Palette** - bring up the Command Palette and select `PEP8: Format Code` or `PEP8: Preview Changes`
+ **Hotkeys** - `Command/Control + Shift + l` to format code, `Command/Control + 8` to preview changes
