local all_data = {
["Bowlbug (Rock)"] = {
	Type = "Normal",
	BaseHP = "45-48",
	AscHP = "46-49",
	Image = "StS2_Bowlbug (Rock).png",
	Link = "Bowlbugs#Bowlbug (Rock)",
	Debut = "{{2|Hive}}",
	StartsWith = "{{BD2|Imbalanced}}",
	Encounters = {
		{
			location = "{{2|Hive}} Easy Encounter",
			enemies = "[[File:Bowlbug (Rock) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs#Bowlbug (Rock)]][[File:Bowlbug (Egg or Nectar) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs]]"
		},
		{
			location = "{{2|Hive}} Normal Encounter",
			enemies = "[[File:Bowlbug (Rock) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs#Bowlbug (Rock)]][[File:Bowlbug (Lesser) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs]][[File:Bowlbug (Lesser) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs]]"
		},
		{
			location = "{{2|Hive}} Normal Encounter",
			enemies = "[[File:Slumbering Beetle Icon.png|class=monster-icon|48px|link=StS2:Slumbering Beetle]][[File:Bowlbug (Rock) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs#Bowlbugs (Rock)]][[File:Bowlbug (Silk) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs#Bowlbugs (Silk)]]"
		}
	},
	Intents = {
		{	Name = "Headbutt",
			IntentIcons = { "Attack3" },
			Text = "Deals 15 ({{Asc2|9|16}}) damage.",
			AscText = {
				"Deals 15 damage.",
				"Deals {{Asc2|9|16}} damage."
			}
		},
		{	Name = "Dizzy", -- codex name; no localization entry for this move
			IntentIcons = { "Stun" },
			Text = "Stunned. Does nothing."
		},
	}
},
["Bowlbug (Egg)"] = {
	Type = "Normal",
	BaseHP = "21-22",
	AscHP = "23-24",
	Image = "StS2_Bowlbug (Egg).png",
	Link = "Bowlbugs#Bowlbug (Egg)",
	Debut = "{{2|Hive}}",
	Encounters = {
		{
			location = "{{2|Hive}} Easy Encounter",
			enemies = "[[File:Bowlbug (Rock) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs#Bowlbug (Rock)]][[File:Bowlbug (Egg or Nectar) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs]]"
		},
		{
			location = "{{2|Hive}} Normal Encounter",
			enemies = "[[File:Bowlbug (Rock) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs#Bowlbug (Rock)]][[File:Bowlbug (Lesser) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs]][[File:Bowlbug (Lesser) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs]]"
		}
	},
	Intents = {
		{	Name = "Bite",
			IntentIcons = { "Attack2", "Defend" },
			Text = "Deals 7 ({{Asc2|9|8}}) damage. Gains 7 ({{Asc2|9|8}}) {{KW2|Block}}.",
			AscText = {
				"Deals 7 damage. Gains 7 {{KW2|Block}}.",
				"Deals {{Asc2|9|8}} damage. Gains {{Asc2|9|8}} {{KW2|Block}}."
			}
		},
	}
},
["Bowlbug (Silk)"] = {
	Type = "Normal",
	BaseHP = "40-43",
	AscHP = "41-44",
	Image = "StS2_Bowlbug (Silk).png",
	Link = "Bowlbugs#Bowlbug (Silk)",
	Debut = "{{2|Hive}}",
	Encounters = {
		{
			location = "{{2|Hive}} Normal Encounter",
			enemies = "[[File:Bowlbug (Rock) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs#Bowlbug (Rock)]][[File:Bowlbug (Lesser) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs]][[File:Bowlbug (Lesser) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs]]"
		},
		{
			location = "{{2|Hive}} Normal Encounter",
			enemies = "[[File:Slumbering Beetle Icon.png|class=monster-icon|48px|link=StS2:Slumbering Beetle]][[File:Bowlbug (Rock) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs#Bowlbug (Rock)]][[File:Bowlbug (Silk) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs#Bowlbug (Silk)]]"
		},
	},
	Intents = {
		{	Name = "Thrash",
			IntentIcons = { "Attack2" },
			Text = "Deals 4 ({{Asc2|9|5}}) damage x2.",
			AscText = {
				"Deals 4 damage x2.",
				"Deals {{Asc2|9|5}} damage x2."
			}
		},
		{	Name = "Spin Web",
			IntentIcons = { "Debuff" },
			Text = "Applies 1 {{BD2|Weak}}.",
		},
	}
},
["Bowlbug (Nectar)"] = {
	Type = "Normal",
	BaseHP = "35-38",
	AscHP = "36-39",
	Image = "StS2_Bowlbug (Nectar).png",
	Link = "Bowlbugs#Bowlbug (Nectar)",
	Debut = "{{2|Hive}}",
	Encounters = {
		{
			location = "{{2|Hive}} Easy Encounter",
			enemies = "[[File:Bowlbug (Rock) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs#Bowlbug (Rock)]][[File:Bowlbug (Egg or Nectar) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs]]"
		},
		{
			location = "{{2|Hive}} Normal Encounter",
			enemies = "[[File:Bowlbug (Rock) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs#Bowlbug (Rock)]][[File:Bowlbug (Lesser) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs]][[File:Bowlbug (Lesser) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs]]"
		}
	},
	Intents = {
		{	Name = "Thrash",
			IntentIcons = { "Attack1" },
			Text = "Deals 3 damage.",
		},
		{	Name = "Buff",
			IntentIcons = { "Buff" },
			Text = "Gains 15 ({{Asc2|9|16}}) {{BD2|Strength}}.",
			AscText = {
				"Gains 15 {{BD2|Strength}}.",
				"Gains {{Asc2|9|16}} {{BD2|Strength}}."
			}
		},
	}
},
["Chomper"] = {
	Type = "Normal",
	BaseHP = "60-64",
	AscHP = "63-67",
	Image = "StS2_Chomper.png",
	Debut = "{{2|Hive}}",
	StartsWith = "{{BD2|Artifact}} 2",
	Encounters = {
		{
			location = "{{2|Hive}} Normal Encounter",
			enemies = "[[File:Chomper Icon.png|class=monster-icon|48px|link=StS2:Chomper]][[File:Chomper Icon.png|class=monster-icon|48px|link=StS2:Chomper]]"
		}
	},
	Intents = {
		{	Name = "Clamp",
			IntentIcons = { "Attack3" },
			Text = "Deals 8 ({{Asc2|9|9}}) damage ×2.",
			AscText = {
				"Deals 8 damage ×2.",
				"Deals {{Asc2|9|9}} damage ×2."
			}
		},
		{	Name = "Screech",
			IntentIcons = { "StatusCard" },
			Text = "Shuffles 3 {{C2|Dazed}} into your discard pile."
		},
	}
},
["Exoskeleton"] = {
	Type = "Normal",
	BaseHP = "24-28",
	AscHP = "25-29",
	Image = "StS2_Exoskeleton.png",
	Debut = "{{2|Hive}}",
	StartsWith = "{{BD2|Hard to Kill}} 9",
	Encounters = {
		{
			location = "{{2|Hive}} Easy Encounter",
			enemies = "[[File:Exoskeleton Icon.png|class=monster-icon|48px|link=StS2:Exoskeleton]][[File:Exoskeleton Icon.png|class=monster-icon|48px|link=StS2:Exoskeleton]][[File:Exoskeleton Icon.png|class=monster-icon|48px|link=StS2:Exoskeleton]]"
		},
		{
			location = "{{2|Hive}} Normal Encounter",
			enemies = "[[File:Exoskeleton Icon.png|class=monster-icon|48px|link=StS2:Exoskeleton]][[File:Exoskeleton Icon.png|class=monster-icon|48px|link=StS2:Exoskeleton]][[File:Exoskeleton Icon.png|class=monster-icon|48px|link=StS2:Exoskeleton]][[File:Exoskeleton Icon.png|class=monster-icon|48px|link=StS2:Exoskeleton]]"
		},
	},
	Intents = {
		{	Name = "Skitter",
			IntentIcons = { "Attack1" },
			Text = "Deals 1 damage ×3 ({{Asc2|9|×4}}).",
			AscText = {
				"Deals 1 damage ×3.",
				"Deals 1 damage {{Asc2|9|×4}}."
			}
		},
		{	Name = "Mandibles",
			IntentIcons = { "Attack2" },
			Text = "Deals 8 ({{Asc2|9|9}}) damage.",
			AscText = {
				"Deals 8 damage.",
				"Deals {{Asc2|9|9}} damage."
			}
		},
		{	Name = "Enrage",
			IntentIcons = { "Buff" },
			Text = "Gains 2 {{BD2|Strength}}."
		},
	}
},
["Hunter Killer"] = {
	Type = "Normal",
	BaseHP = "121",
	AscHP = "126",
	Image = "StS2_Hunter Killer.png",
	Debut = "{{2|Hive}}",
	Encounters = {
		{
			location = "{{2|Hive}} Normal Encounter",
			enemies = "[[File:Hunter Killer Icon.png|class=monster-icon|48px|link=StS2:Hunter Killer]]"
		}
	},
	Intents = {
		{	Name = "Tenderizing Goop",
			IntentIcons = { "Debuff" },
			Text = "Applies 1 {{BD2|Tender}}."
		},
		{	Name = "Bite",
			IntentIcons = { "Attack3" },
			Text = "Deals 17 ({{Asc2|9|19}}) damage.",
			AscText = {
				"Deals 17 damage.",
				"Deals {{Asc2|9|19}} damage."
			}
		},
		{	Name = "Puncture",
			IntentIcons = { "Attack4" },
			Text = "Deals 7 ({{Asc2|9|8}}) damage ×3.",
			AscText = {
				"Deals 7 damage ×3.",
				"Deals {{Asc2|9|8}} damage ×3."
			}
		},
	}
},
["Louse Progenitor"] = {
	Type = "Normal",
	BaseHP = "134-136",
	AscHP = "138-141",
	Image = "StS2_Louse Progenitor.png",
	Debut = "{{2|Hive}}",
	StartsWith = "{{BD2|Curl Up}} 14 ({{Asc2|8|18}})",
	Encounters = {
		{
			location = "{{2|Hive}} Normal Encounter",
			enemies = "[[File:Louse Progenitor Icon.png|class=monster-icon|48px|link=StS2:Louse Progenitor]]"
		}
	},
	Intents = {
		{	Name = "Web Cannon",
			IntentIcons = { "Attack2", "Debuff" },
			Text = "Deals 9 ({{Asc2|9|10}}) damage. Applies 2 {{BD2|Frail}}.",
			AscText = {
				"Deals 9 damage. Applies 2 {{BD2|Frail}}.",
				"Deals {{Asc2|9|10}} damage. Applies 2 {{BD2|Frail}}."
			}
		},
		{	Name = "Curl and Grow",
			IntentIcons = { "Defend", "Buff" },
			Text = "Gains 14 ({{Asc2|8|18}}) {{KW2|Block}}. Gains 5 {{BD2|Strength}}.",
			AscText = {
				"Gains 14 {{KW2|Block}}. Gains 5 {{BD2|Strength}}.",
				"Gains {{Asc2|8|18}} {{KW2|Block}}. Gains 5 {{BD2|Strength}}."
			}
		},
		{	Name = "Pounce", -- NEEDS REVIEW: move name "Pounce" not in localization, using codex name
			IntentIcons = { "Attack3" },
			Text = "Deals 14 ({{Asc2|9|16}}) damage.",
			AscText = {
				"Deals 14 damage.",
				"Deals {{Asc2|9|16}} damage."
			}
		},
	}
},
["Mysterious Knight"] = {
	Type = "Normal",
	BaseHP = "101",
	AscHP = "108",
	Image = "StS2_Mysterious Knight.png",
	Debut = "{{2|The Lantern Key}}", -- NEEDS REVIEW: shared event, not tied to a specific act; verify correct Debut format for event monsters
	StartsWith = "{{BD2|Strength}} 6<br>{{BD2|Plating}} 6",
	Intents = {
		{	Name = "Breaker",
			IntentIcons = { "Buff" },
			Text = "Gains 3 {{BD2|Strength}}.",
		},
		{	Name = "Flail",
			IntentIcons = { "Attack3" },
			Text = "Deals 9 ({{Asc2|9|10}}) damage x2.",
			AscText = {
				"Deals 9 damage x2.",
				"Deals {{Asc2|9|10}} damage x2."
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
["Myte"] = {
	Type = "Normal",
	BaseHP = "61-67",
	AscHP = "64-69",
	Image = "StS2_Myte.png",
	Debut = "{{2|Hive}}",
	Encounters = {
		{
			location = "{{2|Hive}} Normal Encounter",
			enemies = "[[File:Myte Icon.png|class=monster-icon|48px|link=StS2:Myte]][[File:Myte Icon.png|class=monster-icon|48px|link=StS2:Myte]]"
		}
	},
	Intents = {
		{	Name = "Toxic Cornucopia",
			IntentIcons = { "StatusCard" },
			Text = "Adds 2 {{C2|Toxic}} to your hand."
		},
		{	Name = "Bite",
			IntentIcons = { "Attack3" },
			Text = "Deals 13 ({{Asc2|9|15}}) damage.",
			AscText = {
				"Deals 13 damage.",
				"Deals {{Asc2|9|15}} damage."
			}
		},
		{	Name = "Suck",
			IntentIcons = { "Attack1", "Buff" },
			Text = "Deals 4 ({{Asc2|9|6}}) damage. Gains 2 ({{Asc2|9|3}}) {{BD2|Strength}}.",
			AscText = {
				"Deals 4 damage. Gains 2 {{BD2|Strength}}.",
				"Deals {{Asc2|9|6}} damage. Gains {{Asc2|9|3}} {{BD2|Strength}}."
			}
		},
	}
},
["Ovicopter"] = {
	Type = "Normal",
	BaseHP = "124-130",
	AscHP = "126-132",
	Image = "StS2_Ovicopter.png",
	Debut = "{{2|Hive}}",
	Encounters = {
		{
			location = "{{2|Hive}} Normal Encounter",
			enemies = "[[File:Ovicopter Icon.png|class=monster-icon|48px|link=StS2:Ovicopter]][[File:Summon Divider Icon.png]][[File:Tough Egg (+) Icon.png|class=monster-icon|48px|link=StS2:Ovicopter#Tough Egg]]"
		}
	},
	Intents = {
		{	Name = "Lay Eggs",
			IntentIcons = { "Summon" },
			Text = "Summons 3 {{2|Tough Egg|Tough Eggs}}."
		},
		{	Name = "Smash",
			IntentIcons = { "Attack3" },
			Text = "Deals 16 ({{Asc2|9|17}}) damage.",
			AscText = {
				"Deals 16 damage.",
				"Deals {{Asc2|9|17}} damage."
			}
		},
		{	Name = "Tenderizer",
			IntentIcons = { "Attack2", "Debuff" },
			Text = "Deals 7 ({{Asc2|9|8}}) damage. Applies 2 {{BD2|Vulnerable}}.",
			AscText = {
				"Deals 7 damage. Applies 2 {{BD2|Vulnerable}}.",
				"Deals {{Asc2|9|8}} damage. Applies 2 {{BD2|Vulnerable}}."
			}
		},
		{	Name = "Nutritional Paste",
			IntentIcons = { "Buff" },
			Text = "Gains 3 ({{Asc2|9|4}}) {{BD2|Strength}}.",
			AscText = {
				"Gains 3 {{BD2|Strength}}.",
				"Gains {{Asc2|9|4}} {{BD2|Strength}}."
			}
		},
	}
},
["Tough Egg"] = {
	Type = "Minion",
	BaseHP = "14-18",
	AscHP = "15-19",
	Image = "StS2_Tough Egg.png",
	Link = "Ovicopter#Tough Egg",
	Debut = "{{2|Hive}}",
	StartsWith = "{{BD2|Hatch}}",
	Encounters = {
		{
			location = "{{2|Hive}} Normal Encounter",
			enemies = "[[File:Ovicopter Icon.png|class=monster-icon|48px|link=StS2:Ovicopter]][[File:Summon Divider Icon.png]][[File:Tough Egg (+) Icon.png|class=monster-icon|48px|link=StS2:Ovicopter#Tough Egg]]"
		}
	},
	Intents = {
		{	Name = "Hatch",
			IntentIcons = { "Summon" },
			Text = "Hatches into a Hatchling with 19-22 ({{Asc2|8|20-23}}) HP. Removes all powers except {{BD2|Minion}}.",
			AscText = {
				"Hatches into a Hatchling with 19-22 HP. Removes all powers except {{BD2|Minion}}.",
				"Hatches into a Hatchling with {{Asc2|8|20-23}} HP. Removes all powers except {{BD2|Minion}}."
			}
		},
		{	Name = "Nibble", -- NEEDS REVIEW: move name "Nibble" not in localization, using codex name
			IntentIcons = { "Attack1" },
			Text = "Deals 4 ({{Asc2|9|5}}) damage.",
			AscText = {
				"Deals 4 damage.",
				"Deals {{Asc2|9|5}} damage."
			}
		},
	}
},
["Slumbering Beetle"] = {
	Type = "Normal",
	BaseHP = "86",
	AscHP = "89",
	Image = "StS2_Slumbering Beetle.png",
	Debut = "{{2|Hive}}",
	StartsWith = "{{BD2|Plating}} 15 ({{Asc2|8|18}})<br>{{BD2|Slumber}} 3",
	Encounters = {
		{
			location = "{{2|Hive}} Normal Encounter",
			enemies = "[[File:Slumbering Beetle Icon.png|class=monster-icon|48px|link=StS2:Slumbering Beetle]][[File:Bowlbug (Rock) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs#Bowlbug (Rock)]][[File:Bowlbug (Silk) Icon.png|class=monster-icon|48px|link=StS2:Bowlbugs#Bowlbug (Silk)]]"
		},
	},
	Intents = {
		{	Name = "Snore",
			IntentIcons = { "Sleep" },
			Text = "Does nothing. Asleep."
		},
		{	Name = "Roll Out",
			IntentIcons = { "Attack3", "Buff" },
			Text = "Deals 16 ({{Asc2|9|18}}) damage. Gains 2 {{BD2|Strength}}.",
			AscText = {
				"Deals 16 damage. Gains 2 {{BD2|Strength}}.",
				"Deals {{Asc2|9|18}} damage. Gains 2 {{BD2|Strength}}."
			}
		},
	}
},
["Spiny Toad"] = {
	Type = "Normal",
	BaseHP = "116-119",
	AscHP = "121-124",
	Image = "StS2_Spiny Toad.png",
	Debut = "{{2|Hive}}",
	Encounters = {
		{
			location = "{{2|Hive}} Normal Encounter",
			enemies = "[[File:Spiny Toad Icon.png|class=monster-icon|48px|link=StS2:Spiny Toad]]"
		}
	},
	Intents = {
		{	Name = "Protruding Spikes",
			IntentIcons = { "Buff" },
			Text = "Gains 5 {{BD2|Thorns}}."
		},
		{	Name = "Spike Explosion",
			IntentIcons = { "Attack4" },
			Text = "Deals 23 ({{Asc2|9|25}}) damage. Loses 5 {{BD2|Thorns}}.",
			AscText = {
				"Deals 23 damage. Loses 5 {{BD2|Thorns}}.",
				"Deals {{Asc2|9|25}} damage. Loses 5 {{BD2|Thorns}}."
			}
		},
		{	Name = "Tongue Lash",
			IntentIcons = { "Attack3" },
			Text = "Deals 17 ({{Asc2|9|19}}) damage.",
			AscText = {
				"Deals 17 damage.",
				"Deals {{Asc2|9|19}} damage."
			}
		},
	}
},
["The Obscura"] = {
	Type = "Normal",
	BaseHP = "123",
	AscHP = "129",
	Image = "StS2_The Obscura.png",
	Debut = "{{2|Hive}}",
	Encounters = {
		{
			location = "{{2|Hive}} Normal Encounter",
			enemies = "[[File:The Obscura Icon.png|class=monster-icon|48px|link=StS2:The Obscura]][[File:Summon Divider Icon.png]][[File:Parafright Icon.png|class=monster-icon|48px|link=StS2:The Obscura#Parafright]]"
		}
	},
	Intents = {
		{	Name = "Illusion",
			IntentIcons = { "Summon" },
			Text = "Summons a {{M|Parafright}}."
		},
		{	Name = "Piercing Gaze",
			IntentIcons = { "Attack3" },
			Text = "Deals 10 ({{Asc2|9|11}}) damage.",
			AscText = {
				"Deals 10 damage.",
				"Deals {{Asc2|9|11}} damage."
			}
		},
		{	Name = "Wail",
			IntentIcons = { "Buff" },
			Text = "All enemies gain 3 {{BD2|Strength}}."
		},
		{	Name = "Hardening Strike",
			IntentIcons = { "Attack2", "Defend" },
			Text = "Deals 6 ({{Asc2|9|7}}) damage. Gains 6 ({{Asc2|9|7}}) {{KW2|Block}}.",
			AscText = {
				"Deals 6 damage. Gains 6 {{KW2|Block}}.",
				"Deals {{Asc2|9|7}} damage. Gains {{Asc2|9|7}} {{KW2|Block}}."
			}
		},
	}
},
["Parafright"] = {
	Type = "Minion",
	BaseHP = "21",
	Image = "StS2_Parafright.png",
	Link = "The Obscura#Parafright",
	Debut = "{{2|Hive}}",
	StartsWith = "{{BD2|Illusion}}",
	Encounters = {
		{
			location = "{{2|Hive}} Normal Encounter",
			enemies = "[[File:The Obscura Icon.png|class=monster-icon|48px|link=StS2:The Obscura]][[File:Summon Divider Icon.png]][[File:Parafright Icon.png|class=monster-icon|48px|link=StS2:The Obscura#Parafright]]"
		}
	},
	Intents = {
		{	Name = "Slam",
			IntentIcons = { "Attack3" },
			Text = "Deals 16 ({{Asc2|9|17}}) damage.",
			AscText = {
				"Deals 16 damage.",
				"Deals {{Asc2|9|17}} damage."
			}
		},
	}
},
["Thieving Hopper"] = {
	Type = "Normal",
	BaseHP = "79",
	AscHP = "84",
	Image = "StS2_Thieving Hopper.png",
	Debut = "{{2|Hive}}",
	StartsWith = "{{BD2|Escape Artist}} 5",
	Encounters = {
		{
			location = "{{2|Hive}} Easy Encounter",
			enemies = "[[File:Thieving Hopper Icon.png|class=monster-icon|48px|link=StS2:Thieving Hopper]]"
		}
	},
	Intents = {
		{	Name = "Thievery",
			IntentIcons = { "Attack3", "CardDebuff" },
			Text = "Deals 17 ({{Asc2|9|19}}) damage. Steals a card from your deck.",
			AscText = {
				"Deals 17 damage. Steals a card from your deck.",
				"Deals {{Asc2|9|19}} damage. Steals a card from your deck."
			}
		},
		{	Name = "Flutter",
			IntentIcons = { "Buff" },
			Text = "Gains {{BD2|Flutter}} (takes 50% less Attack damage; must be hit 5 times to {{BD2|Stun}} it)."
		},
		{	Name = "Hat Trick",
			IntentIcons = { "Attack4" },
			Text = "Deals 21 ({{Asc2|9|23}}) damage.",
			AscText = {
				"Deals 21 damage.",
				"Deals {{Asc2|9|23}} damage."
			}
		},
		{	Name = "Nab",
			IntentIcons = { "Attack3" },
			Text = "Deals 14 ({{Asc2|9|16}}) damage.",
			AscText = {
				"Deals 14 damage.",
				"Deals {{Asc2|9|16}} damage."
			}
		},
		{	Name = "Escape",
			IntentIcons = { "Escape" },
			Text = "Flees the combat, taking any stolen cards with it."
		},
	}
},
["Tunneler"] = {
	Type = "Normal",
	BaseHP = "87",
	AscHP = "92",
	Image = "StS2_Tunneler.png",
	Debut = "{{2|Hive}}",
	Encounters = {
		{
			location = "{{2|Hive}} Easy Encounter",
			enemies = "[[File:Tunneler Icon.png|class=monster-icon|48px|link=StS2:Tunneler]]"
		},
	},
	Intents = {
		{	Name = "Bite",
			IntentIcons = { "Attack3" },
			Text = "Deals 13 ({{Asc2|9|15}}) damage.",
			AscText = {
				"Deals 13 damage.",
				"Deals {{Asc2|9|15}} damage."
			}
		},
		{	Name = "Burrow",
			IntentIcons = { "Buff", "Defend" },
			Text = "Gains {{BD2|Burrowed}} and 32 ({{Asc2|8|37}}) {{KW2|Block}}.",
			AscText = {
				"Gains {{BD2|Burrowed}} and 32 {{KW2|Block}}.",
				"Gains {{BD2|Burrowed}} and {{Asc2|8|37}} {{KW2|Block}}."
			}
		},
		{	Name = "Attack from Below",
			IntentIcons = { "Attack4" },
			Text = "Deals 23 ({{Asc2|9|26}}) damage.",
			AscText = {
				"Deals 23 damage.",
				"Deals {{Asc2|9|26}} damage."
			}
		},
		{	Name = "Emerging Strike", -- NEEDS REVIEW: move name "Emerging Strike" in localization but not used in state machine; Stun intent move has no localization entry
			IntentIcons = { "Stun" },
			Text = "{{KW2|Stunned}}. Does nothing this turn."
		},
	}
},
}

local formatted = {}
for name, enemy in pairs(all_data) do
	enemy.EditLink = "Module:Enemies/StS2_data/Hive"
	formatted[name] = enemy
end

return formatted