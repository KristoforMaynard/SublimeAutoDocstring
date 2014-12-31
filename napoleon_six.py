# -*- coding: utf-8 -*-
# This source has been adapted from the napoleon sphinx extension.
# Essentially these are whole sale copy/pasted and then hackilly
# edited until things worked. Good thing sphynx is BSD licensed :)

import sys

# Adapted from the six module...
# Copyright (c) 2010-2014 Benjamin Peterson
PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

"""
    sphinx.util.pycompat
    ~~~~~~~~~~~~~~~~~~~~

    Stuff for Python version compatibility.

    :copyright: Copyright 2007-2014 by the Sphinx team, see AUTHORS.
    :license: BSD, see LICENSE for details.
"""
if PY3:
    string_types = str,

    def iteritems(d, **kw):
        return iter(d.items(**kw))

    class UnicodeMixin(object):
        """Mixin class to handle defining the proper __str__/__unicode__
        methods in Python 2 or 3."""

        def __str__(self):
            return self.__unicode__()
else:
    string_types = basestring,  # pylint: disable=undefined-variable

    def iteritems(d, **kw):
        return iter(d.iteritems(**kw))

    class UnicodeMixin(object):
        """Mixin class to handle defining the proper __str__/__unicode__
        methods in Python 2 or 3."""

        def __str__(self):
            return self.__unicode__().encode('utf8')
