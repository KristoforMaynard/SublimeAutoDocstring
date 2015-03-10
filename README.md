SublimeAutoDocstring
====================

SublimeText plugin for inserting template docstrings in Python after analyzing
function parameters and the like.

Features
--------

  - Inspects function definitions and inserts a stub for each parameter
  - Rearranges parameters to reflect their order in the function definition
  - Automatically detects style: Google, Numpy

Usage
-----

  - <`cmd` + `alt` + `'`> will update a docstring for the first module/class/function preceeding the cursor.
  - <`cmd` + `alt` + `shift` + `'`> will update docstrings for every class/method/function in the current file

Settings
--------

  - `style`: can be 'google', 'numpy', or 'auto' for auto-detection based on the other docstrings in the module. A fallback can be specified with something like 'auto_google' in case auto-detection fails. Default is auto_google.
  - `template_order` (boolean): If true, then reorder section to the same order that they appear in the style's template. If false, section order of existings docstrings is preserved. Default is false.

Coming Soon
-----------

  - make more robust function argument parser: at the moment, things go awry when lists/tuples/dicts show up as default values
  - parse class attributes similar to function/method arguments
