# Rosetta Translations Framework

This is a framework mod aimed to facilitate translating Battle Brother mods to various languages. Design goals:

- be easy to use and maintain
- work on top of unmodified mods
- no central infrastructure required
- untie translation cycle from mod release cycle
- flexibility of packaging: bundle with mod, separate mod, translations pack

Currently all the translation is done in squirrel by intercepting strings either at the squirrel/js border or earlier if that is easier to implement.

<!-- MarkdownTOC autolink="true" levels="1,2,3" autoanchor="false" start="here" -->

- [Usage](#usage)
- [Compatibility](#compatibility)
- [Using Translations](#using-translations)
- [Translating Mods](#translating-mods)
    - [Extractor](#extractor)
    - [Limitations](#limitations)
    - [More Examples](#more-examples)
- [For Mod Authors](#for-mod-authors)
- [Feedback](#feedback)
- [Index](#index)

<!-- /MarkdownTOC -->


# Usage

Install it from [NexusMods][nexus-mods], or grab from here and zip. Then:

```squirrel
// Skip this file if mod_rosetta is not installed,
// useful to make rosetta an optional dependency when bundling translation into your mod.
if (!("Rosetta" in getroottable())) return;

// Provide mod and translation info
local rosetta = {
    mod = {id = "mod_necro", version = "0.4.0"} // the translated mod info
    author = "hackflow"                         // the translation author
    lang = "ru"                                 // target language, source is presumed to be english
}
// ... and translation pairs
local pairs = [
    // A literal pair
    {
        en = "Proper Necro"
        ru = "Годный Некромант"
    }
    // Capture names and numbers using patterns
    {
        mode = "pattern"
        en = "<actor:str_tag> heals for <hp:int> points"
        ru = "<actor> восстанавливает <hp> ОЗ"
    }
    // Can use id for longer string
    {
        id = "scripts/scenarios/world/necro_scenario.Description"
        ru = "[p=c][img]gfx/ui/events/event_76.png[/img][/p][p]После многих лет ..."
    }
    // Proper language dependent pluralization
    {
        plural = "range"
        en = "Has a range of <range:int_tag> tiles"
        n1 = "Имеет дальность в <range> клетку"
        n2 = "Имеет дальность в <range> клетки"
        n5 = "Имеет дальность в <range> клеток"
    }
    ...
]
// Register translation with rosetta
::Rosetta.add(rosetta, pairs);
```

Then put this file to scripts or include it. See also a [full example](https://github.com/Suor/battle-brothers-mods/blob/master/necro/necro/rosetta_ru.nut).


# Compatibility

Should be compatible with everything. It's ok to add, update or remove it midgame. Same goes for any rosetta based translations.


# Using Translations

To use Rosetta-based translation you need: original mod, its translation and mod_rosetta and its dependencies installed. This is different from when translation is done via replacing strings in the original mod and distributing localized version. Translation is simply a squirrel file, which could be shipped as a separate mod, bundled with the original mod or bundled with other translations.

When a **new version of a mod** is released you can update it right away, no need to wait for a new translated version or something. Old translation will mostly work, only new and changed strings will go untranslated. This works particularly well with bugfix releases, will never need to wait on those anymore.

If in trouble setting this up contact the translation author. The mod author might not be even aware of it being translated.


# Translating Mods

A Rosetta-based translation is a squirrel script registering english - target language pairs to be replaced during runtime. These could be literal strings, patterns and plural replacements as you can see in [Usage](#usage) above.

Since this is just a squirrel code you can split it into several files if you like to. It can also be shipped as a separate mod, be bundled with a mod itself or translations for several mods be bundled together. The full example you can find from the link at the bottom of the Usage section.

To set up transaltion of a new mod, i.e. extract strings to translate, you may use special extractor script:

```bash
python rosetta.py -lru mod_necro > mod_necro/necro/rosetta_ru.nut
```

This will provide you with a biolerplate filled in with all the strings found in the `mod_necro` dir. Then you will need to write fill in some metadata and translations, unless the latter are provided for you automatically, see `-e` option. In any case you will need to look those through and identify cases where you need to use patterns to capture substrings and do so.

To **update your translation** you can run extractor again setting output to a new file next to the old one. Then use some utility like Meld to look through and add new or changed strings to your existing translation. For this to work you will, however, need to not change translation file besides necessary, i.e. split it, reorder things in there and such.


## Extractor

This is a python script, which requires Python 3.12 and for automatic translations to work also requires python requests library.

```
Usage:
    python rosetta.py [options] <mod-file> > <to-file>
    python rosetta.py [options] <mod-dir> > <to-file>

Extracts strings and prepares a rosetta style translation file.

Arguments:
    <mod-file>  The path to a mod file
    <mod-dir>   Process all *.nut files in a dir
    <to-file>   Rosetta file to write

Options:
    -l<lang>    Target language to translate to, defaults to ru
    -t<engine>  Use automatic translation. Available options are:
                    yt (Yandex Translate), claude35 (Anthropic Claude-3.5-sonnet)
    -f          Overwrite existing files
    -v          Verbose output
    -h, --help  Show this help
```

## Limitations

addLang() (only russian is there already)
no options, only autodetect
no js
some hooks might be absent
same string is translated same, but see id


## More Examples

...

    {
        mode = "pattern"
        en = "Master raising undead. Use <open:tag><ap:int> AP<close:tag> and <fat:str_tag> less fatigue to raise."
        ru = "Мастер поднятия нежити. Тратит только <open><ap> ОД<close> и на <fat> меньше выносливости для поднятия мертвецов."
    }

...



# For Mod Authors

Rosetta is designed the way that translation is put on top, i.e. you won't need to apply any changes to your mod for this to work. There still might be corner cases and you

```squirrel
local _ = "Rosetta" in getroottable() ? Rosetta.translate.bindenv(Rosetta) : @(s) s;

_("Some string");
_("Thing does " + num + " things"); // Do not split this, otherwise pluralization won't be possible
```

...


# Feedback

Any suggestions, bug reports, other feedback are welcome. The best place for it is this Github, i.e. just create an issue. You can also find me on BB Modding Discord by **suor.hackflow** username.


# Index

<!-- MarkdownTOC autolink="true" levels="2,3,4" autoanchor="false" start="top" -->

- [Extractor](#extractor)
- [Limitations](#limitations)
- [More Examples](#more-examples)

<!-- /MarkdownTOC -->

[nexus-mods]: https://www.nexusmods.com/battlebrothers/mods/...
[ModernHooks]: https://www.nexusmods.com/battlebrothers/mods/685
[modhooks]: https://www.nexusmods.com/battlebrothers/mods/42
[stdlib]: https://www.nexusmods.com/battlebrothers/mods/676
[necro]: https://www.nexusmods.com/battlebrothers/mods/775
