# More Hooks Plan

Looks like there are more stuff to hook on top of #8, fce44f1 and 02e12b9.

## User requests

- On factions: "we don't care about old saves! Otherwise we'll need to hook same thing twice, which is unnecessary complication for a weird use case"
- On the retinue: "Many effects will have some values or percents, mods might change those, so using
  patterns will make sense"; and, on hooking the accessors instead of the UI funnel: "I wonder if we
  loose an ability to pass id"
- On the harbor hook in hardened: "'Sail to ...' can be matched with pattern and the other one
  is already caught by buildTextFromTemplate. The rest call accessors, which we might have already"

## Decisions

1. **Prefer accessors over UI funnels.** An accessor runs on the owning instance, so `makeGetter`
   can pass `<script>.<field>` as the id; a UI funnel (`getFollowersForUI`, `getUITravelRoster`,
   `convertFactionsToUIData`) hands us bare strings with no id and no way to recover one. Funnels
   are for text that has no accessor behind it. Clean *UI methods are a good target otherwise.
2. **Composed strings are patterns, not pairs.** Retinue effects and requirements carry numbers and
   percents that mods change, `ListName` carries a town name — those are pattern rules in packs,
   the hook only has to deliver the composed string. Unless this is handled by buildTextFromTemplate
3. **Faction descriptions stay with the template engine.** They already pass through
   `::buildTextFromTemplate` at world-gen; a second hook on the relations screen would translate the
   same text twice, only to serve saves generated before the pack was installed. Those saves are out
   of scope.
4. **Double `_()` is acceptable, silence is not.** Where an accessor hook feeds a path we already
   hook (retinue tooltips), the second `translate()` finds nothing and only costs a NOT FOUND line.
   That is preferable to leaving a conduit unhooked, but each such overlap is worth a note so the
   log noise is expected rather than investigated twice.

## Facts

Vanilla paths cite `base/data_001` (verified against `data_014` where the overlay carries the file).

### Retinue

- Strings are per-follower class fields: `scripts/retinue/followers/cook_follower.nut:7-20`
  (`m.Name`, `m.Description`, `m.Effects[]`), with `m.Requirements[].Text` composed in `onEvaluate`
  with numbers baked in (`:33`).
- Accessors on the base class: `scripts/retinue/follower.nut:21,26,36,47`
  (`getName`, `getDescription`, `getEffects`, `getRequirements`). Followers are engine-created via
  `this.new(scriptFile)` (`scripts/retinue/retinue_manager.nut:178`), so `ClassNameHash` is
  available and `makeGetter` works.
- The hire screen reads all four through `retinue_manager.getFollowersForUI()` (`:118`), the only
  caller being `campfire_hire_dialog_module.nut:33`.
- The tooltip half is already covered: `follower.getTooltip()` (`follower.nut:70`) builds its items
  from `getName()`/`getDescription()` plus raw `m.Effects`, and `tooltip_events`
  `onQueryFollowerTooltipData` is wrapped by `tooltipHook` (`rosetta/hooks.nut:145`).
- `getEffects`/`getRequirements` return the `m` arrays by reference — a hook must return a mapped
  copy, or the translation is written back into the follower and re-translated next call.
- One id per string is the runtime's model, so the several effects of one follower cannot each get
  an id; they stay literal or pattern pairs.

### Town subtitle

- `m.UIDescription` is set per settlement type, e.g. `scripts/entity/world/settlements/
  small_fishing_village.nut:56`, ~60 such files.
- It surfaces only through `settlement.getUIInformation()` (`scripts/entity/world/settlement.nut:401`),
  read by the town screen and the campfire screen. Same call also carries `Slots[i].Tooltip`, built
  by `building.getTooltip()` (`settlement.nut:436`), which bypasses `tooltip_events` entirely.
- `Title` there is the generated town name — not translatable.
- Settlements sit in the `world_entity` tree, which Rosetta hooks only for `getName` (02e12b9); their
  `m.Description` (`small_fishing_village.nut:57`, the same sentence as `UIDescription` modulo the
  final period) has no hook.
- Vanilla defines `getUIInformation` only on `settlement`, but mods redefine it on subclasses
  (`3rdparty/north-expansion/NorthExpansionMod/entity_hooks/barbarian_locations_hook.nut:173`).

### Harbor

- `port_building.getUITravelRoster()` (`scripts/entity/world/settlements/buildings/
  port_building.nut:191`) owns two literals of its own, `Title = "Harbor"` and its `SubTitle`
  (`:194-195`).
- Per destination it composes `ListName = "Sail to " + s.getName()` (`:221`) and
  `BackgroundText = s.getDescription() + "<br><br>" + getRandomDescription(...)` (`:227`). The blurb
  half goes through `this.buildTextFromTemplate` (`:246`), i.e. it is already translated by the
  global wrapper; the other half is a settlement description accessor.
- Hardened appends extra roster entries *after* calling the original
  (`3rdparty/Hardened/mod_hardened/hooks/entity/world/settlements/buildings/port_bulding.nut:11-30`),
  composing its own `ListName`/`BackgroundText`. A hook installed before Hardened's sits inside it
  and never sees those entries. Reforged's wrapper only adds an id field (`.../port_building.nut:2`).

### Faction descriptions, mottos, relations

- Archetype templates with `%noblehousename%`-style placeholders live in
  `scripts/config/faction_traits_archetypes.nut`; both city states and noble houses re-set the
  resolved text through the template engine at world-gen (`scripts/factions/faction_manager.nut:476`
  and `:581`), and the result is stored in the faction (`scripts/factions/faction.nut:198`) and saved (`:750`).
- Not covered by that route, because they never touch the template engine:
  mottos (`faction_manager.nut:429,509`, stored with the quotes already attached), city-state titles
  (`:428`, from `Const.Strings.CityStateTitles`), the relation label
  (`faction.getPlayerRelationAsText()`, `faction.nut:321`, from `Const.Strings.Relations`) and the
  two reputation labels — all read together by `world_relations_screen.convertFactionsToUIData()`
  (`scripts/ui/screens/world/world_relations_screen.nut:121-145`).

### Morale bar label

- `Const.MoraleStateName` (`scripts/config/character.nut:289`), six plain labels, no numbers.
  Legends redefines the table (`legends_pack/_scripts/config/character.nut:308`).
- Two uncovered readers: `data_helper.addStatsToUIData()` (`scripts/ui/global/data_helper.nut:369`),
  the chokepoint for the character sheet and the hire screens, and
  `turn_sequence_bar.convertEntityToUIData()` (`scripts/ui/screens/tactical/modules/
  turn_sequence_bar/turn_sequence_bar.nut:1200`).
- Its other readers are already covered: the tooltip progress bars (`actor.nut:1089`,
  `player.nut:416`) via `tooltip_events`, and `morale_check.nut:205` via the skill `getName` hook.
- Reforged concatenates `"Unbreakable"` into its own strings at config time
  (`3rdparty/reforged/mod_reforged/hooks/config/strings.nut:1416`), so translating the `Const` table
  in place changes the shape of those strings and breaks their keys.

## Stages

Each stage is independent; the order is by confidence, not dependency.

1. **Retinue.** Hook the follower accessors (`getName`, `getDescription` with ids; `getEffects`,
   `getRequirements` returning copies). Check: hire screen and campfire tooltip both show translated
   name, description and effects; requirement lines match a pattern rule with the number captured.
2. **Harbor.** Hook `getUITravelRoster` for its own `Title`/`SubTitle`, install it after Hardened,
   and leave `ListName` to a pattern and `BackgroundText` to the accessors behind it. Check: with
   Hardened enabled, greyed-out destinations are translated too; the ship blurb is not translated
   twice.
3. **Town subtitle.** Hook `getUIInformation` as a tree for the subtitle and the building tooltips.
   Check: town screen subtitle and building slot tooltips translated, town name untouched.
4. **Morale label.** Per Q1.
5. **Faction leftovers.** Per Q2.

## Open questions

- **Q1. Morale label: `Const` table or the two UI readers?** Translating
  `Const.MoraleStateName` once at load is the cheapest and mirrors what we already do for
  `Const.Items.WeaponType`, but it double-translates the tooltip and skill paths and breaks
  Reforged's concatenated strings; hooking `addStatsToUIData` and `turn_sequence_bar` touches
  neither but is two hooks. The same choice will recur for other `Const.Strings` tables.
- **Q2. Faction mottos, titles and relation labels: same choice as Q1**, plus whether the stored
  quotes around a motto belong in the pair key or should be stripped by the hook.
- **Q3. Do settlement descriptions need `world_entity.getDescription`?** The harbor plan assumes
  the accessors behind `BackgroundText` are already translated; today only `getName` is hooked in
  that tree. To verify before stage 2.
