dofile(getenv("STDLIB_DIR") + "load.nut", true);
dofile("mocks.nut", true);
dofile("scripts/!mods_preload/!rosetta.nut", true);

local Util = ::std.Util, Str = ::std.Str, Debug = ::std.Debug;

function assertEq(a, b) {
    if (Util.deepEq(a, b)) return;
    throw "assertEq failed:\na = " + Debug.pp(a) + "b = " + Debug.pp(b);
}
function assertTr(_en, _ru) {
    assertEq(::Rosetta.translate(_en), _ru)
}

local def = ::Rosetta;
local rosetta = {
    mod = {id = "mod_rosetta", version = "1.0.0"}
    lang = "ru"
}
function setup(_pairs) {
    def.maps = {};
    def.add(rosetta, typeof _pairs == "array" ? _pairs : [_pairs]);
}
::Rosetta.activate("ru");

// Pattern tests
assertEq(def.parsePattern("Has a range of <range:int>"),
        ["Has a range of ", {name = "range", sub = "int"}]);
assertEq(def.parsePattern("Has a range of <range:int> tiles"),
        ["Has a range of ", {name = "range", sub = "int"}, " tiles"]);
assertEq(def.parsePattern("range <open:tag><range:int><close:tag>"),
        ["range ", {name = "open", sub = "tag"}, {name = "range", sub = "int"}, {name = "close", sub = "tag"}]);
assertEq(def.parsePattern("Has a range of <range:int_tag> tiles"),
        ["Has a range of ", {name = "range", sub = "int_tag"}, " tiles"]);
assertEq(def.parsePattern("<range:int> tiles"),
        [{name = "range", sub = "int"}, " tiles"]);
assertEq(def.parsePattern("1 ... <range:int>"),
        ["1 ... ", {name = "range", sub = "int"}]);


// ...
local s = "[imgtooltip=mod_msu.Perk+perk_brawny]gfx/ui/perks/perk_40.png[/imgtooltip]"
assertEq(!!def._isInteresting(s), false);
assertEq(!!def._isInteresting("MSU Dummy Player Background"), false);


local html = "<div class='rf_tacticalTooltipAttributeList'><span class='rf_tacticalTooltipAttributeEntry'><img src='coui://gfx/ui/icons/melee_skill.png'/> <span class='rf_tacticalTooltipAttributeValue'>55</span><span class='rf_tacticalTooltipAttributeDelta'>([color=#135213]+5[/color])</span></span><span class='rf_tacticalTooltipAttributeEntry'><img src='coui://gfx/ui/icons/ranged_skill.png'/> <span class='rf_tacticalTooltipAttributeValue'>49</span><span class='rf_tacticalTooltipAttributeDelta'>([color=#135213]+4[/color])</span></span><span class='rf_tacticalTooltipAttributeEntry'><img src='coui://gfx/ui/icons/bravery.png'/> <span class='rf_tacticalTooltipAttributeValue'>45</span><span class='rf_tacticalTooltipAttributeDelta'></span></span><span class='rf_tacticalTooltipAttributeEntry'><img src='coui://gfx/ui/icons/melee_defense.png'/> <span class='rf_tacticalTooltipAttributeValue'>28</span><span class='rf_tacticalTooltipAttributeDelta'>([color=#135213]+28[/color])</span></span><span class='rf_tacticalTooltipAttributeEntry'><img src='coui://gfx/ui/icons/ranged_defense.png'/> <span class='rf_tacticalTooltipAttributeValue'>34</span><span class='rf_tacticalTooltipAttributeDelta'>([color=#135213]+34[/color])</span></span><span class='rf_tacticalTooltipAttributeEntry'><img src='coui://gfx/ui/icons/initiative.png'/> <span class='rf_tacticalTooltipAttributeValue'>79</span><span class='rf_tacticalTooltipAttributeDelta'>([color=#8f1e1e]-16[/color])</span></span></div>";
assert(!def._isInteresting(html))
local bbtag = "[105109103116111111108116105112=109111100095109115117046083107105108108043116104114117115116044101110116105116121073100058052056052055057044099115115067108097115115058114102045110101115116101100045115107105108108045105109097103101]gfx/skills/active_04.png[/105109103116111111108116105112][105109103116111111108116105112=109111100095109115117046083107105108108043115112101097114119097108108044101110116105116121073100058052056052055057044099115115067108097115115058114102045110101115116101100045115107105108108045105109097103101]gfx/skills/active_23.png[/105109103116111111108116105112][105109103116111111108116105112=109111100095109115117046083107105108108043116104114111119095100105114116095115107105108108044101110116105116121073100058052056052055057044099115115067108097115115058114102045110101115116101100045115107105108108045105109097103101]gfx/skills/active_215.png[/105109103116111111108116105112][105109103116111111108116105112=109111100095109115117046083107105108108043107110111099107095098097099107044101110116105116121073100058052056052055057044099115115067108097115115058114102045110101115116101100045115107105108108045105109097103101]gfx/skills/active_10.png[/105109103116111111108116105112][105109103116111111108116105112=109111100095109115117046083107105108108043115104105101108100119097108108044101110116105116121073100058052056052055057044099115115067108097115115058114102045110101115116101100045115107105108108045105109097103101]gfx/skills/active_15.png[/105109103116111111108116105112][105109103116111111108116105112=109111100095109115117046083107105108108043114101099111118101114095115107105108108044101110116105116121073100058052056052055057044099115115067108097115115058114102045110101115116101100045115107105108108045105109097103101]gfx/ui/perks/perk_54_active.png[/105109103116111111108116105112]";
assertEq(def._clean(bbtag), "")

::Rosetta.stats.rule_uses = 100; // check logging stats

// Translate via pattern
setup({
    mode = "pattern"
    en = "Has a range of <range:int> tiles"
    ru = "Дальность <range> клеток"
})
assertTr("Has a range of 5 tiles", "Дальность 5 клеток");

setup({
    mode = "pattern"
    en = "Has a range of <open:tag><range:int><close:tag> tiles"
    ru = "Дальность <open><range><close> клеток"
})
assertTr("Has a range of [b]5[/b] tiles", "Дальность [b]5[/b] клеток");

setup({
    mode = "pattern"
    en = "Has a range of <range:int_tag> tiles"
    ru = "Дальность <range> клеток"
})
assertTr("Has a range of [b]5[/b] tiles", "Дальность [b]5[/b] клеток");
assertTr("it Has a range of [b]5[/b] tiles", "it Has a range of [b]5[/b] tiles"); // prefix
assertTr("Has a range of [b]5[/b] tiles.", "Has a range of [b]5[/b] tiles."); // suffix

// plurals
setup({
    plural = "range"
    en = "Has a range of <range:int> tiles"
    n1 = "Дальность - <range> клетка"
    n2 = "Дальность - <range> клетки"
    n5 = "Дальность - <range> клеток"
})
assertTr("Has a range of 1 tiles", "Дальность - 1 клетка");
assertTr("Has a range of 31 tiles", "Дальность - 31 клетка");
assertTr("Has a range of 23 tiles", "Дальность - 23 клетки");
assertTr("Has a range of 5 tiles", "Дальность - 5 клеток");
assertTr("Has a range of 14 tiles", "Дальность - 14 клеток");

setup({
    plural = "range"
    en = "Has a range of <range:int_tag> tiles"
    n1 = "Дальность - <range> клетка"
    n2 = "Дальность - <range> клетки"
    n5 = "Дальность - <range> клеток"
})
assertTr("Has a range of [b]4[/b] tiles", "Дальность - [b]4[/b] клетки");

// Reverse labels and no proper contenKey
setup({
    mode = "pattern"
    en = "<x:int> and <y:int>"
    ru = "<y> и <x>"
})
assertTr("11 and 22", "22 и 11");

// This works using "" rule key
setup({
    mode = "pattern"
    en = "Some<x:int>"
    ru = "Типа<x>"
})
assertTr("Some2", "Типа2");

// Label match as a potential contentKey
setup({
    mode = "pattern"
    en = "<name:word> says hello"
    ru = "<name> передаёт привет"
})
assertTr("Yarg says hello", "Yarg передаёт привет");
assertTr("Йарг says hello", "Йарг передаёт привет"); // Check matching non-english words


setup({
    mode = "pattern"
    en = "with <others:str> you only"
    ru = "с <others> вы только"
})
assertTr("with Nimble you only", "с Nimble вы только");
// Multi-word :str -- exposed Squirrel's regexp backtracking bug, motivated matchParts().
assertTr("with Nimble and Battle Forged you only", "с Nimble and Battle Forged вы только");

setup({
    mode = "pattern"
    en = "with <item:str><num:int> item"
    ru = "с предметом <item><num>"
})
assertTr("with Sword+1 item", "с предметом Sword+1");
assertTr("with Battle Axe+1 item", "с предметом Battle Axe+1");

// :line -- like :str but bounded by \n; eats the trailing \n (or end of string)
assertEq(def.parsePattern("Spent <x:line>"),
        ["Spent ", {name = "x", sub = "line"}]);

setup({
    mode = "pattern"
    en = "Spent <x:line>"
    ru = "Потратил <x>"
})
assertTr("Spent foo", "Потратил foo");
// The fix: :line does not cross \n -- with :str the rule would greedy-eat past
// the newline and translate "Spent foo\nrest" as "Потратил foo\nrest".
assertTr("Spent foo\nrest", "Spent foo\nrest"); // didn't match, returned as-is

// :line eats the trailing \n; the literal that follows starts AFTER it.
setup({
    mode = "pattern"
    en = "<x:line>then <y:str>"
    ru = "<x>далее <y>"
})
assertTr("first\nthen rest", "first\nдалее rest");

// Limitation: :line is greedy and the engine doesn't backtrack -- same family
// of issues as :str via single regex. Don't place :line before a non-\n anchor;
// it will eat it whole and the rule won't match.
setup({
    mode = "pattern"
    en = "<x:line> tail"
    ru = "<x> хвост"
})
assertTr("abc tail", "abc tail"); // didn't match


setup({
    mode = "pattern"
    en = "Use <open:tag><ap:int> AP<close:tag> and <fat:str_tag> less fatigue."
    ru = "Тратит только <open><ap> ОД<close> и на <fat> меньше выносливости."
})
assertTr(
    "Use [color=#135213]4 AP[/color] and [color=#135213]25%[/color] less fatigue.",
    "Тратит только [color=#135213]4 ОД[/color] и на [color=#135213]25%[/color] меньше выносливости."
)


setup({
    mode = "pattern"
    en = "this perk has a <chance:val_tag> chance"
    ru = "По достижении 5 уровня есть <chance> шанс"
})
assertTr(
    "this perk has a [color=#135213]70%[/color] chance",
    "По достижении 5 уровня есть [color=#135213]70%[/color] шанс"
)


// Bad rules
try {
    setup({
        mode = "pattern"
        en = "this perk has a <chance:abc> chance"
        ru = "... <chance> ..."
    })
} catch (err) {
    assert(Str.startswith(err, "Label type 'abc' is not supported"))
}

try {
    setup({
        mode = "pattern"
        en = "this perk has a <chance:val> chance"
        ru = "... <not_found> ..."
    })
} catch (err) {
    assert(Str.startswith(err, "Label 'not_found' is in 'ru' but not in 'en'"))
}


// Double translation
setup([
    {
        plural = "uses"
        en = "Used nine lives <uses:int> times<end:str>"
        n1 = "Использовал 'Девять жизней' <uses> раз<end:t>"
        n2 = "Использовал 'Девять жизней' <uses> раза<end:t>"
        n5 = "Использовал 'Девять жизней' <uses> раз<end:t>"
    }
    {
        mode = "pattern"
        en = "Used nine lives once<end:str>"
        ru = "Однажды использовал 'Девять жизней'<end:t>"
    }
    {
        en = ", died every time"
        ru = ", помирал каждый раз"
    }
    {
        en = ", died anyway"
        ru = ", всё равно подох"
    }
    {
        plural = "saves"
        en = ", survived <saves:int> times"
        n1 = ", выжил <saves> раз"
        n2 = ", выжил <saves> раза"
        n5 = ", выжил <saves> раз"
    }
    {
        en = ", survived once"
        ru = ", выжил разок"
    }
])
assertTr(
    "Used nine lives 2 times, survived once",
    "Использовал 'Девять жизней' 2 раза, выжил разок"
)
assertTr(
    "Used nine lives 7 times, died every time",
    "Использовал 'Девять жизней' 7 раз, помирал каждый раз"
)
assertTr(
    "Used nine lives 7 times, survived 3 times",
    "Использовал 'Девять жизней' 7 раз, выжил 3 раза"
)
assertTr(
    "Used nine lives once, died anyway",
    "Однажды использовал 'Девять жизней', всё равно подох"
)

// Non-obvious rule keys
setup({
    mode = "pattern"
    en = "<open:tag>is not perfect<close:tag>, i.e. "
    ru = "<open>не идеально<close>, т.е. "
})
assertTr(
    "[b]is not perfect[/b], i.e. ",
    "[b]не идеально[/b], т.е. "
)

setup({
    mode = "pattern"
    en = "<num:int> day<s:str>"
    // en = "<num:int> day<|s>"
    ru = "<num> дней"
})
assertTr("1 day", "1 дней")
assertTr("5 days", "5 дней")

setup({
    plural = "days"
    en = "Light Wounds (<days:int> day<s:str>)"
    n1 = "Лёгкие раны (<days> день)"
    n2 = "Лёгкие раны (<days> дня)"
    n5 = "Лёгкие раны (<days> дней)"
})
assertTr("Light Wounds (1 day)", "Лёгкие раны (1 день)")
assertTr("Light Wounds (2 days)", "Лёгкие раны (2 дня)")

setup({
    mode = "pattern"
    en = "<num:int> day<s:str><img:tag>"
    ru = "<num> дней<img>"
})
assertTr("1 day[img]", "1 дней[img]")
assertTr("5 days[img=123]", "5 дней[img=123]")


::Rosetta.stats.rule_uses = 200; // check logging stats

setup([
    {
        mode = "pattern"
        en = "<title:str> (Failed)"
        ru = "<title:t> (Провал)"
    }
    {
        en = "Something"
        ru = "Что-то"
    }
])
assertTr("Something (Failed)", "Что-то (Провал)")

// Don't allow partial
setup({
    mode = "pattern"
    en = "<title:str> (Failed)"
    ru = "<title:t> (Провал)"
})
assertTr("Something (Failed)", "Something (Failed)")


setup([
    {
        // mode = "pattern"
        en = "Hired for <end:str>"
        split = "\n"
    }
    {
        mode = "pattern"
        en = "Hired for <money:img><hire:int>."
        ru = "Нанят за <money><hire>."
    }
    {
        mode = "pattern"
        en = "Spent <spent:str>"
        ru = "Потратил <spent>"
    }
    // {
    //     mode = "pattern"
    //     en = "<start:str>\nTCO ~ <end:str>"
    //     split = "\n"
    // }
    {
        mode = "pattern"
        en = "TCO ~ <money:img><total:int>"
        ru = "TCO ~ <money><total>"
    }
])
assertTr("Hired for [img]...[/img]171.", "Нанят за [img]...[/img]171.")
assertTr("Hired for [img]...[/img]171.\nSpent 45\nTCO ~ [img]...[/img]267",
         "Нанят за [img]...[/img]171.\nПотратил 45\nTCO ~ [img]...[/img]267")


setup([
    {
        // local text = "Was " + Str.join(", ", desc);
        mode = "pattern"
        en = "Was <middle:str> times"
        function use(_str, _m) {
            return "Был " + ::Rosetta.useSplit(this, ", ", _m.middle + " times")
        }
    }
    {
        // .map(@(n) format("%s %d times", n, effects[n]));
        plural = "n"
        en = "<effect:str> <n:int> times"
        n1 = "<effect:t> <n> раз"
        n2 = "<effect:t> <n> раза"
        n5 = "<effect:t> <n> раз"
    }
    {
        en = "charmed"
        ru = "зачарован"
    }
    {
        en = "swallowed"
        ru = "проглочен"
    }
    {
        en = "netted"
        ru = "спутан"
    }
    {
        en = "stunned"
        ru = "оглушён"
    }
])
assertTr("Was stunned 2 times, swallowed 5 times", "Был оглушён 2 раза, проглочен 5 раз")


// setup({
//     mode = "pattern"
//     en = "Level <lvl:int>, Health <hp:val>%" // val slurps %
//     ru = "Уровень <lvl>, Здоровье <hp>%"
// })
// assertTr("Level 3, Health 100%", "Уровень 3, Здоровье 100%")


print("Tests OK\n");
