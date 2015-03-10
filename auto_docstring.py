# -*- coding: utf-8 -*-
"""Business end of the AutoDocstring plugin"""

# TODO: parse declarations better
# TODO: custom indentation on parameters
# TODO: check other and kwargs on update_parameters
# TODO: detect first_space used in the current docstring?

import os
import re
from textwrap import dedent
from string import whitespace
from collections import OrderedDict
import ast

import sublime
import sublime_plugin

from . import docstring_styles

_SETTINGS_FNAME = "AutoDocstring.sublime-settings"
_simple_decl_re = r"^[^\S\n]*(def|class)\s+(\S+)\s*\(([\s\S]*?)\)\s*:"


def find_all_declarations(view, include_module=False):
    """Find all complete function/class declarations

    Args:
        view: current ST view
        include_module (bool): whether or not to include first
            character of file for the module docstring

    Returns:
        list: the ST regions of all the declarations, from
            'def'/'class' to the ':' inclusive.
    """
    defs = view.find_all(_simple_decl_re)
    # now prune out definitions found in comments / strings
    _defs = []

    if include_module:
        _defs.append(sublime.Region(0, 0))

    for d in defs:
        scope_name = view.scope_name(d.a)
        if not ("comment" in scope_name or "string" in scope_name):
            _defs.append(d)
    return _defs

def find_preceeding_declaration(view, defs, region):
    """Find declaration immediately preceeding the cursor

    Args:
        view: current view in which to search
        defs: list of all valid declarations (as regions)
        region: region of the current selection

    Returns:
        region: Region of preceeding declaration or None
    """
    preceeding_defs = [d for d in defs if d.a <= region.a]
    # print("PRECEEDING_DEFS", preceeding_defs)
    target = None

    # for bypassing closures... as in, find the function that the
    # selection actually belongs to, don't just pick the first
    # preceeding "def" since it could be a closure
    for d in reversed(preceeding_defs):
        is_closure = False
        block = view.substr(sublime.Region(view.line(d).a,
                                           view.line(region).b))
        block = dedent(block)

        if len(block) == 0:
            raise NotImplementedError("Shouldn't be here?")
        elif d.a == d.b == 0:
            # in case d is region(0, 0), aka module level
            is_closure = False
        elif block[0] in whitespace:
            # print("block 0 is whitespace")
            is_closure = True
        else:
            for line in block.splitlines()[1:]:
                if len(line) > 0 and line[0] not in whitespace:
                    # print("line[0] not whitespace:", line)
                    is_closure = True
                    break

        if not is_closure:
            target = d
            break

    return target

def get_indentation(view, target):
    """Get indentation of a declaration and its body

    Args:
        view: current view
        target: region of the declaration of interest

    Returns:
        (decl_indent, body_indent, has_indented_body)
        decl_indent (str): indent of declaration
        body_indent (str): indent of body
        has_indented_body (bool): True if there is already text at
            body's indentation level
    """
    def_level = view.indentation_level(target.a)
    def_indent_txt = view.substr(view.find(r"\s*", view.line(target.a).a))

    # get indentation of the first non-whitespace char after the declaration
    nextline = view.line(target.b).b
    next_char_reg = view.find(r"\S", nextline)
    body = view.substr(view.line(next_char_reg))
    body_level = view.indentation_level(next_char_reg.a)
    body_indent_txt = body[:len(body) - len(body.lstrip())]

    # if no body text yet, attempt to auto-discover indentation
    if body_level > def_level:
        has_indented_body = True
    else:
        has_indented_body = False
        try:
            single_indent = def_indent_txt[:len(def_indent_txt) // def_level]
        except ZeroDivisionError:
            single_indent = "    "
        body_indent_txt = def_indent_txt + single_indent

    return def_indent_txt, body_indent_txt, has_indented_body

def get_docstring(view, edit, target):
    """Find a declaration's docstring

    This will return a docstring even if it has to write one
    into the buffer. The idea is that all the annoying indentation
    discovery will be consolidated here, so in the future, all we
    have to do is run a replace on an existing docstring.

    Args:
        view: current view
        edit (sublime.Edit or None): ST edit object for inserting
            a new docstring if one does not already exist. None
            means "don't edit the buffer"
        target: region of the declaration of interest

    Returns:
        (whole_region, docstr_region, style, new)

        whole_region: Region of entire docstring (including quotes)
        docstr_region: Region of docstring excluding quotes
        style: the character marking the ends of the docstring,
            will be one of [\""", ''', ", ']
        new: True if we inserted a new docstring

    Note:
        If no docstring exists, this will edit the buffer
        to add one if a sublime.Edit object is given.
    """
    target_end_lineno, _ = view.rowcol(target.b)
    module_level = (target_end_lineno == 0)

    # exclude the shebang line / coding line
    # by saying they're the declaration
    if module_level:
        cnt = -1
        while True:
            line = view.substr(view.line(cnt + 1))
            if line.startswith("#!") or line.startswith("# -*-"):
                cnt += 1
            else:
                break
        if cnt >= 0:
            target = sublime.Region(view.line(0).a, view.line(cnt).b)
    search_start = target.b

    next_chars_reg = view.find(r"\S{1,4}", search_start)
    next_chars = view.substr(next_chars_reg)

    # hack for if there is a comment at the end of the declaration
    if view.rowcol(next_chars_reg.a)[0] == target_end_lineno and \
       next_chars[0] == '#' and not module_level:
        search_start = view.line(target.b).b
        next_chars_reg = view.find(r"\S{1,4}", search_start)
        next_chars = view.substr(next_chars_reg)

    if view.rowcol(next_chars_reg.a)[0] == target_end_lineno:
        same_line = True
    else:
        same_line = False

    style = None
    whole_region = None
    docstr_region = None

    # for raw / unicode literals
    if next_chars.startswith(('r', 'u')):
        literal_prefix = next_chars[0]
        next_chars = next_chars[1:]
    else:
        literal_prefix = ""

    if next_chars.startswith(('"""', "'''")):
        style = next_chars[:3]
    elif next_chars.startswith(('"', "'")):
        style = next_chars[0]

    if style:
        # there exists a docstring, get its region
        next_chars_reg.b = next_chars_reg.a + len(literal_prefix) + len(style)
        docstr_end = view.find(r"(?<!\\){0}".format(style), next_chars_reg.b)
        if docstr_end.a < next_chars_reg.a:
            print("Autodocstr: oops, existing docstring on line",
                  target_end_lineno, "has no end?")
            return None, None, None, None

        whole_region = sublime.Region(next_chars_reg.a, docstr_end.b)
        docstr_region = sublime.Region(next_chars_reg.b, docstr_end.a)
        new = False
    elif edit is None:
        # no docstring exists, and don't make one
        return None, None, None, False
    else:
        # no docstring exists, but make / insert one
        style = '"""'

        _, body_indent_txt, has_indented_body = get_indentation(view, target)

        if same_line:
            # used if the function body starts on the same line as declaration
            a = target.b
            b = next_chars_reg.a
            prefix, suffix = "\n", "\n{0}".format(body_indent_txt)
            # hack for modules that start with comments
            if module_level:
                prefix = ""
        elif has_indented_body:
            # used if there is a function body at the next indent level
            a = view.full_line(target.b).b
            b = view.find(r"\s*", a).b
            prefix, suffix = "", "\n{0}".format(body_indent_txt)
        else:
            # used if there is no pre-existing indented text
            a = view.full_line(target.b).b
            b = a
            prefix, suffix = "", "\n"
            # hack if we're at the end of a file w/o a final \n
            if not view.substr(view.full_line(target.b)).endswith("\n"):
                prefix = "\n"

        stub = "{0}{1}{2}<FRESHLY_INSERTED>{2}{3}" \
               "".format(prefix, body_indent_txt, style, suffix)
        view.replace(edit, sublime.Region(a, b), stub)

        whole_region = view.find("{0}<FRESHLY_INSERTED>{0}".format(style),
                                 target.b, sublime.LITERAL)
        docstr_region = sublime.Region(whole_region.a + len(style),
                                       whole_region.b - len(style))
        new = True

    return whole_region, docstr_region, style, new

def is_python_file(view):
    """Check if view is a python file

    Checks file extension and syntax highlighting

    Args:
        view: current ST view

    Returns:
        (str, None): "python, "cython", or None if neither
    """
    filename = view.file_name()
    if filename:
        _, ext = os.path.splitext(filename)
    else:
        ext = ""
    if ext in ['.py', '.pyx', '.pxd']:
        return True

    syntax = view.settings().get('syntax')
    if "Python" in syntax or "Cython" in syntax:
        return True

    return False

def get_desired_style(view, default="google"):
    """Get desired style / auto-discover from view if requested

    Args:
        view: ST view
        default (type, optional): Description

    Returns:
        subclass of docstring_styles.Docstring, for now only
        Google or Numpy
    """
    s = sublime.load_settings(_SETTINGS_FNAME)
    style = s.get("style", "auto_google").lower()

    # do we want to auto-discover from the buffer?
    # TODO: cache auto-discovery using buffer_id?
    if style.startswith('auto'):
        try:
            default = style.split("_")[1]
        except IndexError:
            # default already set to google by kwarg
            pass

        defs = find_all_declarations(view, True)
        for d in defs:
            docstr_region = get_docstring(view, None, d)[1]
            if docstr_region is None:
                typ = None
            else:
                # print("??", docstr_region)
                docstr = view.substr(docstr_region)
                typ = docstring_styles.detect_style(docstr)

            if typ is not None:
                # print("Docstring style auto-detected:", typ)
                return typ

        return docstring_styles.STYLE_LOOKUP[default]
    else:
        return docstring_styles.STYLE_LOOKUP[style]

def parse_function_params(s, default_description="Description"):
    """Parse function parameters into an OrderedDict of Parameters

    Args:
        s (str): everything in the parenthesis of a function
            declaration
        default_description (str): default text

    Returns:
        OrderedDict containing Parameter instances
    """
    # Note: use of the ast here is all python3 specific... the attributes
    # and names of items in the ast have changed significantly

    # pretend the args go to a lambda func, then get an ast for the lambda
    tree = ast.parse("lambda {0}: None".format(s), mode='eval')
    arg_ids = [arg.arg for arg in tree.body.args.args]
    default_nodes = tree.body.args.defaults

    # match up default values with keyword arguments from the ast
    defaults = ["type"] * len(arg_ids)
    if len(default_nodes):
        defaults[-len(default_nodes):] = default_nodes

    if tree.body.args.vararg:
        try:
            name = tree.body.args.vararg.arg
        except AttributeError:
            name = tree.body.args.vararg
        arg_ids.append("*{0}".format(name))
        defaults.append(None)
    if tree.body.args.kwarg:
        try:
            name = tree.body.args.kwarg.arg
        except AttributeError:
            name = tree.body.args.kwarg
        arg_ids.append("**{0}".format(name))
        defaults.append(None)

    if len(arg_ids) and (arg_ids[0] == "self" or arg_ids[0] == "cls"):
        arg_ids.pop(0)
        defaults.pop(0)

    # now fill a params dict
    params = OrderedDict()
    for name, default in zip(arg_ids, defaults):
        default_class_name = default.__class__.__name__
        if default is None:
            paramtype = None
        elif default == "type":
            paramtype = default
        elif default_class_name == "NameConstant":
            if default.value is None:
                paramtype = "type"
            else:
                paramtype = default.value.__class__.__name__
        elif default_class_name == "Name":
            if default.id in ["True", "False"]:
                paramtype = "bool"
            else:
                paramtype = "type"
        elif default_class_name == "Num":
            paramtype = default.n.__class__.__name__
        else:
            paramtype = default_class_name.lower()
        param = docstring_styles.Parameter(name, paramtype,
                                           default_description)
        params[name] = param

    return params

def autodoc(view, edit, region, all_defs, desired_style, file_type):
    """actually do the business of auto-documenting

    Args:
        view: current view
        edit: current edit context
        region: region to look backward from to find a
            definition, usually gotten with view.sel()
        all_defs (list): list of declaration regions representing
            all valid declarations
        desired_style (class): subclass of Docstring
        file_type (str): 'python' or 'cython', not yet used
    """
    target = find_preceeding_declaration(view, all_defs, region)
    # print("TARGET::", target)
    _module_flag = (target.a == target.b == 0)
    # print("-> found target", target, _module_flag)

    _, old_docstr_region, _, _ = get_docstring(view, edit, target)

    # TODO: parse existing docstring into meta data
    old_docstr = view.substr(old_docstr_region)
    settings = sublime.load_settings(_SETTINGS_FNAME)
    template_order = settings.get("template_order", False)
    ds = docstring_styles.make_docstring_obj(old_docstr, desired_style,
                                             template_order=template_order)

    # get declaration info
    if not _module_flag:
        decl_str = view.substr(target)
        typ, name, args = re.match(_simple_decl_re, decl_str).groups()  # pylint: disable=unused-variable
        if typ == "def":
            params = parse_function_params(args)
            ds.update_parameters(params)

    try:
        if ds.sections["Summary"].text.strip() == "<FRESHLY_INSERTED>":
            ds.sections["Summary"] = ds.SECTION_STYLE("Summary", "Summary")
    except KeyError:
        pass

    # -> create new docstring from meta
    new_ds = desired_style(ds)

    # -> replace old docstring with the new docstring
    _, body_indent_txt, _ = get_indentation(view, target)
    new_docstr = new_ds.format(body_indent_txt)
    view.replace(edit, old_docstr_region, new_docstr)


class AutoDocstringCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        """Insert/Revise docstring for the scope of the cursor location

        Args:
            edit (type): Description
        """
        print("-> AutoDocstring")
        view = self.view

        file_type = is_python_file(view)
        if not file_type:
            return None

        desired_style = get_desired_style(view)

        defs = find_all_declarations(view, True)
        # print("DEFS::", defs)

        for region in view.sel():
            autodoc(view, edit, region, defs, desired_style, file_type)
        print("-> AutoDocstring done")
        return None


class AutoDocstringAllCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        """Insert/Revise docstrings whole module

        Args:
            edit (type): Description
        """
        print("-> AutoDocstringAll")
        view = self.view

        file_type = is_python_file(view)
        if not file_type:
            return None

        desired_style = get_desired_style(view)

        defs = find_all_declarations(view, True)
        for i in range(len(defs)):
            defs = find_all_declarations(view, True)
            d = defs[i]
            region = sublime.Region(d.b, d.b)
            autodoc(view, edit, region, defs, desired_style, file_type)
        print("-> AutoDocstringAll done")
        return None

##
## EOF
##
