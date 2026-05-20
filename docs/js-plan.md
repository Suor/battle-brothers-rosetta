# Rosetta JS Translation Plan

Working notes from a grilling session on extending Rosetta to translate strings that originate in JavaScript files of BB mods.

## Motivation

Most BB mod text lives in `.nut` files and is already covered by Rosetta's Squirrel runtime. But some UI is built directly in JS (jQuery-based), and those literal strings are currently untranslated. Today the only workaround is to ship a parallel JS file copy with hand-translated literals (e.g. `mod_msu_russian/`) — heavy and brittle.

## Survey of user-facing JS strings in BB mods

Looked at all unpacked mods under `3rdparty/` (including Reforged, MSU, Modern-Hooks, plan_perks, item_spawner, mod_dev_console, north-expansion, dynamic_perks, of_flesh_and_faith_plus, msu_russian-as-reference). Patterns found, sorted by frequency:

1. `createTextButton("Text", callback, ...)` — most common.
   - `prepare_for_battle/world_combat_dialog.js:23` — `"Prepare!"`
   - `north-expansion/duel_circle_screen.js:175,200` — `"Fight"`, `"Leave"`
   - `msu/mod_settings/settings_screen.js:83-104` — `Cancel/Reset/Apply/Save`
   - `msu/popup.js:49` — `"Ok"`
   - `msu/main_menu_module.js:17` — `"Mod Options"`
   - `item_spawner/...:127,191,201,...` — `Stash/Change/Add/Reroll/Close`
   - `mod_dev_console/DevConsoleScreen.js:88-120` — many buttons
   - `plan_perks/mod_plan_perks.js:390-803` — many buttons

2. `.html("Text")` / `.text("Text")` — dynamic state changes.
   - `msu/popup.js:108,116` — `"Quit Game"` ↔ `"Ok"`
   - `msu/msu_connection.js:170,174` — `"Click to hide/show patch notes"`
   - `msu/settings_screen.js:173` — `findDialogSubTitle().html("Select a Mod From the List")`

3. Literal text inside HTML strings `$('<div class="...">Text</div>')`:
   - `msu/popup.js:38` — `"Info Popup"`
   - `Modern-Hooks/.../fps_module.js:48,212` — `"FPS:"`, `"Mod Error"`
   - `item_spawner/...:182,207,244,500,537` — `"Item Name"`, `"Num"`, `"Search Item"`, etc.
   - `plan_perks/mod_plan_perks.js:291,298,375,472,558` — `"Current Perks"`, `"Planned Perks"`, etc.
   - `Dynamic-Perks-Framework/.../dpf_perk_overview_screen.js:29,64` — `"Dynamic Perks"`, `"Filter by name"`

4. Interpolated HTML — variables embedded in HTML strings:
   - `msu/msu_connection.js:149` — `'<div ...>' + currentVersion + ' => ' + start + coloredSpan + ' (Update Available)</div>'` (cohesive phrase split by inline `<span>`).
   - `msu/msu_connection.js:201-202` — `numMods + (numMods == 1 ? " mod" : " mods") + " checked<br>"` (plural concat with `<br>`).
   - Many `<div class="...">' + name + '</div>'` cases where the variable is just a name.

5. Multi-paragraph HTML literal:
   - `Modern-Hooks/fps_module.js:311` — multi-paragraph error message with `<br><br>` separators.

`.append/.prepend/.before/.after` with raw HTML strings are NOT used in the wild — mods always wrap in `$(...)` first. So those don't need direct hooks.

`.attr('title', ...)` / `.val(...)` for user-visible text — found only 3 occurrences in `item_spawner` (`Stash is Full!!!`, `Invalid Script!!!`, `Item is Added!!!`).

Existing translation reference: `mod_msu_russian/` ships as a full duplicate of MSU's JS files with literals replaced. This is what we want to obsolete.

## Decisions

1. **Scope: jQuery-level hook coverage.** Not just `createTextButton`. Goal is to translate (almost) all user-facing JS literals.

2. **Engine: port the Squirrel translation engine to JS.** Reuse the same model — `strs` (literal), `ids` (by file path, if applicable), `rules` (patterns/plurals). Engine is small enough; duplicating in JS is fine.

3. **Pair separation: distinct JS pair tables.** Squirrel pairs and JS pairs are NOT merged. Reasons: don't shovel large unused tables across the SQ/JS boundary; keeps each side smaller and focused.

4. **String-level matching (no DOM parsing, no text-node walking).** Match the input string as-is, the way the Squirrel engine does. If a string happens to contain HTML markup with CSS classes, the key includes them too. Pattern engine is responsible for capturing variable parts.

5. **Pattern syntax: same tag types as Squirrel.** `:tag`, `:int_tag`, `:str_tag`, `:val_tag` keep their names — the type names do NOT bake in HTML vs BBCode. What a tag type captures (HTML elements, BBCode tokens, or both) is an engine-implementation question to be decided when concrete cases require it. Not in v1; v1 patterns include CSS classes verbatim and accept the fragility.

6. **JS engine matches JS-literal strings only.** Strings that flow from Squirrel→JS via `SQ.call` are already translated by the Squirrel runtime (which is the right intercept point for them). Whatever happens to those strings on the JS side afterwards — including possible later conversion of BBCode to HTML somewhere downstream — is out of scope for Rosetta's JS hooks. We had our chance to intercept on the Squirrel side; we don't intercept the same content twice.

7. **No MutationObserver (for v1).** jQuery-level interception covers BB mods (no non-jQuery DOM construction observed). MutationObserver has flash-untranslated risk, infinite-loop risk, and hot-path performance cost. Keep as a fallback option for future if non-jQuery insertions emerge.

8. **Pattern engine implementation: TBD by benchmark.** Two candidates:
   - Port the Squirrel `matchParts()` walker (the parts-list approach used because Squirrel's regex doesn't backtrack — see memory `feedback_test_assertions.md` / `project_squirrel_regex_bug.md`).
   - Use native JS RegExp (which DOES backtrack normally).
   Decide once we benchmark on realistic inputs.

## Hook surface (v1)

| Hook | Behavior |
| --- | --- |
| `$()` (when first arg is a string starting with `<`, i.e. HTML construction) | translate before passing to original `$` |
| `.html(string)` | translate before passing to original |
| `.text(string)` | translate before passing to original |
| `createTextButton(text, ...)` | translate `text` before passing to original |

Not hooked initially:
- `.append/.prepend/.before/.after` — wrappers always pass through `$()` first in BB mods.
- `.attr('title'|'placeholder', ...)`, `.val(...)` — only 3 cases found; revisit.
- `findDialogTitle/findDialogSubTitle/findButtonText` — these are jQuery wrapper accessors that chain to `.html()`, so already covered by the `.html()` hook.

## Open questions (still to resolve)

The grilling did not get to these yet:

1. **File layout for the Rosetta JS code.** Where does it live? `rosetta/ui/mods/rosetta/...`? How does it get loaded before mod JS runs?

2. **Transport of pairs from Squirrel to JS.** SQ.call payload? Generated JS file? Static JSON? When does the active language become known? How do JS hooks delay matching until pairs are loaded?

3. **Mod registration API.** Do translation mods register JS pairs from Squirrel (preferred — single source for the pair list, similar to current `::Rosetta.add(...)`)? Or is there a parallel JS-side `Rosetta.add(...)` they can call?

4. **Plural form support in JS.** Russian and others need `n1/n2/n5` forms. Do we mirror Squirrel's `plural` mode entries? How is the plural rule for the active language taught to the JS engine?

5. **Extractor support for JS.** Does `rosetta.py` learn to parse `.js` files and emit JS pairs? Or is there a separate tool? Or is JS extraction manual for v1?

6. **Avoiding double-translate.** Strings that came from Squirrel (already translated) and end up in `.html(_data.Title)` should not be re-looked-up in JS pairs. In practice keys in JS pair tables are English, so a Russian string passed in is unlikely to match — but worth being explicit.

7. **Loading order vs translation timing.** If JS hooks are installed before pairs are loaded, what do they do — pass-through? Buffer? If installed after, some early UI strings escape. Game start sequence determines what's possible.

8. **Testing strategy.** No JS tests today. Headless browser? jsdom-style unit tests for the pattern engine? At minimum the engine needs unit tests; in-game behavior probably stays manual.

9. **Performance acceptance criteria.** Need a benchmark plan before deciding regex vs. matchParts walker (decision (8) above).

## Cases that drive design (concrete examples to test against)

These are the hard cases pulled from the survey that any v1 must handle (or explicitly defer):

- `prepare_for_battle/world_combat_dialog.js:23` — `createTextButton("Prepare!", ...)` — simplest case, smoke test.
- `msu/popup.js:108,116` — same button alternates between `"Ok"` and `"Quit Game"` via `.html()` — exercises dynamic re-translation.
- `msu/msu_connection.js:201-202` — manual plural concat `numMods + (numMods == 1 ? " mod" : " mods") + " checked<br>"` plus another similar fragment for updates — exercises pluralization.
- `msu/msu_connection.js:149` — `'<div ...>' + ver + ' => ' + start + coloredSpan + ' (Update Available)</div>'` — phrase split by inline `<span>`. Probably motivates extending the tag-capture types (`:tag` etc.) to match HTML elements eventually.
- `Modern-Hooks/fps_module.js:311` — multi-paragraph `<br><br>`-separated error message inside one `<div>` — exercises long literals with embedded inline tags.
- `msu/popup.js:81-83` — `'<div class="...">' + _info.modName + '</div>'` and `' + _info.text + '` — variables that came from Squirrel (already translated) wrapped in plain HTML — must NOT be double-translated.
