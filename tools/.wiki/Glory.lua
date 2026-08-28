local all_data = {
["Devoted Sculptor"] = {
	Type = "Normal",
	BaseHP = "162",
	AscHP = "172",
	Image = "StS2_Devoted Sculptor.png",
	Debut = "{{2|Glory}}",
	Encounters = {
		{
			location = "{{2|Glory}} Easy Encounter",
			enemies = "[[File:Devoted Sculptor Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Devoted Sculptor]]"
		}
	},
	Intents = {
		{	Name = "Forbidden Incantation",
			IntentIcons = { "Buff" },
			Text = "Gains 9 {{BD2|Ritual}}."
		},
		{	Name = "Savage",
			IntentIcons = { "Attack2" },
			Text = "Deals 12 ({{Asc2|9|15}}) damage.",
			AscText = {
				"Deals 12 damage.",
				"Deals {{Asc2|9|15}} damage."
			}
		},
	}
},

["Scroll of Biting"] = {
	Type = "Normal",
	BaseHP = "31-38",
	AscHP = "32-39",
	Image = "StS2_Scroll of Biting.png",
	Debut = "{{2|Glory}}",
	StartsWith = "{{BD2|Paper Cuts}} 2",
	Encounters = {
		{
			location = "{{2|Glory}} Easy Encounter",
			enemies = "[[File:Scroll of Biting Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Scroll of Biting]][[File:Scroll of Biting Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Scroll of Biting]][[File:Scroll of Biting Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Scroll of Biting]]"
		},
		{
			location = "{{2|Glory}} Normal Encounter",
			enemies = "[[File:Scroll of Biting Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Scroll of Biting]][[File:Scroll of Biting Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Scroll of Biting]][[File:Scroll of Biting Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Scroll of Biting]][[File:Scroll of Biting Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Scroll of Biting]]"
		}
	},
	Intents = {
		{	Name = "Chomp",
			IntentIcons = { "Attack3" },
			Text = "Deals 14 ({{Asc2|9|16}}) damage.",
			AscText = {
				"Deals 14 damage.",
				"Deals {{Asc2|9|16}} damage."
			}
		},
		{	Name = "More Teeth",
			IntentIcons = { "Buff" },
			Text = "Gains 2 {{BD2|Strength}}."
		},
		{	Name = "Chew",
			IntentIcons = { "Attack2" },
			Text = "Deals 5 ({{Asc2|9|6}}) damage 2 times.",
			AscText = {
				"Deals 5 damage 2 times.",
				"Deals {{Asc2|9|6}} damage 2 times."
			}
		},
	}
},

["Axebot"] = {
	Type = "Normal",
	BaseHP = "70-78",
	AscHP = "78-86",
	Image = "StS2_Axebot.png",
	Debut = "{{2|Glory}}",
	StartsWith = "{{BD2|Stock}} 2",
	Encounters = {
		{
			location = "{{2|Glory}} Normal Encounter",
			enemies = "[[File:Axebot Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Axebot]]"
		}
	},
	Intents = {
		{	Name = "Boot Up",
			IntentIcons = { "Defend", "Buff" },
			Text = "Gains 10({{Asc2|8|15}}) {{KW2|Block}} and 3/6({{Asc2|9|4/8}}) {{BD2|Strength}}.",
			AscText = {
				"Gains 10 {{KW2|Block}} and 3 {{BD2|Strength}}.",
				"Gains {{Asc2|8|15}} {{KW2|Block}} and {{Asc2|9|4}} {{BD2|Strength}}.",
				"Gains 10 {{KW2|Block}} and 6 {{BD2|Strength}}.",
				"Gains {{Asc2|8|15}} {{KW2|Block}} and {{Asc2|9|8}} {{BD2|Strength}}."
			}
		},
		{	Name = "The One-Two",
			IntentIcons = { "Attack2" },
			Text = "Deals 9 ({{Asc2|9|10}}) damage 2 times.",
			AscText = {
				"Deals 9 damage 2 times.",
				"Deals {{Asc2|9|10}} damage 2 times."
			}
		},
		{	Name = "Hammer Uppercut",
			IntentIcons = { "Attack2", "Debuff" },
			Text = "Deals 12 ({{Asc2|9|14}}) damage. Applies 2 {{BD2|Weak}} and 2 {{BD2|Frail}}.",
			AscText = {
				"Deals 12 damage. Applies 2 {{BD2|Weak}} and 2 {{BD2|Frail}}.",
				"Deals {{Asc2|9|14}} damage. Applies 2 {{BD2|Weak}} and 2 {{BD2|Frail}}."
			}
		},
	}
},

["Fabricator"] = {
	Type = "Normal",
	BaseHP = "150",
	AscHP = "155",
	Image = "StS2_Fabricator.png",
	Debut = "{{2|Glory}}",
	Encounters = {
		{
			location = "{{2|Glory}} Normal Encounter",
			enemies = "[[File:Fabricator Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Fabricator]][[File:Summon Divider Icon.png]][[File:Fabricator Bots Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Fabricator]]"
		}
	},
	Intents = {
		{	Name = "Fabricate",
			IntentIcons = { "Summon" },
			Text = "Summons 1 defensive bot ([[Guardbot]] or [[Noisebot]]) and 1 aggressive bot ([[Zapbot]] or [[Stabbot]])."
		},
		{	Name = "Fabricating Strike",
			IntentIcons = { "Attack3", "Summon" },
			Text = "Deals 18 ({{Asc2|9|21}}) damage. Summons 1 aggressive bot ([[Zapbot]] or [[Stabbot]]).",
			AscText = {
				"Deals 18 damage. Summons 1 aggressive bot ([[Zapbot]] or [[Stabbot]]).",
				"Deals {{Asc2|9|21}} damage. Summons 1 aggressive bot ([[Zapbot]] or [[Stabbot]])."
			}
		},
		{	Name = "Disintegrate",
			IntentIcons = { "Attack3" },
			Text = "Deals 11 ({{Asc2|9|13}}) damage.",
			AscText = {
				"Deals 11 damage.",
				"Deals {{Asc2|9|13}} damage."
			}
		},
	}
},
["Zapbot"] = {
	Type = "Minion",
	BaseHP = "18-23",
	AscHP = "19-24",
	Image = "StS2_Zapbot.png",
	Link = "Fabricator#Zapbot",
	Debut = "{{2|Glory}}",
	StartsWith = "{{BD2|High Voltage}} 2",
	Encounters = {
		{
			location = "{{2|Glory}} Normal Encounter",
			enemies = "[[File:Fabricator Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Fabricator]][[File:Summon Divider Icon.png]][[File:Fabricator Bots Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Fabricator]]"
		}
	},
	Intents = {
		{	Name = "Zap",
			IntentIcons = { "Attack3" },
			Text = "Deals 14 ({{Asc2|9|15}}) damage.",
			AscText = {
				"Deals 14 damage.",
				"Deals {{Asc2|9|15}} damage."
			}
		},
	}
},
["Stabbot"] = {
	Type = "Minion",
	BaseHP = "18-23",
	AscHP = "19-24",
	Image = "StS2_Stabbot.png",
	Link = "Fabricator#Stabbot",
	Debut = "{{2|Glory}}",
	Encounters = {
		{
			location = "{{2|Glory}} Normal Encounter",
			enemies = "[[File:Fabricator Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Fabricator]][[File:Summon Divider Icon.png]][[File:Fabricator Bots Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Fabricator]]"
		}
	},
	Intents = {
		{	Name = "Stab",
			IntentIcons = { "Attack2", "Debuff" },
			Text = "Deals 11 ({{Asc2|9|12}}) damage. Applies 1 {{BD2|Frail}}.",
			AscText = {
				"Deals 11 damage. Applies 1 {{BD2|Frail}}.",
				"Deals {{Asc2|9|12}} damage. Applies 1 {{BD2|Frail}}."
			}
		},
	}
},
["Guardbot"] = {
	Type = "Minion",
	BaseHP = "16-20",
	AscHP = "17-21",
	Image = "StS2_Guardbot.png",
	Link = "Fabricator#Guardbot",
	Debut = "{{2|Glory}}",
	Encounters = {
		{
			location = "{{2|Glory}} Normal Encounter",
			enemies = "[[File:Fabricator Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Fabricator]][[File:Summon Divider Icon.png]][[File:Fabricator Bots Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Fabricator]]"
		}
	},
	Intents = {
		{	Name = "Guard",
			IntentIcons = { "Defend" },
			Text = "Gives the Fabricator 15 {{KW2|Block}}."
		},
	}
},
["Noisebot"] = {
	Type = "Minion",
	BaseHP = "18-23",
	AscHP = "19-24",
	Image = "StS2_Noisebot.png",
	Link = "Fabricator#Noisebot",
	Debut = "{{2|Glory}}",
	Encounters = {
		{
			location = "{{2|Glory}} Normal Encounter",
			enemies = "[[File:Fabricator Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Fabricator]][[File:Summon Divider Icon.png]][[File:Fabricator Bots Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Fabricator]]"
		}
	},
	Intents = {
		{	Name = "Noise",
			IntentIcons = { "StatusCard" },
			Text = "Shuffles 2 {{C2|Dazed}} into the player's draw and discard piles."
		},
	}
},

["Frog Knight"] = {
	Type = "Normal",
	BaseHP = "191",
	AscHP = "199",
	Image = "StS2_Frog Knight.png",
	Debut = "{{2|Glory}}",
	StartsWith = "{{BD2|Plating}} 15 ({{Asc2|8|19}})",
	Encounters = {
		{
			location = "{{2|Glory}} Normal Encounter",
			enemies = "[[File:Frog Knight Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Frog Knight]]"
		}
	},
	Intents = {
		{	Name = "Tongue Lash",
			IntentIcons = { "Attack2", "Debuff" },
			Text = "Deals 13 ({{Asc2|9|14}}) damage. Applies 2 {{BD2|Frail}}.",
			AscText = {
				"Deals 13 damage. Applies 2 {{BD2|Frail}}.",
				"Deals {{Asc2|9|14}} damage. Applies 2 {{BD2|Frail}}."
			}
		},
		{	Name = "Strike Down Evil",
			IntentIcons = { "Attack3" },
			Text = "Deals 21 ({{Asc2|9|23}}) damage.",
			AscText = {
				"Deals 21 damage.",
				"Deals {{Asc2|9|23}} damage."
			}
		},
		{	Name = "For the Queen",
			IntentIcons = { "Buff" },
			Text = "Gains 5 {{BD2|Strength}}."
		},
		{	Name = "Beetle Charge",
			IntentIcons = { "Attack4" },
			Text = "Deals 35 ({{Asc2|9|40}}) damage.",
			AscText = {
				"Deals 35 damage.",
				"Deals {{Asc2|9|40}} damage."
			}
		},
	}
},

["Globe Head"] = {
	Type = "Normal",
	BaseHP = "148",
	AscHP = "158",
	Image = "StS2_Globe Head.png",
	Debut = "{{2|Glory}}",
	StartsWith = "{{BD2|Galvanic}} 6",
	Encounters = {
		{
			location = "{{2|Glory}} Normal Encounter",
			enemies = "[[File:Globe Head Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Globe Head]]"
		}
	},
	Intents = {
		{	Name = "Shocking Slap",
			IntentIcons = { "Attack2", "Debuff" },
			Text = "Deals 13 ({{Asc2|9|14}}) damage. Applies 2 {{BD2|Frail}}.",
			AscText = {
				"Deals 13 damage. Applies 2 {{BD2|Frail}}.",
				"Deals {{Asc2|9|14}} damage. Applies 2 {{BD2|Frail}}."
			}
		},
		{	Name = "Thunder Strike",
			IntentIcons = { "Attack3" },
			Text = "Deals 6 ({{Asc2|9|7}}) damage 3 times.",
			AscText = {
				"Deals 6 damage 3 times.",
				"Deals {{Asc2|9|7}} damage 3 times."
			}
		},
		{	Name = "Galvanic Burst",
			IntentIcons = { "Attack3", "Buff" },
			Text = "Deals 16 ({{Asc2|9|17}}) damage. Gains 2 {{BD2|Strength}}.",
			AscText = {
				"Deals 16 damage. Gains 2 {{BD2|Strength}}.",
				"Deals {{Asc2|9|17}} damage. Gains 2 {{BD2|Strength}}."
			}
		},
	}
},

["Owl Magistrate"] = {
	Type = "Normal",
	BaseHP = "234",
	AscHP = "243",
	Image = "StS2_Owl Magistrate.png",
	Debut = "{{2|Glory}}",
	Encounters = {
		{
			location = "{{2|Glory}} Normal Encounter",
			enemies = "[[File:Owl Magistrate Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Owl Magistrate]]"
		}
	},
	Intents = {
		{	Name = "Magistrate Scrutiny",
			IntentIcons = { "Attack3" },
			Text = "Deals 16 ({{Asc2|9|17}}) damage.",
			AscText = {
				"Deals 16 damage.",
				"Deals {{Asc2|9|17}} damage."
			}
		},
		{	Name = "Peck Assault",
			IntentIcons = { "Attack3" },
			Text = "Deals 4 damage x6.",
		},
		{	Name = "Judicial Flight",
			IntentIcons = { "Buff" },
			Text = "Gains {{BD2|Soar}}.",
		},
		{	Name = "Verdict",
			IntentIcons = { "Attack4", "Debuff" },
			Text = "Deals 33 ({{Asc2|9|36}}) damage. Applies 4 {{BD2|Vulnerable}}. Removes {{BD2|Soar}}.",
			AscText = {
				"Deals 33 damage. Applies 4 {{BD2|Vulnerable}}. Removes {{BD2|Soar}}.",
				"Deals {{Asc2|9|36}} damage. Applies 4 {{BD2|Vulnerable}}. Removes {{BD2|Soar}}."
			}
		},
	}
},

["Slimed Berserker"] = {
	Type = "Normal",
	BaseHP = "266",
	AscHP = "276",
	Image = "StS2_Slimed Berserker.png",
	Debut = "{{2|Glory}}",
	Encounters = {
		{
			location = "{{2|Glory}} Normal Encounter",
			enemies = "[[File:Slimed Berserker Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Slimed Berserker]]"
		}
	},
	Intents = {
		{	Name = "Vomit Ichor",
			IntentIcons = { "StatusCard" },
			Text = "Shuffles 10 {{C2|Slimed}} into the discard pile.",
		},
		{	Name = "Furious Pummeling",
			IntentIcons = { "Attack3" },
			Text = "Deals 4 ({{Asc2|9|5}}) damage x4.",
			AscText = {
				"Deals 4 damage x4.",
				"Deals {{Asc2|9|5}} damage x4."
			}
		},
		{	Name = "Leeching Hug",
			IntentIcons = { "Debuff", "Buff" },
			Text = "Applies 3 {{BD2|Weak}}. Gains 3 {{BD2|Strength}}.",
		},
		{	Name = "Smother",
			IntentIcons = { "Attack4" },
			Text = "Deals 30 ({{Asc2|9|33}}) damage.",
			AscText = {
				"Deals 30 damage.",
				"Deals {{Asc2|9|33}} damage."
			}
		},
	}
},

["Living Shield"] = {
	Type = "Normal",
	BaseHP = "55",
	AscHP = "65",
	Image = "StS2_Living Shield.png",
	Link = "Turret Operator#Living Shield",
	Debut = "{{2|Glory}}",
	StartsWith = "{{BD2|Rampart}} 25",
	Encounters = {
		{
			location = "{{2|Glory}} Easy Encounter",
			enemies = "[[File:Living Shield Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Living Shield]][[File:Turret Operator Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Turret Operator]]"
		}
	},
	Intents = {
		{	Name = "Shield Slam",
			IntentIcons = { "Attack1" },
			Text = "Deals 6 damage.",
		},
		{	Name = "Smash",
			IntentIcons = { "Attack3", "Buff" },
			Text = "Deals 16 ({{Asc2|9|18}}) damage. Gains 3 {{BD2|Strength}}.",
			AscText = {
				"Deals 16 damage. Gains 3 {{BD2|Strength}}.",
				"Deals {{Asc2|9|18}} damage. Gains 3 {{BD2|Strength}}."
			}
		},
	}
},
["Turret Operator"] = {
	Type = "Normal",
	BaseHP = "41",
	AscHP = "51",
	Image = "StS2_Turret Operator.png",
	Debut = "{{2|Glory}}",
	Encounters = {
		{
			location = "{{2|Glory}} Easy Encounter",
			enemies = "[[File:Living Shield Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Living Shield]][[File:Turret Operator Icon.png|class=monster-icon|48px|link=Slay the Spire 2:Turret Operator]]"
		}
	},
	Intents = {
		{	Name = "Unload!",
			IntentIcons = { "Attack3" },
			Text = "Deals 3 ({{Asc2|9|4}}) damage x5.",
			AscText = {
				"Deals 3 damage x5.",
				"Deals {{Asc2|9|4}} damage x5."
			}
		},
		{	Name = "Loading",
			IntentIcons = { "Buff" },
			Text = "Gains 1 {{BD2|Strength}}.",
		},
	}
},

["The Lost"] = {
	Type = "Normal",
	BaseHP = "93",
	AscHP = "99",
	Image = "StS2_The Lost.png",
	Link = "The Lost and Forgotten#The Lost",
	Debut = "{{2|Glory}}",
	StartsWith = "{{BD2|Possess Strength}}",
	Encounters = {
		{
			location = "{{2|Glory}} Normal Encounter",
			enemies = "[[File:The Lost Icon.png|class=monster-icon|48px|link=Slay the Spire 2:The Lost]][[File:The Forgotten Icon.png|class=monster-icon|48px|link=Slay the Spire 2:The Forgotten]]"
		}
	},
	Intents = {
		{	Name = "Debilitating Smog",
			IntentIcons = { "Debuff", "Buff" },
			Text = "Removes 2 {{BD2|Strength}} from the player and gains 2 {{BD2|Strength}}.",
		},
		{	Name = "Eye Lasers",
			IntentIcons = { "Attack2" },
			Text = "Deals 4 ({{Asc2|9|5}}) damage x2.",
			AscText = {
				"Deals 4 damage x2.",
				"Deals {{Asc2|9|5}} damage x2."
			}
		},
	}
},
["The Forgotten"] = {
	Type = "Normal",
	BaseHP = "106",
	AscHP = "111",
	Image = "StS2_The Forgotten.png",
	Link = "The Lost and Forgotten#The Forgotten",
	Debut = "{{2|Glory}}",
	StartsWith = "{{BD2|Possess Speed}}",
	Encounters = {
		{
			location = "{{2|Glory}} Normal Encounter",
			enemies = "[[File:The Lost Icon.png|class=monster-icon|48px|link=Slay the Spire 2:The Lost]][[File:The Forgotten Icon.png|class=monster-icon|48px|link=Slay the Spire 2:The Forgotten]]"
		}
	},
	Intents = {
		{	Name = "Miasma",
			IntentIcons = { "Debuff", "Defend", "Buff" },
			Text = "Removes 2 {{BD2|Dexterity}} from the player. Gains 8 {{KW2|Block}} and 2 {{BD2|Dexterity}}.",
		},
		{	Name = "Dread",
			IntentIcons = { "Attack3" },
			Text = "Deals 13 ({{Asc2|9|15}}) damage plus the amount of {{BD2|Dexterity}} the Forgotten has.",
			AscText = {
				"Deals 13 damage plus the amount of {{BD2|Dexterity}} the Forgotten has.",
				"Deals {{Asc2|9|15}} damage plus the amount of {{BD2|Dexterity}} the Forgotten has."
			}
		},
	}
},
}

local formatted = {}
for name, enemy in pairs(all_data) do
	enemy.EditLink = "Module:Enemies/StS2_data/Glory"
	formatted[name] = enemy
end

return formatted