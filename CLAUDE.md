# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Rosetta is a translation framework for Battle Brothers mods. It enables runtime string interception and translation without modifying original mods. The project consists of:

1. **Python extractor** (`rosetta.py`) - Extracts translatable strings from Squirrel (.nut) files
2. **Translation engine** (`xt.py`) - Automated translation using Yandex Translate or Claude 3.5 Sonnet
3. **Squirrel runtime** (`scripts/`, `rosetta/`) - The actual mod that performs runtime string interception and translation in Battle Brothers

## Development Commands

### Testing
```bash
# Run Squirrel syntax check and tests
make test

# Run Python tests
pytest test_rosetta.py

# Syntax check only
make check-compile
```

### Building
```bash
# Create versioned zip (runs tests first)
make zip

# Install to game directory (requires DATA_DIR in .env)
make install

# Clean modified builds
make clean
```

### Python Extractor
```bash
# Extract strings from a mod directory to create translation template
python rosetta.py -lru path/to/mod_dir > translation_ru.nut

# Extract with auto-translation via Claude
python rosetta.py -lru -tclaude35 path/to/mod_dir > translation_ru.nut

# Extract from specific file
python rosetta.py -lru path/to/file.nut > translation_ru.nut

# Available options:
# -l<lang>    Target language (default: ru)
# -t<engine>  Auto-translate with: yt (Yandex), claude35 (Claude)
# -r<file>    Use reference translation file
# -f          Overwrite existing files
# -v          Verbose output
# -x          Stop on error (failfast)
```

## Architecture

### Python Extractor (`rosetta.py`)

The extractor is a sophisticated string parser that:

1. **Tokenizes** Squirrel code into a stream of tokens (strings, refs, operators, etc.)
2. **Parses expressions** recursively to understand string concatenation, function calls, ternaries
3. **Rewinds** from each string to find the full expression it's part of
4. **Filters** internal/technical strings (IDs, file paths, snake_case, etc.) to extract only user-facing text
5. **Pattern detection** - Identifies dynamic parts like `"Heals " + hp + " points"` and creates patterns like `"Heals <hp> points"`
6. **Deduplicates** by normalizing numbers in patterns
7. **References existing translations** when run with `-r` to preserve manual edits during updates

Key concepts:
- **Expression options**: Ternaries generate multiple translation variants
- **Format expansion**: `format("Text %s", arg)` expands to `"Text <arg>"`
- **Stop functions**: Certain functions (log, debug, settings) are never translated
- **Rewind positions**: Parser tries multiple starting points to capture full expressions

### Translation Engine (`xt.py`)

Manages automated translation with caching:

- SQLite cache (`translations.db`) stores all translations by engine+config+input
- Batches untranslated strings to minimize API calls
- Supports Yandex Translate and Claude 3.5 Sonnet
- Claude prompt uses `<phrase>` tags to ensure reliable parsing
- Requires `.env` file with API credentials (see `.env.sample`)

### Squirrel Runtime Architecture

The runtime intercepts strings at multiple levels:

1. **Core translation engine** (`scripts/!mods_preload/!rosetta.nut`):
   - Language detection and activation
   - Three translation maps: `strs` (literal), `ids` (by script path), `rules` (patterns/plurals)
   - Pattern matching with substitutions (`:str`, `:int`, `:tag`, `:val`, `:img`, `:t`)
   - Plural forms based on language rules
   - Validation and logging

2. **Hooks** (`rosetta/hooks.nut`):
   - Intercepts UI tooltips, entity names, skill descriptions, perks, backgrounds
   - Hooks into ModernHooks (`def.mh`) and MSU (`def.msu`)
   - Translates dynamic content (perk trees, tooltips) at display time
   - Special handling for concatenated titles (e.g., "Occupation: Barkeep")

3. **Language packs** (e.g., `rosetta/pack_ru.nut`):
   - Common strings bundled with Rosetta
   - Reduces duplication across translation mods

### Translation Pair Types

```squirrel
// Literal translation
{en = "Hello", ru = "Привет"}

// By ID (script path)
{id = "scripts/scenarios/world/necro.Description", ru = "..."}

// Pattern with substitutions
{mode = "pattern", en = "<actor:str> heals <hp:int> HP", ru = "<actor> восстанавливает <hp> ОЗ"}

// Plural forms
{plural = "range", en = "Has range of <range:int> tiles", n1 = "...", n2 = "...", n5 = "..."}
```

### Pattern Substitutions

- `:str` - String (greedy, captures until next literal)
- `:int` - Integer
- `:tag` - Match tags like `<open:tag>text<close:tag>` or `<func()>`
- `:val` - Value extraction
- `:img` - Image tags
- `:t` - Double translation (for nested translated strings)

## File Structure

```
rosetta.py          - Main extractor script
xt.py              - Translation engine
test_rosetta.py    - Python extractor tests
scripts/!mods_preload/!rosetta.nut  - Runtime core
rosetta/hooks.nut  - Game hooks
rosetta/pack_ru.nut - Common Russian strings
test.nut           - Squirrel tests
mocks.nut          - Test mocks
load.nut           - Testing helper
```

## Important Notes

- The extractor uses **reference files** (`-r`) to preserve manual edits when updating translations. Always run extraction to a new file and use a diff tool (like Meld) to merge changes.

- **Stop functions**: Functions like `logInfo`, `require`, `getSetting`, `isKindOf` are ignored because their arguments are internal identifiers, not user-facing text.

- **Expression destruction**: Certain contexts destroy expressions for translation (throw, typeof, case, comparisons, .len()) because the string isn't displayed to users.

- **Rewind algorithm**: When a string is found, the parser rewinds to potential expression starts (assignment, comma, paren, bracket) and tries parsing forward. This handles multi-line concatenations.

- **Squirrel syntax**: Uses ModernHooks (`mod.hook`) and MSU framework. Hooks wrap original functions with translations.

## Dependencies

- Python 3.12+
- `requests` library (for auto-translation)
- `pytest` (for tests)
- Squirrel compiler (for syntax checking)
- Battle Brothers with ModernHooks and MSU mods
