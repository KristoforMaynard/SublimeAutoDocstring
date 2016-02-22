# -*- coding: utf-8 -*-
"""For getting string representations of ast nodes

This is used for processing argument types and annotations
from an ast representation of a function
"""

import ast


def format_node(node, quote="'"):
    """Format an ast.expr's value into a string

    This works for all literals as well as type names

    Args:
        node (ast.expr): An ast node of some literal
        quote (str): quote characters for ast.Str types

    Returns:
        str: string representation of a node
    """
    if node is None:
        s = ""
    elif isinstance(node, ast.Str):
        s = "{0}{1}{0}".format(quote, node.s)
    elif isinstance(node, ast.Num):
        s = node.n
    elif isinstance(node, ast.Tuple):
        s = "({0})".format(", ".join([format_node(e) for e in node.elts]))
    elif isinstance(node, ast.List):
        s = "[{0}]".format(", ".join([format_node(e) for e in node.elts]))
    elif isinstance(node, ast.Dict):
        _it = ("{0}: {1}".format(format_node(key), format_node(val))
               for key, val in zip(node.keys, node.values))
        s = "{{{0}}}".format(", ".join(_it))
    elif hasattr(ast, "NameConstant") and isinstance(node, ast.NameConstant):
        s = node.value
    elif isinstance(node, ast.Name):
        s = node.id
    else:
        s = getattr(node, node._fields[0])

    return s

def format_type(node, default="UnknownType"):
    """Get the type of a literal as a str

    Args:
        node (ast.expr): An ast node of some literal

    Returns:
        str: the type of Node
    """
    if node is None:
        s = None
    elif isinstance(node, ast.expr):
        fld0 = getattr(node, node._fields[0])
        if node._fields[0] in ['keys', 'elts']:
            s = node.__class__.__name__.lower()
        elif fld0 in ["True", "False"]:
            s = "bool"
        elif fld0 == "None":
            s = default
        else:
            s = fld0.__class__.__name__

        if s == None.__class__.__name__:
            s = default
    else:
        s = str(node)

    return s


# def _test():
#     tree = ast.parse("def myfunc(a0, a1: 'ano', a2: (int, float, 'ano'), "
#                      "a3: ['a', 'b'], a4: {'dx0': int}, a5: 0, a6: None, "
#                      "a7: A_B): pass")
#     args = tree.body[0].args.args
#     ans = [arg.annotation for arg in args]
#     print("=======")  # pylint: disable=superfluous-parens
#     for i, ano in enumerate(ans):
#         print(i, format_node(ano))
#     print("-------")  # pylint: disable=superfluous-parens
#     for i, ano in enumerate(ans):
#         print(i, ano, format_type(ano))
# _test()
