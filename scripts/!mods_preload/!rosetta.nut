// Qs:
// 1. id but source changed: keep full string / crc => full string
// 1a. Do we need id? To catch changes? => yessish
// 2. place to intercept: overwrite / closest to source / sq-js border / js
//    => simplest to implement for now, may move later
// 3. How to not translate already translated? Esp. going through regexes.
//    => ignore this for now
// 4. Longest keyword or something? Require static start or end?
//    => first non-tag non-stopword lowercased
// 5. What if we have match at the start? Then the string might have different contentKey!!!
//    => go thorugh all potential content keys in a string to translate
// 6. What do we do with < and > in original strings?
//    => escape? Still TODO
// 7. Sentences mode?
// 8. Load earlier, so that some things would work without scheduling? Yes.

local Array = ::std.Array, Table = ::std.Table, Re = ::std.Re, Str = ::std.Str;
local Log = ::std.Debug.with({prefix = "rosetta: "});
local Warn = Log.with({level = "warning"});
local Debug = Log.noop();
local def = ::Rosetta <- {
    ID = "mod_rosetta"
    Name = "Rosetta Translations"
    Version = "0.2.0"
    Updates = {
        nexus = "https://www.nexusmods.com/battlebrothers/mods/802"
        github = "https://github.com/Suor/battle-brothers-rosetta"
    }
}

Table.extend(def, {
    active = null
    langs = {}
    function addLang(_key, _desc) {
        if (_key in langs) throw "Language " + _key + " is already registered";
        langs[_key] <- _desc;
        if (_desc.detect()) activate(_key);
    }
    function activate(_lang) {
        active = _lang;
        // TODO: return en Name and Tooltip before dropping cache
        perksCache = {}; // Empty cache
    }

    maps = {}
    function add(_def, _pairs) {
        local lang = _def.lang;
        Log.log("Adding " + _pairs.len() + " " + lang + " pairs in " + _def.mod.id);
        if (!(lang in langs))
            throw "Please register your language with ::Rosetta.addLang(" + lang + ", ...) first";

        if (!(lang in maps)) maps[lang] <- {strs = {}, ids = {}, rules = {}};
        local strs = maps[lang].strs, ids = maps[lang].ids, rules = maps[lang].rules;
        foreach (pair in _pairs) {
            if (!validatePair(lang, pair)) continue;

            local mode = Table.get(pair, "mode", "str");
            if (mode == "pattern" || "plural" in pair || "split" in pair) {
                local key = _ruleKey(pair.en);
                if (!(key in rules)) rules[key] <- [];
                rules[key].push(makeRule(lang, pair));
            } else {
                if ("id" in pair) ids[pair.id] <- pair[lang];
                if ("en" in pair) strs[pair.en] <- pair[lang];
            }
        }

        // Log stats
        if (Log.enabled) {
            local rulesNum = Array.sum(Table.values(rules).map(@(v) v.len()));
            Log.log(ids.len() + " ids, " + strs.len() + " strings, " + rulesNum + " rules.");
            if (rules.len() > 0) {
                local ruleCounts = Table.mapValues(rules, @(k, v) v.len());
                local limit = Array.nlargest(3, Table.values(ruleCounts)).top();
                Log.log("most used keys", ruleCounts, {filter = @(k, v) k == "" || v >= limit});
            }
        }
    }
    function validatePair(_lang, _pair) {
        if (!("en" in _pair) && !("id" in _pair))
            throw "No en nor id in Rosetta pair: " + Log.pp(_pair);

        local def = langs[_lang];

        if (Table.get(_pair, "mode") == "pattern" || "plural" in _pair) {
            if ("id" in _pair) throw "Can't use mode=\"pattern\" or plural with id";
        }

        if ("plural" in _pair) {
            local empty = false;
            foreach (n in def.plural.forms) {
                local key = "n" + n;
                if (!(key in _pair)) throw "No " + key + " in Rosetta pair: " + Log.pp(_pair);
                if (_pair[key] == "") empty = true;
            }
            if (empty) {
                Warn.log("untranslated plural pair en = " + _pair.en + ", skipping");
                return false;
            }
        }
        else if ("split" in _pair || "use" in _pair) {
            return true;
        }
        else {
            if (!(_lang in _pair))
                throw "No " + _lang + " in Rosetta pair: " + Log.pp(_pair);
            if (_pair[_lang] == "") {
                local ident = "en" in _pair ? "en = " + _pair.en : "id = " + _pair.id;
                Warn.log("untranslated pair with " + ident + ", skipping");
                return false; // Not loading pairs with empty translations
            }
        }

        return true;
    }

    tagsRe = regexp(@"\[img[^\]]*\][^\[]+\[/img\w*\]|\[[^\]]+]|%\w+%") // img + imgtooltip + bbcode + %name%
    patternKeyRe = regexp(@"([\w!-;?-~]*)<\w+:(\w+)>([\w!-;?-~]*)") // drop partial words adjacent to patterns
    stop = (function () {
        local set = {};
        foreach (w in split("a the of in at to as is be are do has have having not and or"
                          + " it  it's its this that he she his her him ah eh , .", " "))
            set[w] <- true;
        return set;
    })()
    function _stripTags(_str) {
        return Re.replace(_str, tagsRe, " ");
    }
    function _ruleKey(_pat) {
        local str = Re.replace(_pat, patternKeyRe, function (_prefix, _sub, _suffix) {
            return _sub == "tag" || Str.endswith(_sub, "_tag")
                ? (_prefix || "") + " " + (_suffix || "") : "";
        })
        return resume _iterKeys(str);
    }
    // TODO: return longer words first
    function _iterKeys(_str) {
        local words = split(strip(_stripTags(_str).tolower()), " \n")
        // skip stop words, numbers and control chars
        foreach (w in words) if (!(w in stop) && (w[0] > ' ' && w[0] < '0' || w[0] > '9')) yield w;
        yield "";
    }

    patternRe = regexp(@"([^<]+)|<(\w+):(\w+)>")
    placesRe = regexp(@"<(\w+)(?::(\w+))?>")
    subRes = (function () {
        local open = @"\[[^\]]+\]", close = @"\[/[^\]]+\]";
        local res = {
            int = @"[+\-]?\d+"
            val = @"[+\-]?\d+(?:\.\d+)?%?"
            word = @"[^ \t\n,.:;!\[\]()]+"
            str = @"[^\[\]]*" // Not used in matchParts() because of a buggy regexp engine
            tag = open
            img = @"\[img\][^\]]+\[/img\]"
        }
        foreach (key in ["int" "val" "str"])
            res[key + "_tag"] <- open + res[key] + close;

        return Table.mapValues(res, @(k, v) regexp(v));
    })()
    function makeRule(_lang, _pair) {
        local parts = parsePattern(_pair.en);
        local rule = Table.merge(_pair, {parts = parts});
        validateRule(_lang, rule);
        return rule;
    }
    function parsePattern(_pat) {
        return Re.all(_pat, patternRe).map(
            @(p) p[0] && p[0] != "" ? p[0] : {name = p[1], sub = p[2]})
    }
    RuleErr = Log.with({prefix = " in ", filter = @(k, _) k.len() == 2 || k == "mode" || k == "plural"})
    function validateRule(_lang, _rule) {
        local labels = {};
        foreach (p in _rule.parts)
            if (typeof p == "table") labels[p.name] <- true;

        if ("plural" in _rule && !(_rule.plural in labels)) {
            throw "Plural label is not in 'en'" + RuleErr.pp(_rule);
        }

        foreach (i, part in _rule.parts) {
            if (typeof part == "string") continue;
            if (!(part.sub in subRes)) {
                throw format("Label type '%s' is not supported", part.sub) + RuleErr.pp(_rule);
            }
            local prev = i > 0 ? _rule.parts[i-1] : null;
            if (part.sub == "str" && typeof prev == "table" && prev.sub == "str") {
                throw "Two :str next to each other not allowed" + RuleErr.pp(_rule);
            }
        }

        foreach (key, val in _rule) {
            if (!(key == _lang || key[0] == 'n' && key.len() == 2)) continue; // output keys
            foreach (i, p in Re.all(val, placesRe)) {
                if (!(p[0] in labels)) {
                    throw format("Label '%s' is in '%s' but not in 'en'", p[0], key) + RuleErr.pp(_rule);
                }
            }
        }
    }

    wordRe = regexp(@"[a-zA-Z][a-zA-Z]")
    nonAsciiRe = regexp(@"[^\c -~]")
    function _isInteresting(_str) {  # TODO: strip html shit?
        // if (nonAsciiRe.search(_str) || !wordRe.search(_str)) return false;
        local str = Re.replace(_str, "Reforged|MSU|MSU Dummy Player Background|SendLog", "");
        if (!wordRe.search(str)) return false;
        return !!wordRe.search(_stripTags(str));
    }
    function _strKey(_str) {
        return Re.replace(_stripTags(_str), @"\d+", "1")
    }

    reports = {}
    stats = {hits = 0, misses = 0, rule_hits = 0, rule_uses = 0}
    ruleUseKeys = {}
    function tap(_str, _id, _value, _rule = false) {
        if (Log.enabled) {
            local statsKey = _value ? (_rule ? "rule_hits" : "hits") : "misses";
            stats[statsKey]++;
        }

        local key = _strKey(_str);
        if (key in reports) return _value || _str;
        if (_value) {
            Debug.log("translate str=" + _str + " TO " + _value + (_id ? " id=" + _id : ""));
        } else if (Log.enabled && _isInteresting(_str)) {
            Log.log("NOT FOUND str=" + _str + (_id ? " id=" + _id : ""));
        }
        reports[key] <- true;
        return _value || _str;
    }
    function translate(_str, _id = null, _skip_rule = null) {
        if (active == null) return _str;

        Debug.log("TRANSLATING", _str)

        local ret = null, amap = maps[active];
        if (_id != null && _id in amap.ids) ret = amap.ids[_id];
        else if (_str in amap.strs) ret = amap.strs[_str];
        if (ret && ret != "") return tap(_str, _id, ret);

        if (Log.enabled) {
            if (stats.rule_uses > 0 && stats.rule_uses % 100 == 0) {
                Log.log("stats", stats);
                if (ruleUseKeys.len() > 0) {
                    local limit = Array.nlargest(3, Table.values(ruleUseKeys)).top();
                    Log.log("most used keys", ruleUseKeys, {filter = @(k, v) k == "" || v >= limit});
                }
            }
            stats.rule_uses++;
        }
        // Look for pattern
        // TODO: think of rules priority, now it's mixed whichever gets the first key,
        //       then added order
        foreach (key in _iterKeys(_str)) {
            foreach (rule in Table.get(amap.rules, key, [])) {
                if (rule == _skip_rule) continue; // Protect against split rule stack overflow
                                                  // TODO: nicer way to do this?
                if (Log.enabled) {
                    if (key in ruleUseKeys) ruleUseKeys[key]++; else ruleUseKeys[key] <- 1;
                }
                Debug.log("rule", rule);
                local matches = matchParts(_str, rule.parts);
                Debug.log("matches", matches);
                if (!matches) continue;

                local ret = useRule(rule, _str, matches);
                return tap(_str, _id, ret, true)
            }
        }
        return tap(_str, _id, null, true);
    }
    function useRule(_rule, _str, _matches) {
        if ("split" in _rule) {
            return useSplit(_rule, _rule.split, _str);
        }
        else if ("use" in _rule) {
            return _rule.use(_str, _matches);
        } else {
            local to = "plural" in _rule ? "n" + plural(_matches[_rule.plural]) : active;
            // NOTE: if we use parts then here also can join parts, which might be faster
            return Re.replace(_rule[to], placesRe, function (_label, _flags) {
                local t = _matches[_label];
                return _flags == "t" ? def.translate(t) : t;
            })
        }
    }
    function useSplit(_rule, _sep, _str) {
        return Str.join(_sep, Str.split(_sep, _str).map(@(p) def.translate(p, null, _rule)));
    }
    function matchParts(_str, _parts) {
        local pos = 0, matches = {};
        local sn = _str.len();
        for (local i = 0; i < _parts.len(); i++) {
            local p = _parts[i];
            if (typeof p == "string") {
                local pn = p.len();
                if (pos + pn > sn || _str.slice(pos, pos + pn) != p) return null;
                pos += pn;
            } else if (p.sub != "str") {
                local re = subRes[p.sub];
                local m = re.search(_str, pos);
                if (m == null || m.begin != pos) return null;
                matches[p.name] <- _str.slice(m.begin, m.end);
                pos = m.end;
            } else {
                if (i == _parts.len() - 1) {
                    matches[p.name] <- _str.slice(pos);
                    return matches;
                }
                local next = _parts[i + 1], re;
                if (typeof next == "table") {
                    assert(next.sub != "str", "Should be prevented by rule validation")
                    re = subRes[next.sub];
                }

                local np = pos, m;
                while (true) {
                    // We look matches from left to right, this makes <...:str> non-greedy
                    if (typeof next == "string") {
                        np = _str.find(next, np);
                        if (np == null) return null;
                        m = {begin = np, end = np + next.len()}
                    } else {
                        m = re.search(_str, np);
                        if (!m) return null;
                        np = m.begin;
                    }

                    local tailMatches = matchParts(_str.slice(m.end), _parts.slice(i + 2));
                    if (tailMatches) {
                        matches[p.name] <- _str.slice(pos, np);
                        if (typeof next != "string")
                            matches[next.name] <- _str.slice(m.begin, m.end);
                        return Table.extend(matches, tailMatches)
                    }
                    np++;
                }
                return null;
            }
        }
        return pos == sn ? matches : null;
    }
    function plural(_s) {
        local n;
        try {n = _s.tointeger()}
        catch (err) {
            try {n = strip(_stripTags(_s)).tointeger()}
            catch (err) {
                ::logWarning("rosetta: ERROR failed to convert to number: " + err);
                return langs[active].plural.fallback;
            }
        }
        return langs[active].plural.choose(n);
    }

    function translateTooltip(_tooltip) {
        if (_tooltip == null) return null;
        return _tooltip.map(
            @(item) "text" in item ? Table.extend(item, {text = def.translate(item.text)}) : item);
    }
    perksCache = {}
    function translatePerk(_perk) {
        if (_perk == null) return _perk;
        if (_perk in perksCache) return _perk;// perksCache[_perk];
        // local perk = clone _perk;
        local stash = {Name = _perk.Name, Tooltip = _perk.Tooltip};
        _perk.Name <- translate(_perk.Name);
        _perk.Tooltip = translate(_perk.Tooltip, "perk:" + _perk.ID + ".Tooltip");
        perksCache[_perk] <- stash;
        return _perk;
    }
    function translatePerkTree(_perks) {
        return _perks.map(@(row) row.map(@(p) ::Rosetta.translatePerk(p)));
    }
})

def.addLang("ru", {
    name = "Русский"
    function detect() {
        return ::Const.Strings.EntityName[0] == "Некромант";
    }
    plural = {
        forms = [1 2 5]
        fallback = 5
        function choose(n) {
            return n % 10 == 1 && n % 100 != 11 ? 1
                 : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? 2 : 5
        }
    }
})
def.addLang("es", {
    name = "Español"
    function detect() {
        return ::Const.Strings.EntityName[0] == "???";
    }
    plural = {
        forms = [1 2]
        fallback = 2
        function choose(n) {
            return n == 1 ? 1 : 2
        }
    }
})
def.addLang("ja", {
    name = "日本語"
    plural = null // no plurals in japanese
    function detect() {
        // TODO: better detect, this doesn't work
        return ::Const.Strings.EntityName[0] == "ネクロマンサー";
    }
})


local mod = def.mh <- ::Hooks.register(def.ID, def.Version, def.Name);
mod.require("mod_msu >= 1.6.0", "stdlib >= 2.5");

::include("rosetta/hooks");
::include("rosetta/pack_ru");
