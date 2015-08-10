SublimeAutoDocstring
====================

SublimeText plugin for inserting template docstrings in Python after analyzing
function parameters and the like.

Features
--------

  - Inspects function definitions and inserts a stub for each parameter
  - Discovers what exceptions are raised in a function and inserts a stub for each
  - Inspects class / module attributes and inserts a stub for each
  - Rearranges parameters to reflect their order in the function definition
  - Automatically detects style: Google, Numpy

Usage
-----

  - <`cmd` + `alt` + `'`> will update a docstring for the first module/class/function preceding the cursor.
  - <`cmd` + `alt` + `shift` + `'`> will update docstrings for every class/method/function in the current file

Settings
--------

  - `inspect_class_attributes`: add / remove class attributes to stay in sync with the code
  - `inspect_exceptions`: add / remove exceptions to stay in sync with the code
  - `inspect_function_parameters`: add / remove function parameters to stay in sync with the code
  - `inspect_module_attributes`: add / remove module attributes to stay in sync with the code
  - `optional_tag` (string): text to add to the type of keyword arguments. Supplying an empty string won't add anything special to new keyword arguments.
  - `style`: can be 'google', 'numpy', or 'auto' for auto-detection based on the other docstrings in the module. A fallback can be specified with something like 'auto_google' in case auto-detection fails. Default is auto_google.
  - `template_order` (boolean): If true, then reorder section to the same order that they appear in the style's template. If false, section order of existings docstrings is preserved. Default is false.
  - `use_snippet` (boolean): If true, then insert a snippet so that you can
  tab through newly inserted fields (Summary / Types / Desciptions). Default
  is false, but should become true in the future, when this feature is more
  fully tested.
