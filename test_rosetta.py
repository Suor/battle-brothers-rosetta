from pprint import pprint
import io
import re
from textwrap import dedent

import sys
import pytest
from rosetta import extract, load_ref, run_check, OPTS, SEEN, REF_PAIRS, REF_RULES, CODE_RULES, REF_BLOCKS

OPTS['context'] = True
OPTS['debug'] = True
OPTS['failfast'] = True


def test_concat():
    code = 'print();\nlocal s = "Hello, " + "there"\nprint()'
    assert list_pairs(code) == [
        {'_code': ['local s = "Hello, " + "there"'], 'en': 'Hello, there', 'ru': '', '_context': 's'}
    ]

def test_concat_2_lines():
    code = '''
local s = "Hello, "
        + "there"
'''
    assert list_pairs(code) == [
        {'_code': ['local s = "Hello, "',
                   '        + "there"'],
        'en': 'Hello, there', 'ru': '', '_context': 's'}
    ]

def test_dangling_paren():
    code = '''
    ::Tactical.EventLog.log(
        ::Const.UI.getColorizedEntityName(actor) + " restores some armor"
    );'''
    assert list_pairs(code) == [
        {
            '_code': [
                '        ::Const.UI.getColorizedEntityName(actor) + " restores some armor"',
            ],
            '_context': '::Tactical.EventLog.log()',
            'en': '<::Const.UI.getColorizedEntityName(actor)> restores some armor',
            'mode': 'pattern',
            'ru': '',
        },
    ]


def test_concat_in_func():
    code = '''
        ::MSU.Class.EnumSetting("selectMode",
        "Select which bros become masters:" +
        " none - no new masters"
    );'''
    assert list_en(code) == ["Select which bros become masters: none - no new masters"]

def test_func_with_3_strings():
    code = '::MSU.Class.EnumSetting("selectMode", "hoThere", "no new masters");'
    assert list_en(code) == ["no new masters"]


def test_concat_ref():
    code = 'local s = "Hello, " + name'
    assert list_en(code) == ["Hello, <name>"]

def test_concat_ref_back():
    code = 'local s = name + " heals somewhat";'
    assert list_en(code) == ["<name> heals somewhat"]

def test_concat_paren():
    code = 'local s = "Hello, " + (name + "!")'
    assert list_en(code) == ["Hello, <name>!"]

def test_concat_paren_back():
    code = 'local s = (m.Name + " " + m.Title) + " dies"'
    assert list_en(code) == ["<m.Name> <m.Title> dies"]


def test_func():
    code = 'local s = "Requires " + Text.negative(fat) + " fatigue"'
    assert list_en(code) == ["Requires <Text.negative(fat)> fatigue"]

def test_func_first():
    code = 'Text.positive("is perfect") + ", i.e. "'
    assert list_en(code) == ["<Text.positive(is perfect)>, i.e. "]

def test_unknown_func_first():
    code = 'someFunc("is perfect") + ", i.e. "'
    assert list_en(code) == ["<someFunc(is perfect)>, i.e. "]

def test_func_dot():
    code = '''_entity.getName() + " against " + this.m.getEntity().getName() + "!");'''
    assert list_en(code) == ["<_entity.getName()> against <this.m.getEntity().getName()>!"]


def test_plural():
    code = 'Text.damage(kills) + Text.plural(kills, " wolf", " wolves"))'
    assert list_en(code) == ["<Text.damage(kills) + Text.plural(kills,  wolf,  wolves)>"]


def test_failed_to_parse():
    OPTS['failfast'] = False
    code = 'text = "Only receive " + Text.positive((100 ! bonus) + "%") + " of any attack damage"'
    assert list_en(code) == ["Only receive <Text.positive>", " of any attack damage"]
    OPTS['failfast'] = True

def test_complex_expr():
    code = 'text = "Only receive " + Text.positive((100 - bonus) + "%") + " of any attack damage"'
    assert list_en(code) == ["Only receive <Text.positive(100-bonus + %)> of any attack damage"]

def test_ternary_string_var():
    code = '''local x = condition ? "First option" : secondOption'''
    assert list_en(code) == ["First option"]

def test_ternary_var_string():
    code = '''local x = condition ? firstOption : "Second option"'''
    assert list_en(code) == ["Second option"]

def test_tricky_ternary():
    code = '''
        "which " + (bonus == this.m.BonusMax ? Text.positive("is perfect") + ", i.e. " :
                                       bonus > 0 ? Text.negative("is not perfect") + ", i.e. " :
                                       Text.negative("disables Stabilized") + ", get back to ")'''
    assert list_en(code) == [
        "which <Text.positive(is perfect)>, i.e. ",
        "which <Text.negative(is not perfect)>, i.e. ",
        "which <Text.negative(disables Stabilized)>, get back to ",
    ]


def test_value_destroyed():
    code = '''throw "Mod '" + codeName + "' is using an illegal code name"'''
    assert list_en(code) == []

def test_stop_func():
    code = '''::logInfo("mods_hookExactClass " + name);'''
    assert list_en(code) == []

def test_stop_func_ternary():
    code = ''' logInfo("mod_hooks: " + (cond ? friendlyName : "") + " version."); '''
    assert list_en(code) == []

def test_stop_func_second_arg():
    code = '''mod.require("mod_msu >= 1.6.0", "stdlib is interesting");'''
    assert list_en(code) == []

def test_stop_func_parse_error():
    code = '''logInfo("* " + _entity.getName() + ": Using " + !);'''
    assert list_en(code) == []


def test_flags():
    code = 'Flags.get("my str")'
    assert list_en(code) == []
    code = 'Flags.get("key") + "my str"'
    assert list_en(code) == ["<Flags.get(key)>my str"]
    code = '"a" + Flags.get("key") + "my str"'
    assert list_en(code) == ["a<Flags.get(key)>my str"]
    code = '"there are " + Flags.get("key")'
    assert list_en(code) == ["there are <Flags.get(key)>"]

def test_flags_has():
    code = '_entity.getFlags().has("ghoul")'
    assert list_en(code) == []

def test_long_list():
    names = [f'"Alex {c}"' for c in 'ABCD'] #* 100
    code = f'::Names <- [{", ".join(names)}]'
    assert list_en(code) == ['Alex A', 'Alex B', 'Alex C', 'Alex D']


def test_format_n_tabs():
    code = '''
        text = format("[color=%s]%s[/color] skill have [color=%s]%s[/color] chance to hit"
\t\t\t\t, NegativeValue, "Knock Back"
\t\t\t\t, PositiveValue, "100%"
\t\t\t\t)'''
    assert list_en(code) == [
        '[color=<NegativeValue>]Knock Back[/color] skill have '
        '[color=<PositiveValue>]100%[/color] chance to hit',
    ]

def test_brackets():
    code = ''' ::Const.UI.getColorized(arr[arr.len() - 1], "#afafaf") + " via " + ::Const.Thing,'''
    assert list_en(code) == ['<::Const.UI.getColorized(arr[arr.len()-1], #afafaf)> via <::Const.Thing>']

def test_tooltip():
    code = '''
        text = "Not enough Action Points to change items ([b][color=" + NegativeValue + "]"
             + _activeEntity.getItems().getActionCost([
            _item
        ]) + "[/color][/b] required)"'''
    assert list_en(code) == [
        'Not enough Action Points to change items '
        '([b][color=<NegativeValue>]<_activeEntity.getItems().getActionCost([_item])>[/color][/b] '
        'required)'
    ]

def test_rewind_dot():
    code = '''"hey: " + _activeEntity.getItems().getActionCost([_item]) + " AP required"'''
    assert list_en(code) == ['hey: <_activeEntity.getItems().getActionCost([_item])> AP required']

def test_rewind_ternary():
    code = 'text += ". " + (fromBros == 1 ? "One" : fromBros) + " of them from a hand of a bro."'
    assert list_en(code) == [
        '. One of them from a hand of a bro.',
        '. <fromBros> of them from a hand of a bro.',
    ]

def test_negative_int():
    code = '''"Has " + (-2 + this.m.AdditionalHitChance) + "% chance to hit"'''
    assert list_en(code) == ['Has <-2 + this.m.AdditionalHitChance>% chance to hit']

def test_concat_ternary():
    code = '"Inflicts additional " + mastery ? 10 : 5 + " bleeding damage over time"'
    assert list_en(code) == ['<5> bleeding damage over time']

def test_index():
    code = '"Captain, it is I, " + bros[2].getName() + ", who commands ..."'
    assert list_en(code) == ['Captain, it is I, <bros[2].getName()>, who commands ...']

def test_kind_of():
    code = 'this.isKindOf(this.getContainer().getActor().get(), "player")'
    assert list_en(code) == []


def test_ternary_destroyed():
    code = '''local text = deaths == 1 ? "Died once"
                    : format("Died %s time%s", red(deaths), Text.plural(deaths));'''
    assert list_en(code) == [
        'Died once',
        'Died <red(deaths)> time<Text.plural(deaths)>',
    ]

def test_curly():
    code = '''if ("FunFacts" in fallen) {
                ::std.Flags.pack(this.m.Flags, "FallenFunFacts." + i, fallen.FunFacts.pack());
            }'''
    assert list_en(code) == []

def test_no_semicolon():
    code = '''::mods_queue(mod.ID, function() {})
              ::mods_queue(mod.ID, ">msu", function () {})'''
    assert list_en(code) == []

def test_push():
    code = 'spent.push("[img]gfx/fun_facts/ammo.png[/img]" + Util.round(S.Ammo) + "hi");'
    assert list_en(code) == ['[img]gfx/fun_facts/ammo.png[/img]<Util.round(S.Ammo)>hi']

def test_in():
    code = 'local tpl = _kill.Fatality in fatalities ? fatalities[_kill.Fatality] : "Killed %s";'
    assert list_en(code) == ['Killed %s']

def test_if():
    code = 'if (::mods_isClass(_skill, "injury")) injuries.push(_skill);'
    assert list_en(code) == []

def test_if_and():
    code = 'if (!Util.isNull(master) && Util.isKindOf(master, "player")) {'
    assert list_en(code) == []

def test_foreach():
    code = 'foreach (w in ["mace" "cleaver" "sword" "dagger" "polearm"])'
    assert list_en(code) == ['mace', 'cleaver', 'sword', 'dagger', 'polearm']

def test_first_arg():
    code = 'ExcludedInjuries.add("Face", ["injury.rf_black_eye"]);'
    assert list_en(code) == ['Face']

def test_rewind_table():
    code = 'text = Text.colorizeValue(x, {sign = true}) + " [Renown|Concept.Reputation]"'
    assert list_en(code) == ['<Text.colorizeValue(x, {sign=true})> [Renown|Concept.Reputation]']

def test_comment():
    code = '''arr = [
        "Bardiche", // There is already a vanilla weapon with this name
        "Voulge"
    ]'''
    assert list_en(code) == ['Bardiche', 'Voulge']

def test_multiline_comment():
    code = '''arr = [
        /* This is a multiline comment
           with "multiple" lines */
        "Bardiche",
        "Voulge" /* inline multiline */
    ]'''
    assert list_en(code) == ['Bardiche', 'Voulge']

def test_broken_format():
    code = '''format("Hi, %s, %s", getName())'''
    assert list_en(code) == ['<format(Hi, %s, %s, getName())>']

def test_special_table():
    code = '''arbalester = {
        "mastery.crossbow": 50
        "bullseye": 20
    }'''
    assert list_en(code) == []

def test_incr_decr():
    code = '''_vars.push([
        "bro" + currentBro++ + "name",
        "second" + --currentBro + "name",
    ])'''
    assert list_en(code) == ['bro<currentBro++>name', 'second<--currentBro>name']


# Reference tests

def test_load_ref(clear_ref):
    load_ref(io.StringIO(dedent('''\
        local pairs = [
            {
                en = "Hello"
                ru = "Привет"
            }
            // en = "Skipped"
        ]
    ''')))
    assert set(REF_PAIRS) == {"Hello", "Skipped"}

def test_load_ref_single_line(clear_ref):
    load_ref(io.StringIO('local pairs = [{en = "Hello" ru = "Привет"} {en = "World" ru = "Мир"}]\n'))
    assert set(REF_PAIRS) == {"Hello", "World"}
    assert list_pairs('text = "Hello"') == ['{en = "Hello" ru = "Привет"}']

def test_load_ref_commas(clear_ref):
    load_ref(io.StringIO(dedent('''\
        local pairs = [
            {en = "Hello", ru = "Привет"},
            {en = "World", ru = "Мир"},
        ]
    ''')))
    assert set(REF_PAIRS) == {"Hello", "World"}
    assert list_pairs('text = "Hello"') == ['\n    {en = "Hello", ru = "Привет"},']

def test_load_ref_newlines(clear_ref):
    block = dedent('''\
        {
            en = "Iron\\n\\nContinues"
            ru = "Железо"
               + "\\n\\nПродолжает"
        }''')
    load_ref(io.StringIO(f'local pairs = [{block}]'))
    code = """
        Tooltip = "Iron"
                + "\\n\\nContinues"
    """
    assert list_pairs(code) == [block]

def test_run_check_newlines_not_unmatched(clear_ref, monkeypatch):
    """run_check should not report UNMATCHED for translated entries with \\n in en"""
    import tempfile
    from pathlib import Path

    exits = []
    monkeypatch.setattr(sys, 'exit', exits.append)
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "skill.nut").write_text('Tooltip = "Iron" + "\\n\\nContinues"')
        load_ref(io.StringIO('local pairs = [{en = "Iron\\n\\nContinues" ru = "Железо"}]'))
        SEEN.clear()
        run_check(Path(tmpdir))
    assert exits == []

def test_load_ref_slash_in_block(clear_ref):
    """/  in non-en fields (id, ru) must be preserved in stored blocks"""
    block = dedent('''\
        {
            id = "scripts/world/file.Description"
            en = "Hello"
            ru = "Привет/до свидания"
        }''')
    load_ref(io.StringIO(f'local pairs = [{block}]'))
    assert list_pairs('text = "Hello"') == [block]

def test_str_tag_matches_this_prefix(clear_ref):
    """str_tag pattern should match getColorizedEntityName with this. prefix (not just ::)"""
    block = dedent('''\
        {
            mode = "pattern"
            en = "<actor:str_tag> gains rage!"
            ru = "<actor> впадает в ярость!"
        }''')
    load_ref(io.StringIO(f'local pairs = [{block}]'))
    code = 'this.Tactical.EventLog.log(this.Const.UI.getColorizedEntityName(actor) + " gains rage!")'
    assert list_pairs(code) == [block]

def test_tag_wrapped_matches_color_concat(clear_ref):
    """<open:tag>TEXT<close:tag> pattern should match extracted '[color=<expr>]TEXT[/color]' form"""
    block = dedent('''\
        {
            mode = "pattern"
            en = "<open:tag>Is empty and useless<close:tag>"
            ru = "<open>Пуст и бесполезен<close>"
        }''')
    load_ref(io.StringIO(f'local pairs = [{block}]'))
    code = 'text = "[color=" + this.Const.UI.Color.NegativeValue + "]Is empty and useless[/color]"'
    assert list_pairs(code) == [block]

def test_silent_pack(clear_ref, monkeypatch):
    ref = dedent('''\
        local pairs = [
            {
                en = "Known string"
                ru = "Известная строка"
            }
            {
                mode = "pattern"
                en = "<val:int_tag> Initiative"
                ru = "<val> к инициативе"
            }
        ]
    ''')
    # Verify strings are extractable before silent loading
    assert list_en('text = "Known string"') == ["Known string"]
    assert list_en('text = "[color=" + Color.green + "]+" + this.m.Init + "[/color] Initiative"') \
        == ['[color=<Color.green>]+<this.m.Init>[/color] Initiative']

    load_ref(io.StringIO(ref), silent=True)
    assert list_en('text = "Known string"') == []
    assert list_en('text = "[color=" + Color.green + "]+" + this.m.Init + "[/color] Initiative"') == []


# Context tests

def test_context_simple_assignment():
    code = 'local myVar = "Hello"'
    assert list_context(code) == ["myVar"]

def test_context_object_prop_array():
    code = '''this.m.Titles = [
        "the Keymaster",
        "the Locksmith"
    ]'''
    assert list_context(code) == ["m.Titles", "m.Titles"]

def test_context_table():
    code = '''Titles = {
        a = "the Keymaster",
        b = "the Locksmith"
    }'''
    assert list_context(code) == ["Titles.a", "Titles.b"]

def test_context_array_index():
    code = '''this.m.Titles[2] = "the Keymaster"'''
    assert list_context(code) == ["m.Titles[2]"]

def test_context_function_scope():
    code = '''function create() {
        local x = "Hello"
    }'''
    assert list_context(code) == ["create.x"]

def test_context_nested_functions():
    code = '''function create() {
        function inner() {
            local x = "Hello"
            local y = "Bye"
        }
    }'''
    assert list_context(code) == ["create.inner.x", "create.inner.y"]

def test_context_anonymous_function():
    code = '''create = function() {
        local x = "Hello"
    }'''
    assert list_context(code) == ["create.x"]

def test_context_call():
    code = '''function create() {
        m.Names.push(["item1", "item2"])
    }'''
    assert list_context(code) == ["create.m.Names.push()"]

def test_context_call_then_assign():
    code = '''function create() {
        this.raise_undead.create()
        this.m.Description = "Raises a corpse ..."
    }'''
    assert list_context(code) == ["create.m.Description"]

def test_context_assign_then_call():
    code = '''
    local page = def.msu.ModSettings.addPage("Autopilot");
    page.addElement(::MSU.Class.BooleanSetting("player", true, "Auto Player Characters"));
    '''
    assert list_context(code) == ["page.def.msu.ModSettings.addPage()", "page.addElement().::MSU.Class.BooleanSetting()"]

def test_context_no_context():
    code = 'local x = "Hello"'
    assert list_context(code) == ["x"]

def test_context_inherit_pattern():
    code = '''this.locksmith_background <- this.inherit("...", {
        WRONG = {}
        function create() {
            this.m.Titles = [
                "the Keymaster"
            ]
        }
    })'''
    assert list_context(code) == ["locksmith_background.create.m.Titles"]

def test_context_table_no_commas():
    code = '''some_var = {
        a = "the Keymaster"
        b = "the Locksmith"
    }'''
    assert list_context(code) == ["some_var.a", "some_var.b"]

def test_context_table_function_then_assignment():
    code = '''some_var = {
        function foo() {
            local x = "inside"
        }
        a = "outside"
    }'''
    assert list_context(code) == ["some_var.foo.x", "some_var.a"]

def test_context_function_param_defaults():
    code = '''function foo(x = "default value") {
        local y = "body value"
    }'''
    assert list_context(code) == ["foo.x", "foo.y"]

def test_context_modern_hook():
    code = '''
    mod.queue(mod.ID, function () {
        mod.hook("scripts/skills/actives/possess_undead_skill", function (q) {
            q.create = @(__original) function() {
                __original();
                this.m.Description = "Possess an undead ...";
            }
        })
    })
    '''
    assert list_context(code) == ["possess_undead_skill.q.create.m.Description"]

@pytest.mark.xfail
def test_context_formatted():
    code = '''
        local hi = "Hello, " + Text.positive("Some name");
        local by = Text.positive("Some name") + ", poka-poka!";
    '''
    assert list_context(code) == ["hi", "by"]


# Helpers

def list_en(code):
    return [item["en"] for item in list_pairs(code)]

def list_context(code):
    return [item["_context"] for item in list_pairs(code)]

def list_pairs(code):
    SEEN.clear()
    return list(extract(code))

@pytest.fixture(autouse=False)
def clear_ref():
    yield
    REF_PAIRS.clear()
    REF_RULES.clear()
    CODE_RULES.clear()
    REF_BLOCKS.clear()
