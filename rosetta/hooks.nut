local def = ::Rosetta, mod = def.mh;
local Table = ::std.Table, Str = ::std.Str;
local _ = def.translate.bindenv(def);

mod.queue(function () {
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

    // Hooks
    mod.hook("scripts/ui/screens/tactical/modules/topbar/tactical_screen_topbar_event_log",
            function (q) {
        q.log = q.logEx = @(__original) function (_text) {
            __original(_(_text))
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

    local simpleGetter = @(__original) function () {
        return _(__original());
    }
    local function makeGetter(_field) {
        return @(__original) function () {
            local script = IO.scriptFilenameByHash(this.ClassNameHash);
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
    mod.hookTree("scripts/entity/tactical/actor", function (q) {
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
        // q.rosetta_IsActor <- true;
    })
    mod.hookTree("scripts/entity/tactical/entity", function (q) {
        if (!q.ClassName == "actor" && !q.contains("actor", true)) q.getName = simpleGetter;
        q.getDescription = makeGetter("Description");
    })
    mod.hookTree("scripts/items/item", function (q) {
        q.getName = simpleGetter;
        q.getDescription = makeGetter("Description");
    })
    mod.hookTree("scripts/skills/skill", function (q) {
        q.getName = simpleGetter;
        q.getDescription = makeGetter("Description");
    })
    mod.hookTree("scripts/scenarios/world/starting_scenario", function (q) {
        q.getName = makeGetter("Name");
        q.getDescription = makeGetter("Description");
    })
    mod.hook("scripts/contracts/contract", function (q) {
        q.getUITitle = simpleGetter;
        q.getUIButtons = tooltipHook;
    })

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
