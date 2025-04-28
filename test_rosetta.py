from pprint import pprint
import re
from textwrap import dedent

from rosetta import extract, OPTS, SEEN

OPTS['debug'] = True


def test_concat():
    code = 'print();\nlocal s = "Hello, " + "there"\nprint()'
    assert list_pairs(code) == [
        {'_code': ['local s = "Hello, " + "there"'], 'en': 'Hello, there', 'ru': ''}
    ]

def test_concat_2_lines():
    code = '''
local s = "Hello, "
        + "there"
'''
    assert list_pairs(code) == [
        {'_code': ['local s = "Hello, "',
                   '        + "there"'],
        'en': 'Hello, there', 'ru': ''}
    ]

def test_concat_in_func():
    code = '''
        ::MSU.Class.EnumSetting("selectMode",
        "Select which bros become masters:" +
        " none - no new masters"
    );'''
    assert list_en(code) == ["Select which bros become masters: none - no new masters"]


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

def test_func_dot():
    code = '''_entity.getName() + " against " + this.m.getEntity().getName() + "!");'''
    assert list_en(code) == ["<_entity.getName()> against <this.m.getEntity()><.><getName()>!"]


def test_plural():
    code = 'Text.damage(kills) + Text.plural(kills, " wolf", " wolves"))'
    assert list_en(code) == ["<Text.damage(kills)><Text.plural(kills,  wolf,  wolves)>"]


def test_failed_to_parse():
    code = 'text = "Only receive " + Text.positive((100 ! bonus) + "%") + " of any attack damage"'
    assert list_en(code) == ["Only receive ", " of any attack damage"]

def test_complex_expr():
    code = 'text = "Only receive " + Text.positive((100 - bonus) + "%") + " of any attack damage"'
    assert list_en(code) == ["Only receive <Text.positive(100-bonus%)> of any attack damage"]

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


def test_long_list():
    names = ['"Alex"'] * 400
    code = f'::Names <- [{", ".join(names)}]'
    assert list_en(code) == ['Alex']


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
        '([b][color=<NegativeValue>]<_activeEntity.getItems()><.><getActionCost([_item])>[/color][/b] '
        'required)'
    ]

# def test_rewind_dot():
#     code = '''"hey: " + _activeEntity.getItems().getActionCost() + "AP required"'''
#     assert list_en(code) == ['<_activeEntity.getItems()><.><getActionCost([_item]) AP required']

def test_negative_int():
    code = '''"Has " + (-2 + this.m.AdditionalHitChance) + "% chance to hit"'''
    assert list_en(code) == ['Has <-><2><this.m.AdditionalHitChance>% chance to hit']


# Helpers

def list_en(code):
    SEEN.clear()
    return [item["en"] for item in extract(code.splitlines())]

def list_pairs(code):
    SEEN.clear()
    return list(extract(code.splitlines()))
