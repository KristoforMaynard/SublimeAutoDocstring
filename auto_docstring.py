# -*- coding: utf-8 -*-
"""Business end of the AutoDocstring plugin"""

# TODO: break this module up into smaller pieces
# TODO: custom indentation on parameters
# TODO: check other and kwargs on update_parameters
# TODO: detect first_space used in the current docstring?

import os
import re
from textwrap import dedent
from string import whitespace
from collections import OrderedDict
from itertools import count
import ast

import sublime
import sublime_plugin

from .autodocstring_logging import logger
from . import docstring_styles
from . import dparse


__class_re = r"(class)\s+([^\s\(\):]+)\s*(\(([\s\S]*?)\))?"
__func_re = r"(?:async\s*)?(def)\s+([^\s\(\):]+)\s*\(([\s\S]*?)\)\s*(->.*?)?"

_all_decl_re = r"^[^\S\n]*({0}|{1})\s*:".format(__class_re, __func_re)
_class_decl_re = r"^[^\S\n]*{0}\s*:".format(__class_re)
_func_decl_re = r"^[^\S\n]*{0}\s*:".format(__func_re)


class Settings(object):
    def __init__(self, view=None):
        _sname = "AutoDocstring"
        _sfile = "AutoDocstring.sublime-settings"
        self.project_settings = {}
        if view:
            proj_dat = view.window().project_data()
            if proj_dat:
                self.project_settings = proj_dat.get(_sname, {})
        self.plugin_settings = sublime.load_settings(_sfile)

    def get(self, key, default=None):
        val = self.plugin_settings.get(key, default)
        val = self.project_settings.get(key, val)
        return val

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
    defs = view.find_all(_all_decl_re)
    # now prune out definitions found in comments / strings
    _defs = []

    if include_module:
        _defs.append(sublime.Region(0, 0))

    for d in defs:
        scope_name = view.scope_name(d.a)
        if not ("comment" in scope_name or "string" in scope_name):
            _defs.append(d)
    return _defs

def find_preceding_declaration(view, defs, region):
    """Find declaration immediately preceding the cursor

    Args:
        view: current view in which to search
        defs: list of all valid declarations (as regions)
        region: region of the current selection

    Returns:
        region: Region of preceding declaration or None
    """
    preceding_defs = [d for d in defs if d.a <= region.a]
    logger.debug("PRECEDING_DEFS {}".format(preceding_defs))
    target = None

    # for bypassing closures... as in, find the function that the
    # selection actually belongs to, don't just pick the first
    # preceding "def" since it could be a closure
    for d in reversed(preceding_defs):
        is_closure = False
        block = view.substr(sublime.Region(view.line(d).a,
                                           view.line(region).b))
        block = dedent(block)

        if len(block) == 0:
            # happens on module level docstrings in modules that start
            # with a single blank line
            is_closure = False
        elif d.a == d.b == 0:
            # in case d is region(0, 0), aka module level
            is_closure = False
        elif block[0] in whitespace:
            logger.debug("block 0 is whitespace")
            is_closure = True
        else:
            # ignore the whole declaration when determining closure-ness
            block_start = len(re.search(_all_decl_re, block).group(0))
            for line in block[block_start:].splitlines()[1:]:
                if len(line) > 0 and line[0] not in whitespace:
                    logger.debug("line[0] not whitespace:", line)
                    is_closure = True
                    break

        if not is_closure:
            target = d
            break

    return target

def get_indentation(view, target, module_decl=False):
    """Get indentation of a declaration and its body

    Args:
        view: current view
        target: region of the declaration of interest
        module_decl (bool, optional): whether or not this is for
            doc'ing a module... changes default body_indent_txt

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
            if module_decl:
                single_indent = ""
            else:
                single_indent = "    "
        body_indent_txt = def_indent_txt + single_indent

    return def_indent_txt, body_indent_txt, has_indented_body

def get_docstring(view, edit, target, default_qstyle=None,
                  extra_class_newlines=True):
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
        extra_class_newlines (bool): class docstrings get an extra
            newline above and below, b/c PEP257. I find this
            unnecessary, but it's in a PEP, so it should at least
            be an option.

    Returns:
        (whole_region, docstr_region, qstyle, new)

        whole_region: Region of entire docstring (including quotes)
        docstr_region: Region of docstring excluding quotes
        qstyle: the character marking the ends of the docstring,
            will be one of [\"\"", ''', ", ']
        new: True if we inserted a new docstring

    Note:
        If no docstring exists, this will edit the buffer
        to add one if a sublime.Edit object is given.
    """
    target_end_lineno, _ = view.rowcol(target.b)
    module_level = (target.a == target.b == 0)

    # exclude the shebang line / coding line
    # by saying they're the declaration
    if module_level:
        cnt = -1
        while True:
            line = view.substr(view.line(cnt + 1))
            if (line.startswith("#!") or line.startswith("# -*-") or
                line.startswith("# pylint:")):  # pylint: disable=bad-continuation
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
       not module_level and next_chars and next_chars[0] == '#':
        search_start = view.line(target.b).b
        next_chars_reg = view.find(r"\S{1,4}", search_start)
        next_chars = view.substr(next_chars_reg)

    if next_chars and view.rowcol(next_chars_reg.a)[0] == target_end_lineno:
        same_line = True
    else:
        same_line = False

    qstyle = None
    whole_region = None
    docstr_region = None

    # for raw / unicode literals
    if next_chars.startswith(('r', 'u')):
        literal_prefix = next_chars[0]
        next_chars = next_chars[1:]
    else:
        literal_prefix = ""

    if next_chars.startswith(('"""', "'''")):
        qstyle = next_chars[:3]
    elif next_chars.startswith(('"', "'")):
        qstyle = next_chars[0]

    if qstyle:
        # there exists a docstring, get its region
        next_chars_reg.b = next_chars_reg.a + len(literal_prefix) + len(qstyle)
        docstr_end = view.find(r"(?<!\\){0}".format(qstyle), next_chars_reg.b)
        if docstr_end.a < next_chars_reg.a:
            logger.info("Autodocstr: oops, existing docstring on line",
                  target_end_lineno, "has no end?")
            return None, None, None, None, module_level

        whole_region = sublime.Region(next_chars_reg.a, docstr_end.b)
        docstr_region = sublime.Region(next_chars_reg.b, docstr_end.a)
        new = False

        # trim whitespace after docstring... having whitespace here seems
        # to mess with indentation for some reason
        if edit:
            after_quote_reg = sublime.Region(whole_region.b,
                                             view.line(whole_region.b).b)
            if len(view.substr(whole_region.b).strip()) == 0:
                view.replace(edit, after_quote_reg, "")
    elif edit is None:
        # no docstring exists, and don't make one
        return None, None, None, False, module_level
    else:
        # no docstring exists, but make / insert one
        qstyle = default_qstyle

        _, body_indent_txt, has_indented_body = get_indentation(view, target,
                                                                module_level)

        if module_level:
            # FIXME: whitespace is strange when inserting into a module that
            #        starts with 1-2 blank lines
            a, b = target.b, target.b
            prefix, suffix = "", ""
            if view.rowcol(a)[1] != 0:
                prefix = "\n"
            if same_line:
                suffix = "\n{0}".format(body_indent_txt)

            body_indent_txt = ""    # remove  whitespace added before module docstring
        elif same_line:
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

        if extra_class_newlines:
            if view.substr(target).lstrip().startswith('class'):
                prefix += '\n'
                suffix *= 2

        stub = "{0}{1}{2}<FRESHLY_INSERTED>{2}{3}" \
               "".format(prefix, body_indent_txt, qstyle, suffix)
        view.replace(edit, sublime.Region(a, b), stub)

        whole_region = view.find("{0}<FRESHLY_INSERTED>{0}".format(qstyle),
                                 target.b, sublime.LITERAL)
        docstr_region = sublime.Region(whole_region.a + len(qstyle),
                                       whole_region.b - len(qstyle))
        new = True

    return whole_region, docstr_region, qstyle, new, module_level

def get_whole_block(view, target):
    """Find a region of all the lines that make up a class / function

    Args:
        view (View): current view
        target (Region): region of the declaration of interest

    Returns:
        sublime.Region: all lines in the class / function
    """
    first_line = view.substr(view.line(target.a))
    leading_wspace = first_line[:len(first_line) - len(first_line.lstrip())]

    eoblock_row = None

    first_row = view.rowcol(target.a)[0]
    eof_row = view.rowcol(view.size())[0]
    for i in range(first_row + 1, eof_row + 1):
        line_tp0 = view.text_point(i, 0)
        line = view.substr(view.line(line_tp0)).rstrip()
        tp0_scope = view.scope_name(line_tp0)

        if not line or "comment" in tp0_scope or "string" in tp0_scope:
            continue

        if not (line.startswith(leading_wspace) and
                line[len(leading_wspace)] in " \t"):
            eoblock_row = i - 1
            break

    if eoblock_row is None:
        if "string" in view.scope_name(view.text_point(eof_row, 0)):
            raise RuntimeError("unclosed string literal in file")
        else:
            eoblock_row = eof_row

    block_region = sublime.Region(view.line(target.a).a,
                                  view.text_point(eoblock_row + 1, 0))
    return block_region

def find_all_in_region(view, reg, what, blacklist=None, flags=0):
    """
    Args:
        view (View): view to search in
        reg (Region or point): region to search in. If point, then
            search from that point to the end of the file
        what (str): a regex of the search
        blacklist (list of regions): regions to ignore
        flags (int): passed to :py:func:`view.find`

    Returns:
        list: list of regions that match `what`
    """
    if not isinstance(reg, sublime.Region):
        reg = sublime.Region(reg, view.size())
    if not blacklist:
        blacklist = []

    matches = []

    p0 = reg.a
    while True:
        found_reg = view.find(what, p0, flags=flags)
        if found_reg.b == -1 or found_reg.a >= reg.b:
            break
        else:
            in_blacklist = False
            for bl_reg in blacklist:
                if bl_reg.intersects(found_reg):
                    in_blacklist = True
                    break

            if not in_blacklist:
                matches.append(found_reg)
            p0 = found_reg.b

    return matches

def get_all_blocks(view, reg, classes_only=False):
    """Find all functions / classes in a given region

    Args:
        view(View): current view
        reg(Region): region in which to search
        classes_only(bool): only search for classes, not functions

    Returns:
        list: of regions of the whole blocks
    """
    if not reg:
        reg = sublime.Region(0, view.size())

    if classes_only:
        nested_re = _class_decl_re
    else:
        nested_re = _all_decl_re

    nested_blocks = find_all_in_region(view, reg, nested_re)
    for i in range(len(nested_blocks) - 1, -1, -1):
        block = nested_blocks[i]
        scope_name = view.scope_name(block.a)
        if "comment" in scope_name or "string" in scope_name:
            nested_blocks.pop(i)
        else:
            whole_block = get_whole_block(view, block)
            nested_blocks[i] = whole_block
    return nested_blocks

def get_attr_type(value, default_type, existing_type):
    """Try to figure out type of attribute from declaration

    if existing_type != default_type, then existing_type is returned
    regardless of what's in this declaration

    Args:
        value (str): the right hand side of the equal sign
        default_type (str): default text for the type
        existing_type (str): if attr was already set, what was the
            type? Should equal defualt_type if the attr was not
            previously set

    Returns:
        str: string describing the type of the attribute
    """
    snippet_default = r"${{NUMBER:{0}}}".format(default_type)
    if existing_type not in [default_type, snippet_default]:
        return existing_type

    value = value.strip()
    try:
        ret = ast.literal_eval(value).__class__.__name__
        if ret == None.__class__.__name__:
            ret = default_type
    except ValueError:
        ret = default_type
    except SyntaxError:
        ret = default_type

    return ret

def get_desired_style(view, default="google", desire=None):
    """Get desired style / auto-discover from view if requested

    Args:
        view: ST view
        default (type, optional): Description
        desire (str, optional): if desire is a valid style, then
            always return that one

    Returns:
        subclass of docstring_styles.Docstring, for now only
        Google or Numpy
    """
    if desire and desire.lower() in docstring_styles.STYLE_LOOKUP:
        return docstring_styles.STYLE_LOOKUP[desire]

    s = Settings(view=view)
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
                #logger.debug("?? {}".format(docstr_region))
                docstr = view.substr(docstr_region)
                typ = docstring_styles.detect_style(docstr)

            if typ is not None:
                logger.debug("Docstring style auto-detected : '{}'".format(typ))
                return typ

        return docstring_styles.STYLE_LOOKUP[default]
    else:
        return docstring_styles.STYLE_LOOKUP[style]

def parse_function_params(s, ret_annotation, default_type, default_description,
                          optional_tag="optional"):
    """Parse function parameters into an OrderedDict of Parameters

    Args:
        s (str): everything in the parenthesis of a function
            declaration
        ret_annotation (str): return annotation if any
        default_type (str): default type text
        default_description (str): default text
        optional_tag (str): tag included with type for kwargs when
            they are created

    Returns:
        OrderedDict containing Parameter instances
    """
    # Note: this use of ast Nodes seems to work for python2.6 - python3.4,
    # but there is no guarentee that it'll continue to work in future versions

    # precondition default description for snippet use
    default_description = r"${{NUMBER:{0}}}".format(default_description)

    # pretend the args go to a lambda func, then get an ast for the lambda
    s = s.replace("\r\n", "")
    s = s.replace("\n", "")
    s = "def f({0}) {1}: pass".format(s, ret_annotation)
    _, params, ret_annotation = dparse.parse_funcdef(s)

    if params and params[0]['name'] in ['self', 'cls']:
        params = params[1:]

    # now fill a params dict
    params_dict = OrderedDict()
    # annotations = [None] * len(arg_ids)
    for i, param in enumerate(params):
        name = param['name']

        if param['annotation']:
            paramtype = param['annotation']
        elif param['is_vararg'] or param['is_kwarg']:
            paramtype = None
        elif param['default_type']:
            paramtype = param['default_type']
        else:
            paramtype = default_type

        if paramtype is not None:
            paramtype = r"${{NUMBER:{0}}}".format(paramtype)

        if optional_tag and param['is_optional'] and paramtype:
            paramtype += ", {0}".format(optional_tag)

        p = docstring_styles.Parameter([name], paramtype,
                                       default_description, tag=i,
                                       annotated=bool(param['annotation']))
        params_dict[name] = p
    return params_dict, ret_annotation

def parse_return_keyword(view, target):
    """Scan a function's code to look for how it returns

    Args:
        view (View): current view
        target (Region): region of the declaration of interest

    Returns:
        str: one of 'return' or 'yield'
    """
    whole_func = get_whole_block(view, target)
    func_region = sublime.Region(target.b, whole_func.b)

    blacklist = get_all_blocks(view, func_region, classes_only=False)

    # find all 'return' and 'yield' in function's code ignoring blacklist
    # (nested funcs / classes)
    ret_kw_regs = find_all_in_region(view, func_region, r"^\s*(return|yield)",
                                     blacklist=blacklist)

    for i in reversed(range(len(ret_kw_regs))):
        text = view.substr(ret_kw_regs[i])
        scope_name = view.scope_name(ret_kw_regs[i].a)

        if "string" in scope_name or "comment" in scope_name:
            ret_kw_regs.pop(i)

    if ret_kw_regs:
        last_kw_stripped = view.substr(ret_kw_regs[-1]).lstrip()
    else:
        last_kw_stripped = ''

    if last_kw_stripped.startswith('return'):
        ret = "return"
    elif last_kw_stripped.startswith('yield'):
        ret = "yield"
    else:
        logger.debug("Unknown return keyword '{}'".format(last_kw_stripped))
        ret = ""

    return ret

def parse_function_exceptions(view, target, default_description):
    """Scan a class' code and look for exceptions

    Args:
        view (View): current view
        target (Region): region of the declaration of interest
        default_description (str): default text

    Returns:
        OrderedDict containing Parameter instances
    """
    default_description = r"${{NUMBER:{0}}}".format(default_description)
    excepts = OrderedDict()

    whole_function = get_whole_block(view, target)
    func_region = sublime.Region(target.b, whole_function.b)
    blacklist = get_all_blocks(view, func_region, classes_only=False)

    e_regions = find_all_in_region(view, whole_function,
                                   r"^[^\S\n]*raise[^\S\n]+([^\s\(]+)",
                                   blacklist=blacklist)
    for e in e_regions:
        scope_name = view.scope_name(e.a)
        if "string" in scope_name or "comment" in scope_name:
            continue

        e_name = view.substr(e).strip()[len("raise"):].strip()
        if not e_name in excepts:
            excepts[e_name] = docstring_styles.Parameter([e_name], None,
                                                         default_description,
                                                         tag=len(excepts))
    return excepts

def parse_class_attributes(view, target, default_type, default_description):
    """Scan a class' code and look for attributes

    Args:
        view (View): current view
        target (Region): region of the declaration of interest
        default_type (str): default type text
        default_description (str): default text

    Returns:
        OrderedDict containing Parameter instances
    """
    # precondition description for snippet use
    default_description = r"${{NUMBER:{0}}}".format(default_description)

    attribs = OrderedDict()

    class_region = get_whole_block(view, target)

    # blacklist nested classes, as in, don't detect attributes of nested
    # classes
    body_region = sublime.Region(target.b, class_region.b)
    blacklist = get_all_blocks(view, body_region, classes_only=True)

    # find the attributes that are at the class' indent level, or are set
    # via. `self.*=*` in a method
    _, body_indent_txt, _ = get_indentation(view, target, module_decl=False)
    attr_re = (r"(^{0}([A-Za-z0-9_]+)|"
               r"^[^\S\n]*self\.([A-Za-z0-9_]+))\s*=".format(body_indent_txt))
    all_attr_regions = find_all_in_region(view, body_region, attr_re,
                                          blacklist=blacklist)

    for attr_reg in all_attr_regions:
        name = view.substr(attr_reg).split('=')[0].strip()
        scope_name = view.scope_name(attr_reg.a)
        if name.startswith('self.'):
            name = name[len('self.'):]
        if name.startswith('_'):
            continue
        if "string" in scope_name or "comment" in scope_name:
            continue

        # discover data type from declaration
        if name in attribs:
            existing_type = attribs[name].types
        else:
            existing_type = default_type
        value = view.substr(view.line(attr_reg.a)).split('=')[1]
        paramtype = get_attr_type(value, default_type, existing_type)

        if name in attribs:
            tag = attribs[name].tag
        else:
            tag = len(attribs)

        if not paramtype.startswith(r"${NUMBER:"):
            paramtype = r"${{NUMBER:{0}}}".format(paramtype)

        param = docstring_styles.Parameter([name], paramtype,
                                           default_description,
                                           tag=tag)
        attribs[name] = param

    return attribs

def parse_module_attributes(view, default_type, default_description):
    """Scan a module's code and look for attributes

    Args:
        view (View): current view
        target (Region): region of the declaration of interest
        default_type (str): default type text
        default_description (str): default text

    Returns:
        OrderedDict containing Parameter instances
    """
    # precondition description for snippet use
    default_description = r"${{NUMBER:{0}}}".format(default_description)

    attribs = OrderedDict()

    all_attr_regions = view.find_all(r"^([A-Za-z0-9_]+)\s*=")
    for attr_reg in all_attr_regions:
        name = view.substr(attr_reg).split('=')[0].strip()
        scope_name = view.scope_name(attr_reg.a)

        if name.startswith('_'):
            continue
        if "string" in scope_name or "comment" in scope_name:
            continue

        # discover data type from declaration
        if name in attribs:
            existing_type = attribs[name].types
        else:
            existing_type = default_type
        value = view.substr(view.line(attr_reg.a)).split('=')[1]
        paramtype = get_attr_type(value, default_type, existing_type)

        if name in attribs:
            tag = attribs[name].tag
        else:
            tag = len(attribs)

        if not paramtype.startswith(r"${NUMBER:"):
            paramtype = r"${{NUMBER:{0}}}".format(paramtype)
        param = docstring_styles.Parameter([name], paramtype,
                                           default_description,
                                           tag=tag)
        attribs[name] = param

    return attribs

def snipify(_words, _use_snippet=False):
    if _use_snippet and _words:
        _words = r"${{NUMBER:{0}}}".format(_words)
    return _words

def autodoc(view, edit, region, all_defs, desired_style, file_type,
            default_qstyle=None, update_only=False):
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
    settings = Settings(view=view)
    template_order = settings.get("template_order", False)
    optional_tag = settings.get("optional_tag", "optional")
    default_description = settings.get("default_description", "Description")
    default_return_name = settings.get("default_return_name", "")
    default_summary = settings.get("default_summary", "Summary")
    default_type = settings.get("default_type", "TYPE")
    use_snippet = settings.get("use_snippet", False)
    sort_class_attributes = settings.get("sort_class_attributes", True)
    sort_exceptions = settings.get("sort_exceptions", True)
    sort_module_attributes = settings.get("sort_module_attributes", True)
    start_with_newline = settings.get("start_with_newline", "")
    force_default_qstyle = settings.get("force_default_qstyle", True)
    extra_class_newlines = settings.get("extra_class_newlines", True)
    keep_previous = settings.get("keep_previous", False)
    if not default_qstyle or force_default_qstyle:
        default_qstyle = settings.get("default_qstyle", '"""')

    target = find_preceding_declaration(view, all_defs, region)
    logger.debug("TARGET:: {}".format(target))

    _module_flag = (target.a == target.b == 0)
    logger.debug("-> found target {} {}".format(target, _module_flag))

    _edit = None if update_only else edit
    old_ds_info = get_docstring(view, _edit, target,
                                default_qstyle=default_qstyle,
                                extra_class_newlines=extra_class_newlines)
    old_ds_whole_region, old_ds_region, quote_style, is_new, is_module_level = old_ds_info
    if update_only and old_ds_whole_region is None:
        return -1

    old_docstr = view.substr(old_ds_region)

    ds = docstring_styles.make_docstring_obj(old_docstr, desired_style,
                                             template_order=template_order)

    # if start_with_newline was given as a comma separated list of styles,
    # then turn that into a bool of whether or not ds.STYLE_NAME is in the
    # list
    try:
        start_with_newline = start_with_newline.split(',')
        start_with_newline = [s.strip().lower() for s in start_with_newline]
        start_with_newline = ds.STYLE_NAME in start_with_newline
    except AttributeError:
        # start_with_newline was probably given as a bool to affect all styles
        pass

    # get declaration info
    if _module_flag:
        if settings.get("inspect_module_attributes", True):
            attribs = parse_module_attributes(view, default_type,
                                              default_description)
            ds.update_attributes(attribs, alpha_order=sort_module_attributes)
    else:
        decl_str = view.substr(target).lstrip()

        if decl_str.startswith(('def', 'async')):
            typ, name, args, ret_ano = re.match(_func_decl_re, decl_str).groups()
            if not ret_ano:
                ret_ano = ""
        elif decl_str.startswith('class'):
            typ, name, _, args = re.match(_class_decl_re, decl_str).groups()
        else:
            raise RuntimeError

        if typ == "def":
            params, ret_ano = parse_function_params(args, ret_ano,
                                                    default_type,
                                                    default_description,
                                                    optional_tag=optional_tag)

            # prepare return name/type for new / updated returns section
            if is_new and name != "__init__":
                ret_name = default_return_name
                ret_type = ret_ano if ret_ano else default_type
            else:
                ret_name = ''
                ret_type = ret_ano if ret_ano else ''

            ret_name = snipify(ret_name, use_snippet)
            ret_type = snipify(ret_type, use_snippet)
            s_default_description = snipify(default_description, use_snippet)

            if settings.get("inspect_function_parameters", True):
                ds.update_parameters(params)
                ret_keyword = parse_return_keyword(view, target)
                ds.update_return_type(ret_name, ret_type,
                                      default_description=s_default_description,
                                      keyword=ret_keyword)
            if settings.get("inspect_exceptions", True):
                excepts = parse_function_exceptions(view, target,
                                                    default_description)
                ds.update_exceptions(excepts, alpha_order=sort_exceptions)
        elif typ == "class":
            if settings.get("inspect_class_attributes", True):
                attribs = parse_class_attributes(view, target, default_type,
                                                 default_description)
                ds.update_attributes(attribs, alpha_order=sort_class_attributes)

    if is_new:
        snippet_summary = ""
        if start_with_newline:
            snippet_summary += "\n"
        snippet_summary += r"${{NUMBER:{0}}}".format(default_summary)
        ds.finalize_section("Summary", snippet_summary)

    # -> create new docstring from meta
    new_ds = desired_style(ds)

    # -> replace old docstring with the new docstring
    if use_snippet or is_module_level:
        body_indent_txt = ""
    else:
        _, body_indent_txt, _ = get_indentation(view, target, _module_flag)

    new_docstr = new_ds.format(body_indent_txt) + body_indent_txt

    # replace ${NUMBER:.*} with ${[0-9]+:.*}
    i = 1
    _nstr = r"${NUMBER:"
    while new_docstr.find(_nstr) > -1:
        if use_snippet:
            # for snippets
            new_docstr = new_docstr.replace(_nstr, r"${{{0}:".format(i), 1)
        else:
            # remove snippet markers
            loc = new_docstr.find(_nstr)
            new_docstr = new_docstr.replace(_nstr, "", 1)
            b_loc = new_docstr.find(r"}", loc)
            new_docstr = new_docstr[:b_loc] + new_docstr[b_loc + 1:]
        i += 1

    if keep_previous:
        new_docstr = ("{0}\n"
                      "******* PREVIOUS DOCSTRING *******\n"
                      "{1}\n"
                      "^^^^^^^ PREVIOUS DOCSTRING ^^^^^^^\n"
                      "".format(new_docstr, old_docstr))

    # actually insert the new docstring
    if use_snippet:
        view.replace(edit, old_ds_whole_region, "")
        view.sel().clear()
        view.sel().add(sublime.Region(old_ds_whole_region.a))
        new_docstr = quote_style + new_docstr + quote_style
        view.run_command('insert_snippet', {'contents': new_docstr})
    else:
        view.replace(edit, old_ds_region, new_docstr)

    # # now remove trailing spaces from blank lines; unfortunately,
    # # editing the buffer right after inserting a snippet confuses
    # # the whole tabbing between fields feature. The ironic thing
    # # is that we wanted to kill the trailing spaces because
    # # insert_snippet is what put them in there.
    # new_ds_region = get_docstring(view, _edit, target)[0]
    # lines = view.substr(new_ds_region).splitlines(keepends=True)
    # for i, line in enumerate(lines):
    #     if not line.strip():
    #         lines[i] = line.strip(' \t')
    # view.replace(edit, new_ds_region, "".join(lines))

    return 0

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

    syntax = view.settings().get('syntax').lower()
    if "python" in syntax or "cython" in syntax:
        return True

    return False


class AutoDocstringCommand(sublime_plugin.TextCommand):
    def run(self, edit, default_qstyle=None, to_style=None):
        """Insert/Revise docstring for the scope of the cursor location

        Args:
            edit (type): Description
        """
        try:
            view = self.view

            file_type = is_python_file(view)
            if not file_type:
                raise TypeError("Not a python file")

            SyntaxManager.set_syntax(view)

            desired_style = get_desired_style(view, desire=to_style)

            defs = find_all_declarations(view, True)
            logger.debug("DEFS:: {}".format(defs))

            for region in view.sel():
                autodoc(view, edit, region, defs, desired_style, file_type,
                        default_qstyle=default_qstyle)
        except Exception:
            sublime.status_message("AutoDocstring is confused :-S, check "
                                   "console")
            raise
        else:
            sublime.status_message("AutoDoc'ed :-)")
        finally:
            SyntaxManager.reset_syntax(view)

        return None


class AutoDocstringAllCommand(sublime_plugin.TextCommand):
    def run(self, edit, default_qstyle=None, to_style=None, update_only=False):
        """Insert/Revise docstrings whole module

        Args:
            edit (type): Description
        """
        try:
            view = self.view

            file_type = is_python_file(view)
            if not file_type:
                raise TypeError("Not a python file")

            SyntaxManager.set_syntax(view)

            desired_style = get_desired_style(view, desire=to_style)

            defs = find_all_declarations(view, True)
            for i in range(len(defs)):
                defs = find_all_declarations(view, True)
                d = defs[i]
                region = sublime.Region(d.b, d.b)
                autodoc(view, edit, region, defs, desired_style, file_type,
                        default_qstyle=default_qstyle, update_only=update_only)
        except Exception:
            sublime.status_message("AutoDocstring is confused :-S, check "
                                   "console")
            raise
        else:
            sublime.status_message("AutoDoc'ed :-)")
        finally:
            SyntaxManager.reset_syntax(view)

        return None


class AutoDocstringConvertCommand(sublime_plugin.TextCommand):
    def run(self, edit, to_style=None):
        """Insert/Revise docstrings whole module

        Args:
          edit (type): Description
          to_style (str): Description
        """
        all_styles = list(docstring_styles.STYLE_LOOKUP.keys())
        all_styles = [s.lower() for s in all_styles]
        titled_styles = [s.title() for s in all_styles]
        to_style = to_style.lower if to_style else to_style

        if to_style in all_styles:
            self.view.run_command("auto_docstring", dict(to_style=to_style))
        else:
            window = self.view.window()
            def callback(i):
                to_style = all_styles[i]
                self.view.run_command("auto_docstring", dict(to_style=to_style))
            window.show_quick_panel(titled_styles, callback, 0, 0, None)


class AutoDocstringConvertAllCommand(sublime_plugin.TextCommand):
    def run(self, edit, to_style=None):
        """Revise all docstrings to conform to given style

        Args:
          edit (type): Description
          to_style (str): Description
        """
        all_styles = list(docstring_styles.STYLE_LOOKUP.keys())
        all_styles = [s.lower() for s in all_styles]
        titled_styles = [s.title() for s in all_styles]
        to_style = to_style.lower if to_style else to_style

        if to_style in all_styles:
            self.view.run_command("auto_docstring_all",
                                  dict(to_style=to_style, update_only=True))
        else:
            window = self.view.window()
            def callback(i):
                to_style = all_styles[i]
                self.view.run_command("auto_docstring_all",
                                      dict(to_style=to_style, update_only=True))
            window.show_quick_panel(titled_styles, callback, 0, 0, None)
        return None


class AutoDocstringSnipCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        """Insert/Revise docstring for the scope of the cursor location

        Args:
            edit (type): Description
        """
        view = self.view
        pt = view.sel()[0].a
        regA = sublime.Region(pt - 3, pt)
        qstyleA = view.substr(regA)
        assert qstyleA in ['"""', "'''"]
        view.replace(edit, regA, "")

        regB = sublime.Region(pt - 6, pt - 3)
        qstyleB = view.substr(regB)
        if qstyleB in ['"""', "'''"]:
            view.replace(edit, regB, "")

        args = {}
        args["default_qstyle"] = qstyleA
        view.window().run_command("auto_docstring", args)


class SyntaxManager(object):
    """Manages the state of the syntax highlighting

    This is kind of a hack for return annotations b/c the default
    python grammar falls apart when annotations are present
    """
    _old_syntax = None

    @classmethod
    def set_syntax(cls, view):
        cls._old_syntax = view.settings().get("syntax")

        keep_syntax = (cls._old_syntax.endswith("MagicPython.tmLanguage") or
                       "cython" in cls._old_syntax.lower())
        if keep_syntax:
            cls._old_syntax = None
        else:
            pth0 = "Packages/SublimeAutoDocstring/"
            pth0_full = sublime.packages_path() + '/../' + pth0
            if not os.path.isdir(pth0_full):
                pth0 = "Packages/AutoDocstring/"
            view.set_syntax_file(pth0 + "ADMagicPython.hidden-tmLanguage")

    @classmethod
    def reset_syntax(cls, view):
        if cls._old_syntax:
            view.set_syntax_file(cls._old_syntax)
        cls._old_syntax = None

##
## EOF
##
