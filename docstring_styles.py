# -*- coding: utf-8 -*-
"""Docstring Parsers/Formatters"""

import sys
import string
import re
from textwrap import dedent
from collections import OrderedDict
from itertools import islice


PY3k = sys.version_info[0] == 3
if PY3k:
    string_types = str,
else:
    string_types = basestring,  # pylint: disable=undefined-variable


def make_docstring_obj(docstr, default="google"):
    """Detect docstring style and create a Docstring object

    Parameters:
        docstr (str): source docstring
        default (str, class): 'google', 'numpy' or subclass
            of Docstring

    Returns:
        subclass of Docstring
    """
    typ = detect_style(docstr)
    if typ is None:
        if issubclass(default, Docstring):
            typ = default
        else:
            typ = STYLE_LOOKUP[default.lower()]
    return typ(docstr)

def detect_style(docstr):
    """Detect docstr style from existing docstring

    Parameters:
        docstr(str): docstring whose style we want to know

    Returns:
        class: one of [GoogleDocstring, NumpyDocstring, None]; None
            means no match
    """
    docstr = dedent_docstr(docstr)

    for c in STYLE_LOOKUP.values():
        if c.detect_style(docstr):
            return c
    return None

def dedent_docstr(s):
    """Dedent all lines except first"""
    lines = s.splitlines()
    if lines:
        ret = dedent("\n".join(lines[1:]))
        return lines[0].lstrip() + "\n" + ret
    else:
        return ""

def indent_docstr(s, indent):
    """Add common indentation to all lines except first

    Args:
        s (str): docstring starting at indentation level 0
        indent (str): text used for indentation, in practice
            this will be the level of the declaration + 1

    Returns:
        s with common indentation applied
    """
    lines = s.splitlines()
    if len(lines) == 0:
        return ""

    for i in range(1, len(lines)):
        lines[i] = "{0}{1}".format(indent, lines[i])

    if len(lines) > 1 and not lines[-1].strip() == "":
        lines.append(indent)
    ret = lines[0]
    if len(lines) > 1:
        ret += "\n" + "\n".join(lines[1:])

    return ret


class Parameter(object):
    name = None
    types = None
    description = None
    meta = None

    def __init__(self, name, types, description, **kwargs):
        assert name is not None
        if description is None:
            description = ""
        self.name = name
        self.types = types
        self.description = description
        self.meta = kwargs


class Section(object):
    ALIASES = {}
    PARSERS = {}

    is_formatted = None
    args = None
    args_parser = None
    args_formatter = None

    heading = None
    alias = None
    _text = None
    first_indent = "    "
    indent = "    "

    def __init__(self, heading, text="", indent=None, first_indent=None):
        """
        Args:
            heading (str): heading of the section (should be title case)
            text (str, optional): section text
            indent (str, optional): used by some formatters
        """
        self.heading = heading
        self.alias = self.resolve_alias(heading)

        if self.alias in self.PARSERS:
            parser, formatter = self.PARSERS[self.alias]
            self.args_parser = parser
            self.args_formatter = formatter
            self.is_formatted = True
        else:
            self.is_formatted = False

        if indent is not None:
            self.indent = indent
        if first_indent is not None:
            self.first_indent = first_indent

        self.text = text

    @classmethod
    def resolve_alias(cls, heading):
        heading = heading.title()
        try:
            return cls.ALIASES[heading]
        except KeyError:
            return heading

    @property
    def text(self):
        if self.args_formatter is not None:
            s = self.args_formatter(self)
        else:
            s = self._text
        return s.rstrip() + "\n"

    @text.setter
    def text(self, val):
        val = val.rstrip()
        if self.args_parser is not None:
            self.args = self.args_parser(self, val)
        self._text = val


class NapoleonSection(Section):
    ALIASES = {"Args": "Parameters",
               "Arguments": "Parameters",
               "Keyword Args": "Keyword Arguments",
               "Return": "Returns",
               "Warnings": "Warning"
              }

class GoogleSection(NapoleonSection):
    first_indent = "    "  # 1st indent is only 2 spaces according to the style
    indent = "    "

    @staticmethod
    def finalize_param(s):
        if not ":" in s:
            s += ":"
        m = re.match(r"(.*?)\s*(?:\((.*)\))?\s*:\s*(.*)", s, re.DOTALL)
        groups = m.groups()
        return Parameter(groups[0], groups[1], groups[2])

    def param_parser(self, text):
        params = OrderedDict()
        text = dedent_docstr(text)
        s = ""
        for line in text.splitlines():
            if line[0] not in string.whitespace:
                if s:
                    param = self.finalize_param(s)
                    params[param.name] = param
                s = (line + "\n")
            else:
                s += (line + "\n")
        if s:
            param = self.finalize_param(s)
            params[param.name] = param
        return params

    def param_formatter(self):
        s = ""
        for name, param in self.args.items():
            p = "{0}".format(name)
            if param.types:
                types = param.types.strip()
                if len(types):
                    p += " ({0})".format(types)
            p += ": {0}\n".format(param.description.rstrip())
            s += p

        lines = [self.first_indent + line for line in s.splitlines()]
        s = "\n".join(lines)
        return s

    def returns_parser(self, text):
        return text

    def returns_formatter(self):
        return self.args

    PARSERS = {"Parameters": (param_parser,
                              param_formatter),
               "Other Parameters": (param_parser,
                                    param_formatter),
               "Keyword Arguments": (param_parser,
                                     param_formatter),
               "Returns": (returns_parser,
                           returns_formatter)}


class NumpySection(NapoleonSection):
    @staticmethod
    def param_parser(text):
        return text

    @staticmethod
    def param_formatter(section):
        return section.args

    @staticmethod
    def returns_parser(text):
        return text

    @staticmethod
    def returns_formatter(section):
        return section.args

    # PARSERS = {"Parameters": (NumpySection.param_parser,
    #                           NumpySection.param_formatter),
    #            "Other Parameters": (NumpySection.param_parser,
    #                                 NumpySection.param_formatter),
    #            "Keyword Parameters": (NumpySection.param_parser,
    #                                   NumpySection.param_formatter),
    #            "Returns": (NumpySection.returns_parser,
    #                        NumpySection.returns_formatter)}


class Docstring(object):
    """Handle parsing / modifying / writing docstrings"""

    SECTION_STYLE = Section
    TEMPLATE = OrderedDict([("Summary", None)])
    PREFERRED_PARAMS_ALIAS = "Args"

    sections = None

    def __init__(self, docstr):
        """
        Parameters:
            docstr (Docstring or str): some existing docstring
        """
        if isinstance(docstr, Docstring):
            self.sections = docstr.sections
        elif isinstance(docstr, string_types):
            self.sections = self.TEMPLATE.copy()
            self._parse(docstr)

    def _parse(self, s):
        """Parse docstring into meta data

        Parameters:
            s (str): docstring
        """
        raise NotImplementedError("_parse is an abstract method")

    def format(self, top_indent, indent="    "):
        """Format docstring into a string

        Parameters:
            top_indent (str): indentation added to all but the first
                lines
            indent (str): indent of subsections

        Returns:
            str: properly formatted
        """
        raise NotImplementedError("format is an abstract method")

    def update_parameters(self):
        raise NotImplementedError()

    def finalize_section(self, heading, text):
        section = self.SECTION_STYLE(heading, text)
        self.sections[section.alias] = section


class NapoleonDocstring(Docstring):  # pylint: disable=abstract-method
    """Styles understood by napoleon, aka. Google/Numpy"""
    # TODO: is there any common funcionality to put here?
    TEMPLATE = OrderedDict([("Summary", None),
                            ("Parameters", None),
                            ("Keyword Arguments", None),
                            ("Returns", None),
                            ("Yields", None),
                            ("Other Parameters", None),
                            ("Attributes", None),
                            ("Methods", None),
                            ("Raises", None),
                            ("Warns", None),
                            ("See Also", None),
                            ("Warning", None),
                            ("Note", None),
                            ("Notes", None),
                            ("References", None),
                            ("Example", None),
                            ("Examples", None),
                           ])

    def update_parameters(self, params):
        """
        Args:
            params (OrderedDict): params objects keyed by their names
        """
        if self.sections["Parameters"] is None and len(params) == 0:
            return None
        elif self.sections["Parameters"] is None:
            self.finalize_section(self.PREFERRED_PARAMS_ALIAS, "")
        current = self.sections["Parameters"].args

        new = OrderedDict()
        for name, param in params.items():
            new[name] = current.pop(name, param)

        if len(current):
            print("Warning, killing parameters named:", list(current.keys()))

        self.sections["Parameters"].args = new


class GoogleDocstring(NapoleonDocstring):
    SECTION_STYLE = GoogleSection
    SECTION_RE = r"^[A-Za-z0-9][A-Za-z0-9 \t]*:\s*$"
    PREEFERRED_PARAMS_ALIAS = "Args"

    @classmethod
    def detect_style(cls, docstr):
        m = re.search(cls.SECTION_RE, docstr, re.MULTILINE)
        return m is not None

    def _parse(self, s):
        s = dedent_docstr(s)

        cur_section = "Summary"
        cur_text = ""
        for line in s.splitlines():
            if re.search(self.SECTION_RE, line) is not None:
                self.finalize_section(cur_section, cur_text)
                cur_section = line.rstrip()[:-1]  # takes out ':'
                cur_text = ""
            else:
                cur_text += line + '\n'
        if cur_section.strip() != "":
            self.finalize_section(cur_section, cur_text)

    def format(self, top_indent, indent="    "):
        s = ""
        if self.sections["Summary"] is not None:
            text = self.sections["Summary"].text
            if len(text.strip()) > 0:
                s += "{0}".format(text)

        for _, section in islice(self.sections.items(), 1, None):
            if section is None:
                continue
            s += "\n{0}:\n{1}".format(section.heading, section.text)

        s = indent_docstr(s, top_indent)

        return s


class NumpyDocstring(NapoleonDocstring):
    SECTION_STYLE = NumpySection
    SECTION_RE = r"^([A-Za-z0-9][A-Za-z0-9 \t]*)\s*\n-+"
    PREEFERRED_PARAMS_ALIAS = "Parameters"

    @classmethod
    def detect_style(cls, docstr):
        m = re.search(cls.SECTION_RE, docstr, re.MULTILINE)
        return m is not None

    def _parse(self, s):
        raise NotImplementedError("TODO: put logic here")

    def format(self, top_indent, indent="    "):
        raise NotImplementedError("TODO: put logic here")

STYLE_LOOKUP = OrderedDict([('google', GoogleDocstring),
                            ('numpy', NumpyDocstring)])

##
## EOF
##
