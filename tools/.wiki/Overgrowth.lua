local all_data = {
	["Assassin Raider"] = {
		Type = "Normal",
		BaseHP = "18-23",
		AscHP = "19-24",
		Image = "StS2_Assassin Raider.png",
		Link = "Ruby Raiders#Assassin Raider",
		Debut = "{{2|Overgrowth}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Overgrowth</span><br>* 2 others randomly chosen from {{M|Axe Raider}}, {{M|Brute Raider}}, {{M|Crossbow Raider}}, {{M|Tracker Raider}}",
		Encounters = {
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Ruby_Raiders_Icon.png|class=monster-icon|48px|link=StS2:Ruby Raiders]][[File:Ruby_Raiders_Icon.png|class=monster-icon|48px|link=StS2:Ruby Raiders]][[File:Ruby_Raiders_Icon.png|class=monster-icon|48px|link=StS2:Ruby Raiders]]"
			}
		},
		Intents = {
			{	Name = "Killshot",
				IntentIcons = { "Attack3" },
				Text = "Deals 10 ({{Asc2|9|11}}) damage.",
				AscText = {
					"Deals 10 damage.",
					"Deals {{Asc2|9|11}} damage."
				}
			},
		}
	},
	["Axe Raider"] = {
		Type = "Normal",
		BaseHP = "20-22",
		AscHP = "21-23",
		Image = "StS2_Axe Raider.png",
		Link = "Ruby Raiders#Axe Raider",
		Debut = "{{2|Overgrowth}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Overgrowth</span><br>* 2 others randomly chosen from {{M|Assassin Raider}}, {{M|Brute Raider}}, {{M|Crossbow Raider}}, {{M|Tracker Raider}}",
		Encounters = {
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Ruby_Raiders_Icon.png|class=monster-icon|48px|link=StS2:Ruby Raiders]][[File:Ruby_Raiders_Icon.png|class=monster-icon|48px|link=StS2:Ruby Raiders]][[File:Ruby_Raiders_Icon.png|class=monster-icon|48px|link=StS2:Ruby Raiders]]"
			}
		},
		Intents = {
			{	Name = "Swing", -- NEEDS REVIEW: move name "Swing" not in localization, using codex name (SWING_1/SWING_2 share same move method)
				IntentIcons = { "Attack2", "Defend" },
				Text = "Deals 5 ({{Asc2|9|6}}) damage. Gains 5 ({{Asc2|9|6}}) {{KW2|Block}}.",
				AscText = {
					"Deals 5 damage. Gains 5 {{KW2|Block}}.",
					"Deals {{Asc2|9|6}} damage. Gains {{Asc2|9|6}} {{KW2|Block}}."
				}
			},
			{	Name = "Big Swing",
				IntentIcons = { "Attack3" },
				Text = "Deals 12 ({{Asc2|9|13}}) damage.",
				AscText = {
					"Deals 12 damage.",
					"Deals {{Asc2|9|13}} damage."
				}
			},
		}
	},
	["Brute Raider"] = {
		Type = "Normal",
		BaseHP = "30-33",
		AscHP = "31-34",
		Image = "StS2_Brute Raider.png",
		Link = "Ruby Raiders#Brute Raider",
		Debut = "{{2|Overgrowth}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Overgrowth</span><br>* 2 others randomly chosen from {{M|Axe Raider}}, {{M|Assassin Raider}}, {{M|Crossbow Raider}}, {{M|Tracker Raider}}",
		Encounters = {
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Ruby_Raiders_Icon.png|class=monster-icon|48px|link=StS2:Ruby Raiders]][[File:Ruby_Raiders_Icon.png|class=monster-icon|48px|link=StS2:Ruby Raiders]][[File:Ruby_Raiders_Icon.png|class=monster-icon|48px|link=StS2:Ruby Raiders]]"
			}
		},
		Intents = {
			{	Name = "Beat",
				IntentIcons = { "Attack2" },
				Text = "Deals 7 ({{Asc2|9|8}}) damage.",
				AscText = {
					"Deals 7 damage.",
					"Deals {{Asc2|9|8}} damage."
				}
			},
			{	Name = "Clap",
				IntentIcons = { "Buff" },
				Text = "Gains 3 {{BD2|Strength}}.",
			},
		}
	},
	["Crossbow Raider"] = {
		Type = "Normal",
		BaseHP = "18-21",
		AscHP = "19-22",
		Image = "StS2_Crossbow Raider.png",
		Link = "Ruby Raiders#Crossbow Raider",
		Debut = "{{2|Overgrowth}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Overgrowth</span><br>* 2 others randomly chosen from {{M|Axe Raider}}, {{M|Assassin Raider}}, {{M|Brute Raider}}, {{M|Tracker Raider}}",
		Encounters = {
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Ruby_Raiders_Icon.png|class=monster-icon|48px|link=StS2:Ruby Raiders]][[File:Ruby_Raiders_Icon.png|class=monster-icon|48px|link=StS2:Ruby Raiders]][[File:Ruby_Raiders_Icon.png|class=monster-icon|48px|link=StS2:Ruby Raiders]]"
			}
		},
		Intents = {
			{	Name = "Reload",
				IntentIcons = { "Defend" },
				Text = "Gains 3 {{KW2|Block}}.",
			},
			{	Name = "Fire!",
				IntentIcons = { "Attack3" },
				Text = "Deals 14 ({{Asc2|9|16}}) damage.",
				AscText = {
					"Deals 14 damage.",
					"Deals {{Asc2|9|16}} damage."
				}
			},
		}
	},
	["Cubex Construct"] = {
		Type = "Normal",
		BaseHP = "65",
		AscHP = "70",
		Image = "StS2_Cubex Construct.png",
		Debut = "{{2|Overgrowth}}",
		StartsWith = "{{BD2|Artifact}} 1",
		InPartyWith = "<span class='enemy-infobox-party-header'>Overgrowth</span><br>Appears as a solo normal encounter.<br><span class='enemy-infobox-party-header'>Glory</span><br>* Construct Menagerie: {{M|Punch Construct}} + {{M|Cubex Construct}} ×2",
		Encounters = {
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Cubex Construct Icon.png|class=monster-icon|48px|link=StS2:Cubex Construct]]"
			},
			{
				location = "{{2|Glory}} Normal Encounter",
				enemies = "[[File:Punch Construct Icon.png|class=monster-icon|48px|link=StS2:Punch Construct]][[File:Cubex Construct Icon.png|class=monster-icon|48px|link=StS2:Cubex Construct]][[File:Cubex Construct Icon.png|class=monster-icon|48px|link=StS2:Cubex Construct]]"
			}
		},
		Intents = {
			{	Name = "Charge Up",
				IntentIcons = { "Buff" },
				Text = "Gains 2 {{BD2|Strength}}."
			},
			{	Name = "Repeater Blast",
				IntentIcons = { "Attack2", "Buff" },
				Text = "Deals 7 ({{Asc2|9|8}}) damage. Gains 2 {{BD2|Strength}}.",
				AscText = {
					"Deals 7 damage. Gains 2 {{BD2|Strength}}.",
					"Deals {{Asc2|9|8}} damage. Gains 2 {{BD2|Strength}}."
				}
			},
			{	Name = "Expel Blast", -- NEEDS REVIEW: move name "Expel Blast" not in localization, using codex name
				IntentIcons = { "Attack3" },
				Text = "Deals 5 ({{Asc2|9|6}}) damage ×2.",
				AscText = {
					"Deals 5 damage ×2.",
					"Deals {{Asc2|9|6}} damage ×2."
				}
			},
		}
	},
	["Eye With Teeth"] = {
		Type = "Minion",
		BaseHP = "6",
		Image = "StS2_Eye With Teeth.png",
		Link = "Fogmog#Eye With Teeth",
		Debut = "{{2|Overgrowth}}",
		StartsWith = "{{BD2|Illusion}}",
		InPartyWith = "Summoned by {{M|Fogmog||2}}.",
		Encounters = {
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Fogmog Icon.png|class=monster-icon|48px|link=StS2:Fogmog]][[File:Eye With Teeth Icon.png|class=monster-icon|48px|link=StS2:Fogmog#Eye With Teeth]]"
			}
		},
		Intents = {
			{	Name = "Distract",
				IntentIcons = { "StatusCard" },
				Text = "Shuffles 3 {{C2|Dazed}} into your discard pile."
			},
		}
	},
	["Flyconid"] = {
		Type = "Normal",
		BaseHP = "47-49",
		AscHP = "51-53",
		Image = "StS2_Flyconid.png",
		Debut = "{{2|Overgrowth}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Overgrowth</span><br>* Flyconid encounter: {{M|Flyconid}} + 1 random from {{M|Leaf Slime (M)}} or {{M|Twig Slime (M)}}<br>* Snapping Jaxfruit encounter: {{M|Snapping Jaxfruit}} + {{M|Flyconid}}",
		Encounters = {
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Flyconid Icon.png|class=monster-icon|48px|link=StS2:Flyconid]][[File:Slimes (M) Icon.png|class=monster-icon|48px|link=StS2:Slimes]]"
			},
		{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Flyconid Icon.png|class=monster-icon|48px|link=StS2:Flyconid]][[File:Snapping Jaxfruit Icon.png|class=monster-icon|48px|link=StS2:Snapping Jaxfruit]]"
			},
		},
		Intents = {
			{	Name = "Weakening Spores",
				IntentIcons = { "Debuff" },
				Text = "Applies 2 {{BD2|Vulnerable}}."
			},
			{	Name = "Frail Spores",
				IntentIcons = { "Attack2", "Debuff" },
				Text = "Deals 8 ({{Asc2|9|9}}) damage. Applies 2 {{BD2|Frail}}.",
				AscText = {
					"Deals 8 damage. Applies 2 {{BD2|Frail}}.",
					"Deals {{Asc2|9|9}} damage. Applies 2 {{BD2|Frail}}."
				}
			},
			{	Name = "Smash",
				IntentIcons = { "Attack3" },
				Text = "Deals 11 ({{Asc2|9|12}}) damage.",
				AscText = {
					"Deals 11 damage.",
					"Deals {{Asc2|9|12}} damage."
				}
			},
		}
	},
	["Fogmog"] = {
		Type = "Normal",
		BaseHP = "74",
		AscHP = "78",
		Image = "StS2_Fogmog.png",
		Debut = "{{2|Overgrowth}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Overgrowth</span><br>Appears as a solo normal encounter.<br>Summons {{M|Eye With Teeth}} mid-fight.",
		Encounters = {
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Fogmog Icon.png|class=monster-icon|48px|link=StS2:Fogmog]][[File:Eye With Teeth Icon.png|class=monster-icon|48px|link=StS2:Fogmog#Eye With Teeth]]"
			}
		},
		Intents = {
			{	Name = "Illusory Spores",
				IntentIcons = { "Summon" },
				Text = "Summons an {{M|Eye With Teeth||2}}."
			},
			{	Name = "Thwack",
				IntentIcons = { "Attack2", "Buff" },
				Text = "Deals 8 ({{Asc2|9|9}}) damage. Gains 1 {{BD2|Strength}}.",
				AscText = {
					"Deals 8 damage. Gains 1 {{BD2|Strength}}.",
					"Deals {{Asc2|9|9}} damage. Gains 1 {{BD2|Strength}}."
				}
			},
			{	Name = "Headbutt", -- NEEDS REVIEW: move name "Headbutt" not in localization, using codex name
				IntentIcons = { "Attack3" },
				Text = "Deals 14 ({{Asc2|9|16}}) damage.",
				AscText = {
					"Deals 14 damage.",
					"Deals {{Asc2|9|16}} damage."
				}
			},
		}
	},
	["Fuzzy Wurm Crawler"] = {
		Type = "Normal",
		BaseHP = "55-57",
		AscHP = "58-59",
		Image = "StS2_Fuzzy Wurm Crawler.png",
		Debut = "{{2|Overgrowth}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Overgrowth</span><br>Appears as a solo weak encounter.<br>Also appears in a strong encounter with {{M|Shrinker Beetle}}.",
		Encounters = {
			{
				location = "{{2|Overgrowth}} Easy Encounter",
				enemies = "[[File:Fuzzy Wurm Crawler Icon.png|class=monster-icon|48px|link=StS2:Fuzzy Wurm Crawler]]"
			},
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Fuzzy Wurm Crawler Icon.png|class=monster-icon|48px|link=StS2:Fuzzy Wurm Crawler]][[File:Shrinker Beetle Icon.png|class=monster-icon|48px|link=StS2:Shrinker Beetle]]"
			}
		},
		Intents = {
			{	Name = "Acid Goop",
				IntentIcons = { "Attack1" },
				Text = "Deals 4 ({{Asc2|9|6}}) damage.",
				AscText = {
					"Deals 4 damage.",
					"Deals {{Asc2|9|6}} damage."
				}
			},
			{	Name = "Inhale",
				IntentIcons = { "Buff" },
				Text = "Gains 7 {{BD2|Strength}}.",
			},
		}
	},
	["Inklet"] = {
		Type = "Normal",
		BaseHP = "11-17",
		AscHP = "12-18",
		Image = "StS2_Inklet.png",
		Debut = "{{2|Overgrowth}}",
		StartsWith = "{{BD2|Slippery}} 1",
		InPartyWith = "<span class='enemy-infobox-party-header'>Overgrowth</span><br>* Inklets: {{M|Inklet}} x3",
		Encounters = {
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Inklet Icon.png|class=monster-icon|48px|link=StS2:Inklet]][[File:Inklet Icon.png|class=monster-icon|48px|link=StS2:Inklet]][[File:Inklet Icon.png|class=monster-icon|48px|link=StS2:Inklet]]"
			}
		},
		Intents = {
			{	Name = "Jab",
				IntentIcons = { "Attack1" },
				Text = "Deals 3 ({{Asc2|9|4}}) damage.",
				AscText = {
					"Deals 3 damage.",
					"Deals {{Asc2|9|4}} damage."
				}
			},
			{	Name = "Windup Punch",
				IntentIcons = { "Attack2" },
				Text = "Deals 2 ({{Asc2|9|3}}) damage ×3.",
				AscText = {
					"Deals 2 damage ×3.",
					"Deals {{Asc2|9|3}} damage ×3."
				}
			},
			{	Name = "Piercing Gaze",
				IntentIcons = { "Attack3" },
				Text = "Deals 10 ({{Asc2|9|11}}) damage.",
				AscText = {
					"Deals 10 damage.",
					"Deals {{Asc2|9|11}} damage."
				}
			},
		}
	},
	["Leaf Slime (M)"] = {
		Type = "Normal",
		BaseHP = "32-35",
		AscHP = "33-36",
		Image = "StS2_Leaf Slime (M).png",
		Link = "Slimes#Leaf Slime (M)",
		Debut = "{{2|Overgrowth}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Overgrowth</span><br>* Slimes (Weak): {{M|Leaf Slime (S)}}, {{M|Twig Slime (S)}}, and randomly chosen as the medium slime<br>* Slimes (Normal): {{M|Leaf Slime (S)}}, {{M|Twig Slime (S)}}, {{M|Twig Slime (M)}}<br>* Flyconid: randomly chosen companion with {{M|Flyconid}}<br>* Slithering Strangler: possible companion with {{M|Slithering Strangler}} (medium slime variant)",
		Encounters = {
			{
				location = "{{2|Overgrowth}} Easy Encounter",
				enemies = "[[File:Slimes (M) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Slimes (S) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Slimes (S) Icon.png|class=monster-icon|48px|link=StS2:Slimes]]"
			},
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Twig Slime (M) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Leaf Slime (M) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Twig Slime (S) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Leaf Slime (S) Icon.png|class=monster-icon|48px|link=StS2:Slimes]]"
			},
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Flyconid Icon.png|class=monster-icon|48px|link=StS2:Flyconid]][[File:Slimes (M) Icon.png|class=monster-icon|48px|link=StS2:Slimes]]"
			},
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Slithering Strangler Icon.png|class=monster-icon|48px|link=StS2:Slithering Strangler]][[File:Slimes (M) Icon.png|class=monster-icon|48px|link=StS2:Slimes]]"
			}
		},
		Intents = {
			{	Name = "Clump Shot",
				IntentIcons = { "Attack2" },
				Text = "Deals 8 ({{Asc2|9|9}}) damage.",
				AscText = {
					"Deals 8 damage.",
					"Deals {{Asc2|9|9}} damage."
				}
			},
			{	Name = "Sticky Shot",
				IntentIcons = { "StatusCard" },
				Text = "Shuffles 2 {{C2|Slimed}} into your discard pile."
			},
		}
	},
	["Leaf Slime (S)"] = {
		Type = "Normal",
		BaseHP = "11-15",
		AscHP = "12-16",
		Image = "StS2_Leaf Slime (S).png",
		Link = "Slimes#Leaf Slime (S)",
		Debut = "{{2|Overgrowth}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Overgrowth</span><br>* Slimes (Weak): {{M|Twig Slime (S)}} + 1 random from {{M|Leaf Slime (M)}} or {{M|Twig Slime (M)}}<br>* Slimes (Normal): {{M|Leaf Slime (M)}}, {{M|Twig Slime (S)}}, {{M|Twig Slime (M)}}<br>* Slithering Strangler: possible companion with {{M|Slithering Strangler}} (2 small slimes variant)",
		Encounters = {
			{
				location = "{{2|Overgrowth}} Easy Encounter",
				enemies = "[[File:Slimes (M) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Slimes (S) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Slimes (S) Icon.png|class=monster-icon|48px|link=StS2:Slimes]]"
			},
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Twig Slime (M) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Leaf Slime (M) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Twig Slime (S) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Leaf Slime (S) Icon.png|class=monster-icon|48px|link=StS2:Slimes]]"
			},
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Slithering Strangler Icon.png|class=monster-icon|48px|link=StS2:Slithering Strangler]][[File:Slimes (S) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Slimes (S) Icon.png|class=monster-icon|48px|link=StS2:Slimes]]"
			}
		},
		Intents = {
			{	Name = "Tackle",
				IntentIcons = { "Attack1" },
				Text = "Deals 3 ({{Asc2|9|4}}) damage.",
				AscText = {
					"Deals 3 damage.",
					"Deals {{Asc2|9|4}} damage."
				}
			},
			{	Name = "Goop",
				IntentIcons = { "StatusCard" },
				Text = "Shuffles 1 {{C2|Slimed}} into your discard pile."
			},
		}
	},
	["Mawler"] = {
		Type = "Normal",
		BaseHP = "72",
		AscHP = "76",
		Image = "StS2_Mawler.png",
		Debut = "{{2|Overgrowth}}",
		Encounters = {
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Mawler Icon.png|class=monster-icon|48px|link=StS2:Mawler]]"
			}
		},
		Intents = {
			{	Name = "Rip and Tear",
				IntentIcons = { "Attack3" },
				Text = "Deals 14 ({{Asc2|9|16}}) damage.",
				AscText = {
					"Deals 14 damage.",
					"Deals {{Asc2|9|16}} damage."
				}
			},
			{	Name = "Roar",
				IntentIcons = { "Debuff" },
				Text = "Applies 3 {{BD2|Vulnerable}}."
			},
			{	Name = "Claw",
				IntentIcons = { "Attack2" },
				Text = "Deals 4 ({{Asc2|9|5}}) damage ×2.",
				AscText = {
					"Deals 4 damage ×2.",
					"Deals {{Asc2|9|5}} damage ×2."
				}
			},
		}
	},
	["Nibbit"] = {
		Type = "Normal",
		BaseHP = "42-46",
		AscHP = "44-48",
		Image = "StS2_Nibbit.png",
		Debut = "{{2|Overgrowth}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Overgrowth</span><br>* Nibbits (Weak): appears alone<br>* Nibbits (Normal): {{M|Nibbit}} x2",
		Encounters = {
			{
				location = "{{2|Overgrowth}} Easy Encounter",
				enemies = "[[File:Nibbit_Icon.png|class=monster-icon|48px|link=StS2:Nibbit]]"
			},
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Nibbit_Icon.png|class=monster-icon|48px|link=StS2:Nibbit]][[File:Nibbit_Icon.png|class=monster-icon|48px|link=StS2:Nibbit]]"
			}
		},
		Intents = {
			{	Name = "Butt",
				IntentIcons = { "Attack3" },
				Text = "Deals 12 ({{Asc2|9|13}}) damage.",
				AscText = {
					"Deals 12 damage.",
					"Deals {{Asc2|9|13}} damage."
				}
			},
			{	Name = "Hesitant Slice",
				IntentIcons = { "Attack2", "Defend" },
				Text = "Deals 6 ({{Asc2|9|7}}) damage. Gains 5 ({{Asc2|8|6}}) {{KW2|Block}}.",
				AscText = {
					"Deals 6 damage. Gains 5 {{KW2|Block}}.",
					"Deals {{Asc2|9|7}} damage. Gains {{Asc2|8|6}} {{KW2|Block}}."
				}
			},
			{	Name = "Hiss",
				IntentIcons = { "Buff" },
				Text = "Gains 2 ({{Asc2|9|3}}) {{BD2|Strength}}.",
				AscText = {
					"Gains 2 {{BD2|Strength}}.",
					"Gains {{Asc2|9|3}} {{BD2|Strength}}."
				}
			},
		}
	},
	["Shrinker Beetle"] = {
		Type = "Normal",
		BaseHP = "38-40",
		AscHP = "40-42",
		Image = "StS2_Shrinker Beetle.png",
		Debut = "{{2|Overgrowth}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Overgrowth</span><br>Appears as a solo weak encounter.<br>Also appears in a strong encounter with {{M|Fuzzy Wurm Crawler}}.",
		Encounters = {
			{
				location = "{{2|Overgrowth}} Easy Encounter",
				enemies = "[[File:Shrinker Beetle Icon.png|class=monster-icon|48px|link=StS2:Shrinker Beetle]]"
			},
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Fuzzy Wurm Crawler Icon.png|class=monster-icon|48px|link=StS2:Fuzzy Wurm Crawler]][[File:Shrinker Beetle Icon.png|class=monster-icon|48px|link=StS2:Shrinker Beetle]]"
			}
		},
		Intents = {
			{	Name = "Shrinker",
				IntentIcons = { "DebuffStrong" },
				Text = "Applies {{BD2|Shrink}}.",
			},
			{	Name = "Chomp",
				IntentIcons = { "Attack2" },
				Text = "Deals 7 ({{Asc2|9|8}}) damage.",
				AscText = {
					"Deals 7 damage.",
					"Deals {{Asc2|9|8}} damage."
				}
			},
			{	Name = "Stomp",
				IntentIcons = { "Attack3" },
				Text = "Deals 13 ({{Asc2|9|14}}) damage.",
				AscText = {
					"Deals 13 damage.",
					"Deals {{Asc2|9|14}} damage."
				}
			},
		}
	},
	["Slithering Strangler"] = {
		Type = "Normal",
		BaseHP = "53-55",
		AscHP = "54-56",
		Image = "StS2_Slithering Strangler.png",
		Debut = "{{2|Overgrowth}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Overgrowth</span><br>* {{M|Slithering Strangler}} + 1 random secondary: {{M|Snapping Jaxfruit}}, or 1 medium slime ({{M|Leaf Slime (M)}} or {{M|Twig Slime (M)}}), or 2 small slimes ({{M|Leaf Slime (S)}} + {{M|Twig Slime (S)}})",
		Encounters = {
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Slithering Strangler Icon.png|class=monster-icon|48px|link=StS2:Slithering Strangler]][[File:Snapping Jaxfruit Icon.png|class=monster-icon|48px|link=StS2:Snapping Jaxfruit]] -or-<br>[[File:Slithering Strangler Icon.png|class=monster-icon|48px|link=StS2:Slithering Strangler]][[File:Slimes (M) Icon.png|class=monster-icon|48px|link=StS2:Slimes]] -or-<br>[[File:Slithering Strangler Icon.png|class=monster-icon|48px|link=StS2:Slithering Strangler]][[File:Slimes (S) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Slimes (S) Icon.png|class=monster-icon|48px|link=StS2:Slimes]]"
			}
		},
		Intents = {
			{	Name = "Constrict",
				IntentIcons = { "Debuff" },
				Text = "Applies 3 {{BD2|Constrict}}."
			},
			{	Name = "Thwack",
				IntentIcons = { "Attack2", "Defend" },
				Text = "Deals 7 ({{Asc2|9|8}}) damage. Gains 5 {{KW2|Block}}.",
				AscText = {
					"Deals 7 damage. Gains 5 {{KW2|Block}}.",
					"Deals {{Asc2|9|8}} damage. Gains 5 {{KW2|Block}}."
				}
			},
			{	Name = "Lash",
				IntentIcons = { "Attack3" },
				Text = "Deals 12 ({{Asc2|9|13}}) damage.",
				AscText = {
					"Deals 12 damage.",
					"Deals {{Asc2|9|13}} damage."
				}
			},
		}
	},
	["Snapping Jaxfruit"] = {
		Type = "Normal",
		BaseHP = "31-33",
		AscHP = "34-36",
		Image = "StS2_Snapping Jaxfruit.png",
		Debut = "{{2|Overgrowth}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Overgrowth</span><br>* Snapping Jaxfruit encounter: {{M|Snapping Jaxfruit}} + {{M|Flyconid}}<br>* Slithering Strangler encounter: {{M|Slithering Strangler}} + 1 random companion ({{M|Snapping Jaxfruit}} or 1 medium slime or 2 small slimes)",
		Encounters = {
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Snapping Jaxfruit Icon.png|class=monster-icon|48px|link=StS2:Snapping Jaxfruit]][[File:Flyconid Icon.png|class=monster-icon|48px|link=StS2:Flyconid]]"
			},
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Snapping Jaxfruit Icon.png|class=monster-icon|48px|link=StS2:Snapping Jaxfruit]][[File:Slithering Strangler Icon.png|class=monster-icon|48px|link=StS2:Slithering Strangler]]"
			}
		},
		Intents = {
			{	Name = "Energy Orb",
				IntentIcons = { "Attack1", "Buff" },
				Text = "Deals 3 ({{Asc2|9|4}}) damage. Gains 2 {{BD2|Strength}}.",
				AscText = {
					"Deals 3 damage. Gains 2 {{BD2|Strength}}.",
					"Deals {{Asc2|9|4}} damage. Gains 2 {{BD2|Strength}}."
				}
			},
		}
	},
	["Tracker Raider"] = {
		Type = "Normal",
		BaseHP = "21-25",
		AscHP = "22-26",
		Image = "StS2_Tracker Raider.png",
		Link = "Ruby Raiders#Tracker Raider",
		Debut = "{{2|Overgrowth}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Overgrowth</span><br>* 2 others randomly chosen from {{M|Axe Raider}}, {{M|Assassin Raider}}, {{M|Brute Raider}}, {{M|Crossbow Raider}}",
		Encounters = {
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Ruby_Raiders_Icon.png|class=monster-icon|48px|link=StS2:Ruby Raiders]][[File:Ruby_Raiders_Icon.png|class=monster-icon|48px|link=StS2:Ruby Raiders]][[File:Ruby_Raiders_Icon.png|class=monster-icon|48px|link=StS2:Ruby Raiders]]"
			}
		},
		Intents = {
			{	Name = "Track",
				IntentIcons = { "Debuff" },
				Text = "Applies 2 {{BD2|Frail}}.",
			},
			{	Name = "Unleash the Hounds",
				IntentIcons = { "Attack2" },
				Text = "Deals 1 damage x8 ({{Asc2|9|x9}}).",
				AscText = {
					"Deals 1 damage x8.",
					"Deals 1 damage {{Asc2|9|x9}}."
				}
			}, -- NEEDS REVIEW: hit count scales with ascension (8 base, 9 at Asc 9), damage per hit stays 1
		}
	},
	["Twig Slime (M)"] = {
		Type = "Normal",
		BaseHP = "26-28",
		AscHP = "27-29",
		Image = "StS2_Twig Slime (M).png",
		Link = "Slimes#Twig Slime (M)",
		Debut = "{{2|Overgrowth}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Overgrowth</span><br>* Slimes (Weak): {{M|Leaf Slime (S)}}, {{M|Twig Slime (S)}}, and randomly chosen as the medium slime<br>* Slimes (Normal): {{M|Leaf Slime (S)}}, {{M|Leaf Slime (M)}}, {{M|Twig Slime (S)}}<br>* Flyconid: randomly chosen companion with {{M|Flyconid}}<br>* Slithering Strangler: possible companion with {{M|Slithering Strangler}} (medium slime variant)",
		Encounters = {
			{
				location = "{{2|Overgrowth}} Easy Encounter",
				enemies = "[[File:Slimes (M) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Slimes (S) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Slimes (S) Icon.png|class=monster-icon|48px|link=StS2:Slimes]]"
			},
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Twig Slime (M) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Leaf Slime (M) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Twig Slime (S) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Leaf Slime (S) Icon.png|class=monster-icon|48px|link=StS2:Slimes]]"
			},
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Flyconid Icon.png|class=monster-icon|48px|link=StS2:Flyconid]][[File:Slimes (M) Icon.png|class=monster-icon|48px|link=StS2:Slimes]]"
			},
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Slithering Strangler Icon.png|class=monster-icon|48px|link=StS2:Slithering Strangler]][[File:Slimes (M) Icon.png|class=monster-icon|48px|link=StS2:Slimes]]"
			}
		},
		Intents = {
			{	Name = "Chomp",
				IntentIcons = { "Attack3" },
				Text = "Deals 11 ({{Asc2|9|12}}) damage.",
				AscText = {
					"Deals 11 damage.",
					"Deals {{Asc2|9|12}} damage."
				}
			},
			{	Name = "Sticky Shot",
				IntentIcons = { "StatusCard" },
				Text = "Shuffles 1 {{C2|Slimed}} into your discard pile."
			},
		}
	},
	["Twig Slime (S)"] = {
		Type = "Normal",
		BaseHP = "7-11",
		AscHP = "8-12",
		Image = "StS2_Twig Slime (S).png",
		Link = "Slimes#Twig Slime (S)",
		Debut = "{{2|Overgrowth}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Overgrowth</span><br>* Slimes (Weak): {{M|Leaf Slime (S)}} + 1 random from {{M|Leaf Slime (M)}} or {{M|Twig Slime (M)}}<br>* Slimes (Normal): {{M|Leaf Slime (S)}}, {{M|Leaf Slime (M)}}, {{M|Twig Slime (M)}}<br>* Slithering Strangler: possible companion with {{M|Slithering Strangler}} (2 small slimes variant)",
		Encounters = {
			{
				location = "{{2|Overgrowth}} Easy Encounter",
				enemies = "[[File:Slimes (M) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Slimes (S) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Slimes (S) Icon.png|class=monster-icon|48px|link=StS2:Slimes]]"
			},
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Twig Slime (M) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Leaf Slime (M) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Twig Slime (S) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Leaf Slime (S) Icon.png|class=monster-icon|48px|link=StS2:Slimes]]"
			},
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Slithering Strangler Icon.png|class=monster-icon|48px|link=StS2:Slithering Strangler]][[File:Slimes (S) Icon.png|class=monster-icon|48px|link=StS2:Slimes]][[File:Slimes (S) Icon.png|class=monster-icon|48px|link=StS2:Slimes]]"
			}
		},
		Intents = {
			{	Name = "Tackle",
				IntentIcons = { "Attack1" },
				Text = "Deals 4 ({{Asc2|9|5}}) damage.",
				AscText = {
					"Deals 4 damage.",
					"Deals {{Asc2|9|5}} damage."
				}
			},
		}
	},
	["Vine Shambler"] = {
		Type = "Normal",
		BaseHP = "61",
		AscHP = "64",
		Image = "StS2_Vine Shambler.png",
		Debut = "{{2|Overgrowth}}",
		Encounters = {
			{
				location = "{{2|Overgrowth}} Normal Encounter",
				enemies = "[[File:Vine Shambler Icon.png|class=monster-icon|48px|link=StS2:Vine Shambler]]"
			}
		},
		Intents = {
			{	Name = "Swipe",
				IntentIcons = { "Attack3" },
				Text = "Deals 6 ({{Asc2|9|7}}) damage ×2.",
				AscText = {
					"Deals 6 damage ×2.",
					"Deals {{Asc2|9|7}} damage ×2."
				}
			},
			{	Name = "Grasping Vines",
				IntentIcons = { "Attack2", "CardDebuff" },
				Text = "Deals 8 ({{Asc2|9|9}}) damage. Applies 1 {{BD2|Tangled}}.",
				AscText = {
					"Deals 8 damage. Applies 1 {{BD2|Tangled}}.",
					"Deals {{Asc2|9|9}} damage. Applies 1 {{BD2|Tangled}}."
				}
			},
			{	Name = "Chomp",
				IntentIcons = { "Attack3" },
				Text = "Deals 16 ({{Asc2|9|18}}) damage.",
				AscText = {
					"Deals 16 damage.",
					"Deals {{Asc2|9|18}} damage."
				}
			},
		}
	},
	["Wriggler"] = {
		Type = "Normal",
		BaseHP = "17-21",
		AscHP = "18-22",
		Image = "StS2_Wriggler.png",
		Debut = "{{2|Overgrowth}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Overgrowth</span><br>* Appears in the [[Dense Vegetation]] event (×4)<br>* Summoned by {{M|Phrog Parasite}} upon death (×4, via {{BD2|Infested}})",
		Encounters = {
			{
				location = "{{2|Overgrowth}} Event - [[sts2:Dense Vegetation|Dense Vegetation]]",
				enemies = "[[File:Wriggler Icon.png|class=monster-icon|48px|link=StS2:Wriggler]][[File:Wriggler Icon.png|class=monster-icon|48px|link=StS2:Wriggler]][[File:Wriggler Icon.png|class=monster-icon|48px|link=StS2:Wriggler]][[File:Wriggler Icon.png|class=monster-icon|48px|link=StS2:Wriggler]]"
			},
			{
				location = "{{2|Overgrowth}} Elite Encounter",
				enemies = "[[File:Phrog Parasite Icon.png|class=monster-icon|48px|link=StS2:Phrog Parasite]][[File:Wriggler Icon.png|class=monster-icon|48px|link=StS2:Wriggler]][[File:Wriggler Icon.png|class=monster-icon|48px|link=StS2:Wriggler]][[File:Wriggler Icon.png|class=monster-icon|48px|link=StS2:Wriggler]][[File:Wriggler Icon.png|class=monster-icon|48px|link=StS2:Wriggler]]"
			}
		},
		Intents = {
			{	Name = "Nasty Bite", -- NEEDS REVIEW: move name "Nasty Bite" not in localization, using codex name
				IntentIcons = { "Attack2" },
				Text = "Deals 6 ({{Asc2|9|7}}) damage.",
				AscText = {
					"Deals 6 damage.",
					"Deals {{Asc2|9|7}} damage."
				}
			},
			{	Name = "Wriggle", -- NEEDS REVIEW: move name "Wriggle" not in localization, using codex name
				IntentIcons = { "Buff", "StatusCard" },
				Text = "Shuffles 1 {{C2|Infection}} into your discard pile. Gains 2 {{BD2|Strength}}."
			},
		}
	},
}

local formatted = {}
for name, enemy in pairs(all_data) do
	enemy.EditLink = "Module:Enemies/StS2_data/Overgrowth"
	formatted[name] = enemy
end

return formatted