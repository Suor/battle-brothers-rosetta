# Rosetta Translations Framework

This is a framework mod aimed to facilitate translating Battle Brother mods to various languages. Design goals:

- be easy to use and maintain
- work on top of unmodified mods
- no central infrastructure required
- untie translation cycle from mod release cycle
- flexibility of packaging: bundle with mod, separate mod, translations pack

Currently all the translation is done in squirrel by intercepting strings either at the squirrel/js border or earlier if that is easier to implement.

Or just a thing to take the place of lacking Squirrel/Battle Brothers standard library. An assortment of various utils to help coding mods. If you here first time I suggest starting from the [Usage](#usage) section.

<!-- MarkdownTOC autolink="true" levels="1,2,3" autoanchor="false" start="here" -->

- [Usage](#usage)
- [Compatibility](#compatibility)
- [API](#api)
- [Extractor](#extractor)
- [Feedback](#feedback)
- [Index](#index)

<!-- /MarkdownTOC -->


# Usage

Install it from [NexusMods][nexus-mods], or grab from here and zip. Then:

```squirrel
...
```


# Compatibility

Should be highly compatible.


# API

...


# Extractor

```
Usage:
    python rosetta.py <mod-file> <to-file> [options]
    python rosetta.py <mod-dir> <to-file> [options]

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


# Feedback

Any suggestions, bug reports, other feedback are welcome. The best place for it is this Github, i.e. just create an issue. You can also find me on Discord by **suor.hackflow** username.


# Index

<!-- MarkdownTOC autolink="true" levels="2,3,4" autoanchor="false" start="top" -->

<!-- /MarkdownTOC -->

[nexus-mods]: https://www.nexusmods.com/battlebrothers/mods/...
[ModernHooks]: https://www.nexusmods.com/battlebrothers/mods/685
[modhooks]: https://www.nexusmods.com/battlebrothers/mods/42
[stdlib]: https://www.nexusmods.com/battlebrothers/mods/676
[necro]: https://www.nexusmods.com/battlebrothers/mods/775
