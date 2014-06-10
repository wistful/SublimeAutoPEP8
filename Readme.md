### Sublime Auto PEP8 Formatting

## About
Automatically formats Python code to conform to the PEP 8 style guide using [autopep8](https://github.com/hhatto/autopep8) module  
Supported ST2 and ST3

## Features
+ format / preview code according PEP8
+ format / preview selected text
+ format / preview all python modules in folder
+ side bar menu
+ formated code while saving

## Installing
The easiest way to install AutoPEP8 in through Package Control, which can be found at this site: [http://wbond.net/sublime_packages/package_control](http://wbond.net/sublime_packages/package_control)

Once you install Package Control, restart ST2/ST3 and bring up the Command Palette (`Command+Shift+P` on OS X, `Control+Shift+P` on Linux/Windows). Select "Package Control: Install Package", wait while Package Control fetches the latest package list, then select AutoPEP8 when the list appears.

## Per-project settings
```javascript
{
    "settings": {
        "sublimeautopep8": {
            "max-line-length": 79,
            "format_on_save": false,
            "show_output_panel": true,
            // show Format/Preview menu items only for views
            // with syntax from `syntax_list`
            // value is base filename of the .tmLanguage syntax files
            "syntax_list": ["Python"],

            // Behaviour for right click context menu (Format/Preview PEP8)
            // "always": menu appears always, even folder doesn't contain *.py files
            // "never":  menu never appears
            // "ifneed": menu appears only if path or childs contain *.py file
            "file_menu_behaviour": "ifneed",
            "file_menu_search_depth": 3  // max search depth, uses for 'ifneed' mode
        }
    }
}
```

## Using

+ **SideBar** - right click on the file(s) or folder(s)
+ **Active view** - right click on the view
+ **Selected text** - right click on the selected text
+ **On Save** - provide by settings: option `format_on_save`
+ **Command Palette** - bring up the Command Palette and select `PEP8: Format Code` or `PEP8: Preview Changes`
+ **Hotkeys** - `Command/Control + Shift + 8` to format code, `Command/Control + 8` to preview changes

