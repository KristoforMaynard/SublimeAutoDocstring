#!/usr/bin/env python

import ast


def _extract_type(s, default=None):
    try:
        ret = ast.literal_eval(s).__class__.__name__
    except Exception:  # pylint: disable=broad-except
        ret = default

    if ret in ('NoneType', 'NotImplementedType'):
        ret = ret[:-len('Type')]

    return ret


def _trim_enclosing(s, quotes=True, sequence_markers=True):
    s = s.strip()
    if quotes and s[:3] == s[-3:] and s[:3] in ('"""', "'''"):
        s = s[3:-3]
    elif quotes and s[:1] == s[-1:] and s[:1] in ('"', "'"):
        s = s[1:-1]
    elif sequence_markers and s[:1] == '(' and s[-1:] == ')':
        s = s[1:-1]
    elif sequence_markers and s[:1] == '[' and s[-1:] == ']':
        s = s[1:-1]
    return s


def _unparse(node):
    return ast.unparse(node) if node is not None else ""


def parse_funcdef(s, trim_string_markers=True, trim_sequence_markers=True):
    """Parse a function definition

    Args:
        s (str): function definition
        trim_string_markers (bool): if an annotation is a string
            then remove the surrounding quotes

    Returns:
        tuple: (funcname, parameters, return_annotation)

        parameters are dicts with keys: name, default_value, default_type,
        annotation, is_optional, is_vararg, is_kwarg, kwonly
    """
    func = ast.parse(s.strip()).body[0]
    a = func.args
    params = []

    def _sanitize(text):
        if not trim_string_markers:
            return text
        return _trim_enclosing(text, quotes=trim_string_markers,
                               sequence_markers=trim_sequence_markers)

    def add(arg, default=None, prefix="", kwonly=False):
        default_value = _unparse(default) if default is not None else None
        params.append(dict(
            name=prefix + arg.arg,
            default_value=default_value,
            default_type=(_extract_type(default_value)
                          if default_value is not None else None),
            annotation=_sanitize(_unparse(arg.annotation)),
            is_optional=default is not None,
            is_vararg=prefix == "*",
            is_kwarg=prefix == "**",
            kwonly=kwonly,
        ))

    positional = a.posonlyargs + a.args
    defaults = [None] * (len(positional) - len(a.defaults)) + a.defaults
    for arg, default in zip(positional, defaults):
        add(arg, default)
    if a.vararg:
        add(a.vararg, prefix="*")
    for arg, default in zip(a.kwonlyargs, a.kw_defaults):
        add(arg, default, kwonly=True)
    if a.kwarg:
        add(a.kwarg, prefix="**")

    return func.name, params, _sanitize(_unparse(func.returns))


def parse_classdef(s):
    """Parse a class definition

    Returns:
        tuple: ('class_name', ['BaseClass0', 'BaseClass1', ...])
    """
    cls = ast.parse(s.strip()).body[0]
    bases = [_unparse(b) for b in cls.bases]
    bases += ["{0}={1}".format(k.arg, _unparse(k.value)) for k in cls.keywords]
    return cls.name, bases


def _main():
    def test_func(s):
        funcname, params, ret_annotation = parse_funcdef(s)
        print("::", s)
        print()
        print("FUNCNAME::", funcname)
        print("PARAMS::")
        for p in params:
            print("    -", p)
        print("ret_annotation::", ret_annotation)

    test_func("""def test1(a, *args, kw1, **kwargs) -> 'xyz': pass""")
    test_func("""def test2(a, *, b, c, **kwargs) -> 'xyz': pass""")
    test_func("""def test3(a, b: typing.Tuple[typing.Int, typing.Int],
                           c: int=123, d=3+11.23j, e='abc', **kw) -> 'xyz':
                     pass""")

    classname, base_classes = parse_classdef("""class ABC123(str, int): pass""")
    print("CLASSNAME::", classname)
    print("BASE_CLASSES::")
    for bc in base_classes:
        print("    -", bc)


if __name__ == "__main__":
    _main()