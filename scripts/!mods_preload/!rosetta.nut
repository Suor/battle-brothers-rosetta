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
// 8. Load earlier, so that some things would work without scheduling?

local Table = ::std.Table, Re = ::std.Re, Str = ::std.Str;
local Debug = ::std.Debug.noop();
local def = ::Rosetta <- {
    ID = "mod_rosetta"
    Name = "Rosetta Translations"
    Version = "0.1.1"
    Updates = {
        nexus = "https://www.nexusmods.com/battlebrothers/mods/802"
        github = "https://github.com/Suor/battle-brothers-rosetta"
    }
}

local regexp = regexp;
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
        if (!(lang in langs))
            throw "Please register your language with ::Rosetta.addLang(" + lang + ", ...) first";

        if (!(lang in maps)) maps[lang] <- {strs = {}, ids = {}, rules = {}};
        local strs = maps[lang].strs, ids = maps[lang].ids, rules = maps[lang].rules;
        foreach (pair in _pairs) {
            if (lang in pair && pair[lang] == "") continue;
            local pluralKey = langs[lang].pluralDefault;
            if (pluralKey in pair && pair[pluralKey] == "") continue;

            local mode = Table.get(pair, "mode", "str");
            if (mode == "pattern" || "plural" in pair) {
                if ("id" in pair) throw "Can't use mode=\"pattern\" or plural with id";

                local key = _contentKey(pair.en);
                if (!(key in rules)) rules[key] <- [];
                rules[key].push(makeRule(lang, pair));
                Debug.log("Put rule with key=" + key + ", chain-len=" + rules[key].len() + ", rule", rules[key].top());
            } else {
                if ("id" in pair) ids[pair.id] <- pair[lang];
                if ("en" in pair) strs[pair.en] <- pair[lang];
            }
        }
    }

    // TODO: join these two
    imgRe = regexp(@"\[img][^\[]+\[/img\]")
    tagsRe = regexp(@"\[[^\]]+]")
    stop = (function () {
        local set = {};
        foreach (w in split("a the of in at to as is be are do has have having not and or"
                          + " it  it's its this that he she his her him ah eh", " "))
            set[w] <- true;
        return set;
    })()
    function _stripTags(_str) {
        local s = Re.replace(_str, imgRe, "");
        return Re.replace(s, tagsRe, "");
    }
    function _contentKey(_str) {
        return resume _iterKeys(_str);
    }
    // TODO: return longer words first
    function _iterKeys(_str) {
        local words = split(strip(_stripTags(_str).tolower()), " ")
        foreach (w in words) if (!(w in stop) && w[0] > '>') yield w; // skip numbers and <x:type>
        yield "";
    }

    patternRe = regexp(@"([^<]+)|<(\w+):(\w+)>")
    placesRe = regexp(@"<(\w+)>")
    subRes = {
        int = @"[+\-]?\d+"
        article = @"[Aa]n? "
        word = @"[^ \t\n,.:;!\[\]]+"
        str = @"[^\[\]]+" // TODO: test this
        tag = @"\[[^\]]+\]"
        // tag_close = @"\[/[^\]]+\]"
        int_tag = @"\[[^\]]+\][+\-]?\d+\[/[^\]]+\]" // is there a better way?
        str_tag = @"\[[^\]]+\][^\]]+\[/[^\]]+\]"
    }.setdelegate({
        function _get(_key) {throw "Label type '" + _key + "' not supported"}
    })
    subResComp = {}.setdelegate({
        function _get(_key) {return this[_key] <- regexp(def.subRes[_key])}
    })
    function makeRule(_lang, _pair) {
        local pat = parsePattern(_pair.en);
        local rule = Table.merge(_pair, {parts = pat.parts, l2i = {}});
        foreach (i, l in pat.labels) rule.l2i[l] <- i;

        if ("plural" in _pair) rule.plural_i <- pat.labels.find(_pair.plural);

        validateRule(_lang, pat, rule);
        return rule;
    }
    function parsePattern(_pat) {
        local patterns = Re.all(_pat, patternRe);
        return {
            // TODO: prepare all regexes beforehand
            parts = patterns.map(@(p) p[0] && p[0] != "" ? p[0] : {sub = p[2]})
            labels = patterns.filter(@(_, p) !p[0] || p[0] == "").map(@(p) p[1])
        }
    }
    function validateRule(_lang, _pat, _rule) {
        if ("plural_i" in _rule && _rule.plural_i == null)
            throw format("Plural label '%s' is not in the pattern '%s'", _rule.plural, _rule.en);

        foreach (key, val in _rule) {
            if (!(key == _lang || key[0] == 'n' && key.len() == 2)) continue; // output keys
            foreach (i, p in Re.all(val, placesRe)) {
                if (!(p in _rule.l2i))
                    throw format("Label '%s' is found in '%s' but not in the pattern", p, val);
            }
        }
    }

    reports = {}
    function tap(_str, _id, _value) {
        if (_str in reports) return _value || _str;
        if (_value) {
            Debug.log("rosetta: translate str=" + _str + " TO " + _value + (_id ? " id=" + _id : ""));
        } else {
            Debug.log("rosetta: translate str=" + _str + " NOT FOUND" + (_id ? " id=" + _id : ""));
        }
        reports[_str] <- true;
        return _value || _str;
    }
    function translate(_str, _id = null) {
        if (active == null) return _str;

        local ret = null, amap = maps[active];
        if (_id != null && _id in amap.ids) ret = amap.ids[_id];
        else if (_str in amap.strs) ret = amap.strs[_str];
        if (ret && ret != "") return tap(_str, _id, ret);

        // Look for pattern
        foreach (key in _iterKeys(_str)) {
            foreach (rule in Table.get(amap.rules, key, [])) {
                Debug.log("rule", rule);
                local matches = matchParts(_str, rule.parts);
                Debug.log("matches", matches);
                if (!matches) continue;
                if (typeof matches == "string") matches = [matches];

                local to = "plural_i" in rule ? "n" + plural(matches[rule.plural_i]) : active;
                if (!rule[to] || rule[to] == "") continue;
                // NOTE: if we use parts then here also can join parts, which might be faster
                local ret = Re.replace(rule[to], @"<(\w+)>", @(l) matches[rule.l2i[l]]);
                return tap(_str, _id, ret)
            }
        }
        return tap(_str, _id, null);
    }
    function matchParts(_str, _parts) {
        local pos = 0, matches = [];
        local sn = _str.len();
        for (local i = 0; i < _parts.len(); i++) {
            local p = _parts[i];
            if (typeof p == "string") {
                local pn = p.len();
                if (pos + pn > sn || _str.slice(pos, pos + pn) != p) return null;
                pos += pn;
            } else if (p.sub != "str") {
                local re = subResComp[p.sub];
                local m = re.search(_str, pos);
                if (m == null || m.begin != pos) return null;
                matches.push(_str.slice(m.begin, m.end));
                pos = m.end;
            } else {
                if (i == _parts.len() - 1) {
                    matches.push(_str.slice(pos));
                    return matches;
                }
                local next = _parts[i + 1], re;
                if (typeof next == "table") {
                    if (next.sub == "str") throw "<a:str><b:str> is prohibited!";
                    re = subResComp[next.sub];
                }

                local np = pos, m;
                while (true) {
                    // We look matches from left to right, this makes <...:str> non-greedy
                    if (typeof next == "string") {
                        np = _str.find(next, np + 1);
                        if (np == null) return null;
                        m = {begin = np, end = np + next.len()}
                    } else {
                        m = re.search(_str, np + 1);
                        if (!m) return null;
                        np = m.begin;
                    }

                    local tailMatches = matchParts(_str.slice(m.end), _parts.slice(i + 2));
                    if (tailMatches) {
                        matches.push(_str.slice(pos, np));
                        matches.push(_str.slice(m.begin, m.end));
                        matches.extend(tailMatches);
                        return matches;
                    }
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
                return langs[active].pluralDefault;
            }
        }
        return langs[active].plural(n);
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
local _ = def.translate.bindenv(def);

def.addLang("ru", {
    name = "Русский"
    pluralDefault = 5 // if in doubt
    function plural(n) {
        return n % 10 == 1 && n % 100 != 11 ? 1
             : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? 2 : 5
    }
    function detect() {
        return ::Const.Strings.EntityName[0] == "Некромант";
    }
})


local mod = def.mh <- ::Hooks.register(def.ID, def.Version, def.Name);
mod.require("mod_msu >= 1.6.0", "stdlib >= 2.2");
mod.queue(function () {
    def.msu <- ::MSU.Class.Mod(def.ID, def.Version, def.Name);

    local msd = ::MSU.System.Registry.ModSourceDomain, upd = def.Updates;
    def.msu.Registry.addModSource(msd.NexusMods, upd.nexus);
    def.msu.Registry.addModSource(msd.GitHub, upd.github);

    // This fixes MSU.isWeaponType() for russian language, which fixes some skills dependent on it,
    // i.e. many Reforged perks.
    Table.extend(::Const.Items.WeaponType, {
        "Топор": 1
        "Лук": 2
        "Тесак": 4
        "Арбалет": 8
        "Кинжал": 16
        "Пищаль": 32
        "Кистень": 64
        "Молот": 128
        "Булава": 256
        "Древковое оружие": 512
        "Праща": 1024
        "Копьё": 2048
        "Меч": 4096
        "Посох": 8192
        "Метательное оружие": 16384
        "Музыкальный инструмент": 32768
    })

    // Hooks
    mod.hook("scripts/ui/screens/tactical/modules/topbar/tactical_screen_topbar_event_log",
            function (q) {
        q.log = q.logEx = @(__original) function (_text) {
            __original(def.translate(_text))
        }
    })

    // Perks
    mod.hook("scripts/ui/global/data_helper", function (q) {
        q.convertEntityToUIData = @(__original) function (_entity, _activeEntity) {
            local result = __original(_entity, _activeEntity);
            // result.character.name = def.translate(result.character.name);
            // result.character.title = def.translate(result.character.title);

            if ("necro_perkTree" in result) {
                result.necro_perkTree = def.translatePerkTree(result.necro_perkTree);
            }
            return result;
        }
    })

    local Perks_findById = ::Const.Perks.findById;
    ::Const.Perks.findById = function (_id) {
        return def.translatePerk(Perks_findById(_id));
    }

    // Tooltips
    mod.hook("scripts/ui/screens/tooltip/tooltip_events", function (q) {
        local tooltipHook = @(__original) function (...) {
            vargv.insert(0, this);
            return def.translateTooltip(__original.acall(vargv));
        }
        q.onQueryTileTooltipData = tooltipHook;
        q.onQueryEntityTooltipData = tooltipHook;
        q.onQueryEntityTooltipData = tooltipHook;
        q.onQueryRosterEntityTooltipData = tooltipHook;
        q.onQuerySkillTooltipData = tooltipHook;
        q.onQueryStatusEffectTooltipData = tooltipHook;
        q.onQuerySettlementStatusEffectTooltipData = tooltipHook;
        q.onQueryUIElementTooltipData = tooltipHook;
        q.onQueryUIItemTooltipData = tooltipHook;
        q.onQueryUIPerkTooltipData = tooltipHook;
        q.onQueryFollowerTooltipData = tooltipHook;
    })

    local simpleGetter = @(__original) function () {
        return _(__original());
    }
    local function makeGetter(_field) {
        return @(__original) function () {
            local script = IO.scriptFilenameByHash(this.ClassNameHash);
            Debug.log("get" + _field + " " + this.ClassName + " " + script)
            return _(__original(), script + "." + _field);
        }
    }

    // Background
    mod.hook("scripts/skills/backgrounds/character_background", function (q) {
        q.getName = @(__original) function () {
            local ret = __original();
            local parts = Str.split(": ", ret, 1);
            if (parts.len() == 2) return parts[0] + ": " + _(parts[1]);
            return ret;
        }
        q.getNameOnly = simpleGetter;
    })
    mod.hookTree("scripts/skills/backgrounds/character_background", function (q) {
        q.onBuildDescription = @(__original) function () {
            local script = IO.scriptFilenameByHash(this.ClassNameHash);
            return _(__original(), script + ".onBuildDescription");
        }
    })

    // TODO: hook other things with names, descriptions, etc too
    mod.hook("scripts/entity/tactical/actor", function (q) {
        q.getNameOnly = simpleGetter;
        q.getKilledName = simpleGetter;
        q.getTitle = simpleGetter;
        q.getName = @(__original) function () {
            local ret = __original();
            // Allow translating name and title separately
            local vanilla = m.Title == "" ? m.Name : m.Name + " " + m.Title;
            if (ret == vanilla) return m.Title == "" ? _(m.Name) : _(m.Name) + " " + _(m.Title);
            return _(ret);
        }
    })
    mod.hook("scripts/entity/tactical/player", function (q) {
        q.getTitle = simpleGetter;
    })
    mod.hookTree("scripts/skills/skill", function (q) {
        q.getDescription = makeGetter("Description");
    })
    mod.hookTree("scripts/scenarios/world/starting_scenario", function (q) {
        q.getName = makeGetter("Name");
        q.getDescription = makeGetter("Description");
    })

}, ::Hooks.QueueBucket.Late);
