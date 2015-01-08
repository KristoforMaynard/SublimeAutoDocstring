SublimeAutoDocstring
====================

SublimeText plugin for inserting template docstrings after analyzing
function parameters and the like.

Features
--------
  - Inspects function definitions and inserts a stub for each parameter
  - Can rearrange parameters to reflect their order in the function definition
  - Can automatically detect and use Google / Numpy docstring style

What Works
----------
  - <`cmd` + `alt` + `'`> will update a docstring for the first module/class/function preceeding the cursor.
  - <`cmd` + `alt` + `shift` + `'`> will update docstrings for every class/method/function in the current file

Settings
--------

  - `style`: can be 'google', 'numpy', or 'auto' for auto-detection based on the other docstrings in the module. A fallback can be specified with something like 'auto_google' in case auto-detection fails. Default is auto_google.

TODO
----
  - make more robust function argument parser
  - implement Numpy style
