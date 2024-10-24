from pprint import pprint
import re
from textwrap import dedent

from rosetta import extract


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


# Helpers

def list_en(code):
    return [item["en"] for item in extract(code.splitlines())]

# def test_parse_table():
#     code = dedent("""\
#         gt.Props = {
#             Count = 0,
#             SpawnList = null
#             Flag = true
#             function test(_param)
#             {
#                 return _param > 100;
#             }
#         }
#     """)
#     assert roundtrip(code) == code.replace(",", "").replace(")\n    {", ") {")

# def test_parse_table_bad_indent():
#     code = dedent("""\
#         gt.Props = {
#             Sub = {
#                 X = 1
#                }
#             Arr = [
#              ]
#             function test(_param) {
#                 return _param > 100;
#             }
#             function test2(_param)
#           {
#                 return _param > 100;
#          }
#         }
#     """)
#     fixed = re.sub(r'\)\s*\{', ') {', code)
#     fixed = re.sub(r'\n\s+([}\]])', r'\n    \1', fixed)
#     assert roundtrip(code) == fixed

# def test_aoa():
#     # NOTE: should not loose comma between elements
#     code = """\
#         gt.Skills = [
#             "start",
#             [
#                 "dash"
#                 5
#             ],
#             // comment
#             [
#                 "slash"
#                 17
#             ]
#         ]
#     """
#     assert roundtrip(code) == dedent(code)

# def test_parse_nested_curly():
#     code = dedent("""\
#         gt.Data = {
#             function some() {
#                 if (cond) {
#                     do something;
#                 }
#             }
#         }
#     """)
#     assert roundtrip(code) == dedent(code)

# def test_parse_inherit():
#     code = """\
#         this.location <- this.inherit("scripts/entity/world/world_entity", {
#             m = {
#                 Name = "",
#                 Type = 0,
#                 Loot = null
#             },
#             function create()
#             {
#                 this.world_entity.create();
#                 this.m.IsAttackable = true;
#             }
#         })
#     """
#     assert roundtrip(code) == dedent(code).replace(",\n", "\n").replace(")\n    {", ") {")


# def test_diff_inherit():
#     base_code = """\
#         this.location <- this.inherit("scripts/entity/world/world_entity", {
#             m = {
#                 Name = "",
#                 Type = 0,
#                 Banner = "banner_beasts_01",
#                 Loot = null
#             },

#             function create()
#             {
#                 this.world_entity.create();
#                 this.m.IsAttackable = true;
#                 this.m.Loot = this.new("scripts/items/stash_container");
#                 this.m.Loot.setResizable(true);
#             }
#             function getTypeID()
#             {
#                 return this.m.TypeID;
#             }

#             function isLocation()
#             {
#                 return true;
#             }
#         })
#     """
#     code = """\
#         this.location <- this.inherit("scripts/entity/world/world_entity", {
#             m = {
#                 Name = ""
#                 Type = 2,
#                 Description = "<not-set>",
#                 // Troops = [] // comment is lost
#                 Loot = null
#             },
#             function create()
#             {
#                 this.world_entity.create();
#                 this.m.IsAttackable = false;
#                 this.m.Loot = this.new("scripts/items/stash_container");
#                 this.m.Loot.setResizable(true);
#             }
#             function newFunc (_a, _b) {
#                 return _a + _b;
#             }
#             function getTypeID()
#             {
#                 return this.m.TypeID;
#             }
#         })
#     """
#     assert diff(code, code) == ""
#     assert diff(base_code, code) == dedent("""\
#         ::mods_hookExactClass("path/to/location", function(cls) {
#             delete cls.m.Banner;
#             cls.m.Type = 2; // 0
#             cls.m.Description <- "<not-set>";

#             local create = cls.create;
#             cls.create = function () {
#                 this.world_entity.create();
#                 // this.m.IsAttackable = true;
#                 this.m.IsAttackable = false;
#                 this.m.Loot = this.new("scripts/items/stash_container");
#                 this.m.Loot.setResizable(true);
#             }

#             cls.newFunc <- function (_a, _b) {
#                 return _a + _b;
#             }
#             delete cls.isLocation;
#         })
#     """)


# def test_diff_table():
#     base_code = """\
#         gt.Props = {
#             Name = "",
#             Count = 0
#             Flag = false
#         }
#     """
#     code = """\
#         gt.Props = {
#             Count = 0,
#             SpawnList = null,
#             Flag = true
#         }
#     """
#     assert diff(base_code, code) == dedent("""\
#         delete gt.Props.Name;
#         gt.Props.SpawnList <- null;
#         gt.Props.Flag = true; // false
#     """)

# def test_tot():
#     base_code = """\
#         gt.Const = {
#             Props = {
#                 Num = 12
#             }
#         }
#     """
#     code = """\
#         gt.Const = {
#             Props = {
#                 Num = 25
#                 Type = "goblin"
#             }
#         }
#     """
#     assert diff(base_code, code) == dedent("""\
#         gt.Const.Props.Num = 25; // 12
#         gt.Const.Props.Type <- "goblin";
#     """)

# def test_new_table():
#     base_code = ""
#     code = """\
#     """
#     assert diff(base_code, code) == dedent(code)


# def test_array_simple():
#     base_code = """\
#         gt.Skills = [
#             "dash",
#             "slash",
#             "throw_net"
#         ];
#     """
#     code = """\
#         gt.Skills = [
#             "slash",
#             "special",
#             "throw_net"
#         ]
#     """
#     assert diff(base_code, code) == dedent("""\
#         gt.Skills = [
#             // "dash",
#             "slash",
#             // START NEW CODE
#             "special",
#             // END NEW CODE
#             "throw_net"
#         ]
#     """)

# def test_aot():
#     base_code = """\
#         gt.Skills = [
#             {
#                 name = "dash"
#             },
#             {
#                 name = "slash"
#             }
#         ];
#     """
#     code = """\
#         gt.Skills = [
#             {
#                 name = "dash"
#             },
#             {
#                 name = "special"
#             },
#             {
#                 name = "slash"
#             }
#         ]
#     """
#     assert diff(base_code, code) == dedent("""\
#         gt.Skills = [
#             gt.Skills[0]
#             {
#                 name = "special"
#             }
#             gt.Skills[1]
#         ]
#     """)

# def test_aot_complex():
#     base_code = """\
#         gt.Skills = [
#             {
#                 name = "dash",
#                 type = 12,
#                 num = 1
#             },
#             {
#                 name = "slash",
#                 type = 13,
#                 num = 2
#             }
#         ];
#     """
#     code = """\
#         gt.Skills = [
#             {
#                 name = "dash"
#                 type = 12,
#                 num = 1
#             },
#             {
#                 name = "slash"
#                 type = 13,
#                 num = 3
#             },
#         ]
#     """
#     assert diff(base_code, code) == dedent("""\
#         gt.Skills = [
#             gt.Skills[0]
#             {
#                 name = "slash"
#                 type = 13
#                 num = 3
#             }
#         ]
#     """)

# def test_aot_swap():
#     base_code = """\
#         gt.Skills = [
#             {
#                 name = "active"
#             },
#             // junk
#             {
#                 name = "dash"
#             },
#             {
#                 name = "slash"
#             },
#             "value",
#             {
#                 name = "deleted"
#             }
#         ];
#     """
#     code = """\
#         gt.Skills = [
#             {
#                 name = "slash"
#             },
#             // junk
#             {
#                 name = "dash"
#             },
#             {
#                 name = "active"
#             },
#             "value"
#         ]
#     """
#     # TODO: understand here that "value" and "value", are the same
#     assert diff(base_code, code) == dedent("""\
#         gt.Skills = [
#             gt.Skills[2]
#             // junk
#             gt.Skills[1]
#             // "value",
#             gt.Skills[0]
#             // START NEW CODE
#             "value"
#             // END NEW CODE
#         ]
#     """)


# def test_toaoa():
#     base_code = """\
#         gt.Trait <- {
#             None = 0,
#             Actions = [
#                 [],
#                 [
#                     "patrol_action",
#                     "raze_attached_location_action",
#                     "destroy_orc_camp_action"
#                 ],
#                 [
#                     "build_camp_action"
#                 ]
#             ]
#         }
#     """
#     code = """\
#         gt.Trait <- {
#             None = 0,
#             Actions = [
#                 [
#                     "patrol_action",
#                     "raze_attached_location_action",
#                     "new_action"
#                     "destroy_orc_camp_action"
#                 ],
#                 [
#                     "build_camp_action"
#                 ]
#             ]
#         }
#     """
#     assert diff(base_code, code) == dedent("""\
#         gt.Trait.Actions = [
#             // [],
#             [
#                 "patrol_action",
#                 "raze_attached_location_action",
#                 // START NEW CODE
#                 "new_action"
#                 // END NEW CODE
#                 "destroy_orc_camp_action"
#             ]
#             gt.Trait.Actions[2]
#         ]
#     """)

# def test_toaoa2():
#     # NOTE: the array with "extra-element" catches similar and same, but have junk case
#     base_code = """\
#         gt.Const.Perks.BeastClassTree.Tree <- [
#             [],
#             [
#                 gt.Const.Perks.PerkDefs.LegendNetRepair
#             ],
#             [
#                 gt.Const.Perks.PerkDefs.LegendNetCasting,
#                 "extra-element"
#             ],
#             [
#                 gt.Const.Perks.PerkDefs.LegendMasteryNets
#             ],
#             [
#                 gt.Const.Perks.PerkDefs.LegendEscapeArtist
#             ],
#             [],
#             []
#         ];
#     """
#     code = """\
#         gt.Const.Perks.BeastClassTree.Tree <- [
#             [
#                 gt.Const.Perks.PerkDefs.LegendNetRepair
#             ],
#             [
#             ],
#             [
#             ],
#             [
#                 // gt.Const.Perks.PerkDefs.LegendMasteryNets
#                 gt.Const.Perks.PerkDefs.LegendNetCasting,
#                 "extra-element"
#             ],
#             [
#             ],
#             [],
#             []
#         ]
#     """
#     assert diff(base_code, code) == dedent("""\
#         gt.Const.Perks.BeastClassTree.Tree = [
#             // [],
#             gt.Const.Perks.BeastClassTree.Tree[1],
#             [
#             ],
#             [
#             ],
#             [
#                 // START NEW CODE
#                 // gt.Const.Perks.PerkDefs.LegendMasteryNets
#                 // END NEW CODE
#                 gt.Const.Perks.PerkDefs.LegendNetCasting,
#                 "extra-element"
#             ],
#             [
#             ],
#             [],
#             []
#         ]
#     """)


# def test_diff_code():
#     base_code = """\
#         local gt = getroottable();
#         if (!("Const" in gt)) gt.Const <- {};

#         a = 1;
#         b = 2;
#         c = 3;
#         d = 4;

#         if (a > b) {
#             if (...) {
#                 d = c + 1;
#             }

#             print(a - b);
#         }
#     """
#     code = """\
#         a = 1;
#         b = 2;
#         c = 3;
#         c1 = 3.2;
#         c2 = 3.7;
#         d = 4;

#         if (a > b) {
#             print("EXPLAIN");
#             print(a - b);
#         }
#     """
#     assert diff(code, code) == ""
#     assert diff(base_code, code) == dedent("""\
#         // local gt = getroottable();
#         // if (!("Const" in gt)) gt.Const <- {};
#         //
#         a = 1;
#         b = 2;
#         c = 3;
#         // START NEW CODE
#         c1 = 3.2;
#         c2 = 3.7;
#         // END NEW CODE
#         d = 4;

#         if (a > b) {
#             // if (...) {
#             //     d = c + 1;
#             // }
#             //
#             // START NEW CODE
#             print("EXPLAIN");
#             // END NEW CODE
#             print(a - b);
#         }
#     """)


# # Helpers

# def roundtrip(code):
#     defs = parse(dedent(code))
#     # pprint(defs[""])
#     return unparse("path/to/location.nut", defs)

# def diff(base_code, code):
#     return _hookify("path/to/location.nut", base_code, code)

# def _hookify(filename, base_code, code):
#     defs = parse(dedent(code))
#     # pprint(defs[""])
#     base_defs = parse(dedent(base_code))
#     diff = calc_diff(base_defs, defs)
#     pprint(diff[""])
#     return unparse(filename, diff);
