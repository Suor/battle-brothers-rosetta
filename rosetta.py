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
    -x          Stop on error
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
from itertools import groupby
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

OPTS = {"lang": "ru", "debug": False, "failfast": False}

def main():
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__)
        return

    opt_to_kwarg = {"f": "force", "t": "tabs", "v": "verbose", "d": "debug", "x": "failfast"}
    arg_opts = {"l": "lang", "t": "engine"}

    # Parse options
    if lopts := [x for x in sys.argv[1:] if x.startswith("--")]:
        exit('Unknown option "%s"' % lopts[0])

    for x in sys.argv[1:]:
        if x[0] != "-" or x == "-": continue
        if x[1] in arg_opts:
            OPTS[arg_opts[x[1]]] = x[2:]
        else:
            for i, o in enumerate(x[1:], start=1):
                if o in arg_opts:
                    OPTS[arg_opts[o]] = x[i+1:]
                    break
                if o not in opt_to_kwarg:
                    exit('Unknown option "-%s"' % o)
                OPTS[opt_to_kwarg[o]] = True

    # Parse args
    args = [x for x in sys.argv[1:] if x == "-" or not x.startswith("-")]
    if len(args) < 1:
        exit("Please specify file or dir")
    elif len(args) > 2:
        exit("Too many arguments")

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
        try:
            extract_file(subfile, out)
        except Exception as e:
            if OPTS["failfast"]:
                raise
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

    if pairs:
        out("    // FILE: %s" % filename)

    if OPTS.get("engine"):
        import xt

        ens = [p["en"] for p in pairs]
        rus = xt.translate(OPTS["engine"], ens)
        for p, ru in zip(pairs, rus):
            p[OPTS["lang"]] = ru

    for pair in pairs:
        out(_format(pair))

def _format(d):
    lines = "".join(f"        {key} = {nutstr(val)}\n" for key, val in d.items() if key[0] != "_")
    return f"    {{\n{_prepare_code(d)}{lines}    }}"

def _prepare_code(d):
    if '_code' not in d:
        return ''
    lines = [l.replace('\t', ' ') for l in d['_code']]
    prefix = min(len(l) - len(l.lstrip(' ')) for l in lines)
    return "".join(f"        // {line[prefix:].rstrip()}\n" for line in lines)


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
        debug(green('>>>>>'), tok)

        prev_pos = stream.pos
        debug('LINE to REWIND', lines[tok.n - 1])
        rewind_str(stream)
        debug("REWIND", stream.peek(0))

        if value_destroyed(stream):
            stream.pos = prev_pos
            continue

        stream.pos -= 1
        expr = parse_expr(stream)
        debug("PARSE", expr)

        # If we failed to parse then simply use string as is
        if stream.pos < prev_pos:
            if stream.peek().val != ",":
                print(red("FAILED TO PARSE around %s, line %d" % (str(tok), tok.n)), file=sys.stderr)
                if OPTS["failfast"]:
                    sys.exit(1)
            stream.pos = prev_pos
            expr = tok

        if expr.op == 'call' and STOP_FUNCS_RE.search(expr.val[0].val):
            continue

        debug('EXPR', expr)
        for opt in expr_options(expr):
            debug('OPT', opt)
            opt = str_opt(opt)

            if opt in SEEN: continue
            SEEN.add(opt)

            # TODO: better expr detection
            pair = {"mode": "pattern"} if "<" in opt and expr.op != 'str' else {}
            pair |= {"en": opt, OPTS["lang"]: ""}
            if expr.op != 'str':
                pair["_code"] = lines[expr.n - 1:stream.peek(0).n]
            debug(_format(pair))
            yield pair

        stream.chop()


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


from functools import wraps
from itertools import product


STOP_FUNCS = [
    r'regexp|rawin|rawget|createColor|getSprite|addSprite|setSpriteOffset',
    r'startswith|endswith|cutprefix|cutsuffix',
    r'log(Info|Warning|Error)|Debug\.log|printData|printLog',
    r'mods_queue|queue|require|conf|getSetting|hasSetting',
    r'isKindOf|mods_isClass|Properties\.(get|remove)',
    r'(has|get|getAsInt|getAsFloat|remove|increment)|Flags\.(set|pack|unpack)',
]

STOP_FUNCS_RE = re.compile(r'\b(%s)\b' % '|'.join(STOP_FUNCS))
FIRST_ARG_STOP_RE = re.compile(
    r'\b(Class\.\w+Setting|lockSetting|add[A-Z]\w+Setting|rawset)\b')
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
        if force or re.search(FORMAT_FUNCS_RE, tok.val):
            rewind_str(stream)
            return
        if STOP_FUNCS_RE.search(tok.val):
            return
    return REVERT

def rewind_expr(stream, plus=False):
    tok = stream.back()
    debug("rewind_expr >", stream.pos, tok)
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
            elif paren.val is None:
                if stream.pos < 0:
                    print(red("Found unpaired ) on line %s" % tok.n), file=sys.stderr)
                    if OPTS["failfast"]:
                        sys.exit(1)
                return REVERT

        tok = stream.peek(-1)
        if tok.op == 'ref':
            rewind_func(stream, force=True)
        else:
            rewind_str(stream)
    else:
        return REVERT


def parse_expr(stream):
    args = []
    debug("parse_expr >", stream.pos, stream.peek())
    while operand := parse_operand(stream):
        debug("parse_expr operand:", stream.pos, operand)
        if operand is REVERT:
            break
        args.append(operand)

        tok = stream.peek()
        if tok.op == 'op' and (tok.val in "+-/*<>" or tok.val in {"==", ">=", "<=", "!="}):
            stream.pos += 1
            args.append(tok)
        elif tok.val == '?' and args:
            stream.pos += 1
            cond = Token(args[0].n, 'expr', args) if len(args) > 1 else args[0]
            args = []
            tern = parse_ternary(cond, stream)
            if tern:
                args.append(tern)
            else:
                args.append(cond)
                break
        else:
            break

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
    if not negative:
        return
    return Token(cond.n, 'ternary', [cond, positive, negative])


def parse_operand(stream):
    debug("parse_operand >", stream.pos, stream.peek())
    base = parse_primitive(stream)
    if base is REVERT:
        return REVERT

    args = [base]
    while tok := stream.peek():
        if tok.val == '.':
            if stream.peek(2).op == 'ref':
                stream.pos += 1
                args.extend([tok, stream.read()])
            else:
                break

        elif tok.val == '(':
            assert args, "Should be handled by parse_primitive"
            if args[-1].op != 'ref': # Do not handle <arbitrary-expr>(...) calls for now
                print(red("Found weird call: %s(...)" % args), file=sys.stderr)
                break

            func = args[-1]
            call = parse_call(func, stream)
            if call is REVERT:
                break
            args[-1] = call

        elif tok.val == '[':
            assert args, "Should be handled by parse_primitive"
            stream.pos += 1
            expr = parse_expr(stream)
            if expr is REVERT:
                stream.pos -= 1
                break

            if close := stream.eat(']'):
                args.extend([tok, expr, close])
            else:
                break

        else:
            break

    if not args:
        return REVERT
    return Token(args[0].n, 'expr', args) if len(args) > 1 else args[0]


@revert_pos
def parse_primitive(stream):
    tok = stream.read()

    if tok.op in {'str', 'num'}:
        return tok

    elif tok.op == 'ref':
        return tok

    elif tok.val == '-':
        expr = parse_primitive(stream)
        if expr is REVERT:
            return REVERT
        return Token(tok.n, 'expr', [tok, expr])

    elif tok.val == '(':
        expr = parse_expr(stream)
        if stream.peek().val == ')':
            stream.read()
            return expr

    elif tok.val == '[':
        tokens = parse_parens(stream, tok)
        if tokens is REVERT:
            return REVERT
        return Token(tok.n, 'expr', [tok] + tokens + [stream.peek(0)])

    debug("parse_primitive REVERT", stream.peek())
    return REVERT

def parse_call(func, stream):
    debug("parse_call >", func)
    paren = stream.read()
    assert paren.val == '('

    if STOP_FUNCS_RE.search(func.val):
        tokens = parse_parens(stream, paren, break_at={'function'})
        if tokens is REVERT:
            return REVERT
        return Token(func.n, 'call', [func, tokens])

    args = []
    while not stream.eat(')') and (expr := parse_expr(stream)):
        args.append(expr)

        tok = stream.read()
        if tok.val == ')':
            break
        elif tok.val != ',':
            debug("parse_call > unexpected", tok)
            return REVERT

    return Token(func.n, 'call', [func, args])

def parse_parens(stream, paren, break_at=()):
    debug("parse_parens", paren)
    open_val = paren.val
    close_val = {'(': ')', '[': ']'}[paren.val]

    count, tokens = 1, []
    for tok in stream:
        tokens.append(tok)
        if tok.val == open_val:
            count += 1
        elif tok.val == close_val:
            count -= 1
            if count == 0:
                return tokens[:-1]
        elif tok.val in break_at:
            stream.back()
            return []
    else:
        print(red("Found unpaired %s on line %s" % (paren.val, paren.n)), file=sys.stderr)
        return REVERT


STR_OPS = {'+': ' + ', ',': ', '}

def str_opt(opt, in_ref=False):
    if isinstance(opt, Token):
        if opt.op == 'call':
            func, args = opt.val
            pat = '%s(%s)' % (func.val, ', '.join(str_opt(a, in_ref=True) for a in args))
            return pat if in_ref else "<%s>" % pat
        else:
            assert isinstance(opt.val, str)
            s = STR_OPS.get(opt.val, opt.val)
            return s if in_ref else '<%s>' % s

    elif isinstance(opt, tuple):
        tokens = flatten(opt, follow=lambda x: type(x) is tuple)
        if not in_ref:
            tokens = hide_concats(tokens)

        res = ''
        for is_str, group in groupby(tokens, key=isa(str)):
            if is_str:
                res += ''.join(group)
            else:
                expr_s = ''.join(str_opt(x, in_ref=True) for x in group)
                res += expr_s if in_ref else '<%s>' % expr_s
        return res

    assert isinstance(opt, str)
    return opt
    # return "'%s'" % opt if in_ref else str(opt)


def hide_concats(seq):
    seq = list(seq)
    prev = None
    for i, opt in enumerate(seq):
        if isinstance(opt, Token) and opt.val == '+':
            if isinstance(prev, str):
                continue
            if (ntok := seq[i+1] if i < len(seq) - 1 else None) and isinstance(ntok, str):
                continue
        yield opt
        prev = opt


def expr_options(tok):
    if tok is REVERT:
        yield "!PARSING_FAILED!"
    elif isinstance(tok, str):  # Result of format unpacking
        yield tok
    elif tok.op == "str":
        yield ast.literal_eval(tok.val)
    elif tok.op == "expr":
        yield from product(*[expr_options(sub) for sub in tok.val])
    elif tok.op == "call":
        func, args = tok.val
        if func.val in {"format", "::format"} and args and args[0].op == "str":
            parts = re.split(r'(%[.\d]*\w)', ast.literal_eval(args[0].val))
            parts[1::2] = args[1:]
            # TODO: add op.+
            yield from expr_options(Token(tok.n, "expr", parts))
            return
        for t in product(*[expr_options(sub) for sub in args]):
            yield Token(tok.n, 'call', [func, t])
    elif tok.op == "ternary":
        cond, pos, neg = tok.val
        yield from expr_options(pos)
        yield from expr_options(neg)
    else:
        yield tok


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
        self.start = 0

    def chop(self):
        self.start = self.pos + 1

    def __iter__(self):
        return self

    def __next__(self):
        self.pos += 1
        if self.pos >= len(self.tokens):
            raise StopIteration
        return self.tokens[self.pos]

    def read(self):
        return next(self, self.NONE)

    def eat(self, val):
        if self.peek().val == val:
            return self.read()

    def back(self):
        self.pos -= 1
        return self.tokens[self.pos] if self.pos >= self.start else self.NONE

    def peek(self, n=1):
        return self.tokens[self.pos + n] if self.start <= self.pos + n < len(self.tokens) else self.NONE


res = {
    "comment": r'//.*|#.*',
    "str": r'"(?:\\.|[^"\\])*"',
    "num": r'\d[\d.]*',
    "ref": r'(?:::)?[a-zA-Z_][\w.]*',
    "op": r'==|!=|<=|>=|[+=\-/*?(){},:;[\].<>]',
    "shit": r'[^\s(){}]+',
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
    "url": r'^https?://',
    "num": r'^[0-9.]+$',
    "hex": r'^#[a-fA-F0-9]+$',
    "snake": r'^[_a-zA-Z]*_\w*$',
    "mixed": r'^[a-z]+[A-Z]+[A-Za-z0-9]*$',
    "camel": r'^(?:[A-Z][a-z0-9]+){2,}+[A-Z]*$',
    "kebab": r'^[a-zA-Z]*-[\w-]*$',
    "common": r'^(title|description|text|hint|socket)$',
    "junk": r'^[`~!@#$%^&*()_+=[\]\\{}|;:\'",./<>?\s-]+$',
    "prefix": r'^[a-z]+:\s*$',
    "req": r'^\w+ *>= *[0-9.-]+$',
    # "key": r'^[a-z]+$',  # may have false positives
}
INTERNAL_RE = '|'.join(INTERNAL_RES.values())

def is_interesting(s):
    return s and not re.search(INTERNAL_RE, s)


# Helpers

from itertools import chain
from operator import methodcaller
import re

def flatten(seq, follow=None):
    """Flattens arbitrary nested sequence.
       Unpacks an item if follow(item) is truthy."""
    for item in seq:
        if follow(item):
            yield from flatten(item, follow)
        else:
            yield item

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
