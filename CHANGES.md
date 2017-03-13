# Changelog

## master branch

## 0.5.5

  - fix bug if no return / yield is present

## 0.5.4

  - support yield statement as alternative to return
  - keep types from appearing for *varargs and **kwargs parameters

## 0.5.0

  - function parameters and return types now update to stay in sync with function annotations
  - definition parsing is now ast-less

## 0.4.0

# New Features:
  - Convert single docstrings or whole modules from one style to another with one command. See the `AutoDocstring: Convert...` and `AutoDocstring: Convert All...` commands.
  - Pull parameter and return type information from Python 3 annotations. For now, return types will only be filled for new docstrings, and left unchanged on updates.
  - Settings can be in a JSON hash (dictionary) called "AutoDocstring" in a project-settings file. Project settings will override package settings.

# New Settings:
  - `keep_previous` *(default=false)*: If true, then always append the existing docstring to the newly updated docstring. Could be useful for *processing legacy code*.

# Bugfixes:
  - This plugin now ships with the MagicPython grammar, so return annotations don't completely break this plugin since we rely on syntax highlighting, and the default ST3 grammar doesn't support return annotations. This plugin always switches to MagicPython, runs, then switches back, so the end user shoun't even know the switch happened.
  - Lots of bugs with newlines and indentation
  - "Parameters" sections are now more flexable and support blocks of arbitrary text
  - "Returns" sections are now formatted like Parameters

## 0.3.2

  - Add `default_description`, `default_summary`, and `default_type` settings per [Issue #2](https://github.com/KristoforMaynard/SublimeAutoDocstring/issues/2)
  - Add `start_with_newline` setting for new docstrings per [Issue #4](https://github.com/KristoforMaynard/SublimeAutoDocstring/issues/4)
  - Add `default_return_names` for numpy style

## 0.3.0

  - Inspects class / module attributes and inserts a stub for each
  - Discovers what exceptions are raised in a function and inserts a stub for each
  - add settings for suppressing autodetection

## 0.2.6

  - add `optional_tag` setting so users can keep ", optional" from showing up by default
  - support multiple parameters with the same description for numpy style
  - stop Returns sections from being automatically added to classes and __init__ methods

## 0.2.5
  Features:
    - add template Returns with new docstrings

## 0.2.4
  - fix indentations on module docstrings

## 0.2.3
  - give the user some feedback in the status bar

## 0.2.2
  - fix parsing multi-line function definitions

## 0.2.1
  - fix misspelling

## 0.2.0

Features:
  - add Numpy docstring style
  - let sections preserve their existing order (configurable via the template_order setting)
  - can parse any valid function declaration and auto-discovers kwarg types

Bugfixes:
  - indentation bug on module level functions

## 0.1.0

Features:
  - Google docstring style
  - Fill / Update Args with actual parameters
