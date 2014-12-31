SublimeAutoDocstring
====================

SublimeText plugin for inserting template docstrings after analyzing
function parameters and the like.

WORK IN PROGRESS

WHAT WORKS:
  - <cmd + alt + '> will insert a docstring if none exists as well as
    setting its text to something not very useful

TODO:
  - parse declaration parameters so they are auto-filled into the docstring
  - actually format a proper docstring
  - parse existing docstring so the operation is not destructive
  - Switch for either Google or Numpy/Scipy style
