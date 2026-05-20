# Old Translation Bootstrap Plan

Goal: add an extractor mode that converts an old replacement-style translated mod into an initial Rosetta translation file.

This mode is for bootstrapping only. After a Rosetta file exists, normal updates should use `-r` and verification should use `-c`.

## CLI

Use `-o<old-mod>`:

```bash
python rosetta.py -lru -o path/to/old_translated_mod path/to/original_mod > rosetta_ru.nut
```

`-o` is mutually exclusive with `-r` and `-c`.

The target language is still controlled only by `-l`; for example `-lru` writes `ru = "..."`.

## Inputs

Both the positional source path and the `-o` path must point at a Battle Brothers mod root.

For directories, the supplied directory is the root. For zip files, the archive root is the root. Do not guess or strip wrapper directories.

Require a root-level `scripts/` directory. If it is missing, fail with a clear error telling the user to point at the mod root.

After applying the existing extractor file skip rules, root-relative `.nut` file sets must match exactly. If they do not, fail; this probably means the old translation and original mod are different versions.

## Extraction

Use the existing extractor behavior as much as possible.

Do not run normal extraction once on the original and then once on the old translated mod. Normal extraction mutates global output state such as `SEEN`, and reference lookup can mutate reference state such as `CODE_RULES`.

Instead, use a side-effect-free candidate collection pass per file:

- use normal string filtering
- force context tracking internally
- do not short-circuit candidates because of duplicate suppression
- do not short-circuit candidates because a silent language pack covers them
- keep ordinary parse-failure behavior: report and fall back per expression where the extractor already does so
- if an exception escapes a file, handle it like normal extraction: warn and continue unless `-x`

`pack_<lang>.nut` should still be loaded silently, but only affect the emit/postprocess phase, not candidate counts.

Internally, context tracking is required for matching even if the user did not pass `--context`. Do not emit `_context` comments unless `--context` was explicitly requested, matching normal extractor behavior.

## Processing Pipeline

Process files in normal English extraction order. For each root-relative `.nut` file:

1. Collect original candidates from the English file with refs and dedup disabled.
2. Collect old candidates from the translated file with refs and dedup disabled.
3. Match those two candidate lists by `file + _context`.
4. Postprocess only the English candidates for output:
   - apply normal global duplicate suppression
   - apply silent pack/reference suppression
   - fill the target language field from confident old matches
   - leave the target language field empty for ambiguous or missing matches
5. Emit the resulting English pairs and any ambiguous old-candidate comment block.

This can be implemented per file; there is no need to collect the entire original mod and then the entire old translated mod before matching.

Global state rules:

- Candidate collection must not read or write `SEEN`.
- Candidate collection must not call `ref_en()` or `ref_code()`.
- The output/postprocess phase should start with duplicate state equivalent to normal extraction from scratch.
- Only the output/postprocess phase may use the silent pack refs.
- Old translated candidates never participate in duplicate or reference suppression.
- Temporarily forcing `OPTS["context"]` for candidate collection must not change whether context comments are emitted.

## Matching

Match only by:

```text
root-relative file path + extractor _context
```

Within a matched context:

- if original and old translated candidate counts are equal, pair by order
- if counts differ, treat the context as ambiguous

Entries with empty context are still valid and can be matched the same way.

Do not do fuzzy matching, structural matching, root guessing, AI-assisted repair, or pattern rewriting in v1.

## Implementation Notes

Keep changes minimal and prefer existing extractor facilities.

If the implementation needs to annotate an English-side candidate with a replacement/suppression decision, use a single optional `_pair` key rather than introducing `_action`, `_skip`, `_dedup_key`, or similar fields:

- no `_pair`: emit the generated pair normally
- `_pair == ""`: suppress output, e.g. duplicate or silent-pack-covered candidate
- `_pair` is a block string or pair-like object: format that replacement instead of the generated pair

If `_pair` is introduced, `_format(pair)` can handle it directly:

```python
if isinstance(pair, dict) and "_pair" in pair:
    return _format(pair["_pair"])
```

Only English-side candidates need this, because only the original source decides Rosetta output. Old translated candidates are matching/reference material only.

Do not add `_pair` unless it is actually needed for a small implementation.

## Output

Output remains normal Rosetta extractor output based on the original English source:

- preserve normal file order and English extraction order
- use English source code comments as update keys
- emit normal generated pairs with `en = ...` and `<lang> = ...`
- preserve existing normal semantics for duplicate and silent-pack suppression, but only after matching counts are computed
- duplicate suppression should remain global like normal extraction output

For confident contexts, fill the target language field from the old translated candidate's normalized extracted string exactly as extracted, including placeholder hints.

For ambiguous contexts:

- emit the English pairs first with empty target language fields
- after the last emitted pair from that context, emit one comment block with all old translated candidates from that context
- do not emit an orphan candidate block if all English pairs from the context were suppressed

Suggested ambiguous comment block:

```squirrel
    // Strings extracted for this context from the translated version of the mod.
    // Cannot automatically tell which of them correspond to which English phrases above.
    // "Первый старый текст"
    // "<::MSU.Text.colorPositive(15%)> второй старый текст"
```

Use `nutstr()` formatting for commented candidate strings so multiline strings, quotes, and backslashes are copyable.

Do not use `// en = ...` in these comments because the reference parser treats that as an intentional ignore marker.

## Diagnostics

When not quiet, print concise stderr diagnostics for non-confident contexts, for example:

```text
parallel: scripts/foo.nut q.getTooltip(): 3 original strings, 5 old strings, emitted old candidates as comments
parallel: scripts/bar.nut create(): 2 original strings, 0 old strings
```

Stdout must remain valid Squirrel output.
