# -*- coding: utf-8 -*-
"""Docstring Parsers/Formatters"""

# TODO: break this module up into smaller pieces

import sys
import re
from textwrap import dedent
from collections import OrderedDict
from itertools import islice

from .autodocstring_logging import logger


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
    logger.info("[make_docstring_obj] from {} to {}"
                "".format(typ.__name__ if typ is not None else None, default.__name__))

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
    lines = s.splitlines(keepends=True)
    if lines:
        first_n_lines = "".join([l.lstrip(' \t') for l in lines[:n]])
        dedented = dedent("".join(lines[n:]))
        return first_n_lines + dedented
    else:
        return ""

def dedent_verbose(s, n=1):
    new = dedent_docstr(s, n=n)

    s_split = s.splitlines(keepends=True)
    new_split = new.splitlines(keepends=True)
    i, ind = 0, -1
    for i in range(n, len(s_split)):
        if s_split[i].strip():
            ind = s_split[i].find(new_split[i])
            break
    if ind >= 0:
        indent = s_split[i][:ind]
    else:
        indent = ""

    return indent, new

def indent_docstr(s, indent, n=1, trim=True):
    """Add common indentation to all lines except first

    Args:
        s (str): docstring starting at indentation level 0
        indent (str): text used for indentation, in practice
            this will be the level of the declaration + 1
        n (int): don't indent first n lines
        trim (bool): trim whitespace (' \t') out of blank lines

    Returns:
        s with common indentation applied
    """
    lines = s.splitlines(keepends=True)
    for i in range(n, len(lines)):
        if lines[i].strip() or not trim:
            lines[i] = "{0}{1}".format(indent, lines[i])
        else:
            lines[i] = lines[i].strip(' \t')
    return "".join(lines)

def count_leading_newlines(s):
    """count number of leading newlines

    this includes newlines that are separated by other whitespace
    """
    return s[:-len(s.lstrip())].count('\n')

def count_trailing_newlines(s):
    """count number of trailing newlines

    this includes newlines that are separated by other whitespace
    """
    return s[len(s.rstrip()):].count('\n')

def with_bounding_newlines(s, nleading=0, ntrailing=0, nl='\n'):
    """return s with at least # leading and # trailing newlines

    this includes newlines that are separated by other whitespace
    """
    return "{0}{1}{2}".format(nl * (nleading - count_leading_newlines(s)),
                              s,
                              nl * (ntrailing - count_trailing_newlines(s)))

def strip_newlines(s, nleading=0, ntrailing=0):
    """strip at most nleading and ntrailing newlines from s"""
    for _ in range(nleading):
        if s.lstrip(' \t')[0] == '\n':
            s = s.lstrip(' \t')[1:]
        elif s.lstrip(' \t')[0] == '\r\n':
            s = s.lstrip(' \t')[2:]

    for _ in range(ntrailing):
        if s.rstrip(' \t')[-2:] == '\r\n':
            s = s.rstrip(' \t')[:-2]
        elif s.rstrip(' \t')[-1:] == '\n':
            s = s.rstrip(' \t')[:-1]

    return s


class Parameter(object):
    """"""
    names = None
    types = None
    description = None
    tag = None
    descr_only = None
    meta = None

    def __init__(self, names, types, description, tag=None, descr_only=False,
                 annotated=False, **kwargs):
        """
        Args:
            names (list): list of names
            types (str): string describing data types
            description (str): description text
            tag (int): some meaningful index? not fleshed out yet
            descr_only (bool): only description is useful
            **kwargs: Description
        """
        assert names is not None
        if description is None:
            description = ""
        self.names = names
        self.types = types
        self.description = description
        self.tag = tag
        self.descr_only = descr_only
        self.annotated = annotated
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
    section_indent = ""
    indent = "    "
    meta = None

    formatter_override = None

    def __init__(self, heading, text="", indent=None, **kwargs):
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

        self.text = text
        self.meta = kwargs

        logger.debug("create section '{}' ({}) with args : '{}'".format(self.heading,
                                                                         self.alias,
                                                                         self.args))

    @classmethod
    def from_section(cls, sec):
        new_sec = cls(sec.alias)
        new_sec._text = sec._text  # pylint: disable=protected-access
        # when changing styles, the indentation should change to better fit
        # the new style
        # new_sec.section_indent = sec.section_indent
        # new_sec.indent = sec.indent
        if hasattr(sec, "args"):
            new_sec.args = sec.args
        return new_sec

    @classmethod
    def resolve_alias(cls, heading):
        """"""
        titled_heading = heading.title()
        try:
            return cls.ALIASES[titled_heading]
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
        return s

    @text.setter
    def text(self, val):
        """"""
        val = strip_newlines(val, ntrailing=1)
        if self.args_parser is not None:
            self.args = self.args_parser(self, val)
        else:
            section_indent, self._text = dedent_verbose(val, n=0)
            # don't overwrite section indent if val isn't indented
            if section_indent:
                self.section_indent = section_indent


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
               "Yield": "Yields",
               "No Longer Returns": "No Longer Returned",
               "No Longer Yields": "No Longer Yielded",
               "Warnings": "Warning"
              }

    def is_return_section(self):
        return self.heading and self.heading.lower() in ('return', 'returns',
                                                         'yield', 'yields')

    def param_parser_common(self, text):
        # NOTE: there will be some tricky business if there is a
        # section break done by "resuming unindented text"
        param_list = []
        param_dict = OrderedDict()
        text = dedent_docstr(text, 0)

        _r = r"^\S[^\r\n]*(?:\n[^\S\n]+\S[^\r\n]*|\n)*"
        param_blocks = re.findall(_r, text, re.MULTILINE)
        for i, block in enumerate(param_blocks):
            param = self.finalize_param(block, len(param_list))
            param_list.append(param)
            if self.is_return_section():
                param.names = [", ".join(param.names)]
                param_dict[i] = param
            else:
                for name in param.names:
                    param_dict[name] = param
        return param_dict


class GoogleSection(NapoleonSection):
    """"""
    section_indent = "    "
    indent = "    "

    @staticmethod
    def finalize_param(s, tag):
        """
        Args:
            s (type): Description
            tag (int): index of param? not fleshed out yet
        """
        meta = {}
        _r = r"([^,\s]+(?:\s*,\s*[^,\s]+)*\s*)(?:\((.*)\))?\s*:\s*(.*)"
        m = re.match(_r, s, re.DOTALL | re.MULTILINE)
        if m:
            names, typ, descr = m.groups()
            names = [n.strip() for n in names.split(',')]
            meta['indent'], descr = dedent_verbose(descr, n=1)
            descr_only = False
        else:
            names = ["{0}".format(tag)]
            typ = ""
            descr = s
            descr_only = True
        return Parameter(names, typ, descr, tag=tag, descr_only=descr_only, **meta)

    def param_parser(self, text):
        logger.info("[GoogleSection] section '{}' starts parsing".format(self.alias))
        return self.param_parser_common(text)

    def param_formatter(self):
        """"""
        logger.info("[GoogleSection] section '{}' starts formatting".format(self.alias))

        s = ""
        for param in self.args.values():
            if param.descr_only:
                s += with_bounding_newlines(param.description, ntrailing=1)
            else:
                if len(param.names) > 1:
                    logger.warn("section '{}' : Google docstrings don't allow > 1 "
                                 "parameter per description".format(self.alias))
                p = "{0}".format(", ".join(param.names))
                if param.types:
                    types = param.types.strip()
                    if types:
                        p = "{0} ({1})".format(p, types)
                if param.description:
                    desc = indent_docstr(param.description,
                                         param.meta.get("indent", self.indent))
                    p = "{0}: {1}".format(p, desc)
                s += with_bounding_newlines(p, ntrailing=1)
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

               "Yields": (param_parser,
                          param_formatter),

               "No Longer Returned": (param_parser,
                                      param_formatter),

               "No Longer Yielded": (param_parser,
                                     param_formatter),
              }


class NumpySection(NapoleonSection):
    """"""
    indent = "    "

    @staticmethod
    def finalize_param(s, i):
        meta = {}
        _r = r"\s*([^,\s]+(?:\s*,\s*[^,\s]+)*)\s*(?::\s*(.*?))?[^\S\n]*?\n(\s+.*)"
        m = re.match(_r, s, re.DOTALL)
        if m:
            names, typ, desc = m.groups()
            # FIXME hack, name for numpy parameters is always a list of names
            # to support the multiple parameters per description option in
            # numpy docstrings
            names = [n.strip() for n in names.split(',')]
            meta['indent'], descr = dedent_verbose(desc, 0)
            descr_only = False
        else:
            names = ["{0}".format(i)]
            typ = ""
            descr = s
            descr_only = True
        return Parameter(names, typ, descr, tag=i, descr_only=descr_only, **meta)

    def param_parser(self, text):
        logger.info("[NumpySection] section '{}' starts parsing".format(self.alias))
        return self.param_parser_common(text)

    def param_formatter(self):
        """"""
        # NOTE: there will be some tricky business if there is a
        # section break done by "resuming unindented text"
        logger.info("[NumpySection] section '{}' starts formatting".format(self.alias))

        s = ""
        # already_seen = {}
        for param in self.args.values():
            if param.descr_only:
                s += with_bounding_newlines(param.description, ntrailing=1)
            else:
                p = "{0}".format(", ".join(param.names))
                if param.types:
                    types = param.types.strip()
                    if types:
                        p = "{0} : {1}".format(p, param.types.strip())
                p = with_bounding_newlines(p, ntrailing=1)
                if param.description:
                    p += indent_docstr(param.description,
                                       param.meta.get("indent", self.indent),
                                       n=0)
                s += with_bounding_newlines(p, ntrailing=1)
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

               "Yields": (param_parser,
                          param_formatter),

               "No Longer Returned": (param_parser,
                                      param_formatter),

               "No Longer Yielded": (param_parser,
                                     param_formatter),

              }


class Docstring(object):
    """Handle parsing / modifying / writing docstrings"""

    STYLE_NAME = "none"
    SECTION_STYLE = Section
    TEMPLATE = OrderedDict([("Summary", None)])
    PREFERRED_PARAMS_ALIAS = "Args"

    sections = None
    trailing_newlines = None

    def __init__(self, docstr, template_order=False):
        """
        Parameters:
            docstr (Docstring or str): some existing docstring
            template_order (bool, optional): iff True, reorder the
                sections to match the order they appear in the template
        """
        if isinstance(docstr, Docstring):
            self.sections = docstr.sections
            self.trailing_newlines = docstr.trailing_newlines
            if not isinstance(docstr, type(self)):

                # fixme, this is kinda hacky
                make_new_sec = self.SECTION_STYLE.from_section
                for sec_name, sec in docstr.sections.items():
                    # when the section should not exists
                    # i.e. when a section was generated, but isn't needed anymore
                    # e.g. when there isn't any exception raised
                    if sec:
                        docstr.sections[sec_name] = make_new_sec(sec)

                    else:
                        # deleting section that shouldn't be here
                        # including those generated with template_order=True
                        del docstr.sections[sec_name]

                # ok, this way of changing indentation is a thunder hack
                if "Parameters" in docstr.sections:
                    self.get_section("Parameters").heading = self.PREFERRED_PARAMS_ALIAS
                    for arg in self.get_section("Parameters").args.values():
                        arg.meta['indent'] = self.get_section("Parameters").indent
                if "Returns" in docstr.sections:
                    for arg in self.get_section("Returns").args.values():
                        arg.meta['indent'] = self.get_section("Returns").indent
                if "Yields" in docstr.sections:
                    for arg in self.get_section("Yields").args.values():
                        arg.meta['indent'] = self.get_section("Yields").indent

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

    def format(self, top_indent):
        """Format docstring into a string

        Parameters:
            top_indent (str): indentation added to all but the first
                lines

        Returns:
            str: properly formatted
        """
        raise NotImplementedError("format is an abstract method")

    def update_parameters(self, params):
        """"""
        raise NotImplementedError("update_parameters is an abstract method")

    def update_return_type(self, ret_name, ret_type,
                           default_description="Description",
                           keyword="return"):
        """"""
        raise NotImplementedError("update_return_type is an abstract method")


    def update_attributes(self, attribs, alpha_order=True):
        """
        Args:
            params (OrderedDict): params objects keyed by their names
        """
        raise NotImplementedError("update_attributes is an abstract method")

    def update_exceptions(self, attribs, alpha_order=True):
        """
        Args:
            params (OrderedDict): params objects keyed by their names
        """
        raise NotImplementedError("update_exceptions is an abstract method")

    def add_dummy_returns(self, name, typ, description):
        raise NotImplementedError("add_dummy_returns is an abstract method")

    def finalize_section(self, heading, text):
        """
        Args:
            heading (type): Description
            text (type): Description
        """
        section = self.SECTION_STYLE(heading, text)
        self.sections[section.alias] = section

    def get_section(self, section_name):
        if section_name in self.sections:
            return self.sections[section_name]
        elif section_name in self.SECTION_STYLE.ALIASES:
            alias = self.SECTION_STYLE.resolve_alias(section_name)
            if alias in self.sections:
                return self.sections[alias]
        raise KeyError("Section '{0}' not found".format(section_name))

    def pop_section(self, section_name):
        if section_name in self.sections:
            return self.sections.pop(section_name)
        elif section_name in self.SECTION_STYLE.ALIASES:
            alias = self.SECTION_STYLE.resolve_alias(section_name)
            if alias in self.sections:
                return self.sections.pop(alias)
        raise KeyError("Section '{0}' not found".format(section_name))

    def insert_section(self, section_name, section):
        if section.heading != section_name:
            section.heading = section_name
        self.sections[section_name] = section

    def section_exists(self, section_name):
        """returns True iff section exists, and was finalized"""
        sec = None
        if section_name in self.sections:
            sec = self.sections[section_name]
        elif section_name in self.SECTION_STYLE.ALIASES:
            alias = self.SECTION_STYLE.resolve_alias(section_name)
            if alias in self.sections:
                sec = self.sections[alias]

        if sec is not None:
            return True
        return False


class NapoleonDocstring(Docstring):  # pylint: disable=abstract-method
    """Styles understood by napoleon, aka. Google/Numpy"""
    STYLE_NAME = "napoleon"

    TEMPLATE = OrderedDict([("Summary", None),
                            ("Parameters", None),
                            ("Keyword Arguments", None),
                            ("Returns", None),
                            ("Yields", None),
                            ("No Longer Returned", None),
                            ("No Longer Yielded", None),
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

    @staticmethod
    def _extract_section_name(sec_re_result):
        return sec_re_result.strip()

    def _parse(self, s):
        """
        Args:
            s (type): Description
        """
        logger.info("[NapoleonDocstring] starts parsing text")

        self.trailing_newlines = count_trailing_newlines(s)
        s = dedent_docstr(s)

        sec_starts = [(m.start(), m.end(), m.string[m.start():m.end()])
                      for m in re.finditer(self.SECTION_RE, s, re.MULTILINE)]

        sec_starts.insert(0, (0, 0, "Summary"))
        sec_starts.append((len(s), len(s), ""))

        for current_sec, next_sec in zip(sec_starts[:-1], sec_starts[1:]):
            sec_name = self._extract_section_name(current_sec[2])
            sec_body = s[current_sec[1]:next_sec[0]]
            self.finalize_section(sec_name, sec_body)

    @staticmethod
    def _format_section_text(heading, body):
        raise NotImplementedError("This is an abstract method")

    def format(self, top_indent):
        """
        Args:
            top_indent (type): Description

        """
        logger.info("[NapoleonDocstring] starts formatting")

        s = ""
        if self.section_exists("Summary"):
            sec_text = self.get_section("Summary").text
            if sec_text.strip():
                s += with_bounding_newlines(sec_text, nleading=0, ntrailing=1)

        for _, section in islice(self.sections.items(), 1, None):
            if section is None:
                continue

            sec_body = indent_docstr(section.text, section.section_indent, n=0)
            sec_text = self._format_section_text(section.heading, sec_body)
            s += with_bounding_newlines(sec_text, nleading=1, ntrailing=1)

        if self.trailing_newlines:
            s = with_bounding_newlines(s, ntrailing=self.trailing_newlines)
        s = indent_docstr(s, top_indent)

        return s

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
            if self.section_exists(_secname):
                _other.append(self.get_section(_secname))
        other_sections = _other

        if alpha_order:
            sorted_params = OrderedDict()
            for k in sorted(list(params.keys()), key=str.lower):
                sorted_params[k] = params[k]
            params = sorted_params

        current_dict = self.get_section(sec_name).args

        # go through params in the order of the function declaration
        # and cherry-pick from current_dict if there's already a description
        # for that parameter
        tags_seen = dict()
        new = OrderedDict()
        for name, param in params.items():
            if name in current_dict:
                def_param = param
                param = current_dict.pop(name)

                if param.tag in tags_seen:
                    param = None
                else:
                    tags_seen[param.tag] = True

                # update the type if annotated
                if def_param.annotated:
                    param.types = def_param.types

            else:
                # if param is in one of the 'other sections', then don't
                # worry about it
                for sec in other_sections:
                    if name in sec.args:
                        # update the type if the annotated
                        if param.annotated:
                            sec.args[name].types = param.types
                        # now ignore it
                        param = None
            if param:
                new[name] = param

        # add description only parameters back in
        for key, param in current_dict.items():
            if param.descr_only:
                # param.description = '\n' + param.description
                new[key] = current_dict.pop(key)

        # not sure when this guy gets created
        if '' in current_dict:
            del current_dict['']

        # go through params that are no linger in the arguments list and
        # move them from the Parameters section of the docstring to the
        # deleted parameters section
        if len(current_dict):
            del_sec_name = del_prefix + sec_name
            del_sec_alias = del_prefix + sec_alias
            logger.warn("killing parameters named: {}".format(current_dict.keys()))
            # TODO: put a switch here for other bahavior?
            if not self.section_exists(self.SECTION_STYLE.resolve_alias(del_sec_name)):
                self.finalize_section(del_sec_name, "")

            deled_params = self.get_section(del_sec_name)
            deleted_tags = dict()
            for key, val in current_dict.items():
                if key in deled_params.args:
                    logger.warn("Stronger Warning: Killing old deleted param: "
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
        logger.info("[NapoleonDocstring] update parameters")
        other_sections = ['Other Parameters', 'Keyword Parameters']
        self._update_section(params, "Parameters", self.PREFERRED_PARAMS_ALIAS,
                             other_sections=other_sections)

    def update_return_type(self, ret_name, ret_type,
                           default_description="Description",
                           keyword="return", del_prefix="No Longer "):
        """"""
        logger.info("[NapoleonDocstring] update return type")

        if keyword == "yield":
            sec_name = "Yields"
        elif keyword == "return":
            sec_name = "Returns"
        else:
            logger.debug("Unknown return keyword: '{}'".format(keyword))

            for std_ret_name in ("Yields", "Returns"):
                if self.section_exists(std_ret_name):
                    del_sec_name = del_prefix + std_ret_name
                    del_sec_alias = self.SECTION_STYLE.resolve_alias(del_sec_name)
                    if not self.section_exists(del_sec_alias):
                        self.finalize_section(del_sec_alias, "")

                    del_sec = self.get_section(del_sec_alias)

                    sec = self.pop_section(std_ret_name)
                    del_sec.args = sec.args

            return

        if not self.section_exists(sec_name):
            # see if a section exists from another keyword, ie, maybe
            # this function used to return, but now it yields
            for std_ret_name in ("Yields", "Returns"):
                if self.section_exists(std_ret_name):
                    # necessary to recreate completly the section
                    # in order to use the right parser and formatter
                    logger.debug("old return section exists : '{}'".format(std_ret_name))
                    old_sec = self.pop_section(std_ret_name)

                    self.finalize_section(sec_name, "")
                    new_sec = self.get_section(sec_name)
                    new_sec.args = old_sec.args

                    self.insert_section(sec_name, new_sec)
                    break

        if self.section_exists(sec_name):
            sec = self.get_section(sec_name)

            if sec.args and ret_type:
                p0 = next(iter(sec.args.values()))
                if p0.descr_only:
                    p0.description = ret_type
                elif p0.types:
                    p0.types = ret_type
                elif p0.names:
                    p0.names = [ret_type]
            elif ret_name or ret_type:
                description = default_description
                sec.args = OrderedDict()
                if ret_name:
                    sec.args[ret_name] = Parameter([ret_name], ret_type, description)
                else:
                    sec.args[ret_type] = Parameter([ret_type], "", description)
            else:
                # and i ask myself, how did i get here?
                pass
        else:
            self.finalize_section(sec_name, "")
            sec = self.get_section(sec_name)
            ret_type = ret_type if ret_type != "" else "${NUMBER:TYPE}"
            sec.args = OrderedDict()
            sec.args[ret_type] = Parameter([ret_type], "", default_description)


    def update_attributes(self, attribs, alpha_order=True):
        """
        Args:
            params (OrderedDict): params objects keyed by their names
        """
        logger.info("[NapoleonDocstring] update attributes")
        self._update_section(attribs, "Attributes", alpha_order=alpha_order)

    def update_exceptions(self, attribs, alpha_order=True):
        """
        Args:
            params (OrderedDict): params objects keyed by their names
        """
        logger.info("[NapoleonDocstring] update exceptions")
        self._update_section(attribs, "Raises", del_prefix="No Longer ",
                             alpha_order=alpha_order)

    def add_dummy_returns(self, name, typ, description):
        # No longer used??
        if not self.section_exists("Returns"):
            sec = self.SECTION_STYLE("Returns")
            if name:
                sec.args = {name: Parameter([name], typ, description)}
            else:
                sec.args = {typ: Parameter([typ], "", description)}
            self.sections["Returns"] = sec


class GoogleDocstring(NapoleonDocstring):
    """"""
    STYLE_NAME = "google"
    SECTION_STYLE = GoogleSection
    SECTION_RE = r"^[A-Za-z0-9][A-Za-z0-9 \t]*:\s*$\r?\n?"
    PREFERRED_PARAMS_ALIAS = "Args"

    @classmethod
    def detect_style(cls, docstr):
        """"""
        m = re.search(cls.SECTION_RE, docstr, re.MULTILINE)
        return m is not None

    @staticmethod
    def _extract_section_name(sec_re_result):
        return sec_re_result.strip().rstrip(':').rstrip()

    @staticmethod
    def _format_section_text(heading, body):
        return "{0}:\n{1}".format(heading, body)


class NumpyDocstring(NapoleonDocstring):
    """"""
    STYLE_NAME = "numpy"
    SECTION_STYLE = NumpySection
    SECTION_RE = r"^([A-Za-z0-9][A-Za-z0-9 \t]*)\s*\n-+\s*?$\r?\n?"
    PREFERRED_PARAMS_ALIAS = "Parameters"

    @classmethod
    def detect_style(cls, docstr):
        """"""
        m = re.search(cls.SECTION_RE, docstr, re.MULTILINE)
        return m is not None

    @staticmethod
    def _extract_section_name(sec_re_result):
        return sec_re_result.strip().rstrip('-').rstrip()

    @staticmethod
    def _format_section_text(heading, body):
        return "{0}\n{1}\n{2}".format(heading, "-" * len(heading), body)


STYLE_LOOKUP = OrderedDict([('numpy', NumpyDocstring),
                            ('google', GoogleDocstring)])

##
## EOF
##
