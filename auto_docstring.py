# -*- coding: utf-8 -*-
"""Business end of the AutoDocstring plugin"""

import os
import re
from textwrap import dedent
from string import whitespace

import sublime
import sublime_plugin


_simple_decl_re = r"^[^\S\n]*(def|class)\s+(\S+)\s*\(([\s\S]*?)\)\s*:"


def find_preceeding_declaration(defs, view, region):
    """Find declaration immediately preceeding the cursor

    Parameters:
        defs: list of all valid declarations (as regions)
        view: current view in which to search
        region: region of the current selection

    Returns:
        (region, not_found_flag)

        region: Region of preceeding declaration
        not_found_flag: True if no declaration was found
    """
    preceeding_defs = [d for d in defs if d.a <= region.a]
    target = None

    # for bypassing closures... as in, find the function that the
    # selection actually belongs to, don't just pick the first
    # preceeding "def" since it could be a closure
    for d in reversed(preceeding_defs):
        is_closure = False
        block = view.substr(sublime.Region(view.line(d).a,
                                           view.line(region).b))
        block = dedent(block)

        if block[0] in whitespace:
            is_closure = True
        else:
            for line in block.splitlines()[1:]:
                if len(line) > 0 and line[0] not in whitespace:
                    is_closure = True
                    break

        if not is_closure:
            target = d
            break

    if target is None:
        return sublime.Region(0, 0), True
    else:
        return target, False

def get_indentation(view, target):
    """Get indentation of a declaration and its body

    Parameters:
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
            single_indent = ""
        body_indent_txt = def_indent_txt + single_indent

    return def_indent_txt, body_indent_txt, has_indented_body

def get_docstring(view, edit, target):
    """Find a declaration's docstring

    This will return a docstring even if it has to write one
    into the buffer. The idea is that all the annoying indentation
    discovery will be consolidated here, so in the future, all we
    have to do is run a replace on an existing docstring.

    Note:
        If no docstring exists, this will edit the buffer
        to add one.

    Parameters:
        view: current view
        target: region of the declaration of interest

    Returns:
        (whole_region, docstr_region, style, new)

        whole_region: Region of entire docstring (including quotes)
        docstr_region: Region of docstring excluding quotes
        style: the character marking the ends of the docstring,
            will be one of [\""", ''', ", ']
        new: True if we inserted a new docstring
    """
    target_end_lineno, _ = view.rowcol(target.b)
    module_level = (target_end_lineno == 0)

    # exclude the shebang line by saying it's the declaration
    if module_level and view.substr(view.line(target)).startswith("#!"):
        target = view.line(0)
    search_start = target.b

    next_chars_reg = view.find(r"\S{1,3}", search_start)
    next_chars = view.substr(next_chars_reg)

    # hack for if there is a comment at the end of the declaration
    if view.rowcol(next_chars_reg.a)[0] == target_end_lineno and \
       next_chars[0] == '#' and not module_level:
        search_start = view.line(target.b).b
        next_chars_reg = view.find(r"\S{1,3}", search_start)
        next_chars = view.substr(next_chars_reg)

    if view.rowcol(next_chars_reg.a)[0] == target_end_lineno:
        same_line = True
    else:
        same_line = False

    style = None
    whole_region = None
    docstr_region = None

    if next_chars in ['"""', "'''"]:
        style = next_chars
    elif len(next_chars) > 0 and next_chars[0] in ['"', "'"]:
        style = next_chars[0]

    if style:
        docstr_end = view.find(r"(?<!\\){0}".format(style), next_chars_reg.b)
        if docstr_end.a < next_chars_reg.a:
            print("Autodocstr: oops, existing docstring on line",
                  target_end_lineno, "has no end?")
            return None, None, None, None

        whole_region = sublime.Region(next_chars_reg.a, docstr_end.b)
        docstr_region = sublime.Region(next_chars_reg.a + len(style),
                                       docstr_end.a)
        new = False
    else:
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

        stub = "{0}{1}{2} {2}{3}".format(prefix, body_indent_txt, style, suffix)
        view.replace(edit, sublime.Region(a, b), stub)

        whole_region = view.find("{0} {0}".format(style), target.b,
                                 sublime.LITERAL)
        docstr_region = sublime.Region(whole_region.a + len(style),
                                       whole_region.b - len(style))
        new = True

    return whole_region, docstr_region, style, new


class AutoDocstringCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        """Insert/Revise docstring for the scope of the cursor location"""
        view = self.view

        # bail if not a python file (i guess cython too)
        filename = self.view.file_name()
        if filename:
            _, ext = os.path.splitext(filename)
        else:
            ext = ""
        syntax = view.settings().get('syntax')
        if not ("Python" in syntax or "Cython" in syntax or
                ext in ['.py', '.pyx', '.pxd']):
            return

        # find all complete function definitions
        defs = self.view.find_all(_simple_decl_re)
        # now prune out definitions found in comments / strings
        _defs = []
        for d in defs:
            scope_name = view.scope_name(d.a)
            if not ("comment" in scope_name or "string" in scope_name):
                _defs.append(d)
        defs = _defs

        # go over each region in the selection
        for region in view.sel():
            target, _module_flag = find_preceeding_declaration(defs, view, region)

            # -> pull out docstring region
            _, old_docstr_region, _, _ = get_docstring(view, edit, target)

            # TODO: parse existing docstring into meta data
            # decl = Declaration(target)  # put into class?
            if not _module_flag:
                decl_str = view.substr(target)
                typ, name, args = re.match(_simple_decl_re, decl_str).groups()  # pylint: disable=unused-variable
            else:
                decl_str = None
                typ, name, args = None, None, None

            # TODO: modify meta data for changes to parameters

            # TODO: create new docstring from meta
            _, body_indent_txt, _ = get_indentation(view, target)
            new_docstr = ('ShortDescription\n\n'
                          '{0}LongDescription\n'
                          '{0}'.format(body_indent_txt))

            # -> replace old docstring with the new docstring
            view.replace(edit, old_docstr_region, new_docstr)

        return None

##
## EOF
##
