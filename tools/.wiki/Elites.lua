local all_data = {
	-- Act 1A Overgrowth
		["Bygone Effigy"] = {
		Type = "Elite",
		BaseHP = "127",
		AscHP = "132",
		Image = "StS2_Bygone Effigy.png",
		Debut = "{{2|Overgrowth}}",
		StartsWith = "{{BD2|Slow}}",
		Intents = {
			{	Name = "Sleep",
				IntentIcons = { "Sleep" },
				Text = "Does nothing. Asleep."
			},
			{	Name = "Wake",
				IntentIcons = { "Buff" },
				Text = "Gains 10 {{BD2|Strength}}."
			},
			{	Name = "Slashes",
				IntentIcons = { "Attack3" },
				Text = "Deals 13 ({{Asc2|9|15}}) damage.",
				AscText = {
					"Deals 13 damage.",
					"Deals {{Asc2|9|15}} damage."
				}
			},
		}
	},
	["Byrdonis"] = {
		Type = "Elite",
		BaseHP = "81-84",
		AscHP = "90",
		Image = "StS2_Byrdonis.png",
		Debut = "{{2|Overgrowth}}",
		StartsWith = "{{BD2|Territorial}} 1",
		Intents = {
			{	Name = "Swoop", -- NEEDS REVIEW: move name "Swoop" not in localization, using codex name. Localization has "Bite" instead.
				IntentIcons = { "Attack3" },
				Text = "Deals 17 ({{Asc2|9|19}}) damage.",
				AscText = {
					"Deals 17 damage.",
					"Deals {{Asc2|9|19}} damage."
				}
			},
			{	Name = "Peck",
				IntentIcons = { "Attack2" },
				Text = "Deals 3x3 ({{Asc2|9|4x3}}) damage.",
				AscText = {
					"Deals 3x3 damage.",
					"Deals {{Asc2|9|4x3}} damage."
				}
			},
		}
	},
	["Phrog Parasite"] = {
		Type = "Elite",
		BaseHP = "61-64",
		AscHP = "66-68",
		Image = "StS2_Phrog Parasite.png",
		Debut = "{{2|Overgrowth}}",
		StartsWith = "{{BD2|Infested}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Overgrowth</span><br>Appears as a solo elite encounter.<br>Summons {{M|Wriggler}} ×4 upon death (via {{BD2|Infested}}).",
		Intents = {
			{	Name = "Infect",
				IntentIcons = { "StatusCard" },
				Text = "Shuffles 3 {{C2|Infection}} into your discard pile."
			},
			{	Name = "Lash",
				IntentIcons = { "Attack3" },
				Text = "Deals 4 ({{Asc2|9|5}}) damage ×4.",
				AscText = {
					"Deals 4 damage ×4.",
					"Deals {{Asc2|9|5}} damage ×4."
				}
			},
		}
	},
    -- Act 1B Underdocks
	["Phantasmal Gardener"] = {
		Type = "Elite",
		BaseHP = "26-31",
		AscHP = "27-32",
		Image = "StS2_Phantasmal Gardener.png",
		Debut = "{{2|Underdocks}}",
		StartsWith = "{{BD2|Skittish}} 6 ({{Asc2|8|7}})",
		InPartyWith = "<span class='enemy-infobox-party-header'>Underdocks</span><br>* {{M|Phantasmal Gardener}} ×4",
		Intents = {
			{	Name = "Bite",
				IntentIcons = { "Attack2" },
				Text = "Deals 5 damage.",
			},
			{	Name = "Lash",
				IntentIcons = { "Attack2" },
				Text = "Deals 7 damage.",
			},
			{	Name = "Flail",
				IntentIcons = { "Attack1" },
				Text = "Deals 1 damage ×3.",
			},
			{	Name = "Enlarge",
				IntentIcons = { "Buff" },
				Text = "Gains 2 ({{Asc2|9|3}}) {{BD2|Strength}}.",
				AscText = {
					"Gains 2 {{BD2|Strength}}.",
					"Gains {{Asc2|9|3}} {{BD2|Strength}}."
				}
			},
		}
	},
	["Skulking Colony"] = {
		Type = "Elite",
		BaseHP = "75",
		AscHP = "80",
		Image = "StS2_Skulking Colony.png",
		Debut = "{{2|Underdocks}}",
		StartsWith = "{{BD2|Hardened Shell}} 20",
		Intents = {
			{	Name = "Zoom",
				IntentIcons = { "Attack3"},
				Text = "Deals 14 ({{Asc2|9|16}}) damage.",
				AscText = {
					"Deals 14 damage.",
					"Deals {{Asc2|9|16}} damage."
				}
			},
			{	Name = "Inertia",
				IntentIcons = { "Attack2", "Buff" },
				Text = "Deals 9 ({{Asc2|9|11}}) damage and gains 2 ({{Asc2|9|3}}) {{BD2|Strength}}.",
				AscText = {
					"Deals 9 damage and gains 2 {{BD2|Strength}}.",
					"Deals {{Asc2|9|11}} damage and gains {{Asc2|9|4}} {{BD2|Strength}}."
				}
			},
			{	Name = "Piercing Stabs",
				IntentIcons = { "Attack3" },
				Text = "Deals 7x2 ({{Asc2|9|8x2}}) damage.",
				AscText = {
					"Deals 7x2 damage.",
					"Deals {{Asc2|9|8x2}} damage."
				}
			},
		}
	},
	["Terror Eel"] = {
		Type = "Elite",
		BaseHP = "140",
		AscHP = "150",
		Image = "StS2_Terror Eel.png",
		Debut = "{{2|Underdocks}}",
		StartsWith = "{{BD2|Shriek}} 70 ({{Asc2|8|75}})",
		Intents = {
			{	Name = "Crash",
				IntentIcons = { "Attack3" },
				Text = "Deals 16 ({{Asc2|9|18}}) damage.",
				AscText = {
					"Deals 16 damage.",
					"Deals {{Asc2|9|18}} damage."
				}
			},
			{	Name = "Thrash",
				IntentIcons = { "Attack2", "Buff" },
				Text = "Deals 3x3 ({{Asc2|9|4x3}}) damage. Gains 6 {{BD2|Vigor}}.",
				AscText = {
					"Deals 3x3 damage. Gains 6 {{BD2|Vigor}}.",
					"Deals {{Asc2|9|4x3}} damage. Gains 6 {{BD2|Vigor}}."
				}
			},
			{	Name = "Stun", -- NEEDS REVIEW: move name "Stun" not in localization, using codex name
				IntentIcons = { "Stun" },
				Text = "Stunned. Does nothing."
			},
			{	Name = "Terror", -- NEEDS REVIEW: move name "Terror" not in localization, using codex name
				IntentIcons = { "Debuff" },
				Text = "Applies 99 {{BD2|Vulnerable}}."
			},
		}
	},
	-- Hive Elites
	["Decimillipede"] = {
		Type = "Elite",
		BaseHP = "40-46",
		AscHP = "46-52",
		Image = "StS2_Decimillipede.png",
		Debut = "{{2|Hive}}",
		StartsWith = "{{BD2|Reattach}} 25",
		Intents = {
			{	Name = "Bulk",
				IntentIcons = { "Attack2", "Buff" },
				Text = "Deals 6 ({{Asc2|9|7}}) damage. Gains 2 {{BD2|Strength}}.",
				AscText = {
					"Deals 6 damage. Gains 2 {{BD2|Strength}}.",
					"Deals {{Asc2|9|7}} damage. Gains 2 {{BD2|Strength}}."
				}
			},
			{	Name = "Writhe",
				IntentIcons = { "Attack2" },
				Text = "Deals 5x2 ({{Asc2|9|6x2}}) damage.",
				AscText = {
					"Deals 5x2 damage.",
					"Deals {{Asc2|9|6x2}} damage."
				}
			},
			{	Name = "Outgas",
				IntentIcons = { "Attack2", "Debuff" },
				Text = "Deals 8 ({{Asc2|9|9}}) damage. Applies 1 {{BD2|Weak}}.",
				AscText = {
					"Deals 8 damage. Applies 1 {{BD2|Weak}}.",
					"Deals {{Asc2|9|9}} damage. Applies 1 {{BD2|Weak}}."
				}
			},
			{	Name = "Reattach",
				IntentIcons = { "Heal" },
				Text = "Revives with 25 HP (if other segments are alive)."
			},
		}
	},
	["Entomancer"] = {
		Type = "Elite",
		BaseHP = "145",
		AscHP = "155",
		Image = "StS2_Entomancer.png",
		Debut = "{{2|Hive}}",
		StartsWith = "{{BD2|Personal Hive}} 1",
		Intents = {
			{	Name = "Beeeees!",
				IntentIcons = { "Attack4" },
				Text = "Deals 3 damage ×7 ({{Asc2|9|×8}}).",
				AscText = {
					"Deals 3 damage ×7.",
					"Deals 3 damage {{Asc2|9|×8}}."
				}
			},
			{	Name = "Spear!",
				IntentIcons = { "Attack3" },
				Text = "Deals 18 ({{Asc2|9|20}}) damage.",
				AscText = {
					"Deals 18 damage.",
					"Deals {{Asc2|9|20}} damage."
				}
			},
			{	Name = "Pheromone Spit",
				IntentIcons = { "Buff" },
				Text = "Gains 1 {{BD2|Personal Hive}} and 1 {{BD2|Strength}}. If {{BD2|Personal Hive}} is already at 3, gains 2 {{BD2|Strength}} instead."
			},
		}
	},
	["Infested Prism"] = {
		Type = "Elite",
		BaseHP = "161",
		AscHP = "171",
		Image = "StS2_Infested Prism.png",
		Debut = "{{2|Hive}}",
		StartsWith = "{{BD2|Vital Spark}} 2({{Asc2|9|3}})",
		Intents = {
			{	Name = "Jab",
				IntentIcons = { "Attack4" },
				Text = "Deals 15 ({{Asc2|9|17}}) damage.",
				AscText = {
					"Deals 15 damage.",
					"Deals {{Asc2|9|17}} damage."
				}
			},
			{	Name = "Radiate",
				IntentIcons = { "Attack3", "Defend" },
				Text = "Deals 11 ({{Asc2|9|13}}) damage. Gains 16 ({{Asc2|9|18}}) {{KW2|Block}}.",
				AscText = {
					"Deals 11 damage. Gains 16 {{KW2|Block}}.",
					"Deals {{Asc2|9|13}} damage. Gains {{Asc2|9|18}} {{KW2|Block}}."
				}
			},
			{	Name = "Whirlwind",
				IntentIcons = { "Attack4" },
				Text = "Deals 5 ({{Asc2|9|6}}) damage ×3.",
				AscText = {
					"Deals 5 damage ×3.",
					"Deals {{Asc2|9|6}} damage ×3."
				}
			},
			{	Name = "Pulsate",
				IntentIcons = { "Attack3", "Buff", "Defend" },
				Text = "Deal 8({{Asc2|9|10}}) damage. Gains 20 ({{Asc2|8|22}}) {{KW2|Block}} and {{BD2|Vital Spark}} 2({{Asc2|9|3}}).",
				AscText = {
					"Deal 8 damage. Gains 20 {{KW2|Block}} and {{BD2|Vital Spark}} 2.",
					"Deal {{Asc2|9|10}} damage. Gains {{Asc2|8|22}} {{KW2|Block}} and {{BD2|Vital Spark}} {{Asc2|9|3}}."
				}
			},
		}
	},
	-- Glory Elites
	["Knight Gang"] = {
		Type = "Elite",
		Link = "Knight_Gang",
		Debut = "{{2|Glory}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Glory</span><br>* {{M|Flail Knight}} + {{M|Spectral Knight}} + {{M|Magi Knight}}",
	},
	["Flail Knight"] = {
		Type = "Elite",
		BaseHP = "101",
		AscHP = "108",
		Image = "StS2_Mysterious Knight.png",
		Link = "Knight_Gang#Flail Knight",
		Debut = "{{2|Glory}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Glory</span><br>* {{M|Spectral Knight}} + {{M|Magi Knight}}",
		Intents = {
			{	Name = "Breaker",
				IntentIcons = { "Buff" },
				Text = "Gains 3 {{BD2|Strength}}.",
			},
			{	Name = "Flail",
				IntentIcons = { "Attack3" },
				Text = "Deals 9 ({{Asc2|9|10}}) damage ×2.",
				AscText = {
					"Deals 9 damage ×2.",
					"Deals {{Asc2|9|10}} damage ×2."
				}
			},
			{	Name = "Ram",
				IntentIcons = { "Attack3" },
				Text = "Deals 15 ({{Asc2|9|17}}) damage.",
				AscText = {
					"Deals 15 damage.",
					"Deals {{Asc2|9|17}} damage."
				}
			},
		}
	},
	["Spectral Knight"] = {
		Type = "Elite",
		BaseHP = "93",
		AscHP = "97",
		Image = "StS2_Spectral Knight.png",
		Link = "Knight_Gang#Spectral Knight",
		Debut = "{{2|Glory}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Glory</span><br>* {{M|Flail Knight}} + {{M|Magi Knight}}",
		Intents = {
			{	Name = "Hex",
				IntentIcons = { "Debuff" },
				Text = "Applies {{BD2|Hex}}.",
			},
			{	Name = "Soul Slash",
				IntentIcons = { "Attack3" },
				Text = "Deals 15 ({{Asc2|9|17}}) damage.",
				AscText = {
					"Deals 15 damage.",
					"Deals {{Asc2|9|17}} damage."
				}
			},
			{	Name = "Soul Flame",
				IntentIcons = { "Attack2" },
				Text = "Deals 3 ({{Asc2|9|4}}) damage ×3.",
				AscText = {
					"Deals 3 damage ×3.",
					"Deals {{Asc2|9|4}} damage ×3."
				}
			},
		}
	},
	["Magi Knight"] = {
		Type = "Elite",
		BaseHP = "82",
		AscHP = "89",
		Image = "StS2_Magi Knight.png",
		Link = "Knight_Gang#Magi Knight",
		Debut = "{{2|Glory}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Glory</span><br>* {{M|Flail Knight}} + {{M|Spectral Knight}}",
		Intents = {
			{	Name = "Power Shield",
				IntentIcons = { "Attack1", "Defend" },
				Text = "Deals 6 ({{Asc2|9|7}}) damage. Gains 5 ({{Asc2|8|9}}) {{KW2|Block}}.",
				AscText = {
					"Deals 6 damage. Gains 5 {{KW2|Block}}.",
					"Deals {{Asc2|9|7}} damage. Gains {{Asc2|8|9}} {{KW2|Block}}."
				}
			},
			{	Name = "Dampen",
				IntentIcons = { "Debuff" },
				Text = "Applies {{BD2|Dampen}}. While Magi Knight is alive, all your cards are Downgraded.",
			},
			{	Name = "Ram",
				IntentIcons = { "Attack2" },
				Text = "Deals 10 ({{Asc2|9|11}}) damage.",
				AscText = {
					"Deals 10 damage.",
					"Deals {{Asc2|9|11}} damage."
				}
			},
			{	Name = "Prep",
				IntentIcons = { "Defend" },
				Text = "Gains 5 ({{Asc2|8|9}}) {{KW2|Block}}.",
				AscText = {
					"Gains 5 {{KW2|Block}}.",
					"Gains {{Asc2|8|9}} {{KW2|Block}}."
				}
			},
			{	Name = "Magic Bomb",
				IntentIcons = { "Attack4" },
				Text = "Deals 35 ({{Asc2|9|40}}) damage.",
				AscText = {
					"Deals 35 damage.",
					"Deals {{Asc2|9|40}} damage."
				}
			},
		}
	},
	["Mecha Knight"] = {
		Type = "Elite",
		BaseHP = "300",
		AscHP = "320",
		Image = "StS2_Mecha Knight.png",
		Debut = "{{2|Glory}}",
		StartsWith = "{{BD2|Artifact}} 3",
		Intents = {
			{	Name = "Charge",
				IntentIcons = { "Attack4" },
				Text = "Deals 25 ({{Asc2|9|30}}) damage.",
				AscText = {
					"Deals 25 damage.",
					"Deals {{Asc2|9|30}} damage."
				}
			},
			{	Name = "Flamethrower",
				IntentIcons = { "StatusCard" },
				Text = "Shuffles 4 {{C2|Burn}} into your hand.",
			},
			{	Name = "Windup",
				IntentIcons = { "Defend", "Buff" },
				Text = "Gains 15 {{KW2|Block}} and 5 {{BD2|Strength}}.",
			},
			{	Name = "Heavy Cleave",
				IntentIcons = { "Attack4" },
				Text = "Deals 35 ({{Asc2|9|40}}) damage.",
				AscText = {
					"Deals 35 damage.",
					"Deals {{Asc2|9|40}} damage."
				}
			},
		}
	},
	["Soul Nexus"] = {
		Type = "Elite",
		BaseHP = "234",
		AscHP = "254",
		Image = "StS2_Soul Nexus.png",
		Debut = "{{2|Glory}}",
		Intents = {
			{	Name = "Soul Burn",
				IntentIcons = { "Attack4" },
				Text = "Deals 29 ({{Asc2|9|31}}) damage.",
				AscText = {
					"Deals 29 damage.",
					"Deals {{Asc2|9|31}} damage."
				}
			},
			{	Name = "Maelstrom",
				IntentIcons = { "Attack4" },
				Text = "Deals 6 ({{Asc2|9|7}}) damage ×4.",
				AscText = {
					"Deals 6 damage ×4.",
					"Deals {{Asc2|9|7}} damage ×4."
				}
			},
			{	Name = "Drain Life",
				IntentIcons = { "Attack3", "DebuffStrong" },
				Text = "Deals 18 ({{Asc2|9|19}}) damage. Applies 2 {{BD2|Vulnerable}} and 2 {{BD2|Weak}}.",
				AscText = {
					"Deals 18 damage. Applies 2 {{BD2|Vulnerable}} and 2 {{BD2|Weak}}.",
					"Deals {{Asc2|9|19}} damage. Applies 2 {{BD2|Vulnerable}} and 2 {{BD2|Weak}}."
				}
			},
		}
	},
}

local formatted = {}
for name, enemy in pairs(all_data) do
	enemy.EditLink = "Module:Enemies/StS2_data/Elites"
	formatted[name] = enemy
end

return formatted