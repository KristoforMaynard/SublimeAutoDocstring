# -*- coding: utf-8 -*-
"""Docstring Parsers/Formatters"""

# TODO: break this module up into smaller pieces

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


def make_docstring_obj(docstr, default="google", template_order=False):
    """Detect docstring style and create a Docstring object

    Parameters:
        docstr (str): source docstring
        default (str, class): 'google', 'numpy' or subclass
            of Docstring
        template_order (bool, optional): iff True, reorder the
            sections to match the order they appear in the template

    Returns:
        subclass of Docstring
    """
    typ = detect_style(docstr)
    if typ is None:
        if issubclass(default, Docstring):
            typ = default
        else:
            typ = STYLE_LOOKUP[default.lower()]
    return typ(docstr, template_order=template_order)

def detect_style(docstr):
    """Detect docstr style from existing docstring

    Parameters:
        docstr (str): docstring whose style we want to know

    Returns:
        class: one of [GoogleDocstring, NumpyDocstring, None]; None
            means no match
    """
    docstr = dedent_docstr(docstr)

    for c in STYLE_LOOKUP.values():
        if c.detect_style(docstr):
            return c
    return None

def dedent_docstr(s, n=1):
    """Dedent all lines except first n lines

    Args:
        s (type): some text to dedent
        n (int): number of lines to skip, (n == 0 is a normal dedent,
            n == 1 is useful for whole docstrings)
    """
    lines = s.splitlines()
    if lines:
        ret = dedent("\n".join(lines[n:]))
        if n == 0:
            return ret
        else:
            first_n_lines = "\n".join([l.lstrip() for l in lines[:n]])
            return first_n_lines + "\n" + ret
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
    """"""
    names = None
    types = None
    description = None
    tag = None
    meta = None

    def __init__(self, names, types, description, tag=None, **kwargs):
        """
        Args:
            names (list): list of names
            types (str): string describing data types
            description (str): description text
            tag (int): some meaningful index? not fleshed out yet
            **kwargs: Description
        """
        assert names is not None
        if description is None:
            description = ""
        self.names = names
        self.types = types
        self.description = description
        self.tag = tag
        self.meta = kwargs


class Section(object):
    """"""
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
    meta = None

    formatter_override = None

    def __init__(self, heading, text="", indent=None, first_indent=None,
                 **kwargs):
        """
        Args:
            heading (str): heading of the section (should be title case)
            text (str, optional): section text
            indent (str, optional): used by some formatters
            first_indent (type): Description
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
        self.meta = kwargs

    @classmethod
    def from_section(cls, sec):
        new_sec = cls(sec.heading, text=sec.text,
                      indent=sec.indent, first_indend=sec.first_indent,
                      **sec.meta)
        if hasattr(sec, "args"):
            new_sec.args = sec.args
        return new_sec

    @classmethod
    def resolve_alias(cls, heading):
        """"""
        heading = heading.title()
        try:
            return cls.ALIASES[heading]
        except KeyError:
            return heading

    @property
    def text(self):
        """"""
        if self.formatter_override is not None:
            s = self.formatter_override(self)  # pylint: disable=not-callable
        elif self.args_formatter is not None:
            s = self.args_formatter(self)
        else:
            s = self._text
        return s.rstrip() + "\n"

    @text.setter
    def text(self, val):
        """"""
        val = val.rstrip()
        if self.args_parser is not None:
            self.args = self.args_parser(self, val)
        self._text = val


class NapoleonSection(Section):
    """"""
    ALIASES = {"Args": "Parameters",
               "Arguments": "Parameters",
               "Deleted Args": "Deleted Parameters",
               "Deleted Arguments": "Deleted Parameters",
               "Other Args": "Other Parameters",
               "Other Arguments": "Other Parameters",
               "Keyword Args": "Keyword Arguments",
               "Return": "Returns",
               "Warnings": "Warning"
              }

class GoogleSection(NapoleonSection):
    """"""
    first_indent = "    "  # 1st indent is only 2 spaces according to the style
    indent = "    "

    @staticmethod
    def finalize_param(s, tag):
        """
        Args:
            s (type): Description
            tag (int): index of param? not fleshed out yet
        """
        if not ":" in s:
            s += ":"
        m = re.match(r"(.*?)\s*(?:\((.*)\))?\s*:\s*(.*)", s, re.DOTALL)
        groups = m.groups()
        names = [n.strip() for n in groups[0].split(',')]
        types = groups[1]
        descr = groups[2]
        return Parameter(names, types, descr, tag=tag)

    def param_parser(self, text):
        """
        Args:
            text (type): Description
        """
        param_dict = OrderedDict()
        param_list = []
        text = dedent_docstr(text, 0)
        s = ""
        for line in text.splitlines():
            if line and line[0] not in string.whitespace:
                if s:
                    param = self.finalize_param(s, len(param_list))
                    param_list.append(param)
                    for name in param.names:
                        param_dict[name] = param
                s = (line + "\n")
            else:
                s += (line + "\n")
        if s:
            param = self.finalize_param(s, len(param_list))
            param_list.append(param)
            for name in param.names:
                param_dict[name] = param
        return param_dict

    def param_formatter(self):
        """"""
        s = ""
        for param in self.args.values():
            if len(param.names) > 1:
                print("WARNING: Google docstrings don't allow > 1 parameter "
                      "per description")
            p = "{0}".format(", ".join(param.names))
            if param.types:
                types = param.types.strip()
                if types:
                    p += " ({0})".format(types)
            if param.description:
                p += ": {0}".format(param.description.rstrip())
            p += '\n'
            s += p

        lines = [self.first_indent + line for line in s.splitlines()]
        s = "\n".join(lines)
        return s

    PARSERS = {"Parameters": (param_parser,
                              param_formatter),
               "Other Parameters": (param_parser,
                                    param_formatter),
               "Deleted Parameters": (param_parser,
                                      param_formatter),
               "Keyword Arguments": (param_parser,
                                     param_formatter),
               "Attributes": (param_parser,
                              param_formatter),
               "Deleted Attributes": (param_parser,
                                      param_formatter),
               "Raises": (param_parser,
                          param_formatter),
               "No Longer Raises": (param_parser,
                                    param_formatter),
               "Returns": (param_parser,
                           param_formatter),
              }


class NumpySection(NapoleonSection):
    """"""
    first_indent = "    "
    indent = "    "

    @staticmethod
    def finalize_param(s, i):
        """
        Args:
            s (type): Description
        """
        m = re.match(r"(.*?)\s*(?::\s*(.*?))?\s*?\n(.*)", s, re.DOTALL)
        name, typ, desc = m.groups()
        # FIXME hack, name for numpy parameters is always a list of names
        # to support the multiple parameters per description option in
        # numpy docstrings
        name = [n.strip() for n in name.split(',')]
        desc = dedent_docstr(desc, 0)
        return Parameter(name, typ, desc, i)

    def param_parser(self, text):
        """"""
        # NOTE: there will be some tricky business if there is a
        # section break done by "resuming unindented text"
        param_list = []
        param_dict = OrderedDict()
        text = dedent_docstr(text, 0)
        s = ""
        for line in text.splitlines():
            if line and line[0] not in string.whitespace:
                if s:
                    param = self.finalize_param(s, len(param_list))
                    param_list.append(param)
                    for name in param.names:
                        param_dict[name] = param
                s = (line + "\n")
            else:
                s += (line + "\n")
        if s:
            param = self.finalize_param(s, len(param_list))
            param_list.append(param)
            for name in param.names:
                param_dict[name] = param
        return param_dict

    def param_formatter(self):
        """"""
        # NOTE: there will be some tricky business if there is a
        # section break done by "resuming unindented text"
        s = ""
        # already_seen = {}
        for param in self.args.values():
            p = "{0}".format(", ".join(param.names))
            if param.types:
                types = param.types.strip()
                if types:
                    p += " : {0}".format(types)
            p += "\n"
            if param.description:
                desc = param.description.rstrip()
                lines = [self.first_indent + line for line in desc.splitlines()]
                if len(lines) == 0 or not lines[-1].strip() == "":
                    lines.append("")
                p += "\n".join(lines)
            s += p
        return s

    PARSERS = {"Parameters": (param_parser,
                              param_formatter),
               "Other Parameters": (param_parser,
                                    param_formatter),
               "Deleted Parameters": (param_parser,
                                      param_formatter),
               "Keyword Arguments": (param_parser,
                                     param_formatter),
               "Attributes": (param_parser,
                              param_formatter),
               "Deleted Attributes": (param_parser,
                                      param_formatter),
               "Raises": (param_parser,
                          param_formatter),
               "No Longer Raises": (param_parser,
                                    param_formatter),
               "Returns": (param_parser,
                           param_formatter),
              }


class Docstring(object):
    """Handle parsing / modifying / writing docstrings"""

    STYLE_NAME = "none"
    SECTION_STYLE = Section
    TEMPLATE = OrderedDict([("Summary", None)])
    PREFERRED_PARAMS_ALIAS = "Args"

    sections = None

    def __init__(self, docstr, template_order=False):
        """
        Parameters:
            docstr (Docstring or str): some existing docstring
            template_order (bool, optional): iff True, reorder the
                sections to match the order they appear in the template
        """
        if isinstance(docstr, Docstring):
            self.sections = docstr.sections
            if not isinstance(docstr, type(self)):
                # fixme, this is kinda hacky
                make_new_sec = self.SECTION_STYLE.from_section
                for sec_name, sec in docstr.sections.items():
                    docstr.sections[sec_name] = make_new_sec(sec)
                if "Parameters" in docstr.sections:
                    self.sections["Parameters"].heading = self.PREFERRED_PARAMS_ALIAS
        elif isinstance(docstr, string_types):
            if template_order:
                self.sections = self.TEMPLATE.copy()
            else:
                self.sections = OrderedDict()
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

    def update_parameters(self, params):
        """"""
        raise NotImplementedError("update_parameters is an abstract method")

    def add_dummy_returns(self, typ, description):
        raise NotImplementedError("add_dummy_returns is an abstract method")

    def finalize_section(self, heading, text):
        """
        Args:
            heading (type): Description
            text (type): Description
        """
        section = self.SECTION_STYLE(heading, text)
        self.sections[section.alias] = section

    def section_exists(self, section_name):
        """returns True iff section exists, and was finalized"""
        if section_name in self.sections:
            if self.sections[section_name] is not None:
                return True
        return False


class NapoleonDocstring(Docstring):  # pylint: disable=abstract-method
    """Styles understood by napoleon, aka. Google/Numpy"""
    # TODO: is there any common funcionality to put here?
    STYLE_NAME = "napoleon"
    TEMPLATE = OrderedDict([("Summary", None),
                            ("Parameters", None),
                            ("Keyword Arguments", None),
                            ("Returns", None),
                            ("Yields", None),
                            ("Other Parameters", None),
                            ("Deleted Parameters", None),
                            ("Attributes", None),
                            ("Deleted Attributes", None),
                            ("Methods", None),
                            ("Raises", None),
                            ("No Longer Raises", None),
                            ("Warns", None),
                            ("See Also", None),
                            ("Warning", None),
                            ("Note", None),
                            ("Notes", None),
                            ("References", None),
                            ("Example", None),
                            ("Examples", None),
                           ])

    def _update_section(self, params, sec_name, sec_alias=None,
                        del_prefix="Deleted ", alpha_order=False,
                        other_sections=()):
        """Update section to add / remove params

        As a failsafe, params that are removed are placed in a
        "Deleted ..." section

        Args:
            params (OrderedDict): dict of Parameter objects
            sec_name (str): generic section name
            sec_alias (str): section name that appears in teh docstring
            del_prefix (str): prefix for section that holds params that
                no longer exist.
            alpha_order (bool): whether or not to alphabetically sort
                the params
        """
        if not sec_alias:
            sec_alias = sec_name

        if not self.section_exists(sec_name) and len(params) == 0:
            return None
        elif not self.section_exists(sec_name):
            self.finalize_section(sec_alias, "")

        # put together which other sections exist so we can use them to
        # exclude params that exist in them
        _other = []
        for _secname in other_sections:
            if self.section_exists(self.SECTION_STYLE.resolve_alias(_secname)):
                _other.append(self.sections[self.SECTION_STYLE.resolve_alias(_secname)])
        other_sections = _other

        if alpha_order:
            sorted_params = OrderedDict()
            for k in sorted(list(params.keys()), key=str.lower):
                sorted_params[k] = params[k]
            params = sorted_params

        current_dict = self.sections[sec_name].args
        # print("current::", current)

        # go through params in the order of the function declaration
        # and cherry-pick from current_dict if there's already a description
        # for that parameter
        tags_seen = dict()
        new = OrderedDict()
        for name, param in params.items():
            if name in current_dict:
                param = current_dict.pop(name)
                if param.tag in tags_seen:
                    param = None
                else:
                    tags_seen[param.tag] = True
            else:
                # if param is in one of the 'other sections', then don't
                # worry about it
                for sec in other_sections:
                    if name in sec.args:
                        param = None
            if param:
                new[name] = param

        # go through params that are no linger in the arguments list and
        # move them from the Parameters section of the docstring to the
        # deleted parameters section
        if '' in current_dict:
            del current_dict['']
        if len(current_dict):
            del_sec_name = del_prefix + sec_name
            del_sec_alias = del_prefix + sec_alias
            print("Warning, killing parameters named:",
                  list(current_dict.keys()))
            # TODO: put a switch here for other bahavior?
            if not self.section_exists(self.SECTION_STYLE.resolve_alias(del_sec_name)):
                self.finalize_section(del_sec_name, "")

            deled_params = self.sections[self.SECTION_STYLE.resolve_alias(del_sec_name)]
            deleted_tags = dict()
            for key, val in current_dict.items():
                if key in deled_params.args:
                    print("Stronger Warning: Killing old deleted param: "
                          "'{0}'".format(key))

                val.names.remove(key)
                if val.tag in deleted_tags:
                    deleted_tags[val.tag].names.append(key)
                else:
                    new_val = Parameter([key], val.types, val.description)
                    deleted_tags[val.tag] = new_val
                    deled_params.args[key] = new_val

        if len(new) == 0:
            self.sections[sec_name] = None
        else:
            self.sections[sec_name].args = new

    def update_parameters(self, params):
        """
        Args:
            params (OrderedDict): params objects keyed by their names
        """
        other_sections = ['Other Parameters', 'Keyword Parameters']
        self._update_section(params, "Parameters", self.PREFERRED_PARAMS_ALIAS,
                             other_sections=other_sections)

    def update_attributes(self, attribs, alpha_order=True):
        """
        Args:
            params (OrderedDict): params objects keyed by their names
        """
        self._update_section(attribs, "Attributes", alpha_order=alpha_order)

    def update_exceptions(self, attribs, alpha_order=True):
        """
        Args:
            params (OrderedDict): params objects keyed by their names
        """
        self._update_section(attribs, "Raises", del_prefix="No Longer ",
                             alpha_order=alpha_order)

class GoogleDocstring(NapoleonDocstring):
    """"""
    STYLE_NAME = "google"
    SECTION_STYLE = GoogleSection
    SECTION_RE = r"^[A-Za-z0-9][A-Za-z0-9 \t]*:\s*$"
    PREFERRED_PARAMS_ALIAS = "Args"

    @classmethod
    def detect_style(cls, docstr):
        """"""
        m = re.search(cls.SECTION_RE, docstr, re.MULTILINE)
        return m is not None

    def _parse(self, s):
        """
        Args:
            s (type): Description
        """
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
        """
        Args:
            top_indent (type): Description
            indent (type): Description
        """
        s = ""
        if self.section_exists("Summary"):
            text = self.sections["Summary"].text
            if len(text.strip()) > 0:
                s += "{0}".format(text)

        for _, section in islice(self.sections.items(), 1, None):
            if section is None:
                continue
            s += "\n{0}:\n{1}".format(section.heading, section.text)

        s = indent_docstr(s, top_indent)

        return s

    def add_dummy_returns(self, name, typ, description):
        if not self.section_exists("Returns"):
            if name:
                # text = "    {0} ({1}): {2}".format(name, typ, description)
                # print("Note: Google docstrings ignore name of return types")
                text = "    {0}: {1}".format(typ, description)
            else:
                text = "    {0}: {1}".format(typ, description)
            self.finalize_section("Returns", text)
            self.sections["Returns"].formatter_override = lambda s: s._text


class NumpyDocstring(NapoleonDocstring):
    """"""
    STYLE_NAME = "numpy"
    SECTION_STYLE = NumpySection
    SECTION_RE = r"^([A-Za-z0-9][A-Za-z0-9 \t]*)\s*\n-+\s*?$"
    PREFERRED_PARAMS_ALIAS = "Parameters"

    @classmethod
    def detect_style(cls, docstr):
        """"""
        m = re.search(cls.SECTION_RE, docstr, re.MULTILINE)
        return m is not None

    def _parse(self, s):
        """
        Args:
            s (type): Description
        """
        s = dedent_docstr(s)

        heading_inds = []
        section_titles = []
        section_texts = []
        for m in re.finditer(self.SECTION_RE, s, re.MULTILINE):
            heading_inds.append((m.start(), m.end()))
            section_titles.append(m.group(1).strip())

        section_titles.insert(0, "Summary")
        heading_inds.insert(0, (0, 0))
        heading_inds.append((len(s), None))

        for i, heading_ind in enumerate(heading_inds[1:], 1):
            text = s[heading_inds[i - 1][1]:heading_ind[0]]
            # Evidently leading newlines are sometimes desirable for numpy
            if section_titles[i - 1] != "Summary":
                if text[:1] == '\n':
                    text = text[1:]
                elif text[:2] == '\r\n':
                    text = text[2:]
            section_texts.append(text.rstrip())

        for title, text in zip(section_titles, section_texts):
            self.finalize_section(title, text)

    def format(self, top_indent, indent="    "):
        """
        Args:
            top_indent (type): Description
            indent (type, optional): Description
        """
        s = ""
        if self.section_exists("Summary"):
            text = self.sections["Summary"].text
            if len(text.strip()) > 0:
                s += "{0}".format(text)

        for _, section in islice(self.sections.items(), 1, None):
            if section is None:
                continue
            title = section.heading
            text = section.text
            s += "\n{0}\n{1}\n{2}".format(title, "-"*len(title), text)

        s = indent_docstr(s, top_indent)

        return s

    def add_dummy_returns(self, name, typ, description):
        if not self.section_exists("Returns"):
            if name:
                text = "{0} : {1}\n    {2}".format(name, typ, description)
            else:
                text = "{0}\n    {1}".format(typ, description)
            self.finalize_section("Returns", text)
            self.sections["Returns"].formatter_override = lambda s: s._text


STYLE_LOOKUP = OrderedDict([('numpy', NumpyDocstring),
                            ('google', GoogleDocstring)])

##
## EOF
##
