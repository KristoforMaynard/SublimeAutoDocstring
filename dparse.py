#!/usr/bin/env python

import ast
import parser
import symbol
import sys
import token


class STTree(object):
    def __init__(self, s):
        st = parser.suite(s)
        st_tup = st.totuple()
        self.root = STNode(st_tup)

    def find(self, val, max_depth=None):
        return self.root.find(val, max_depth=max_depth)

    def find_all(self, val, max_depth=None):
        return self.root.find_all(val, max_depth=max_depth)

    def find_bfs(self, val, max_depth=None):
        return self.root.find_bfs(val, max_depth=max_depth)

    def find_all_bfs(self, val, max_depth=None):
        return self.root.find_all_bfs(val, max_depth=max_depth)

    def dump(self, prefix='', max_depth=None):
        return self.root.dump(prefix=prefix, max_depth=max_depth)

    def __str__(self):
        return self.format()

    def format(self, max_depth=None):
        return self.root.format(max_depth=max_depth)


class STNode(object):
    OPERATORS = set([token.PLUS, token.MINUS, token.STAR, token.DOUBLESTAR,
                     token.SLASH, token.DOUBLESLASH, token.PERCENT,
                     token.LEFTSHIFT, token.RIGHTSHIFT, token.AMPER, token.VBAR,
                     token.CIRCUMFLEX, token.TILDE, token.LESS, token.GREATER,
                     token.LESSEQUAL, token.GREATEREQUAL, token.EQEQUAL,
                     token.NOTEQUAL, token.RARROW])

    def __init__(self, tok, parent=None):
        self.toknum = int(tok[0])
        self.parent = parent
        self.value = None
        self.children = []

        if self.toknum in token.tok_name:
            self.name = token.tok_name[self.toknum]
            self.value = tok[1]
            if len(tok) > 2:
                raise ValueError("leaf with multiple values? {0}".format(tok))
        elif self.toknum in symbol.sym_name:
            self.name = symbol.sym_name[self.toknum]
            for child_tok in tok[1:]:
                self.children.append(STNode(child_tok, parent=self))
        else:
            raise ValueError("invalid token number:", tok)

    @property
    def isleaf(self):
        return len(self.children) == 0

    @property
    def isroot(self):
        return self.parent is None

    @property
    def siblings(self):
        if self.isroot:
            return []
        else:
            return self.parent.children

    @property
    def index(self):
        for idx, sib in enumerate(self.siblings):
            if sib is self:
                return idx
        raise RuntimeError("Broken Tree")

    @property
    def idx(self):
        return self.index

    @staticmethod
    def _get_valid_maxdepth(max_depth):
        if max_depth is None:
            max_depth = sys.maxsize
        return max_depth

    @staticmethod
    def default_condition(node, val):
        if isinstance(val, (list, tuple)):
            return node.toknum in val or node.name in val
        else:
            return node.toknum == val or node.name == val

    def _get_valid_condition(self, condition):
        if condition is None:
            condition = self.default_condition
        return condition

    def find(self, val, max_depth=None, condition=None):
        """Depth first search for first node whose toknum or name == val"""
        l = self.find_all(val, max_depth=max_depth, condition=condition,
                          _saf=True)
        if l:
            return l[0]
        else:
            return None

    def find_bfs(self, val, max_depth=None, condition=None):
        """Breadth first search for nodes whose toknum or name == val"""
        l = self.find_all_bfs(val, max_depth=max_depth, condition=condition,
                              _saf=True)
        if l:
            return l[0]
        else:
            return None

    def find_all(self, val, max_depth=None, condition=None, _saf=False):
        """Depth first search for nodes whose toknum or name == val"""
        max_depth = self._get_valid_maxdepth(max_depth)
        condition = self._get_valid_condition(condition)
        if max_depth < 0:
            return []

        ret = []
        if condition(self, val):
            ret.append(self)
            if _saf and ret:
                return ret
        for child in self.children:
            ret.extend(child.find_all(val, max_depth=max_depth - 1,
                                      condition=condition, _saf=_saf))
            if _saf and ret:
                return ret
        return ret

    def find_all_bfs(self, val, max_depth=None, condition=None, _saf=False):
        """Breadth first search for nodes whose toknum or name == val"""
        max_depth = self._get_valid_maxdepth(max_depth)
        condition = self._get_valid_condition(condition)
        ret = []

        depth = 0
        this_level = [self]
        while this_level and depth <= max_depth:
            ret.extend([n for n in this_level if condition(n, val)])
            if _saf and ret:
                break
            next_level = []
            for n in this_level:
                next_level.extend(n.children)
            this_level = next_level
            depth += 1

        return ret

    def find_parent(self, val, max_depth=None, condition=None):
        max_depth = self._get_valid_maxdepth(max_depth)
        condition = self._get_valid_condition(condition)
        if condition(self, val):
            return self
        elif self.isroot:
            return None
        else:
            return self.parent.find_parent(val, max_depth=max_depth,
                                           condition=condition)

    def __str__(self):
        s = ""

        if self.isleaf:
            if self.toknum == token.COMMA:
                s = ", "
            elif self.toknum == token.COLON:
                if self.find_parent('subscriptlist'):
                    s = ":"
                else:
                    s = ": "
            elif self.toknum == token.EQUAL:
                if self.find_parent('parameters'):
                    s = "="
                else:
                    s = " = "
            elif self.toknum in (token.STAR, token.DOUBLESTAR):
                if self.find_parent('typedargslist', max_depth=1):
                    s = "{0}".format(self.value)
                else:
                    s = " {0} ".format(self.value)
            elif self.toknum in self.OPERATORS:
                s = " {0} ".format(self.value)
            elif self.toknum == token.NAME:
                s = "{0}".format(self.value)
            else:
                s = "{0}".format(self.value)
        else:
            s = self.format()

        return s

    def format(self, max_depth=None, start=None, stop=None, ends=True):
        max_depth = self._get_valid_maxdepth(max_depth)
        condition = lambda node, _: node.isleaf

        leaves = self.find_all(0, max_depth=max_depth, condition=condition)
        if start:
            for i, leaf in enumerate(leaves):
                if leaf is start:
                    if not ends:
                        i += 1
                    leaves = leaves[i:]
                    break
        if stop:
            for i, leaf in enumerate(leaves):
                if leaf is stop:
                    if ends:
                        i += 1
                    leaves = leaves[:i]
                    break

        # insert a space when 2 NAMEs are next to each other
        for i in range(len(leaves) - 1, 0, -1):
            if leaves[i].toknum == leaves[i - 1].toknum == token.NAME:
                leaves.insert(i, " ")
        return "".join(str(n) for n in leaves)

    def dump(self, prefix='', max_depth=None):
        max_depth = self._get_valid_maxdepth(max_depth)

        if self.isleaf:
            print("{0}{1} ({2}) = {3}".format(prefix, token.tok_name[self.toknum],
                                              self.toknum, self.value))
        else:
            print("{0}{1} ({2})".format(prefix, symbol.sym_name[self.toknum],
                                        self.toknum))
            for child in self.children:
                child.dump(prefix=prefix + ": ", max_depth=max_depth - 1)

    def get_next_sibling(self, offset=1):
        if self.isroot:
            return None
        try:
            return self.siblings[self.index + offset]
        except IndexError:
            return None

    def find_next_sibling(self, val, condition=None, max_distance=None,
                          direction=1):
        condition = self._get_valid_condition(condition)
        max_distance = self._get_valid_maxdepth(max_distance)

        idx = self.index
        if direction > 0:
            siblings = self.siblings[idx:idx + 1 + max_distance][1:]
        else:
            siblings = self.siblings[idx: idx - 1 - max_distance:-1][1:]

        for sib in siblings:
            if condition(sib, val):
                return sib
        return None


def _extract_type(s, default=None):
    try:
        val = ast.literal_eval(s)
        ret = val.__class__.__name__
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

def parse_funcdef(s, trim_string_markers=True, trim_sequence_markers=True):
    """Tokenize and parse a function definition

    Args:
        s (str): function definition
        trim_string_markers (bool): if an annotation is a string
            then remove the surrounding quotes

    Returns:
        tuple: (funcname, parameters, return_annotation)

        prameters are dicts that look like
            {'name': 'param_name', 'default': '', 'annotation': ''}
    """
    tree = STTree(s)
    funcdef = tree.find('funcdef')
    funcname = str(funcdef.find_all(token.NAME, max_depth=1)[1])

    # parse parameters
    params = []

    argslist = funcdef.find('typedargslist')
    if argslist:
        tfpdefs = argslist.find_all('tfpdef', max_depth=1)
    else:
        tfpdefs = []

    lone_star = argslist.find(token.STAR, max_depth=1)
    lone_star_idx = lone_star.index if lone_star else sys.maxsize
    # nxt = lone_star.get_next_sibling() if lone_star else None
    # if nxt and nxt.toknum == token.COMMA:
    #     lone_star_idx = lone_star.index
    # else:
    #     lone_star = None
    #     lone_star_idx = sys.maxsize

    for p in tfpdefs:
        default_value = None
        default_type = None
        annotation = ""
        is_vararg = False
        is_kwarg = False
        is_optional = False

        name_node = p.find(token.NAME, max_depth=1)
        name = str(name_node)
        marker = p.find_next_sibling((token.STAR, token.DOUBLESTAR),
                                     max_distance=1, direction=-1)
        if marker:
            if marker.toknum == token.STAR:
                is_vararg = True
            elif marker.toknum == token.DOUBLESTAR:
                is_kwarg = True
            name = str(marker) + name

        # get default value if one exists
        default_marker = p.get_next_sibling()
        if default_marker and default_marker.toknum == token.EQUAL:
            is_optional = True
            default_value = default_marker.get_next_sibling().format()
            default_type = _extract_type(default_value)

        # get annotation if one exists
        annotation_token = p.find(token.COLON)
        if annotation_token:
            annotation = p.format(start=annotation_token, ends=False)

        # lone_star_idx + 1 keeps kwonly == False for vararg
        params.append(dict(name=name, default_value=default_value,
                           default_type=default_type, annotation=annotation,
                           is_optional=is_optional, is_vararg=is_vararg,
                           is_kwarg=is_kwarg,
                           kwonly=p.index > lone_star_idx + 1))

    # parse the return annotation
    rarrow = funcdef.find(token.RARROW, max_depth=1)
    if rarrow:
        annot_end = rarrow.find_next_sibling(token.COLON)
        ret_annotation = funcdef.format(start=rarrow, stop=annot_end,
                                        ends=False)
    else:
        ret_annotation = ""


    _sanitize = lambda s: _trim_enclosing(s, quotes=trim_string_markers,
                                          sequence_markers=trim_sequence_markers)
    if trim_string_markers:
        for p in params:
            if p['annotation']:
                p['annotation'] = _sanitize(p['annotation'])
        ret_annotation = _sanitize(ret_annotation)

    return funcname, params, ret_annotation

def parse_classdef(s):
    """Tokenize and parse a class definition

    Args:
        s (str): class definition

    Returns:
        tuple: ('class_name', ['BaseClass0', 'BaseClass1', ...])
    """
    tree = STTree(s)
    classdef = tree.find('classdef')
    classname = str(classdef.find_all(token.NAME, max_depth=1)[1])

    arglist = classdef.find('arglist')
    if arglist:
        base_classes = [str(c) for c in arglist.find_all('argument')]
    else:
        base_classes = []

    return classname, base_classes

def _main():
    def test_func(s):
        # STTree(s).dump()
        # print(STTree(s).format())
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


    def test_class(s):
        classname, base_classes = parse_classdef(s)
        print("CLASSNAME::", classname)
        print("BASE_CLASSES::")
        for bc in base_classes:
            print("    -", bc)
    test_class("""class ABC123(str, int): pass""")

if __name__ == "__main__":
    _main()
