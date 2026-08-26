// Hooking strategies here - names and such intercept close to their origin, because there are code
// out there both in vanilla and mods, which concats and wraps those a lot. The rest are intercepted
// at squirrel - js border mostly.
local def = ::Rosetta, mod = def.mh, _ = def._;
local Table = ::std.Table, Str = ::std.Str;

local simpleGetter = @(__original) function () {
    return _(__original());
}
local function makeGetter(_field) {
    return @(__original) function () {
        local script = IO.scriptFilenameByHash(this.ClassNameHash);
        return _(__original(), script + "." + _field);
    }
}

mod.queue("<mod_msu", function () {
    mod.hook("scripts/items/item", function (q) {
        // q.getName = simpleGetter;
        q.getDescription = makeGetter("Description");
    })
    mod.hook("scripts/skills/skill", function (q) {
        // q.getName = simpleGetter;
        q.getDescription = makeGetter("Description");
    })

    // Need to hook earlier because if Nested Tooltips messing these
    mod.hookTree("scripts/entity/tactical/actor", function (q) {
        q.getNameOnly = makeGetter("Name");
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
})

mod.queue(">mod_msu", function () {
    def.msu <- ::MSU.Class.Mod(def.ID, def.Version, def.Name);

    local msd = ::MSU.System.Registry.ModSourceDomain, upd = def.Updates;
    def.msu.Registry.addModSource(msd.NexusMods, upd.nexus);
    def.msu.Registry.addModSource(msd.GitHub, upd.github);

    // This fixes MSU.isWeaponType() for russian language, which fixes some skills dependent on it,
    // i.e. many Reforged perks.
    // TODO: update for the newest MSU
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

    // New item types, i.e. Artifact
    local Items_getItemTypeName = ::Const.Items.getItemTypeName;
    ::Const.Items.getItemTypeName = function (_itemType) {
        return _(Items_getItemTypeName(_itemType))
    }

    // Hooks
    mod.hook("scripts/ui/screens/tactical/modules/topbar/tactical_screen_topbar_event_log",
            function (q) {
        q.log = q.logEx = @(__original) function (_text) {
            __original(_(_text))
        }
    })

    // Popup dialogs (single chokepoint for tactical/world/campfire showDialogPopup)
    mod.hook("scripts/ui/screens/dialog_screen", function (q) {
        q.show = @(__original) function (_title, _text, _doneCallback, _okCallback = null, _cancelCallback = null, _isMonologue = false) {
            return __original(_(_title), _(_text), _doneCallback, _okCallback, _cancelCallback, _isMonologue);
        }
    })

    // Combat result screen, its texts are composed in tactical_state and go straight to js
    mod.hook("scripts/ui/screens/tactical/tactical_combat_result_screen", function (q) {
        q.onQueryCombatInformation = @(__original) function () {
            local ret = __original();
            if (ret == null) return ret;
            ret.title = _(ret.title);
            ret.subTitle = _(ret.subTitle);
            return ret;
        }
    })

    // Loading screen tips
    mod.hook("scripts/ui/screens/loading/loading_screen", function (q) {
        q.onQueryData = @(__original) function () {
            local ret = __original();
            if (ret != null) ret.text = _(ret.text);
            return ret;
        }
    })

    // Perks
    mod.hook("scripts/ui/global/data_helper", function (q) {
        q.convertEntityToUIData = @(__original) function (_entity, _activeEntity) {
            local result = __original(_entity, _activeEntity);
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

    local tooltipHook = @(__original) function (...) {
        vargv.insert(0, this);
        return def.translateTooltip(__original.acall(vargv));
    }

    // Tooltips
    mod.hook("scripts/ui/screens/tooltip/tooltip_events", function (q) {
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
        if (q.contains("onQueryMSUTooltipData")) q.onQueryMSUTooltipData = tooltipHook;
    })

    // Background
    mod.hook("scripts/skills/backgrounds/character_background", function (q) {
        q.getName = @(__original) function () {
            local ret = __original();
            local parts = Str.split(": ", ret, 1);
            if (parts.len() != 2) return ret;
            // The name half is the same string getNameOnly() returns, so it takes the same id
            local script = IO.scriptFilenameByHash(this.ClassNameHash);
            return parts[0] + ": " + _(parts[1], script + ".Name");
        }
        q.getNameOnly = makeGetter("Name");
    })
    mod.hookTree("scripts/skills/backgrounds/character_background", function (q) {
        q.onBuildDescription = @(__original) function () {
            local script = IO.scriptFilenameByHash(this.ClassNameHash);
            return _(__original(), script + ".onBuildDescription");
        }
    })

    mod.hookTree("scripts/entity/tactical/entity", function (q) {
        // q.getName = makeGetter("Name"); // not needed?
        q.getDescription = makeGetter("Description");
    })
    // Party labels on the world map: updateStrength() concats getName() with " (4)"
    mod.hook("scripts/entity/world/world_entity", function (q) {
        q.getName = makeGetter("Name");
    })
    mod.hookTree("scripts/items/item", function (q) {
        q.getName = makeGetter("Name");
        q.getDescription = makeGetter("Description");
    })
    mod.hookTree("scripts/skills/skill", function (q) {
        q.getName = makeGetter("Name");
        q.getDescription = makeGetter("Description");
    })
    mod.hookTree("scripts/scenarios/world/starting_scenario", function (q) {
        q.getName = makeGetter("Name");
        q.getDescription = makeGetter("Description");
    })

    // We hook this to translate before %vars% are substituted, which makes it:
    //   - easier for translators: translate bare strings with vars instead of using patterns
    //   - more performant
    // This means some translated strings will be saved. Already the case with backgrounds anyway.
    // Changing active language mid-campaign will lead to some strings be still in the old lang.
    local buildTextFromTemplate = ::buildTextFromTemplate;
    ::buildTextFromTemplate = function (_text, _vars) {
        return buildTextFromTemplate(_(_text), _vars);
    }

    // Screen lists are concatenated in event/contract code, never seeing the template engine
    local listHook = @(__original) function () {
        local ret = __original();
        foreach (list in ret) {
            list.title = _(list.title);
            foreach (item in list.items) item.text = _(item.text);
        }
        return ret;
    }
    mod.hook("scripts/events/event", function (q) {
        q.getUIList = listHook;
        q.getUIButtons = @(__original) function () {
            local ret = __original();
            // Option texts come translated, tooltips are shown verbatim, bypassing tooltip hooks
            foreach (button in ret)
                if ("tooltip" in button) button.tooltip = _(button.tooltip);
            return ret;
        }
    })
    mod.hook("scripts/contracts/contract", function (q) {
        q.getUITitle = simpleGetter;
        q.getUIList = listHook;
    })

    // Translate MSU settings: setting labels, page tab names, panel (mod) names, slider labels
    local function hookGetUIData(_cls, _extra = null) {
        local orig = _cls.getUIData;
        _cls.getUIData <- function (_flags = []) {
            local ret = orig.call(this, _flags);
            ret.name = _(ret.name);
            if (_extra != null) _extra(ret);
            return ret;
        }
    }
    hookGetUIData(::MSU.Class.SettingsElement);
    // Direct subclasses of SettingsElement that don't override getUIData snapshot
    // the original method at class-definition time, so the hook above doesn't reach
    // them. AbstractSetting (and its subclasses) overrides getUIData and calls
    // base.getUIData(), which resolves dynamically — those work via the hook above.
    hookGetUIData(::MSU.Class.SettingsTitle);
    hookGetUIData(::MSU.Class.SettingsPage, function (ret) {
        // TODO: hook slider directly once it lands into MSU
        foreach (setting in ret.settings)
            if ("labels" in setting) setting.labels.apply(_);
    });
    hookGetUIData(::MSU.Class.SettingsPanel);

}, ::Hooks.QueueBucket.Late)

// Unified Perk Descriptions
mod.queue(">mod_upd", "<mod_reforged", function () {
    if (!("UPD" in getroottable())) return

    local UPD_getDescription = ::UPD.getDescription;
    ::UPD.getDescription = function (_info) {
        foreach (key in ["Fluff" "Requirement" "Footer"]) {
            local val = Table.get(_info, key, "");
            if (val != "") _info[key] = _(val);
        }
        if ("Effects" in _info)
            foreach (effect in _info.Effects) effect.Description.apply(_);
        return UPD_getDescription(_info);
    }
})
