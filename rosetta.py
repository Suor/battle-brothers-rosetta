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
    -r<file>    Use this as reference translation
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
from collections import defaultdict, namedtuple
from itertools import count, groupby
from pathlib import Path
import ast
import os
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

OPTS = {"lang": "ru", "engine": None, "ref": None, "debug": False, "failfast": False}

def main():
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__)
        return

    bool_opts = {"f": "force", "t": "tabs", "v": "verbose", "d": "debug", "x": "failfast"}
    arg_opts = {"l": "lang", "t": "engine", "r": "ref"}

    # Parse options
    if lopts := [x for x in sys.argv[1:] if x.startswith("--")]:
        exit('Unknown option "%s"' % lopts[0])

    args = []
    arg_it = iter(sys.argv[1:])
    for x in arg_it:
        if x[0] != "-" or x == "-":
            args.append(x)
        elif x[1] in arg_opts:
            OPTS[arg_opts[x[1]]] = x[2:] or next(arg_it)
        else:
            for i, o in enumerate(x[1:], start=1):
                if o in arg_opts:
                    OPTS[arg_opts[o]] = x[i+1:] or next(arg_it)
                    break
                if o not in bool_opts:
                    exit('Unknown option "-%s"' % o)
                OPTS[bool_opts[o]] = True

    # Validate args
    if len(args) < 1:
        exit("Please specify file or dir")
    elif len(args) > 2:
        exit("Too many arguments")

    filename = args[0]
    outfile = args[1] if len(args) >= 2 else None

    if OPTS["engine"]:
        import xt
        xt.init()

    if OPTS["ref"]:
        load_ref(OPTS["ref"])

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
    sys.exit(1)


# Reference

_LINE_RES = {
    'open': r'\{',
    'close': r'\},?',
    'code': r'//.*',
    'func': r'.*\{',
}
LINE_RE = '|'.join(r'^\s*(%s)\s*$' % r for r in _LINE_RES.values())

REF_PAIRS = {}
REF_RULES = defaultdict(list)
CODE_RULES = defaultdict(str)

def load_ref(ref_file):
    with open(ref_file) as fd:
        block, code, meat = [], [], False
        level = 0
        last_en, last_rule = None, None
        for line in fd:
            block.append(line)
            if m := re_find(LINE_RE, line):
                _open, _close, _code, _func = m
                if _open:
                    if level <= 0:
                        level = 0
                        block, code, meat = [line], [], False
                    level += 1
                elif _close:
                    level -= 1
                    if level == 0 and code:
                        CODE_RULES[_code_key(code)] += ''.join(block)
                elif _code:
                    if not meat:
                        code.append(_code)
                elif _func:
                    if level > 0:
                        level += 1
                        meat = True
            else:
                meat = True

            # TODO: deprecate and remove REF_RULES, get_ref, _rule_key, _opt_keys and shit
            en = re_find(r'^\s*en\s*=\s*("[^"]+")', line)
            if en:
                en = ast.literal_eval(en)
                if "<" in en:
                    key = _rule_key(en)
                    # TODO: support plural
                    last_rule = [_pattern2re(en), en, ""]
                    REF_RULES[key].append(last_rule)
                else:
                    last_en = en
                    REF_PAIRS[en] = True
            # TODO: use lang
            elif last_en or last_rule:
                if ru := re_find(r'^\s*ru\s*=\s*("[^"]*")', line):
                    ru = ast.literal_eval(ru)
                    if last_en:
                        REF_PAIRS[last_en] = ru
                    elif last_rule:
                        last_rule[-1] = ru
                elif re_find(r'^\s*}\s*$', line):
                    last_en = None

def _pattern2re(pat):
    def _prepare(p):
        if not p or p[0] != '<':
            return re.escape(p)
        elif wrapped := re_find(r'<\w+:tag>([^<]+)<\w+:tag>', p):
            return fr'<[\w.:]*{FORMAT_FUNCS_RE}\({re.escape(wrapped)}\)>'
        else:
            return r'<[^>]+>'

    pat_re = ''.join(map(_prepare, re.split(r'(<\w+:tag>[^<]+<\w+:tag>|<[^>]+>)', pat)))
    return f'^{pat_re}$'

def ref_code(code):
    key = _code_key(code)
    if (rule := CODE_RULES.get(key)) is not None:
        CODE_RULES[key] = False
        return rule

def _code_key(code):
    return '\n'.join(line.strip().lstrip('/').lstrip() for line in code)

def get_ref(opt):
    if opt in REF_PAIRS:
        return opt, REF_PAIRS[opt]

    if not REF_RULES:
        return opt, ""

    for key in _opt_keys(opt):
        for en_re, en, ru in REF_RULES.get(key, ()):
            if re.search(en_re, opt):
                return en, ru

    return opt, ""


imgRe = r"\[img\w*\][^\]]+\[/img\w*\]" # img + imgtooltip
tagsRe = r"\[[^\]]+]"
stop = set("""a the of in at to as is be are do has have having not and or"
              it it's its this that he she his her him ah eh , .""".split(" "))
patternKeyRe = r"([\w!-;?-~]*)<\w+:(\w+)>([\w!-;?-~]*)" # drop partial words adjacent to patterns

def _strip_tags(s):
    s = re.sub(imgRe, ' ', s);
    return re.sub(tagsRe, ' ', s)

def _rule_key(pat):
    def repl(m):
        prefix, sub, suffix = m.groups()
        return f'{prefix} {suffix}' if sub == 'tag' or sub.endswith('_tag') else ' '

    s = re.sub(patternKeyRe, repl, pat)
    return first(_iter_keys(s))

def _opt_keys(opt):
    s = re.sub(fr'<[\w.:]*{FORMAT_FUNCS_RE}\(([^)]*)\)>', r' \2 ', opt)
    return _iter_keys(s)

def _iter_keys(s):
    words = _strip_tags(s).lower().strip().split()
    for w in words:
        if w not in stop and (w[0] > ' ' and w[0] < '0' or w[0] > '9'):
            yield w


# Extraction

FILES_SKIP_RE = r'(\b|_)(rosetta(\w+)?|mocks|test|hack_msu)(\b|[_.-])|(?:^|[/\\])(!!|~~)'

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

    if OPTS["engine"]:
        import xt

        todo = [p for p in pairs if isinstance(p, dict) and not p[OPTS["lang"]]]
        ens = [p["en"] for p in todo]
        rus = xt.translate(OPTS["engine"], ens)
        for p, ru in zip(todo, rus):
            p[OPTS["lang"]] = ru

    for pair in pairs:
        out(_format(pair))

def _format(d):
    if isinstance(d, str):
        return d.rstrip()
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

        for start_pos in rewinds(stream):
            stream.pos = start_pos + 1
            debug("REWIND", stream.peek(0), stream.pos)

            if expr_destroyed(stream):
                debug("EXPR DESTROYED")
                stream.pos = prev_pos
                expr = None
                break

            stream.pos -= 1
            expr = parse_expr(stream)
            debug("PARSE", expr)

            if stream.pos < prev_pos:  # Failed to parse
                continue

            if expr.op == 'call' and STOP_FUNCS_RE.search(expr.val[0].val):
                debug("stop_call")
                stream.pos = prev_pos
                expr = None
                break

            if is_str_expr(expr):
                break
            debug("non_str")
        else:
            print(red("FAILED TO PARSE around %s, line %d" % (str(tok), tok.n)), file=sys.stderr)
            if OPTS["failfast"]:
                sys.exit(1)
            # If we failed to parse then simply use string as is
            debug(red("PARSE FAILED"))
            stream.pos = prev_pos
            expr = tok

        if expr is None:
            continue

        debug('EXPR', expr)
        for opt in expr_options(expr):
            debug('OPT', opt)
            if not opt_has_str(opt):
                continue
            opt = str_opt(opt)

            seen_key = re.sub(r'\d+', '1', opt) # TODO: only in <expr>
            if seen_key in SEEN: continue
            SEEN.add(seen_key)

            code = None
            if expr.op != 'str' or '<' in opt or '%s' in opt:
                code = lines[expr.n - 1:stream.peek(0).n]
                pair = ref_code(code)
                if pair == False:
                    continue
                elif pair is not None:
                    yield pair
                    continue

            en, tr = get_ref(opt)

            # TODO: better expr detection
            pair = {"mode": "pattern"} if expr.op != 'str' and '<' in opt or '%s' in opt else {}
            pair |= {"en": en, OPTS["lang"]: tr}
            if code:
                pair["_code"] = code
            debug(_format(pair))
            yield pair

        stream.chop()


def value_destroyed(stream):
    peek = stream.peek(1)
    if peek.val in {'?', '==', '!=', '>=', '<=', 'in'}:
        return True
    if peek.val == '.' and stream.peek(2).val == 'len':
        return True

    return expr_destroyed(stream)

def expr_destroyed(stream):
    peek_back = stream.peek(-1)
    if peek_back.val in {'throw', 'typeof', '==', '!=', '>=', '<='}:
        return True

    peek_b2 = stream.peek(-2).val
    if peek_back.val == '(' and (FIRST_ARG_STOP_RE.search(peek_b2) or STOP_FUNCS_RE.search(peek_b2)):
        return True

def is_str_expr(expr):
    if expr.op == 'call':
        return re.search(FORMAT_FUNCS_RE, expr.val[0].val)
    elif expr.op == 'expr' and expr.val[0].val == '[':
        return False
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


def rewinds(stream):
    return sorted({stream.pos - i for i in _rewinds(stream)})

def _rewinds(stream):
    for i in count():
        tok = stream.peek(-i)
        if tok.val in {'if', 'for'}:
            break
        elif tok.val in {None, ';', '+=', '=', '<-', '{', '}', 'throw'}:
            yield i
            break
        elif tok.val in {',', '['}:
            yield i
        elif tok.val == '(':
            #  yield i will capture the first arg of the func, which is wrong,
            #  while i + 1 captures (arg1, arg2), so works if there is only one argument :)
            yield i + 1
            prev = stream.peek(-i-1)
            if prev.op == 'ref' and not re.search(FORMAT_FUNCS_RE, tok.val):
                yield i + 2


class Revert:  # TODO: refactor into exception?
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


def parse_expr(stream):
    args = []
    debug("parse_expr >", stream.pos, stream.peek())
    while operand := parse_operand(stream):
        debug("parse_expr operand:", stream.pos, operand)
        if operand is REVERT:
            break
        args.append(operand)

        tok = stream.peek()
        if tok.op == 'op' and (tok.val in "+-/*<>" or tok.val in {"==", ">=", "<=", "!=", "in"}):
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


def opt_has_str(opt):
    if isinstance(opt, Token):
        if opt.op == 'call':
            _, args = opt.val
            return any(opt_has_str(a) for a in args)
        else:
            return opt.op == 'str' and opt.val != ''

    elif isinstance(opt, tuple):
        tokens = flatten(opt, follow=lambda x: type(x) is tuple)
        return any(opt_has_str(t) for t in tokens)

    assert isinstance(opt, str)
    return opt != ''


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


# from itertools import tee

# def with_next(seq, fill=None):
#     """Yields each item paired with its following: (item, next)."""
#     a, b = tee(seq)
#     next(b, None)
#     return zip(a, chain(b, [fill]))


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
    "keyword": r'\b(?:if|for|else|function)\b',
    "op ": r'\bin\b',
    "ref": r'(?:::)?[a-zA-Z_][\w.]*',
    "op": r'==|!=|<=|>=|<-|[+\-*/]=|[+=\-/*?(){},:;[\].<>]',
    "shit": r'[^\s(){}]+',
}
names = tuple(res.keys())
tokens_re = '|'.join('(%s)' % r for r in res.values())

def iter_tokens(lines):
    lines_iter = enumerate(lines, start=1)
    for i, line in lines_iter:
        for m in re_iter(tokens_re, line):
            yield first(Token(i, n.strip(), s) for n, s in zip(names, m) if s is not None)


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
