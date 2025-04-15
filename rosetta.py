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
    -l<lang>    Target language to translate to, defaults to ru
    -t<engine>  Use automatic translation. Available options are:
                    yt (Yandex Translate), claude35 (Anthropic Claude-3.5-sonnet)
    -f          Overwrite existing files
    -v          Verbose output
    -h, --help  Show this help
"""
# TODO: autopattern for
#         - [color=<this.Const.UI.Color.NegativeValue>]50%[/color]
#         - Const.UI.getColorizedEntityName(...)
# TODO: autopattern for this.Const.Strings.getArticle(...)
# TODO: autopattern .getName(), .getNameOnly()
# TODO: autodetect integer when - * / ops are used:
#       "And <inv.len()><-><::Const.World.Common.WorldEconomy.Trade.AmountOfLeakedCaravanInventoryInfo> more item(s)"
# TODO: translate to other languages (xt)
# TODO: do not translate <tags> (xt)
# TODO: mod/file specific includes, i.e.:
#       - legends/**/trait_defs.nut Const = ....
from collections import namedtuple
import os
from pathlib import Path
import sys
import re
from pprint import pprint, pformat


NUT_HEADER = """
if (!("Rosetta" in getroottable())) return;

local rosetta = {{
    mod = {{id = "mod_", version = "..."}}
    author = "..."
    lang = "{lang}"
}}
local pairs = [""".lstrip()
NUT_FOOTER = """
]
::Rosetta.add(rosetta, pairs);""".lstrip()

OPTS = {"lang": "ru", "debug": False}

def main():
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__)
        return

    opt_to_kwarg = {"f": "force", "t": "tabs", "v": "verbose", "d": "debug"}
    arg_opts = {"l": "lang", "t": "engine"}

    # Parse options
    if lopts := [x for x in sys.argv[1:] if x.startswith("--")]:
        exit('Unknown option "%s"' % lopts[0])

    for x in sys.argv[1:]:
        if x[0] != "-" or x == "-": continue
        if x[1] in arg_opts:
            OPTS[arg_opts[x[1]]] = x[2:]
        else:
            for o in x[1:]:
                if o not in opt_to_kwarg:
                    exit('Unknown option "-%s"' % o)
                OPTS[opt_to_kwarg[o]] = True

    # opts = lcat(x[1:] for x in sys.argv[1:] if x.startswith("-") and x != "-")
    # if unknown := set(opts) - set(opt_to_kwarg) - {"h", "i"}:
    #     exit('Unknown option "-%s"' % unknown.pop())
    # kwargs = {full: o in opts for o, full in opt_to_kwarg.items()}

    # Parse args
    args = [x for x in sys.argv[1:] if x == "-" or not x.startswith("-")]
    if len(args) < 1:
        exit("Please specify file or dir")
    elif len(args) > 2:
        exit("Too many arguments")
    # args = sys.argv[1:]

    filename = args[0]
    outfile = args[1] if len(args) >= 2 else None

    if OPTS.get("engine"):
        import xt
        xt.init()

    # ctx = {"count": 0, "includes": {"": [], "queue": []}}
    path = Path(filename)
    if path.is_dir():
        extract_dir(path, outfile)
    elif path.is_file():
        print(NUT_HEADER.format(**OPTS))
        extract_file(filename, print)
        print(NUT_FOOTER)
    else:
        exit("File not found: " + filename)


def exit(message):
    print(red(message), file=sys.stderr)
    # print(__doc__, file=sys.stderr)
    sys.exit(1)


import ast

FILES_SKIP_RE = r'(\b|_)(rosetta(_\w+)?|mocks|test|hack_msu)(\b|[_.-])|(?:^|[/\\])(!!|~~)'

def extract_dir(path, outfile):
    count, skipped, failed = 0, 0, 0

    out = print
    out(NUT_HEADER.format(**OPTS))

    for subfile in sorted(path.glob("**/*.nut")):
        if re.search(FILES_SKIP_RE, str(subfile)):
            print(yellow("SKIPPING: %s" % subfile), file=sys.stderr)
            skipped += 1
            continue

        print(yellow("FILE: %s" % subfile), file=sys.stderr)
        out("    // FILE: %s" % subfile)
        try:
            extract_file(subfile, out)
        except Exception as e:
            import traceback
            print(red(traceback.format_exc()), file=sys.stderr)
            failed += 1

        count += 1

    out(NUT_FOOTER)
    print(green(f"Processed {count} files"
        + (f", skipped {skipped}" if skipped else "")
        + (f", failed {failed}" if failed else "")),
          file=sys.stderr)

def extract_file(filename, out):
    with open(filename, encoding='utf8') as fd:
        lines = fd.readlines()

    pairs = list(extract(lines))

    if OPTS.get("engine"):
        import xt

        ens = [p["en"] for p in pairs]
        rus = xt.translate(OPTS["engine"], ens)
        for p, ru in zip(pairs, rus):
            p[OPTS["lang"]] = ru

    for pair in pairs:
        out(_format(pair))

def _format(d):
    lines = "".join(f"        {key} = {nutstr(val)}\n" for key, val in d.items())
    return f"    {{\n{lines}    }}"


SEEN = set()

def debug(*args):
    if OPTS["debug"]:
        print(*args, file=sys.stderr)

def extract(lines):
    stream = TokenStream(lines)
    for tok in stream:
        if tok.op != "str": continue
        s = ast.literal_eval(tok.val)
        if not is_interesting(s): continue
        if value_destroyed(stream): continue
        debug('>>>', tok)

        prev_pos = stream.pos
        rewind_str(stream)
        debug("REWIND", stream.peek(0))

        # NOTE: we don't really know here whether this string is an arg or not:
        #       Flags.get("mystr")          # skip this
        #       Flags.get("key") + "mystr"  # translate this
        # If we parse properly below then we can, but we have only partial parser
        # Solution might be to not REVERT
        peek = stream.peek(0)
        if peek.op == 'ref' and STOP_FUNCS_RE.search(peek.val) or value_destroyed(stream):
            if peek.op == 'ref' and STOP_FUNCS_RE.search(peek.val):
                debug('LINE', lines[peek.n-1])
            stream.pos = prev_pos
            continue

        stream.pos -= 1
        debug(6, stream.peek(0))
        expr = parse_expr(stream)
        debug(7, stream.peek(0))
        debug("PARSE", expr)

        # If we failed to parse then simply use string as is
        if stream.pos < prev_pos:
            stream.pos = prev_pos
            expr = tok
            debug(red("FAILED to parse around %s" % str(tok)))

        if expr.op == 'call' and STOP_FUNCS_RE.search(expr.val[0].val):
            continue

        debug(expr)
        for opt in expr_patterns(expr):
            if opt in SEEN: continue
            SEEN.add(opt)

            # print("%s: %s" % (expr.n, nutstr(opt)))
            pair = {"mode": "pattern"} if "<" in opt else {}
            pair |= {"en": opt, OPTS["lang"]: ""}
            yield pair


def value_destroyed(stream):
    peek_back = stream.peek(-1)
    if peek_back.val in {'throw', 'typeof', '==', '!=', '>=', '<='}:
        return True

    peek = stream.peek(1)
    if peek.val in {'?', '==', '!=', '>=', '<=', 'in'}:
        return True

    peek_b2 = stream.peek(-2).val
    if peek_back.val == '(' and (FIRST_ARG_STOP_RE.search(peek_b2) or STOP_FUNCS_RE.search(peek_b2)):
        return True


# from funcy import print_exits
from functools import wraps
from itertools import product


STOP_FUNCS = [
    r'regexp',
    r'log(Info|Warning|Error)|Debug\.log|printData|printLog',
    r'mods_queue|require|queue|conf|getSetting|hasSetting',#|\w+Setting
    r'isKindOf|Properties\.(get|remove)|(Flags|getFlags\(\))\.(has|get\w*|remove|increment)',
]

STOP_FUNCS_RE = re.compile(r'\b(%s)\b' % '|'.join(STOP_FUNCS))
FIRST_ARG_STOP_RE = re.compile(
    r'\b(Class\.\w+Setting|lockSetting|add[A-Z]\w+Setting)\b')
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
        return rewind_expr(stream, plus=True)
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
        if force or re.search(FORMAT_FUNCS_RE, tok.val):
            rewind_str(stream)
            return
    return REVERT

def rewind_expr(stream, plus=False):
    pp = stream.pos
    tok = stream.back()
    if tok.op in {'str', 'num', 'ref'}:
        # no return so REVERT won't be promoted, i.e. we are fine stopping at current pos
        res = rewind_str(stream)
        return None if plus else res
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

import inspect

# @print_exits
def parse_expr(stream):
    args = []
    debug("parse_expr%s >" % len(inspect.stack()), stream.pos, stream.peek())
    while prim := parse_primitive(stream):
        debug("parse_expr%s  " % len(inspect.stack()), stream.pos, prim)
        if prim is REVERT:
            break
        args.append(prim)
        # tok = stream.read()
        tok = stream.peek()
        if tok.val == '+':
            stream.pos += 1
        elif tok.op == 'op' and tok.val in "-/*<>" or tok.val in {"==", ">=", "<=", "!="}:
            stream.pos += 1
            args.append(tok)
        elif tok.val == '?' and args:
            stream.pos += 1
            # print("tern")
            cond = Token(args[0].n, 'expr', args) if len(args) > 1 else args[0]
            args = []
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

    if not args:
        return REVERT
    return Token(args[0].n, 'expr', args) if len(args) > 1 else args[0]


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
        debug("parse_primitive 3", expr)
        if stream.peek().val == ')':
            stream.read()
            return expr

    debug("parse_primitive REVERT", stream.peek())
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


def expr_patterns(tok, in_ref=False):
    if tok is REVERT:
        yield "!PARSING_FAILED!"
    elif isinstance(tok, str):
        yield tok
    elif tok.op == "str":
        yield ast.literal_eval(tok.val)
    elif tok.op == "expr":
        for t in product(*[expr_patterns(sub, in_ref=in_ref) for sub in tok.val]):
            yield ''.join(t)
    elif tok.op == "call":
        func, args = tok.val
        if func.val == "format" and args and args[0].op == "str":
            parts = re.split(r'(%\w)', ast.literal_eval(args[0].val))
            parts[1::2] = args[1:]
            debug("*" * 80)
            debug(pformat(parts))
            yield from expr_patterns(Token(tok.n, "expr", parts), in_ref=in_ref)
            return
        for t in product(*[expr_patterns(sub, in_ref=True) for sub in args]):
            pat = '%s(%s)' % (func.val, ', '.join(t))
            # pat = '%s:str_tag' % ', '.join(t)
            yield "<%s>" % pat if not in_ref else pat
    elif tok.op == "ternary":
        cond, pos, neg = tok.val
        yield from expr_patterns(pos, in_ref=in_ref)
        yield from expr_patterns(neg, in_ref=in_ref)
    else:
        pat = tok.val
        yield "<%s>" % pat if not in_ref else pat


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
    "str": r'"(?:\\.|[^"\\])*"',
    "num": r'\d[\d.]*',
    "ref": r'(?:::)?[a-zA-Z_][\w.]*',
    "op": r'==|!=|<=|>=|[+=\-/*?(){},:;[\].<>]',
    "shit": r'\S+',
}
names = tuple(res.keys())
tokens_re = '|'.join('(%s)' % r for r in res.values())


def iter_tokens(lines):
    lines_iter = enumerate(lines, start=1)
    for i, line in lines_iter:
        for m in re_iter(tokens_re, line):
            yield first(Token(i, n, s) for n, s in zip(names, m) if s is not None)


INTERNAL_RES = {
    "id": r'^[a-z_-]+(\.[a-z_-]+)++',
    "types": r'^(instance|function|table|array)$',
    "file": r'^\w+/|\.[a-z0-9]{2,3}$',
    "url": r'^https://',
    "num": r'^[0-9.]+$',
    "hex": r'^#[a-fA-F0-9]+$',
    "snake": r'^[_a-zA-Z]*_\w*$',
    "mixed": r'^[a-z]+(?:[A-Z][a-z0-9]+)++$',
    "camel": r'^(?:[A-Z][a-z0-9]+){2,}+$',
    "kebab": r'^[a-zA-Z]*-[\w-]*$',
    "common": r'^(title|description|text|hint|socket)$',
    "junk": r'^[`~!@#$%^&*()_+=[\]\\{}|;:\'",./<>?\s-]+$',
    "prefix": r'^[a-z]+:\s*$',
    "key": r'^[a-z]+$',  # may have false positives
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

def re_iter(regex, s, flags=0):
    """Iterates over matches of regex in s, presents them in simplest possible form"""
    regex, getter = _inspect_regex(regex, flags)
    return map(getter, regex.finditer(s))

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
