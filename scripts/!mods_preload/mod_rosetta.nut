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
local Debug = ::std.Debug;
local def = ::Rosetta <- {
    ID = "mod_rosetta"
    Name = "Rosetta Translations"
    Version = "0.0.1"
    Updates = {
        // nexus = "https://www.nexusmods.com/battlebrothers/mods/775"
        github = "https://github.com/Suor/battle-brothers-rosetta"
        tagPrefix = ""
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
                ::logInfo("Put rule with key=" + key)
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
        word = @"[^ \t\n,.:;!\[\]]+"
        str = @"[^\[\]]+" // TODO: test this
        tag = @"\[[^\]]+\]"
        // tag_close = @"\[/[^\]]+\]"
        int_tag = @"\[[^\]]+\][+\-]?\d+\[/[^\]]+\]" // is there a better way?
        str_tag = @"\[[^\]]+\][^\]]+\[/[^\]]+\]"
    }.setdelegate({
        function _get(_key) {throw "Label type '" + _key + "' not supported"}
    })
    function parsePattern(_pat) {
        local patterns = Re.all(_pat, patternRe);
        local m2re = @(p) p[0] && p[0] != "" ? Re.escape(p[0]) : "(" + def.subRes[p[2]] + ")";
        return {
            re = "^" + Str.join("", patterns.map(m2re)) + "$"
            labels = patterns.filter(@(_, p) !p[0] || p[0] == "").map(@(p) p[1])
        }
    }
    function makeRule(_lang, _pair) {
        local pat = parsePattern(_pair.en);
        local rule = Table.merge(_pair, {re = pat.re, l2i = {}});
        foreach (i, l in pat.labels) rule.l2i[l] <- i;

        if ("plural" in _pair) rule.plural_i <- pat.labels.find(_pair.plural);

        validateRule(_lang, pat, rule);
        return rule;
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
            logInfo("rosetta: translate str=" + _str + " TO " + _value + (_id ? " id=" + _id : ""));
        } else {
            logInfo("rosetta: translate str=" + _str + " NOT FOUND" + (_id ? " id=" + _id : ""));
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
                local matches = Re.find(_str, rule.re);
                // Debug.log("rule", rule);
                // Debug.log("matches", matches);
                if (!matches) continue;
                if (typeof matches == "string") matches = [matches];

                local to = "plural_i" in rule ? "n" + plural(matches[rule.plural_i]) : active;
                if (!rule[to] || rule[to] == "") continue;
                local ret = Re.replace(rule[to], @"<(\w+)>", @(l) matches[rule.l2i[l]]);
                return tap(_str, _id, ret)
            }
        }
        return tap(_str, _id, null);
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
        if (_perk in perksCache) return perksCache[_perk];
        local perk = clone _perk;
        perk.Name = translate(perk.Name);
        perk.Tooltip = translate(perk.Tooltip, "perk:" + perk.ID + ".Tooltip");
        perksCache[_perk] <- perk;
        return perk;
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
    // def.msu.Registry.addModSource(msd.NexusMods, upd.nexus);
    // def.msu.Registry.addModSource(msd.GitHubTags, upd.github, {Prefix = upd.tagPrefix});
    // def.msu.Registry.setUpdateSource(msd.GitHubTags);

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
            logInfo("get" + _field + " " + this.ClassName + " " + script)
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
        q.getTitle = simpleGetter;
        q.getName = @(__original) function () {
            local ret = __original();
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
