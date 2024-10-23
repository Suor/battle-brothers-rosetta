#!/usr/bin/env python3
"""\
Usage:
    python rosetta.py <mod-file> <to-file> [options]
    python rosetta.py <mod-dir> <to-file> [options]

Extracts strings and prepares a rosetta style translation file.

Arguments:
    <mod-file>  The path to a mod file
    <mod-dir>   Process all *.nut files in a dir
    <to-file>   Rosetta file to write

Options:
    -f          Overwrite existing files
    -v          Verbose output
    -h, --help  Show this help
"""
from collections import namedtuple
import os
from pathlib import Path
import sys
import re
# from difflib import Differ, SequenceMatcher
# from itertools import groupby
from pprint import pprint, pformat
from funcy import re_all

SCRIPTS = "/home/suor/_downloads/Battle Brothers mods/bbtmp2/scripts-base/";
# SCRIPTS = "/home/suor/_downloads/Battle Brothers mods/bbtmp2/mod_legends_18.1.0/scripts/";


def main():
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__)
        return



    # opt_to_kwarg = {"f": "force", "t": "tabs", "v": "verbose"}

    # # Parse options
    # if lopts := [x for x in sys.argv[1:] if x.startswith("--")]:
    #     exit('Unknown option "%s"' % lopts[0])
    # opts = lcat(x[1:] for x in sys.argv[1:] if x.startswith("-") and x != "-")
    # if unknown := set(opts) - set(opt_to_kwarg) - {"h", "i"}:
    #     exit('Unknown option "-%s"' % unknown.pop())
    # kwargs = {full: o in opts for o, full in opt_to_kwarg.items()}

    # # Parse args
    # args = [x for x in sys.argv[1:] if x == "-" or not x.startswith("-")]
    # if len(args) < 1:
    #     exit("Please specify file or dir")
    # elif len(args) > 2:
    #     exit("Too many arguments")
    args = sys.argv[1:]

    filename = args[0]
    outfile = args[1] if len(args) >= 2 else None

    # ctx = {"count": 0, "includes": {"": [], "queue": []}}
    path = Path(filename)
    if path.is_dir():
        extract_dir(path, outfile)
    elif path.is_file():
        extract(filename, print)
    else:
        exit("File not found: " + filename)


def exit(message):
    print(red(message), file=sys.stderr)
    # print(__doc__, file=sys.stderr)
    sys.exit(1)


from funcy import lremove, lfilter, re_iter
import ast

FILES_SKIP_RE = r'\b(rosetta(_\w+)?|mocks|test)\b'

def extract_dir(path, outfile):
    count, skipped = 0, 0

    out = print
    out("""local rosetta = {
    mod = "mod_"
    lang = "ru"
    version = "..."
}""")
    out("local pairs = [")

    for subfile in sorted(path.glob("**/*.nut")):
        if re.search(FILES_SKIP_RE, str(subfile)):
            print(yellow("SKIPPING: %s" % subfile), file=sys.stderr)
            skipped += 1
            continue

        # print(yellow("FILE: %s" % subfile), file=sys.stderr)
        out("    // FILE: %s" % subfile)
        extract(subfile, out)
        count += 1

    out("]")
    out("::Rosetta.add(rosetta, pairs);");
    print(green(f"Processed {count} files" + (f", skipped {skipped}" if skipped else "")),
          file=sys.stderr)


def extract(filename, out):
    with open(filename) as fd:
        lines = fd.readlines()

    stream = TokenStream(lines)
    # for n, op, tok in stream.tokens:
    #     # if tok[0] != '"': continue
    #     print(n, op, tok)
    # # pprint(stream.tokens)
    # return

    out = print
    # out = lambda s: print(yellow(s))

    for tok in stream:
        if tok.op != "str": continue
        # print(tok)
        s = ast.literal_eval(tok.val)
        if not is_interesting(s): continue
        if value_destroyed(stream): continue

        # peek = stream.peek(-1)
        # if re.search(r'^[a-z]+$', s):
        #     print(stream.peek(-1), stream.peek(-2))
        if stream.peek(-1).val == '(' and FIRST_ARG_STOP_RE.search(stream.peek(-2).val):
            continue

        # print(tok)
        prev_pos = stream.pos
        rewind_str(stream)

        # NOTE: we don't really know here whether this string is an arg or not:
        #       Flags.get("mystr")          # skip this
        #       Flags.get("key") + "mystr"  # translate this
        # If we parse properly below then we can, but we have only partial parser
        # Solution might be to not REVERT
        peek = stream.peek(0)
        # print(red(str(peek)))
        if peek.op == 'ref' and STOP_FUNCS_RE.search(peek.val):
            stream.pos = prev_pos
            continue

        stream.pos -= 1
        expr = parse_expr(stream)

        # If we failed to parse then simply use string as is
        if stream.pos < prev_pos:
            stream.pos = prev_pos
            expr = tok

        if expr.op == 'call' and STOP_FUNCS_RE.search(expr.val[0].val):
            continue

        # print(expr)
        for opt in expr_patterns(expr):
            # out("%s: %s" % (expr.n, nutstr(opt)))
            if "<" in opt:
                out("""
    {
        mode = "pattern"
        en = %s
        ru = ""
    }""".lstrip("\n") % nutstr(opt))
            else:
                out("""
    {
        en = %s
        ru = ""
    }""".lstrip("\n") % nutstr(opt))


def value_destroyed(stream):
    peek = stream.peek(-1)
    if peek.val in {'throw', 'typeof', '==', '!=', '>=', '<='}:
        return True

    peek = stream.peek(1)
    if peek.val in {'?', '==', '!=', '>=', '<='}:
        return True


from funcy import print_exits
from functools import wraps
from itertools import product


STOP_FUNCS = [
    r'log(Info|Warning|Error)|Debug\.log|printData',
    r'mods_queue|require|queue|conf|getSetting|hasSetting',#|\w+Setting
    r'isKindOf|Properties\.(get|remove)|Flags\.(has|get\w*|remove|increment)',
]
STOP_FUNCS_RE = re.compile(r'\b(%s)\b' % '|'.join(STOP_FUNCS))
FIRST_ARG_STOP_RE = re.compile(
    r'\b(Flags\.(set|add)|Class\.\w+Setting|lockSetting|add[A-Z]\w+Setting)\b')
FORMAT_FUNCS_RE = r'\b(getColorized|Text.\w+|green|red|color|format)'

class Revert:
    def __str__(self):
        return "<revert>"
    __repr__ = __str__
REVERT = Revert()

def revert_pos(func):
    @wraps(func)
    def wrapper(stream, **kwargs):
        pp = stream.pos
        res = func(stream, **kwargs)
        if res is REVERT:
            stream.pos = pp
            # print("REVERTED to %s" % str(stream.peek()))
        return res
    return wrapper


@revert_pos
def rewind_str(stream):
    """Find the start of expression or a wrapping function call"""
    tok = stream.back()
    if tok.val == '+':
        return rewind_expr(stream)
    elif tok.val == '(':
        return rewind_func(stream)
    elif tok.val == ',':
        return rewind_expr(stream)
    return REVERT

def rewind_func(stream, force=False):
    tok = stream.back()
    if tok.op == 'ref':
        if STOP_FUNCS_RE.search(tok.val):
            return  # Q: return some blocking result?
        # if first_arg and FIRST_ARG_STOP_RE.search(tok.val):
        #     return
        if force or re.search(FORMAT_FUNCS_RE, tok.val):
            return rewind_str(stream)
    return REVERT

# @print_exits
def rewind_expr(stream):
    pp = stream.pos
    tok = stream.back()
    if tok.op in {'str', 'num', 'ref'}:
        # no return so REVERT won't be promoted, i.e. we are fine stopping at current pos
        rewind_str(stream)
    elif tok.val == ')':
        count = 1
        while count > 0:
            paren = stream.back()
            if paren.val == ')':
                count += 1
            elif paren.val == '(':
                count -= 1
            elif paren.val is None: # Unpaired )
                print(red("Found unpaired ) on line %s" % tok.n), file=sys.stderr)
                return REVERT

        tok = stream.peek(-1)
        if tok.op == 'ref':
            rewind_func(stream, force=True)
        else:
            rewind_str(stream)
    else:
        return REVERT


# Sum = namedtuple("Sum", "args")
# Call = namedtuple("Call", "func args")

# @print_exits
def parse_expr(stream):
    args = []
    # print("parse_expr", stream.pos, stream.peek())
    while prim := parse_primitive(stream):
        if prim is REVERT:
            break
        # print("in", stream.pos, prim)
        args.append(prim)
        # tok = stream.read()
        tok = stream.peek()
        if tok.val == '+':
            stream.pos += 1
        elif tok.val == '?' and args:
            stream.pos += 1
            # print("tern")
            cond = args.pop()
            tern = parse_ternary(cond, stream)
            # print("tern", tern)
            if tern:
                args.append(tern)
            else:
                args.append(cond)
                break
        else:
            # print("parse_expr: SHIT=" + tok.val)
            break
        # elif tok.val in '),;:'
    # print("after", stream.pos, stream.peek())

    # if not args:
    #     return Token(0, 'sum', [])
    return Token(args[0].n, 'sum', args) if len(args) > 1 else args[0]


def parse_ternary(cond, stream):
    positive = parse_expr(stream)
    if not positive:
        return
    tok = stream.read()
    if tok.val != ':':
        return
    negative = parse_expr(stream)
    # print("parse_ternary 2", stream.peek())
    if not negative:
        return
    return Token(cond.n, 'ternary', [cond, positive, negative])

# @print_exits
@revert_pos
def parse_primitive(stream):
    tok = stream.read()
    # print("in parse_primitive: tok=%s" % tok.val)

    if tok.op in {'str', 'num'}:
        return tok

    elif tok.op == 'ref':
        if stream.peek().val == '(':
            return parse_call(tok, stream)
        else:
            return tok

    elif tok.val == '(':
        # print("parse_primitive 2", tok)
        expr = parse_expr(stream)
        # print("parse_primitive 3", stream.peek())
        if stream.peek().val == ')':
            stream.read()
            return expr

    # print("parse_primitive REVERT", stream.peek())
    # import ipdb; ipdb.set_trace()
    return REVERT

# @print_exits
def parse_call(func, stream):
    assert stream.read().val == '('
    # print("parse_call 1 peek=", stream.peek())
    args = []

    while not stream.eat(')') and (expr := parse_expr(stream)):
        # print("parse_call expr=", expr)
        args.append(expr)

        tok = stream.read()
        # print("parse_call tok=", tok)
        if tok.val == ')':
            break
        elif tok.val != ',':
            return REVERT

    # print("parse_call 2 peek=", stream.peek())
    return Token(func.n, 'call', [func, args])


def expr_patterns(tok, level=0):
    if tok is REVERT:
        yield "!PARSING_FAILED!"
    elif tok.op == 'str':
        yield ast.literal_eval(tok.val)
    elif tok.op == 'sum':
        for t in product(*[expr_patterns(sub, level + 1) for sub in tok.val]):
            yield ''.join(t)
    elif tok.op == 'call':
        func, args = tok.val
        for t in product(*map(expr_patterns, args)):
            pat = '%s(%s)' % (func.val, ', '.join(t))
            # pat = '%s:str_tag' % ', '.join(t)
            yield "<%s>" % pat if level == 1 else pat
    elif tok.op == 'ternary':
        cond, pos, neg = tok.val
        yield from expr_patterns(pos)
        yield from expr_patterns(neg)
    else:
        pat = tok.val
        yield "<%s>" % pat if level == 1 else pat

def nutstr(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace("\n", "\\n") + '"'


class Token(namedtuple("Token", "n op val")):
    __slots__ = ()
    def __str__(self):
        return '%s.%s' % (self.op, self.val)
    __repr__ = __str__

class TokenStream:
    NONE = Token(None, None, None)

    def __init__(self, lines):
        self.tokens = list(iter_tokens(lines))
        self.pos = -1

    def __iter__(self):
        return self
        # return iter(self.tokens)

    def __next__(self):
        self.pos += 1
        if self.pos >= len(self.tokens):
            raise StopIteration
        return self.tokens[self.pos]
    read = __next__

    def eat(self, val):
        if self.peek().val == val:
            return self.read()

    def back(self):
        self.pos -= 1
        return self.tokens[self.pos] if self.pos >= 0 else self.NONE

    def peek(self, n=1):
        return self.tokens[self.pos + n] if 0 <= self.pos + n < len(self.tokens) else self.NONE

    # def eof(self):
    #     return self.pos >= len(self.tokens)


res = {
    "comment": r'//.*|#.*',
    "str": r'"(?:\\.|[^"\\]+)*"',
    "num": r'\d[\d.]*',
    "ref": r'(?:::)?[a-zA-Z_][\w.]*',
    "op": r'==|!=|<=|>=|[+=?(){},:;[\].<>]',
    "shit": r'\S+',
}
names = tuple(res.keys())
tokens_re = '|'.join('(%s)' % r for r in res.values())

from funcy import first


def iter_tokens(lines):
    lines_iter = enumerate(lines, start=1)
    for i, line in lines_iter:
        for m in re_iter(tokens_re, line):
            # print(m)
            yield first(Token(i, n, s) for n, s in zip(names, m) if s is not None)


INTERNAL_RES = {
    "id": r'^[a-z-]+(\.[a-z_-]+)++',
    "types": r'^(instance|function|table|array)$',
    "file": r'^\w+/|\.[a-z0-9]{2,3}$',
    "url": r'^https://',
    "num": r'^[0-9.]+$',
    "snake": r'^[_a-zA-Z]*_\w*$',
    "mixed": r'^[a-z]+(?:[A-Z][a-z0-9]+)++$',
    "camel": r'^(?:[A-Z][a-z0-9]+){2,}+$',
    "common": r'^(title|description|text|socket)$',
    "space": r'^\s+$',
    # "tmp": r'^necro:|head|body',
}
INTERNAL_RE = '|'.join(INTERNAL_RES.values())

def is_interesting(s):
    return s and not re.search(INTERNAL_RE, s)


# Helpers

from itertools import chain
from operator import methodcaller
import re


def is_line_junk(line, pat=re.compile(r"^\s*(?:$|//)")):
    return pat.search(line) is not None

def tabs_to_spaces(lines, num=4):
    for line in lines:
        yield line.replace("\t", " " * num)

def isa(typ):
    return lambda x: isinstance(x, typ)

def lcat(seqs):
    return list(chain.from_iterable(seqs))

def first(seq):
    """Returns the first item in the sequence.
       Returns None if the sequence is empty."""
    return next(iter(seq), None)

def re_find(regex, s, flags=0):
    """Matches regex against the given string,
       returns the match in the simplest possible form."""
    regex, _getter = _inspect_regex(regex, flags)
    getter = lambda m: _getter(m) if m else None
    return getter(regex.search(s))

def _inspect_regex(regex, flags):
    if not isinstance(regex, re.Pattern):
        regex = re.compile(regex, flags)
    return regex, _make_getter(regex)

def _make_getter(regex):
    if regex.groups == 0:
        return methodcaller('group')
    elif regex.groups == 1 and regex.groupindex == {}:
        return methodcaller('group', 1)
    elif regex.groupindex == {}:
        return methodcaller('groups')
    elif regex.groups == len(regex.groupindex):
        return methodcaller('groupdict')
    else:
        return lambda m: m

# Coloring works on all systems but Windows
if os.name == 'nt':
    red = green = yellow = lambda text: text
else:
    red = lambda text: "\033[31m" + text + "\033[0m"
    green = lambda text: "\033[32m" + text + "\033[0m"
    yellow = lambda text: "\033[33m" + text + "\033[0m"


if __name__ == "__main__":
    main()
