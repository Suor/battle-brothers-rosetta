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
    error(message)
    sys.exit(1)

def error(message):
    print(red(message), file=sys.stderr)
    if OPTS["failfast"]:
        sys.exit(1)

def warn(message):
    print(red(message), file=sys.stderr)

def debug(*args):
    if OPTS["debug"]:
        print(*args, file=sys.stderr)


# Reference

_LINE_RES = {
    'open': r'\{',
    'close': r'\},?',
    'no_en': r'//\s*en\s*=\s*("[^"]+")',
    'code': r'//.*',
    'en': r'en\s*=\s*("[^"]+")',  # TODO: support " in strs
    'func': r'.*\{',
}
LINE_RE = '|'.join(r'^\s*(%s)\s*$' % r for r in _LINE_RES.values())

REF_PAIRS = {}
REF_RULES = defaultdict(list)
CODE_RULES = defaultdict(str)

def load_ref(ref_file):
    with open(ref_file) as fd:
        block, en, code, meat = '', None, [], False
        level = 0
        for line in fd:
            block += line
            if m := re_find(LINE_RE, line):
                _open, _close, _, _no_en, _code, _, _en, _func = m
                if _open:
                    if level <= 0:
                        level = 0
                        block, en, code, meat = line, None, [], False
                    level += 1
                elif _close:
                    level -= 1
                    if level == 0:
                        # Ref by commented out code
                        if code:
                            CODE_RULES[_code_key(code)] += block
                        # Ref by en
                        if en:
                            if "<" in en:
                                key = _rule_key(en)
                                REF_RULES[key].append([_pattern2re(en), en, block])
                            else:
                                REF_PAIRS[en] = block
                elif _code:
                    if not meat:
                        code.append(_code)
                elif _func:
                    if level > 0:
                        level += 1
                        meat = True
                elif _en:
                    en = ast.literal_eval(_en)
                elif _no_en:
                    no_en = ast.literal_eval(_no_en)
                    if no_en not in REF_PAIRS:
                        REF_PAIRS[no_en] = line
            else:
                meat = True

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
        # Same code may produce several rule entries, which we concat on ref collection, however,
        # it will be asked for for any opt found in expression
        CODE_RULES[key] = ''
        return rule

def _code_key(code):
    return '\n'.join(line.strip().lstrip('/').lstrip() for line in code)

# TODO: do not update code if ref by en
def ref_en(opt):
    if opt in REF_PAIRS:
        return REF_PAIRS[opt]

    if not REF_RULES:
        return None

    for key in _opt_keys(opt):
        for en_re, en, pair in REF_RULES.get(key, ()):
            if re.search(en_re, opt):
                return pair


nestedRe = r'\[([^|]+)\|[^]]+\]'
imgRe = r'\[img[^\]]*\][^\[]+\[/img\w*\]|\[[^\]]+]' # img + imgtooltip
tagsRe = r'\[[^\]]+]'
stop = set("""a the of in at to as is be are do has have having not and or"
              it it's its this that he she his her him ah eh , .""".split(" "))
patternKeyRe = r"([\w!-;?-~]*)<\w+:(\w+)>([\w!-;?-~]*)" # drop partial words adjacent to patterns

def _strip_tags(s):
    s = re.sub(nestedRe, '\1', s)
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

FILES_SKIP_RE = r'(\b|_)(rosetta(\w+)?|mocks|test|hack_msu)(\b|[_.-])|(?:^|[/\\])(!!redirect|~~finalize)'

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
            warn(traceback.format_exc())
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

    pairs = list(extract(lines, filename=filename))

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

    # Build context comment if available
    context_comment = ""
    if "_context" in d:
        context_comment = f"    // context: {d['_context']}\n"

    lines = "".join(f"        {key} = {nutstr(val)}\n" for key, val in d.items() if key[0] != "_")
    return f"{context_comment}    {{\n{_prepare_code(d)}{lines}    }}"

def _prepare_code(d):
    if '_code' not in d:
        return ''
    lines = [l.replace('\t', ' ') for l in d['_code']]
    prefix = min(len(l) - len(l.lstrip(' ')) for l in lines)
    return "".join(f"        // {line[prefix:].rstrip()}\n" for line in lines)


SEEN = set()


class ContextTracker:
    def __init__(self, stream):
        # TODO:
        #   - clean shit like q, cls, p, m?
        #   - maybe readd filename if it is not duplicated by root assignment like in BB classes
        self.stream = stream
        self.scopes = []  # Stack of {'name': ..., 'depth': (brace, paren), 'type': 'function'|'assignment'|'call'}
        self.depth = 0

    def update_to(self, pos):
        assert pos >= self.stream.pos, "Cannot go backwards"

        while self.stream.pos < pos:
            self._update(self.stream.read())

    def _update(self, tok):
        # Track {}()[] depth, assume it's balanced
        if tok.val in "{([":
            # Transit pending function defs, check their depth to body depth
            top = self.scopes and self.scopes[-1]
            if tok.val == "{" and top and top.get('pending') and top["depth"] == self.depth:
                top.update({'depth': self.depth + 1, 'pending': False})

            self.depth += 1

            # Check if this is a function call (but not function parameters)
            if tok.val == "(" \
                    and self.stream.peek(-2).val != "function" and (lhs := self._extract_lhs()):
                # Special handling for hook() calls
                if re.search(r'\bhook|\bmods_hook', lhs) \
                        and (param := self.stream.peek(1)) and param.op == "str":
                    scope_name = ast.literal_eval(param.val).split('/')[-1]
                    self.scopes.append({'name': scope_name, 'depth': self.depth, 'type': 'call',
                                        'hook': True})
                else:
                    self.scopes.append({'name': lhs + '()', 'depth': self.depth, 'type': 'call'})

        elif tok.val in "})]":
            self.depth -= 1
            self._unwind_scopes()

        # Track function definitions
        elif tok.val == "function":
            next_tok = self.stream.peek(1)
            if next_tok.op == "ref":  # Named function - it's a statement
                self._drop_current_assignment()
                name = next_tok.val
                self.scopes.append({'name': name, 'depth': self.depth, 'type': 'function',
                                    'pending': True})
            # For anonymous functions (followed by `(`), don't drop - part of expression

        # Track assignments
        elif tok.val in {"=", "<-"}:
            self._drop_current_assignment()
            lhs = self._extract_lhs()
            self.scopes.append({'name': lhs, 'depth': self.depth, 'type': 'assignment'})

        elif tok.val in {';', ','} or tok.op == 'keyword':
            self._drop_current_assignment()

    def _unwind_scopes(self):
        while self.scopes and self.scopes[-1]['depth'] > self.depth:
            self.scopes.pop()

    def _drop_current_assignment(self):
        top = self.scopes and self.scopes[-1]
        if top and top['type'] == 'assignment' and top['depth'] >= self.depth:
            self.scopes.pop()

    def _extract_lhs(self):
        i = 1
        while True:
            tok = self.stream.peek(-i)
            if tok.op == "ref":
                i += 1
                if tok.val[0] != ".":
                    break
            elif tok.val in {")", "]"}:
                i = _rewind_parens(self.stream, i, tok)
                i += 1
            else:
                break

        lhs = "".join(self.stream.peek(-j).val for j in range(i - 1, 0, -1))
        return re.sub(r"\s+", "", lhs).removeprefix("this.")

    def get_context(self):
        # Find the last hook scope and cut off everything before it
        hook_idx = first(len(self.scopes) - 1 - i for i, scope in enumerate(reversed(self.scopes))
            if scope.get('hook'))

        # Use scopes from hook onwards, or all scopes if no hook
        parts = [scope['name'] for scope in self.scopes[hook_idx:] if scope['name'] != 'inherit()']
        return ".".join(parts) if parts else ""


def extract(lines, filename=None):
    stream = TokenStream(lines)
    context = ContextTracker(stream.clone())  # iterates independently

    for tok in stream:
        if tok.op != "str": continue
        s = ast.literal_eval(tok.val)
        if not is_interesting(s): continue
        if value_destroyed(stream): continue
        debug(green('>>>>>'), tok)

        context.update_to(stream.pos)
        expr = extract_expr(stream, lines)
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

            code, pair = None, None
            if expr.op != 'str' or '<' in opt or '%s' in opt:
                code = lines[expr.n - 1:stream.peek(0).n]
                pair = ref_code(code)
            if pair is None:
                pair = ref_en(opt)

            if pair is not None:
                yield pair
                continue

            # TODO: better expr detection
            pair = {"mode": "pattern"} if expr.op != 'str' and '<' in opt or '%s' in opt else {}
            pair |= {"en": opt, OPTS["lang"]: ''}
            if code:
                pair["_code"] = code
            pair["_context"] = context.get_context()

            debug(_format(pair))
            yield pair

        stream.chop()


def extract_expr(stream, lines):
    prev_pos = stream.pos
    tok = stream.peek(0)
    debug('LINE to REWIND', lines[tok.n - 1])

    failed = True
    for start_pos in rewinds(stream):
        stream.pos = start_pos + 1
        debug('REWIND', stream.peek(0), stream.pos)

        if expr_destroyed(stream):
            debug('expr_destroyed')
            stream.pos = prev_pos
            return None

        stream.pos -= 1
        expr = parse_expr(stream)
        debug('PARSE', expr)

        if stream.pos < prev_pos:  # Failed to parse
            continue

        if expr.op == 'call' and STOP_FUNCS_RE.search(expr.val[0].val):
            debug('stop_call')
            stream.pos = prev_pos
            return None

        if is_str_expr(expr):
            return expr

        debug('non_str')
        failed = False
    else:
        if failed:
            error('FAILED TO PARSE around %s, line %d' % (str(tok), tok.n))

        # If we failed to parse then simply use string as is
        stream.pos = prev_pos
        return tok


def value_destroyed(stream):
    peek = stream.peek(1)
    if peek.val in {'?', '==', '!=', '>=', '<=', 'in'}:
        return True
    if peek.val == '.' and stream.peek(2).val == 'len':
        return True

    return expr_destroyed(stream)

def expr_destroyed(stream):
    peek_back = stream.peek(-1)
    if peek_back.val in {'throw', 'typeof', 'case', '==', '!=', '>=', '<='}:
        return True

    peek_b2 = stream.peek(-2).val
    if peek_back.val == '(' and (FIRST_ARG_STOP_RE.search(peek_b2) or STOP_FUNCS_RE.search(peek_b2)):
        return True

def is_str_expr(expr):
    if expr.op == 'call':
        return re.search(FORMAT_FUNCS_RE, expr.val[0].val)
    elif expr.op == 'expr':
        if expr.val[0].val == '[':
            return False
        elif len(expr.val) >= 2 and expr.val[1].val == 'in':
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


REWIND_PARENS = {')': '(', ']': '[', '}': '{'}

def rewinds(stream):
    return sorted({stream.pos - i for i in _rewinds(stream)})

def _rewinds(stream):
    i, prev = 0, TokenStream.NONE
    while True:
        tok = stream.peek(-i)
        if tok.val in {'if', 'for', 'case', 'switch'}:
            break
        elif tok.val in {None, ';', '+=', '=', '<-', '&&', '||', 'throw', 'return'}:
            yield i
            break
        elif tok.val in {',', '['}:
            yield i
        elif tok.val in REWIND_PARENS:
            i = _rewind_parens(stream, i, tok)
            tok = stream.peek(-i)
        elif tok.val == '(':
            #  yield i will capture the first arg of the func, which is wrong,
            #  while i + 1 captures (arg1, arg2), so works if there is only one argument :)
            yield i + 1
        elif prev.val == '(' and tok.op == 'ref':
            yield i + 1

        i += 1
        prev = tok

def _rewind_parens(stream, i, paren):
    open_val = REWIND_PARENS[paren.val]

    start, count = i, 1
    while count > 0:
        i += 1
        tok = stream.peek(-i)
        if tok.val == paren.val:
            count += 1
        elif tok.val == open_val:
            count -= 1
        elif tok.val is None:
            if stream.pos < 0:
                warn("Found unpaired %s on line %s" % (tok.val, tok.n))
            return start

    return i


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


UNARY_OPS = {'!', '-'}
BINARY_OPS = {'==', '>=', '<=', '!=', 'in', '&&', '||'} | set('+-/*<>')

def parse_expr(stream):
    args = []
    debug("parse_expr >", stream.pos, stream.peek())
    while operand := parse_operand(stream):
        debug("parse_expr operand:", stream.pos, operand)
        if operand is REVERT:
            break
        args.append(operand)

        tok = stream.peek()
        if tok.op == 'op' and tok.val in BINARY_OPS:
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
                warn("Found weird call: %s(...)" % args)
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

    elif tok.val in UNARY_OPS:
        expr = parse_expr(stream)
        if expr is REVERT:
            return REVERT
        return Token(tok.n, 'expr', [tok, expr])

    elif tok.val == '(':
        expr = parse_expr(stream)
        if stream.peek().val == ')':
            stream.read()
            return expr

    elif tok.val in {'[', '{'}:
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
    close_val = {'(': ')', '[': ']', '{': '}'}[paren.val]

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
        warn("Found unpaired %s on line %s" % (paren.val, paren.n))
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
            if len(parts[1::2]) != len(args[1:]):
                warn("Broken format at line %d" % tok.n)
            else:
                parts[1::2] = args[1:]  # TODO: add op.+ ?
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


# Tokenization

class Token(namedtuple("Token", "n op val")):
    __slots__ = ()
    def __str__(self):
        return '%s.%s' % (self.op, self.val)
    __repr__ = __str__

class TokenStream:
    NONE = Token(None, None, None)

    def __init__(self, lines):
        self.tokens = list(tok for tok in iter_tokens(lines) if tok.op != 'comment')
        self.pos = -1
        self.start = 0

    def clone(self):
        new = TokenStream.__new__(TokenStream)
        new.tokens, new.pos, new.start = self.tokens, self.pos, self.start
        return new

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
    "keyword": r'\b(?:if|else|for|foreach|return|function|switch|case|local|const)\b',
    "op ": r'\bin\b',
    "ref": r'(?:::)?[a-zA-Z_][\w.]*',
    "op": r'==|!=|<=|>=|<-|&&|\|\||[+\-*/]=|[+=\-/*!?(){},:;[\].<>]',
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
    "camel_id": r'^[\w-]+\.[A-Z][a-z0-9]+\w*$',
    "kebab": r'^[a-zA-Z]*-[\w-]*$',
    "common": r'^(title|description|text|hint|socket)$',
    "junk": r'^[`~!@#$%^&*()_+=[\]\\{}|;:\'",./<>?\s-]+$',
    "prefix": r'^[a-z]+:\s*$',
    "req": r'^\w+ *>= *[0-9.-]+$',
    # "key": r'^[a-z]+$',  # may have false positives
}
INTERNAL_RE = '|'.join(INTERNAL_RES.values())

def is_interesting(s):
    s = _strip_tags(strip_html(s))
    return s and not re.search(INTERNAL_RE, s)

def strip_html(s):
    return re.sub(r'<[^>]+>|&\w+;', '', s)


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
