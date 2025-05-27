dofile(getenv("STDLIB_DIR") + "load.nut", true);
dofile("mocks.nut", true);
dofile("scripts/!mods_preload/!rosetta.nut", true);

local Util = ::std.Util, Debug = ::std.Debug;

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
// ::Rosetta.activate("ru");

// Pattern tests
assertEq(def.parsePattern("Has a range of <range:int>"),
        {labels = ["range"], parts = ["Has a range of ", {sub = "int"}]});
assertEq(def.parsePattern("Has a range of <range:int> tiles"),
        {labels = ["range"], parts = ["Has a range of ", {sub = "int"}, " tiles"]});
assertEq(def.parsePattern("range <open:tag><range:int><close:tag>"),
        {labels = ["open", "range", "close"], parts = ["range ", {sub = "tag"}, {sub = "int"}, {sub = "tag"}]});
assertEq(def.parsePattern("Has a range of <range:int_tag> tiles"),
        {labels = ["range"], parts = ["Has a range of ", {sub = "int_tag"}, " tiles"]});
assertEq(def.parsePattern("<range:int> tiles"),
        {labels = ["range"], parts = [{sub = "int"}, " tiles"]});
assertEq(def.parsePattern("1 ... <range:int>"),
        {labels = ["range"], parts = ["1 ... ", {sub = "int"}]});

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

// This won't work - a key oin original text will be Some2, so no partial word labeling!
setup({
    mode = "pattern"
    en = "Some<x:int>"
    ru = "Типа<x>"
})
assertTr("Some2", "Some2");

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
assertTr("with Nimble and Battle Forged you only", "с Nimble and Battle Forged вы только");

setup({
    mode = "pattern"
    en = "with <item:str><num:int> item"
    ru = "с предметом <item><num>"
})
assertTr("with Sword+1 item", "с предметом Sword+1");
assertTr("with Battle Axe+1 item", "с предметом Battle Axe+1");


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
    assertEq(err, "Label type 'abc' is not supported")
}

try {
    setup({
        mode = "pattern"
        en = "this perk has a <chance:val> chance"
        ru = "... <not_found> ..."
    })
} catch (err) {
    assertEq(err, "Label 'not_found' is found in '... <not_found> ...' but not in the pattern")
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


print("Tests OK\n");
