local all_data = {
		["Calcified Cultist"] = {
		Type = "Normal",
		BaseHP = "38-41",
		AscHP = "39-42",
		Image = "StS2_Calcified Cultist.png",
		Link = "Cultists#Calcified Cultist",
		Debut = "{{2|Underdocks}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Underdocks</span><br>* {{M|Damp Cultist}} (Cultists encounter)<br>* {{M|Seapunk}} (Seapunk Normal encounter)",
		Encounters = {
			{
				location = "{{2|Underdocks}} Normal Encounter",
				enemies = "[[File:Calcified Cultist Icon.png|class=monster-icon|48px|link=StS2:Cultists#Calcified Cultist]][[File:Damp Cultist Icon.png|class=monster-icon|48px|link=StS2:Cultists#Damp Cultist]]"
			},
			{
				location = "{{2|Underdocks}} Normal Encounter",
				enemies = "[[File:Calcified Cultist Icon.png|class=monster-icon|48px|link=StS2:Cultists#Calcified Cultist]][[File:Seapunk Icon.png|class=monster-icon|48px|link=StS2:Seapunk]]"
			}
		},
		Intents = {
			{	Name = "Incantation",
				IntentIcons = { "Buff" },
				Text = "Gains 2 {{BD2|Ritual}}.",
			},
			{	Name = "Dark Strike",
				IntentIcons = { "Attack2" },
				Text = "Deals 9 ({{Asc2|9|11}}) damage.",
				AscText = {
					"Deals 9 damage.",
					"Deals {{Asc2|9|11}} damage."
				}
			},
		}
	},
	["Corpse Slug"] = {
		Type = "Normal",
		BaseHP = "25-27",
		AscHP = "27-29",
		Image = "StS2_Corpse Slug.png",
		Debut = "{{2|Underdocks}}",
		StartsWith = "{{BD2|Ravenous}} 4 ({{Asc2|9|5}})",
		InPartyWith = "<span class='enemy-infobox-party-header'>Underdocks</span><br>* Corpse Slugs (Weak): 2× {{M|Corpse Slug}}<br>* Corpse Slugs (Normal): 3× {{M|Corpse Slug}}",
		Encounters = {
			{
				location = "{{2|Underdocks}} Easy Encounter",
				enemies = "[[File:Corpse Slug Icon.png|class=monster-icon|48px|link=StS2:Corpse Slug]][[File:Corpse Slug Icon.png|class=monster-icon|48px|link=StS2:Corpse Slug]]"
			},
			{
				location = "{{2|Underdocks}} Normal Encounter",
				enemies = "[[File:Corpse Slug Icon.png|class=monster-icon|48px|link=StS2:Corpse Slug]][[File:Corpse Slug Icon.png|class=monster-icon|48px|link=StS2:Corpse Slug]][[File:Corpse Slug Icon.png|class=monster-icon|48px|link=StS2:Corpse Slug]]"
			}
		},
		Intents = {
			{	Name = "Whip Slap",
				IntentIcons = { "Attack2" },
				Text = "Deals 3 damage ×2.",
			},
			{	Name = "Glomp", -- NEEDS REVIEW: move name "Glomp" not in localization, using codex name
				IntentIcons = { "Attack2" },
				Text = "Deals 8 ({{Asc2|9|9}}) damage.",
				AscText = {
					"Deals 8 damage.",
					"Deals {{Asc2|9|9}} damage."
				}
			},
			{	Name = "Goop", -- NEEDS REVIEW: move name "Goop" not in localization, using codex name
				IntentIcons = { "Debuff" },
				Text = "Applies 2 {{BD2|Frail}}.",
			},
		}
	},
	["Damp Cultist"] = {
		Type = "Normal",
		BaseHP = "51-53",
		AscHP = "52-54",
		Image = "StS2_Damp Cultist.png",
		Link = "Cultists#Damp Cultist",
		Debut = "{{2|Underdocks}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Underdocks</span><br>* {{M|Calcified Cultist}} (Cultists encounter)",
		Encounters = {
			{
				location = "{{2|Underdocks}} Normal Encounter",
				enemies = "[[File:Calcified Cultist Icon.png|class=monster-icon|48px|link=StS2:Cultists#Calcified Cultist]][[File:Damp Cultist Icon.png|class=monster-icon|48px|link=StS2:Cultists#Damp Cultist]]"
			}
		},
		Intents = {
			{	Name = "Incantation",
				IntentIcons = { "Buff" },
				Text = "Gains 5 ({{Asc2|9|6}}) {{BD2|Ritual}}.",
				AscText = {
					"Gains 5 {{BD2|Ritual}}.",
					"Gains {{Asc2|9|6}} {{BD2|Ritual}}."
				}
			},
			{	Name = "Dark Strike",
				IntentIcons = { "Attack1" },
				Text = "Deals 1 ({{Asc2|9|3}}) damage.",
				AscText = {
					"Deals 1 damage.",
					"Deals {{Asc2|9|3}} damage."
				}
			},
		}
	},
	["Fossil Stalker"] = {
		Type = "Normal",
		BaseHP = "51-53",
		AscHP = "54-56",
		Image = "StS2_Fossil Stalker.png",
		Debut = "{{2|Underdocks}}",
		Encounters = {
			{
				location = "{{2|Underdocks}} Normal Encounter",
				enemies = "[[File:Fossil Stalker Icon.png|class=monster-icon|48px|link=StS2:Fossil Stalker]]"
			}
		},
		StartsWith = "{{BD2|Suck}} 3",
		Intents = {
			{	Name = "Latch",
				IntentIcons = { "Attack3" },
				Text = "Deals 12 ({{Asc2|9|14}}) damage.",
				AscText = {
					"Deals 12 damage.",
					"Deals {{Asc2|9|14}} damage."
				}
			},
			{	Name = "Tackle",
				IntentIcons = { "Attack2", "Debuff" },
				Text = "Deals 9 ({{Asc2|9|11}}) damage. Applies 1 {{BD2|Frail}}.",
				AscText = {
					"Deals 9 damage. Applies 1 {{BD2|Frail}}.",
					"Deals {{Asc2|9|11}} damage. Applies 1 {{BD2|Frail}}."
				}
			},
			{	Name = "Lash",
				IntentIcons = { "Attack2" },
				Text = "Deals 3 ({{Asc2|9|4}}) damage ×2.",
				AscText = {
					"Deals 3 damage ×2.",
					"Deals {{Asc2|9|4}} damage ×2."
				}
			}
		}
	},
	["Gremlin Merc"] = {
		Type = "Normal",
		BaseHP = "47-49",
		AscHP = "51-53",
		Image = "StS2_Gremlin Merc.png",
		Debut = "{{2|Underdocks}}",
		StartsWith = "{{BD2|Surprise}} 1<br>{{BD2|Thievery}} 20",
		InPartyWith = "<span class='enemy-infobox-party-header'>Underdocks</span><br>Appears as a solo normal encounter.<br>Summons {{M|Fat Gremlin}} and {{M|Sneaky Gremlin}} on death.",
		Encounters = {
			{
				location = "{{2|Underdocks}} Normal Encounter",
				enemies = "[[File:Gremlin Merc Icon.png|class=monster-icon|48px|link=StS2:Gremlin Merc]][[File:Summon Divider Icon.png]][[File:Sneaky Gremlin Icon.png|class=monster-icon|48px|link=StS2:Sneaky Gremlin]][[File:Fat Gremlin Icon.png|class=monster-icon|48px|link=StS2:Fat Gremlin]]"
			}
		},
		Intents = {
			{	Name = "Gimme",
				IntentIcons = { "Attack3" },
				Text = "Deals 7x2 ({{Asc2|8|8x2}}) damage.",
				AscText = {
					"Deals 7x2 damage.",
					"Deals {{Asc2|8|8x2}} damage."
				}
			},
			{	Name = "Double Smash",
				IntentIcons = { "Attack3", "Debuff" },
				Text = "Deals 6x2 ({{Asc2|8|7x2}}) damage. Applies 2 {{BD2|Weak}}.",
				AscText = {
					"Deals 6×2. Applies 2 {{BD2|Weak}}.",
					"Deals {{Asc2|8|7x2}} damage. Applies 2 {{BD2|Weak}}."
				}
			},
			{	Name = "Hehe",
				IntentIcons = { "Attack2", "Buff" },
				Text = "Deals 8 ({{Asc2|8|9}}) damage. Gains 2 {{BD2|Strength}}.",
				AscText = {
					"Deals 8 damage. Gains 2 {{BD2|Strength}}.",
					"Deals {{Asc2|8|9}} damage. Gains 2 {{BD2|Strength}}."
				}
			},
		}
	},
	["Fat Gremlin"] = {
		Type = "Minion",
		BaseHP = "13-17",
		AscHP = "14-18",
		Image = "StS2_Fat Gremlin.png",
		Link = "Gremlin Merc#Fat Gremlin",
		Debut = "{{2|Underdocks}}",
		InPartyWith = "Summoned by {{M|Gremlin Merc}} on death.",
		Encounters = {
			{
				location = "{{2|Underdocks}} Normal Encounter",
				enemies = "[[File:Gremlin Merc Icon.png|class=monster-icon|48px|link=StS2:Gremlin Merc]][[File:Summon Divider Icon.png]][[File:Sneaky Gremlin Icon.png|class=monster-icon|48px|link=StS2:Sneaky Gremlin]][[File:Fat Gremlin Icon.png|class=monster-icon|48px|link=StS2:Fat Gremlin]]"
			}
		},
		Intents = {
			{	Name = "Spawned", -- NEEDS REVIEW: move name "Spawned" not in localization, using codex name
				IntentIcons = { "Stun" },
				Text = "Wakes up. Does nothing.",
			},
			{	Name = "Flee",
				IntentIcons = { "Escape" },
				Text = "Flees from combat with any stolen gold.",
			},
		}
	},
	["Sneaky Gremlin"] = {
		Type = "Minion",
		BaseHP = "10-14",
		AscHP = "11-15",
		Image = "StS2_Sneaky Gremlin.png",
		Link = "Gremlin Merc#Sneaky Gremlin",
		Debut = "{{2|Underdocks}}",
		InPartyWith = "Summoned by {{M|Gremlin Merc}} on death.",
		Encounters = {
			{
				location = "{{2|Underdocks}} Normal Encounter",
				enemies = "[[File:Gremlin Merc Icon.png|class=monster-icon|48px|link=StS2:Gremlin Merc]][[File:Summon Divider Icon.png]][[File:Sneaky Gremlin Icon.png|class=monster-icon|48px|link=StS2:Sneaky Gremlin]][[File:Fat Gremlin Icon.png|class=monster-icon|48px|link=StS2:Fat Gremlin]]"
			}
		},
		Intents = {
			{	Name = "Spawned", -- NEEDS REVIEW: move name "Spawned" not in localization, using codex name
				IntentIcons = { "Stun" },
				Text = "Wakes up. Does nothing.",
			},
			{	Name = "Tackle",
				IntentIcons = { "Attack2" },
				Text = "Deals 9 ({{Asc2|9|10}}) damage.",
				AscText = {
					"Deals 9 damage.",
					"Deals {{Asc2|9|10}} damage."
				}
			},
		}
	},
	["Haunted Ship"] = {
		Type = "Normal",
		BaseHP = "63",
		AscHP = "67",
		Image = "StS2_Haunted Ship.png",
		Debut = "{{2|Underdocks}}",
		Encounters = {
			{
				location = "{{2|Underdocks}} Normal Encounter",
				enemies = "[[File:Haunted Ship Icon.png|class=monster-icon|48px|link=StS2:Haunted Ship]]"
			}
		},
		Intents = {
			{	Name = "Haunt",
				IntentIcons = { "StatusCard" },
				Text = "Shuffles 5 {{C2|Dazed}} into your discard pile. Applies 3 {{BD2|Weak}}.",
			},
			{	Name = "Swipe",
				IntentIcons = { "Attack3" },
				Text = "Deals 13 ({{Asc2|9|14}}) damage.",
				AscText = {
					"Deals 13 damage.",
					"Deals {{Asc2|9|14}} damage."
				}
			},
			{	Name = "Stomp",
				IntentIcons = { "Attack3" },
				Text = "Deals 4 ({{Asc2|9|5}}) damage ×3.",
				AscText = {
					"Deals 4 damage ×3.",
					"Deals {{Asc2|9|5}} damage ×3."
				}
			},
		}
	},
	["Living Fog"] = {
		Type = "Normal",
		BaseHP = "80",
		AscHP = "82",
		Image = "StS2_Living Fog.png",
		Debut = "{{2|Underdocks}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Underdocks</span><br>Appears as a solo normal encounter.<br>Summons {{M|Gas Bomb|Gas Bombs|2}} mid-fight.",
		Encounters = {
			{
				location = "{{2|Underdocks}} Normal Encounter",
				enemies = "[[File:Living Fog Icon.png|class=monster-icon|48px|link=StS2:Living Fog]][[File:Summon Divider Icon.png]][[File:Gas Bomb (+) Icon.png|class=monster-icon|48px|link=StS2:Gas Bomb]]"
			}
		},
		Intents = {
			{	Name = "Advanced Gas", -- NEEDS REVIEW: move name "Advanced Gas" not in localization, using codex name
				IntentIcons = { "Attack2", "CardDebuff" },
				Text = "Deals 8 ({{Asc2|9|9}}) damage. Applies 1 {{BD2|Smoggy}}.",
				AscText = {
					"Deals 8 damage. Applies 1 {{BD2|Smoggy}}.",
					"Deals {{Asc2|9|9}} damage. Applies 1 {{BD2|Smoggy}}."
				}
			},
			{	Name = "Bloat",
				IntentIcons = { "Attack2", "Summon" },
				Text = "Deals 5 ({{Asc2|9|6}}) damage. Summons 1 {{M|Gas Bomb|Gas Bomb|2}}.",
				AscText = {
					"Deals 5 damage. Summons 1 {{M|Gas Bomb|Gas Bomb|2}}.",
					"Deals {{Asc2|9|6}} damage. Summons 1 {{M|Gas Bomb|Gas Bomb|2}}."
				}
			},
			{	Name = "Super Gas Blast", -- NEEDS REVIEW: move name "Super Gas Blast" not in localization, using codex name
				IntentIcons = { "Attack2" },
				Text = "Deals 8 ({{Asc2|9|9}}) damage.",
				AscText = {
					"Deals 8 damage.",
					"Deals {{Asc2|9|9}} damage."
				}
			},
		}
	},
	["Gas Bomb"] = {
		Type = "Minion",
		BaseHP = "7",
		AscHP = "8",
		Image = "StS2_Gas Bomb.png",
		Link = "Living Fog#Gas Bomb",
		Debut = "{{2|Underdocks}}",
		StartsWith = "{{BD2|Minion}}",
		InPartyWith = "Summoned by {{M|Living Fog}}.",
		Encounters = {
			{
				location = "{{2|Underdocks}} Normal Encounter",
				enemies = "[[File:Living Fog Icon.png|class=monster-icon|48px|link=StS2:Living Fog]][[File:Summon Divider Icon.png]][[File:Gas Bomb (+) Icon.png|class=monster-icon|48px|link=StS2:Gas Bomb]]"
			}
		},
		Intents = {
			{	Name = "Explode",
				IntentIcons = { "DeathBlow" },
				Text = "Deals 8 ({{Asc2|9|9}}) damage. Dies.",
				AscText = {
					"Deals 8 damage. Dies.",
					"Deals {{Asc2|9|9}} damage. Dies."
				}
			},
		}
	},
	["Punch Construct"] = {
		Type = "Normal",
		BaseHP = "55",
		AscHP = "60",
		Image = "StS2_Punch Construct.png",
		Debut = "{{2|Underdocks}}",
		StartsWith = "{{BD2|Artifact}} 1",
		InPartyWith = "<span class='enemy-infobox-party-header'>Underdocks</span><br>Appears as a solo normal encounter.<br><span class='enemy-infobox-party-header'>Glory</span><br>* {{M|Cubex Construct}} ×2",
		Encounters = {
			{
				location = "{{2|Underdocks}} Normal Encounter",
				enemies = "[[File:Punch Construct Icon.png|class=monster-icon|48px|link=StS2:Punch Construct]]"
			},
			{
				location = "{{2|Underdocks}} Event - [[StS2:Punch Off|Punch Off]]",
				enemies = "[[File:Punch Construct Icon.png|class=monster-icon|48px|link=StS2:Punch Construct]][[File:Punch Construct Icon.png|class=monster-icon|48px|link=StS2:Punch Construct]]"
			},
			{
				location = "{{2|Glory}} Normal Encounter",
				enemies = "[[File:Punch Construct Icon.png|class=monster-icon|48px|link=StS2:Punch Construct]][[File:Cubex Construct Icon.png|class=monster-icon|48px|link=StS2:Cubex Construct]][[File:Cubex Construct Icon.png|class=monster-icon|48px|link=StS2:Cubex Construct]]"
			}
		},
		Intents = {
			{	Name = "READY",
				IntentIcons = { "Defend" },
				Text = "Gains 10 {{KW2|Block}}.",
			},
			{	Name = "Fast Punch",
				IntentIcons = { "Attack3", "Debuff" },
				Text = "Deals 5 ({{Asc2|9|6}}) damage ×2. Applies 1 {{BD2|Frail}}.",
				AscText = {
					"Deals 5 damage ×2. Applies 1 {{BD2|Frail}}.",
					"Deals {{Asc2|9|6}} damage ×2. Applies 1 {{BD2|Frail}}."
				}
			},
			{	Name = "Strong Punch",
				IntentIcons = { "Attack3" },
				Text = "Deals 14 ({{Asc2|9|16}}) damage.",
				AscText = {
					"Deals 14 damage.",
					"Deals {{Asc2|9|16}} damage."
				}
			},
		}
	},
	["Seapunk"] = {
		Type = "Normal",
		BaseHP = "44-46",
		AscHP = "47-49",
		Image = "StS2_Seapunk.png",
		Debut = "{{2|Underdocks}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Underdocks</span><br>* {{M|Calcified Cultist}} (Seapunk encounter)",
		Encounters = {
			{
				location = "{{2|Underdocks}} Easy Encounter",
				enemies = "[[File:Seapunk Icon.png|class=monster-icon|48px|link=StS2:Seapunk]]"
			},
			{
				location = "{{2|Underdocks}} Normal Encounter",
				enemies = "[[File:Seapunk Icon.png|class=monster-icon|48px|link=StS2:Seapunk]][[File:Calcified Cultist Icon.png|class=monster-icon|48px|link=StS2:Cultists#Calcified Cultist]]"
			}
		},
		Intents = {
			{	Name = "Sea Kick",
				IntentIcons = { "Attack3" },
				Text = "Deals 11 ({{Asc2|9|13}}) damage.",
				AscText = {
					"Deals 11 damage.",
					"Deals {{Asc2|9|13}} damage."
				}
			},
			{	Name = "Spinning Kick",
				IntentIcons = { "Attack2" },
				Text = "Deals 2 damage ×4.",
			},
			{	Name = "Bubble Burp",
				IntentIcons = { "Buff", "Defend" },
				Text = "Gains 7 ({{Asc2|8|8}}) {{KW2|Block}} and 1 ({{Asc2|9|2}}) {{BD2|Strength}}.",
				AscText = {
					"Gains 7 {{KW2|Block}} and 1 {{BD2|Strength}}.",
					"Gains {{Asc2|8|8}} {{KW2|Block}} and {{Asc2|9|2}} {{BD2|Strength}}."
				}
			},
		}
	},
	["Sewer Clam"] = {
		Type = "Normal",
		BaseHP = "56",
		AscHP = "58",
		Image = "StS2_Sewer Clam.png",
		Debut = "{{2|Underdocks}}",
		Encounters = {
			{
				location = "{{2|Underdocks}} Normal Encounter",
				enemies = "[[File:Sewer Clam Icon.png|class=monster-icon|48px|link=StS2:Sewer Clam]]"
			}
		},
		StartsWith = "{{BD2|Plating}} 8 ({{Asc2|8|9}})",
		Intents = {
			{	Name = "Jet",
				IntentIcons = { "Attack3" },
				Text = "Deals 10 ({{Asc2|9|11}}) damage.",
				AscText = {
					"Deals 10 damage.",
					"Deals {{Asc2|9|11}} damage."
				}
			},
			{	Name = "Pressurize",
				IntentIcons = { "Buff" },
				Text = "Gains 4 {{BD2|Strength}}.",
			},
		}
	},
	["Sludge Spinner"] = {
		Type = "Normal",
		BaseHP = "37-39",
		AscHP = "41-42",
		Image = "StS2_Sludge Spinner.png",
		Debut = "{{2|Underdocks}}",
		Encounters = {
			{
				location = "{{2|Underdocks}} Easy Encounter",
				enemies = "[[File:Sludge Spinner Icon.png|class=monster-icon|48px|link=StS2:Sludge Spinner]]"
			}
		},
		Intents = {
			{	Name = "Oil Spray",
				IntentIcons = { "Attack2", "Debuff" },
				Text = "Deals 8 ({{Asc2|9|9}}) damage. Applies 1 {{BD2|Weak}}.",
				AscText = {
					"Deals 8 damage. Applies 1 {{BD2|Weak}}.",
					"Deals {{Asc2|9|9}} damage. Applies 1 {{BD2|Weak}}."
				}
			},
			{	Name = "Slam",
				IntentIcons = { "Attack3" },
				Text = "Deals 11 ({{Asc2|9|12}}) damage.",
				AscText = {
					"Deals 11 damage.",
					"Deals {{Asc2|9|12}} damage."
				}
			},
			{	Name = "Rage",
				IntentIcons = { "Attack2", "Buff" },
				Text = "Deals 6 ({{Asc2|9|7}}) damage. Gains 3 {{BD2|Strength}}.",
				AscText = {
					"Deals 6 damage. Gains 3 {{BD2|Strength}}.",
					"Deals {{Asc2|9|7}} damage. Gains 3 {{BD2|Strength}}."
				}
			},
		}
	},
	["Toadpole"] = {
		Type = "Normal",
		BaseHP = "21-25",
		AscHP = "22-26",
		Image = "StS2_Toadpole.png",
		Debut = "{{2|Underdocks}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Underdocks</span><br>* Toadpoles (Weak): {{M|Toadpole}} ×2",
		Encounters = {
			{
				location = "{{2|Underdocks}} Easy Encounter",
				enemies = "[[File:Toadpole Icon.png|class=monster-icon|48px|link=StS2:Toadpole]][[File:Toadpole Icon.png|class=monster-icon|48px|link=StS2:Toadpole]]"
			}
		},
		Intents = {
			{	Name = "Spike Spit",
				IntentIcons = { "Attack2" },
				Text = "Deals 3 ({{Asc2|9|4}}) damage ×3. Removes 2 {{BD2|Thorns}} from self.",
				AscText = {
					"Deals 3 damage ×3. Removes 2 {{BD2|Thorns}} from self.",
					"Deals {{Asc2|9|4}} damage ×3. Removes 2 {{BD2|Thorns}} from self."
				}
			},
			{	Name = "Whirl",
				IntentIcons = { "Attack2" },
				Text = "Deals 7 ({{Asc2|9|8}}) damage.",
				AscText = {
					"Deals 7 damage.",
					"Deals {{Asc2|9|8}} damage."
				}
			},
			{	Name = "Spiken",
				IntentIcons = { "Buff" },
				Text = "Gains 2 {{BD2|Thorns}}.",
			},
		}
	},
	["Two-Tailed Rat"] = {
		Type = "Normal",
		BaseHP = "17-21",
		AscHP = "18-22",
		Image = "StS2_Two-Tailed Rat.png",
		Debut = "{{2|Underdocks}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Underdocks</span><br>* {{M|Two-Tailed Rat}} ×3",
		Encounters = {
			{
				location = "{{2|Underdocks}} Normal Encounter",
				enemies = "[[File:Two-Tailed Rat Icon.png|class=monster-icon|48px|link=StS2:Two-Tailed Rat]][[File:Two-Tailed Rat Icon.png|class=monster-icon|48px|link=StS2:Two-Tailed Rat]][[File:Two-Tailed Rat Icon.png|class=monster-icon|48px|link=StS2:Two-Tailed Rat]][[File:Summon Divider Icon.png]][[File:Two-Tailed Rat (x3) Icon.png|class=monster-icon|48px|link=StS2:Two-Tailed Rat]]"
			}
		},
		Intents = {
			{	Name = "Scratch",
				IntentIcons = { "Attack2" },
				Text = "Deals 8 ({{Asc2|9|9}}) damage.",
				AscText = {
					"Deals 8 damage.",
					"Deals {{Asc2|9|9}} damage."
				}
			},
			{	Name = "Disease Bite",
				IntentIcons = { "Attack2" },
				Text = "Deals 6 ({{Asc2|9|7}}) damage.",
				AscText = {
					"Deals 6 damage.",
					"Deals {{Asc2|9|7}} damage."
				}
			},
			{	Name = "Screech",
				IntentIcons = { "Debuff" },
				Text = "Applies 1 {{BD2|Frail}}.",
			},
			{	Name = "Call for Backup",
				IntentIcons = { "Summon" },
				Text = "Summons a new {{M|Two-Tailed Rat||2}}.",
			},
		}
	},
}

local formatted = {}
for name, enemy in pairs(all_data) do
	enemy.EditLink = "Module:Enemies/StS2_data/Underdocks"
	formatted[name] = enemy
end

return formatted