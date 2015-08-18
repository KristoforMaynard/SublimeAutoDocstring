SublimeAutoDocstring
====================

SublimeText plugin for inserting / updating docstrings in Python after analyzing
function parameters and the like.

Features
--------

  - Inspects function definitions and inserts a stub for each parameter
  - Inspects class / module attributes and inserts a stub for each
  - Discovers what exceptions are raised in a function and inserts a stub for each
  - Rearranges parameters to reflect their order in the function definition
  - Automatically detects style: [Google](https://sphinxcontrib-napoleon.readthedocs.org/en/latest/example_google.html "Example of Google Style")  or [Numpy](https://sphinxcontrib-napoleon.readthedocs.org/en/latest/example_numpy.html "Example of Numpy Style")

Usage
-----

  - <`cmd` + `alt` + `'`> will update a docstring for the first module/class/function preceding the cursor.
  - <`cmd` + `alt` + `shift` + `'`> will update docstrings for every class/method/function in the current file

  Note that on linux / windows, `ctrl` is used in place of `cmd`.

Settings
--------

  A shortcut to open the settings file is in menu under `Preferences/Package Settings/AutoDocstring/Settings - User`

  - `inspect_class_attributes` *(default=true)*: add / remove class attributes to stay in sync with the code
  - `inspect_exceptions` *(default=true)*: add / remove exceptions to stay in sync with the code.
  - `inspect_function_parameters` *(default=true)*: add / remove function parameters to stay in sync with the code.
  - `inspect_module_attributes` *(default=true)*: add / remove module attributes to stay in sync with the code.
  - `optional_tag` *(default="optional")*: text to add to the type of keyword arguments. Supplying an empty string won't add anything special to new keyword arguments.
  - `sort_class_attributes` *(default=true)*: Whether or not to alphabetically sort class attributes.
  - `sort_exceptions` *(default=true)*: Whether or not to alphabetically sort exceptions.
  - `sort_module_attributes` *(default=true)*: Whether or not to alphabetically sort module attributes.
  - `style` *(default="auto_google")*: can be "google", "numpy", or "auto" for auto-detection based on the other docstrings in the module. A fallback can be specified with something like "auto_google" in case auto-detection fails.
  - `template_order` *(default=false)*: If true, then reorder sections to the same order that they appear in the style's template. If false, section order of existings docstrings is preserved.
  - `use_snippet` *(default=true)*: If true, then insert a snippet so that you can
  tab through newly inserted fields (Summary / Types / Desciptions).
