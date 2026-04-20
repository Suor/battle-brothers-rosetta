# Rosetta Translation Guide for Agents

Step-by-step guide for creating or updating Rosetta translations for Battle Brothers mods. Read `README.md` in this repo for the general overview, this document covers the practical details and pitfalls.


## Step 1: Generate the Translation File

Run the extractor from the mod directory:

```bash
cd path/to/mod
rosetta -lru . > <mod_name>/rosetta_ru.nut
```

This produces a boilerplate with all extracted strings having empty `ru = ""` values (replace `ru` with your target language code throughout). The extractor also generates comments showing the **original code lines** from which each string was extracted — these help understand context, especially for complex expressions like ternaries or concatenations. The `<...>` placeholders in generated `en` strings are **hints** derived from the original code (function/variable names) — do NOT copy their syntax into patterns, rewrite them using proper capture types (see Step 4).

To update an existing translation, use `-r` to reference it:

```bash
rosetta -r <mod_name>/rosetta_ru.nut . > new_rosetta_ru.nut
# Then diff/merge new_rosetta_ru.nut into the existing file
```

To verify a translation is complete and has no stale entries, use `-c`:

```bash
rosetta -c <mod_name>/rosetta_ru.nut .
```

Exits with error and reports **NEW** (extractor output not in the translation) and **UNMATCHED** (translation entries the extractor couldn't correlate back) blocks. Run as a final check before shipping.

### Repairing or updating a translation file

Only two things are hand-work: writing `ru = "..."`, and converting the extractor's hint-form `en` (e.g. `"<this.m.Cost>[img]...[/img]"`) into a proper pattern (`"<cost:int><img:img>"`) with a matching `ru`. Everything else — block structure, `// code` comments, initial `en` — comes from the extractor verbatim; paste from `-r` or `-c` output.

The `// code` comment above each pair is **load-bearing**: it's the primary key `-c` and `-r` use to correlate translation entries with extractor output (not `en`). Delete it and the pair is reported `UNMATCHED` even when its runtime pattern is correct; `-r` re-emits it as `NEW`. So the common fix for `UNMATCHED` is to paste the canonical `// code` block from the corresponding `NEW` entry — not to rewrite `en`. If the same string appears in multiple source files, duplicate the pair — one copy per source file's comment block.

The extractor auto-loads `rosetta/pack_<lang>.nut` when it exists. Entries there are matched silently — strings already covered by pack won't appear in the generated output. Before writing a new pattern, check `pack_ru.nut` — common game stat patterns (Durability, Maximum Fatigue, Initiative, Resolve, etc.) are likely already there. If a generic pattern is missing from pack, add it there rather than in the mod-specific file.


## Step 2: Fill in Metadata

```squirrel
local rosetta = {
    mod = {id = "mod_example", version = "1.0.0"}  // the mod being translated
    author = "your_name"
    lang = "ru"
}
```


## Step 3: Translate Literal Pairs

Simple string-to-string translations:

```squirrel
{
    en = "Finds extra food after combat"
    ru = "Находит дополнительную еду после боя"
}
```


## Step 4: Write Patterns — the Tricky Part

The extractor generates placeholder syntax like `<positive(Greatly)>` or `<this.m.Cost>` as **hints only**. These are NOT valid Rosetta syntax. You must rewrite them using proper capture types.

### Available capture types (used in `en` patterns)

| Type        | Matches                                  | Example                        |
|-------------|------------------------------------------|--------------------------------|
| `:int`      | Integer (`+/-` optional)                 | `<hp:int>`                     |
| `:val`      | Number, optionally with `%` or decimal   | `<chance:val>`                 |
| `:word`     | Single word (no spaces/brackets)         | `<name:word>`                  |
| `:str`      | Any string without brackets (greedy)     | `<tease:str>`                  |
| `:tag`      | A bbcode tag like `[color=...]` or `[/color]` | `<open:tag>`              |
| `:img`      | Full `[img]...[/img]` tag               | `<icon:img>`                   |
| `:int_tag`  | Tagged integer: `[tag]123[/tag]`         | `<hp:int_tag>`                 |
| `:val_tag`  | Tagged value: `[tag]15%[/tag]`           | `<bonus:val_tag>`              |
| `:str_tag`  | Tagged string: `[tag]text[/tag]`         | `<name:str_tag>`               |

### How to reference captures in `ru`

- **Without type** `<name>` — insert the captured value as-is
- **With `:t`** `<name:t>` — insert the captured value after recursively translating it through Rosetta

### Common scenarios

**Colorized text that needs translation** — use `<open:tag>` / `<close:tag>` to capture the color tags separately, then translate the text between them:

```squirrel
// Code: positive("Greatly") + " increases the chance..."
// Output: [color=#...]Greatly[/color] increases the chance...
{
    mode = "pattern"
    en = "<open:tag>Greatly<close:tag> increases the chance of encountering champions"
    ru = "<open>Значительно<close> увеличивает шанс встретить чемпионов"
}
```

**Colorized value that does NOT need translation** (numbers, percentages) — use `_tag` compound types:

```squirrel
// Code: positive("15%") + " chance to fix..."
{
    mode = "pattern"
    en = "Give <chance:val_tag> chance to fix permanent injury on level up"
    ru = "<chance> шанс исцелить увечье при повышении уровня"
}
```

**Colorized dynamic value** (variable content) — use `:str_tag`:

```squirrel
// Code: "Unknown " + enemy(faction)  -- faction is a variable
{
    mode = "pattern"
    en = "Unknown <faction:str_tag>"
    ru = "Неизвестные <faction>"
}
```

**Dynamic string that gets translated separately** — use `:str` in `en`, `:t` in `ru`:

```squirrel
// Code: "Promote " + tease + ", costs " + cost + "[img]...[/img]"
// The tease values like "for even more champions" have their own literal pairs
{
    mode = "pattern"
    en = "Promote <tease:str>, costs <cost:int><img:img>"
    ru = "Повысить <tease:t>, стоимость <cost><img>"
}
```

**Image tags** — use `:img` to capture `[img]...[/img]`:

```squirrel
{
    mode = "pattern"
    en = "Hired for <money:img><hire:int>."
    ru = "Нанят за <money><hire>."
}
```

**Pluralization** — use `plural` key pointing to the counter capture. Provide plural form keys specific to the target language (e.g. `n1`/`n2`/`n5` for Russian, `n1`/`n2` for Spanish — see language definitions in `rosetta/pack_*.nut` or `::Rosetta.addLang()`):

```squirrel
{
    plural = "n"
    en = "Killed <n:int_tag> enem<_:word> in a single battle"
    n1 = "Сразил <n> врага в одном бою"
    n2 = "Сразил <n> врагов в одном бою"
    n5 = "Сразил <n> врагов в одном бою"
}
```


## Step 5: Handle Strings That Bypass Rosetta Interception

Rosetta intercepts strings at the Squirrel/JS boundary. If a string is passed to a custom method that forwards it to JS itself (not through the standard tooltip/UI pipeline), Rosetta won't intercept it. In such cases, translate it directly using the `_()` helper in the mod code:

```squirrel
local _ = "Rosetta" in getroottable() ? Rosetta._ : @(s) s;

_player.addLevelUpChanges(_("Promoted Surgeon fixes"), [...])
```

Signs that a string bypasses interception:
- Passed to a custom/modded method that stores it and later sends it to JS
- Stored in flags, serialized data, or custom UI data structures


## Step 6: Handle Strings NOT Worth Translating

Some extracted strings should be skipped. To tell the extractor to ignore them on future runs, leave a commented-out `en` line:

```squirrel
    // en = "mod_retinue_ups.<follower.ClassName>"
```

Common reasons to skip:
- Internal identifiers (flag names, IDs, class names)


## Step 7: Wire It Up

1. **Include the translation file** in the mod's entry point (`scripts/!mods_preload/mod_<name>.nut`), inside `mod.queue()`:

```squirrel
mod.queue(function () {
    ::include("<mod_name>/rosetta_ru");
    // ... rest of mod code
});
```

2. **Ensure the translation file is included in the mod's distribution** (zip/package). How this is done depends on the mod's build system.


## Reference Examples

- Simple mod: `necro/necro/rosetta_ru.nut` — basic literals, patterns with `:tag`/`:int`/`:str_tag`, id-based translations
- Complex mod: `fun_facts/fun_facts/rosetta_ru.nut` — plurals, `:t` recursive translation, `:img`, `:val_tag`, `split`, custom `use` functions, `:word` for consuming English plural suffixes
- Rosetta test suite: `rosetta/test.nut` — exhaustive examples of all pattern types
