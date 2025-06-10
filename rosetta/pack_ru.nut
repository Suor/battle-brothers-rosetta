// Commonly used in mods or forgotten in translation
local def = ::Rosetta;
local rosetta = {
    mod = {id = def.ID, version = def.Version}
    author = "hackflow"
    lang = "ru"
}
local pairs = [
    {
        mode = "pattern"
        en = "<actor:str_tag> has hit <victim:str_tag>'s shield for <damage:int> damage"
        ru = "<actor> нанёс щиту <victim> <damage> урона"
    }
    {
        mode = "pattern"
        en = "Wiederganger <name:str>"
        ru = "Восставший <name>"
    }
    {
        mode = "pattern"
        en = "<actor:str_tag> heals <target:str_tag> for <hp:int> HP."
        ru = "<actor> лечит <target> на <hp:int> ОЗ."
    }
    // FILE: perma_rework/hooks/weakened_heart_injury.nut
    {
        mode = "pattern"
        en = "<bonus:val_tag> Hitpoints"
        ru = "<bonus> к очкам здоровья"
    }
    // FILE: perma_rework/hooks/missing_nose_injury.nut
    {
        // text = "[color=" + this.Const.UI.Color.NegativeValue + "]-5%[/color] Max Fatigue"
        mode = "pattern"
        en = "<bonus:val_tag> Max Fatigue"
        ru = "<bonus> к выносливости"
    }
    // FILE: perma_rework/hooks/traumatized_injury.nut
    {
        mode = "pattern"
        en = "<bonus:val_tag> Resolve"
        ru = "<bonus> к решимости"
    }
    {
        mode = "pattern"
        en = "<bonus:val_tag> Initiative"
        ru = "<bonus> к инициативе"
    }
    {
        mode = "pattern"
        en = "<bonus:val_tag> Melee Skill"
        ru = "<bonus> к навыку ближнего боя"
    }
    {
        mode = "pattern"
        en = "<bonus:val_tag> Ranged Skill"
        ru = "<bonus> к навыку дальнего боя"
    }
    {
        mode = "pattern"
        en = "<bonus:val_tag> Melee Defense"
        ru = "<bonus> к защите в ближнем бою"
    }
    {
        mode = "pattern"
        en = "<bonus:val_tag> Ranged Defense"
        ru = "<bonus> к защите в дальнем бою"
    }
    {
        // text = "[color=" + this.Const.UI.Color.NegativeValue + "]-1[/color] Vision"
        mode = "pattern"
        en = "<bonus:val_tag> Vision"
        ru = "<bonus> к обзору"
    }
    {
        mode = "pattern"
        en = "<bonus:val_tag> Daily wage"
        ru = "<bonus> к плате в день"
    }
    {
        en = "Is always content with being in reserve"
        ru = "Не ухудшается настроение от пребывания в резерве"
    }
    {
        // text = "[color=" + this.Const.UI.Color.NegativeValue + "]-3[/color] Fatigue Recovery per turn"
        mode = "pattern"
        en = "<bonus:val_tag> Fatigue Recovery per turn"
        ru = "<bonus> к восстановлению выносливости за ход"
    }
    {
        // text = "[color=" + this.Const.UI.Color.NegativeValue + "]3[/color] Additional fatigue for each tile travelled"
        mode = "pattern"
        en = "Builds up <bonus:val_tag> more Fatigue for each tile travelled"
        ru = "Получает на <bonus> единицы усталости больше за каждую пройденную клетку"
    }
    {
        mode = "pattern"
        en = "Reduces the Resolve of any opponent engaged in melee by <val:val_tag>"
        ru = "Уменьшает решимость любого противника в ближнем бою на <val>"
    }
]
def.add(rosetta, pairs);
