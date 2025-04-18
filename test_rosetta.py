from pprint import pprint
import re
from textwrap import dedent

from rosetta import extract, SEEN


def test_concat():
    code = 'local s = "Hello, " + "there"'
    assert list_en(code) == ["Hello, there"]

def test_concat_2_lines():
    code = '''local s = "Hello, "
                      + "there"'''
    assert list_en(code) == ["Hello, there"]

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


# Helpers

def list_en(code):
    SEEN.clear()
    return [item["en"] for item in extract(code.splitlines())]
