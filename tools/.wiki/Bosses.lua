local all_data = {
	-- Act 1A Overgrowth
		["Ceremonial Beast"] = {
		Type = "Boss",
		BaseHP = "252",
		AscHP = "262",
		Image = "StS2_Ceremonial Beast.png",
		Icon = "StS2 Icon CeremonialBeastBoss.png",
		Debut = "{{2|Overgrowth}}",
		Intents = {
			{	Name = "Stamp",
				IntentIcons = { "Buff" },
				Text = "Gains {{BD2|Plow}} 150 ({{Asc2|9|160}}). When its HP drops to that amount, it becomes {{BD2|Stunned}} and loses all {{BD2|Strength}}.",
				AscText = {
					"Gains {{BD2|Plow}} 150. When its HP drops to that amount, it becomes {{BD2|Stunned}} and loses all {{BD2|Strength}}.",
					"Gains {{BD2|Plow}} {{Asc2|9|160}}. When its HP drops to that amount, it becomes {{BD2|Stunned}} and loses all {{BD2|Strength}}."
				}
			},
			{	Name = "Plow",
				IntentIcons = { "Attack3", "Buff" },
				Text = "Deals 18 ({{Asc2|9|20}}) damage. Gains 2 {{BD2|Strength}}.",
				AscText = {
					"Deals 18 damage. Gains 2 {{BD2|Strength}}.",
					"Deals {{Asc2|9|20}} damage. Gains 2 {{BD2|Strength}}."
				}
			},
			{	Name = "Stun",
				IntentIcons = { "Stun" },
				Text = "Stunned. Does nothing."
			},
			{	Name = "Beast Cry",
				IntentIcons = { "Debuff" },
				Text = "Applies 1 {{BD2|Ringing}}."
			},
			{	Name = "Stomp",
				IntentIcons = { "Attack3" },
				Text = "Deals 15 ({{Asc2|9|17}}) damage.",
				AscText = {
					"Deals 15 damage.",
					"Deals {{Asc2|9|17}} damage."
				}
			},
			{	Name = "Crush",
				IntentIcons = { "Attack3", "Buff" },
				Text = "Deals 17 ({{Asc2|9|19}}) damage. Gains 3 ({{Asc2|9|4}}) {{BD2|Strength}}.",
				AscText = {
					"Deals 17 damage. Gains 3 {{BD2|Strength}}.",
					"Deals {{Asc2|9|19}} damage. Gains {{Asc2|9|4}} {{BD2|Strength}}."
				}
			},
		}
	},
	["Kin Follower"] = {
		Type = "Boss",
		BaseHP = "58-59",
		AscHP = "62-63",
		Image = "StS2_Kin Follower.png",
		Icon = "StS2 Icon TheKinBoss.png",
		Link = "The Kin#Kin Follower",
		Debut = "{{2|Overgrowth}}",
		StartsWith = "{{BD2|Minion}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Overgrowth</span><br>* {{M|Kin Follower}} ×2<br>* {{M|Kin Priest}}",
		Intents = {
			{	Name = "Quick Slash",
				IntentIcons = { "Attack2" },
				Text = "Deals 5 damage."
			},
			{	Name = "Boomerang",
				IntentIcons = { "Attack1" },
				Text = "Deals 2 damage ×2."
			},
			{	Name = "Power Dance",
				IntentIcons = { "Buff" },
				Text = "Gains 2 ({{Asc2|9|3}}) {{BD2|Strength}}.",
				AscText = {
					"Gains 2 {{BD2|Strength}}.",
					"Gains {{Asc2|9|3}} {{BD2|Strength}}."
				}
			},
		}
	},
	["Kin Priest"] = {
		Type = "Boss",
		BaseHP = "190",
		AscHP = "199",
		Image = "StS2_Kin Priest.png",
		Icon = "StS2 Icon TheKinBoss.png",
		Link = "The Kin#Kin Priest",
		Debut = "{{2|Overgrowth}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Overgrowth</span><br>* {{M|Kin Follower}} ×2<br>* {{M|Kin Priest}}",
		Intents = {
			{	Name = "Orb of Frailty",
				IntentIcons = { "Attack2", "Debuff" },
				Text = "Deals 8 ({{Asc2|9|9}}) damage. Applies 1 {{BD2|Frail}}.",
				AscText = {
					"Deals 8 damage. Applies 1 {{BD2|Frail}}.",
					"Deals {{Asc2|9|9}} damage. Applies 1 {{BD2|Frail}}."
				}
			},
			{	Name = "Orb of Weakness",
				IntentIcons = { "Attack2", "Debuff" },
				Text = "Deals 8 ({{Asc2|9|9}}) damage. Applies 1 {{BD2|Weak}}.",
				AscText = {
					"Deals 8 damage. Applies 1 {{BD2|Weak}}.",
					"Deals {{Asc2|9|9}} damage. Applies 1 {{BD2|Weak}}."
				}
			},
			{	Name = "Soul Beam",
				IntentIcons = { "Attack2" },
				Text = "Deals 3 damage ×3."
			},
			{	Name = "Dark Ritual",
				IntentIcons = { "Buff" },
				Text = "Gains 2 ({{Asc2|9|3}}) {{BD2|Strength}}.",
				AscText = {
					"Gains 2 {{BD2|Strength}}.",
					"Gains {{Asc2|9|3}} {{BD2|Strength}}."
				}
			},
		}
	},
	["Vantom"] = {
		Type = "Boss",
		BaseHP = "173",
		AscHP = "183",
		Image = "StS2_Vantom.png",
		Icon = "StS2 Icon VantomBoss.png",
		Debut = "{{2|Overgrowth}}",
		StartsWith = "{{BD2|Slippery}} 9",
		Intents = {
			{	Name = "Ink Blot",
				IntentIcons = { "Attack2" },
				Text = "Deals 7 ({{Asc2|9|8}}) damage.",
				AscText = {
					"Deals 7 damage.",
					"Deals {{Asc2|9|8}} damage."
				}
			},
			{	Name = "Inky Lance",
				IntentIcons = { "Attack3" },
				Text = "Deals 6 ({{Asc2|9|7}}) damage ×2.",
				AscText = {
					"Deals 6 damage ×2.",
					"Deals {{Asc2|9|7}} damage ×2."
				}
			},
			{	Name = "Dismember",
				IntentIcons = { "Attack4", "StatusCard" },
				Text = "Deals 27 ({{Asc2|9|30}}) damage. Shuffles 3 {{C2|Wound}} into your discard pile.",
				AscText = {
					"Deals 27 damage. Shuffles 3 {{C2|Wound}} into your discard pile.",
					"Deals {{Asc2|9|30}} damage. Shuffles 3 {{C2|Wound}} into your discard pile."
				}
			},
			{	Name = "Prepare",
				IntentIcons = { "Buff" },
				Text = "Gains 2 {{BD2|Strength}}."
			},
		}
	},
	-- Act 1B Underdocks
	["Lagavulin Matriarch"] = {
		Type = "Boss",
		BaseHP = "222",
		AscHP = "233",
		Image = "StS2_Lagavulin Matriarch.png",
		Icon = "StS2 Icon LagavulinMatriarchBoss.png",
		Debut = "{{2|Underdocks}}",
		StartsWith = "{{BD2|Plating}} 12<br>{{BD2|Asleep}} 3",
		Intents = {
			{	Name = "Sleep",
				IntentIcons = { "Sleep" },
				Text = "Asleep. Does nothing."
			},
			{	Name = "Slash",
				IntentIcons = { "Attack3" },
				Text = "Deals 19 ({{Asc2|9|21}}) damage.",
				AscText = {
					"Deals 19 damage.",
					"Deals {{Asc2|9|21}} damage."
				}
			},
			{	Name = "Disembowel",
				IntentIcons = { "Attack3" },
				Text = "Deals 9 ({{Asc2|9|10}}) damage x2.",
				AscText = {
					"Deals 9 damage x2.",
					"Deals {{Asc2|9|10}} damage x2."
				}
			},
			{	Name = "Slash2", -- NEEDS REVIEW: move name "Slash2" not in localization, using codex ID; display name may differ
				IntentIcons = { "Attack3", "Defend" },
				Text = "Deals 12 ({{Asc2|9|14}}) damage. Gains 12 ({{Asc2|8|14}}) {{KW2|Block}}.",
				AscText = {
					"Deals 12 damage. Gains 12 {{KW2|Block}}.",
					"Deals {{Asc2|9|14}} damage. Gains {{Asc2|8|14}} {{KW2|Block}}."
				}
			},
			{	Name = "Soul Siphon",
				IntentIcons = { "Debuff", "Buff" },
				Text = "Removes 2 {{BD2|Strength}} and 2 {{BD2|Dexterity}} from the player. Gains 2 {{BD2|Strength}}."
			},
		}
	},
	["Soul Fysh"] = {
		Type = "Boss",
		BaseHP = "211",
		AscHP = "221",
		Image = "StS2_Soul Fysh.png",
		Icon = "StS2 Icon SoulFyshBoss.png",
		Debut = "{{2|Underdocks}}",
		Intents = {
			{	Name = "Beckon", -- NEEDS REVIEW: move name "Beckon" not in localization, using codex name
				IntentIcons = { "StatusCard" },
				Text = "Shuffles 2 {{C2|Beckon}} into your deck (1 into draw pile, 1 into discard pile)."
			},
			{	Name = "De-Gas",
				IntentIcons = { "Attack3" },
				Text = "Deals 16 ({{Asc2|9|17}}) damage.",
				AscText = {
					"Deals 16 damage.",
					"Deals {{Asc2|9|17}} damage."
				}
			},
			{	Name = "Gaze", -- NEEDS REVIEW: move name "Gaze" not in localization, using codex name
				IntentIcons = { "Attack2", "StatusCard" },
				Text = "Deals 7 ({{Asc2|9|8}}) damage. Shuffles 1 {{C2|Beckon}} into your discard pile.",
				AscText = {
					"Deals 7 damage. Shuffles 1 {{C2|Beckon}} into your discard pile.",
					"Deals {{Asc2|9|8}} damage. Shuffles 1 {{C2|Beckon}} into your discard pile."
				}
			},
			{	Name = "Fade", -- NEEDS REVIEW: move name "Fade" not in localization, using codex name
				IntentIcons = { "Buff" },
				Text = "Gains 2 {{BD2|Intangible}}."
			},
			{	Name = "Scream",
				IntentIcons = { "Attack3", "Debuff" },
				Text = "Deals 13 ({{Asc2|9|15}}) damage. Applies 3 {{BD2|Vulnerable}}.",
				AscText = {
					"Deals 13 damage. Applies 3 {{BD2|Vulnerable}}.",
					"Deals {{Asc2|9|15}} damage. Applies 3 {{BD2|Vulnerable}}."
				}
			},
		}
	},
	["Waterfall Giant"] = {
		Type = "Boss",
		BaseHP = "240",
		AscHP = "250",
		Image = "StS2_Waterfall Giant.png",
		Icon = "StS2 Icon WaterfallGiantBoss.png",
		Debut = "{{2|Underdocks}}",
		Intents = {
			{	Name = "Pressurize",
				IntentIcons = { "Buff" },
				Text = "Gains 15 ({{Asc2|9|20}}) {{BD2|Steam Eruption}}.",
				AscText = {
					"Gains 15 {{BD2|Steam Eruption}}.",
					"Gains {{Asc2|9|20}} {{BD2|Steam Eruption}}."
				}
			},
			{	Name = "Stomp",
				IntentIcons = { "Attack3", "Debuff", "Buff" },
				Text = "Deals 15 ({{Asc2|9|16}}) damage. Applies 1 {{BD2|Weak}}. Gains 3 {{BD2|Steam Eruption}}.",
				AscText = {
					"Deals 15 damage. Applies 1 {{BD2|Weak}}. Gains 3 {{BD2|Steam Eruption}}.",
					"Deals {{Asc2|9|16}} damage. Applies 1 {{BD2|Weak}}. Gains 3 {{BD2|Steam Eruption}}."
				}
			},
			{	Name = "Ram",
				IntentIcons = { "Attack3", "Buff" },
				Text = "Deals 10 ({{Asc2|9|11}}) damage. Gains 3 {{BD2|Steam Eruption}}.",
				AscText = {
					"Deals 10 damage. Gains 3 {{BD2|Steam Eruption}}.",
					"Deals {{Asc2|9|11}} damage. Gains 3 {{BD2|Steam Eruption}}."
				}
			},
			{	Name = "Siphon",
				IntentIcons = { "Heal", "Buff" },
				Text = "Heals 15 HP per player. Gains 3 {{BD2|Steam Eruption}}."
			},
			{	Name = "Pressure Gun",
				IntentIcons = { "Attack4", "Buff" },
				Text = "Deals 20 ({{Asc2|9|23}}) damage (increases by 5 each use). Gains 3 {{BD2|Steam Eruption}}.",
				AscText = {
					"Deals 20 damage (increases by 5 each use). Gains 3 {{BD2|Steam Eruption}}.",
					"Deals {{Asc2|9|23}} damage (increases by 5 each use). Gains 3 {{BD2|Steam Eruption}}."
				}
			},
			{	Name = "Pressure Up", -- NEEDS REVIEW: move name "Pressure Up" not in localization, using codex name
				IntentIcons = { "Attack3", "Buff" },
				Text = "Deals 13 ({{Asc2|9|14}}) damage. Gains 3 {{BD2|Steam Eruption}}.",
				AscText = {
					"Deals 13 damage. Gains 3 {{BD2|Steam Eruption}}.",
					"Deals {{Asc2|9|14}} damage. Gains 3 {{BD2|Steam Eruption}}."
				}
			},
			{	Name = "About To Blow", -- NEEDS REVIEW: move name "About To Blow" not in localization, using codex name
				IntentIcons = { "Stun" },
				Text = "Becomes invulnerable. Removes {{BD2|Steam Eruption}} and prepares to explode."
			},
			{	Name = "Explode", -- NEEDS REVIEW: move name "Explode" not in localization, using codex name
				IntentIcons = { "DeathBlow" },
				Text = "Deals damage equal to its stored {{BD2|Steam Eruption}} amount, then dies."
			},
		}
	},
	-- Hive Bosses
	["The Insatiable"] = {
		Type = "Boss",
		BaseHP = "321",
		AscHP = "341",
		Image = "StS2_The Insatiable.png",
		Icon = "StS2 Icon TheInsatiableBoss.png",
		Debut = "{{2|Hive}}",
		Intents = {
			{	Name = "Liquify Ground",
				IntentIcons = { "Buff", "StatusCard" },
				Text = "Gains 4 {{BD2|Sandpit}} (counted separately for each player). Shuffles 6 {{C2|Frantic Escape}} into each player's deck (3 into draw pile, 3 into discard pile)."
			},
			{	Name = "Thrash",
				IntentIcons = { "Attack3" },
				Text = "Deals 8 ({{Asc2|9|9}}) damage ×2.",
				AscText = {
					"Deals 8 damage ×2.",
					"Deals {{Asc2|9|9}} damage ×2."
				}
			},
			{	Name = "Lunging Bite",
				IntentIcons = { "Attack4" },
				Text = "Deals 28 ({{Asc2|9|31}}) damage.",
				AscText = {
					"Deals 28 damage.",
					"Deals {{Asc2|9|31}} damage."
				}
			},
			{	Name = "Salivate",
				IntentIcons = { "Buff" },
				Text = "Gains 2 ({{Asc2|9|3}}) {{BD2|Strength}}.",
				AscText = {
					"Gains 2 {{BD2|Strength}}.",
					"Gains {{Asc2|9|3}} {{BD2|Strength}}."
				}
			},
		}
	},
	["Knowledge Demon"] = {
		Type = "Boss",
		BaseHP = "379",
		AscHP = "399",
		Image = "StS2_Knowledge Demon.png",
		Icon = "StS2 Icon KnowledgeDemonBoss.png",
		Debut = "{{2|Hive}}",
		Intents = {
			{	Name = "Curse of Knowledge",
				IntentIcons = { "Debuff" },
				Text = "Each player chooses one of two debuffs to receive. The options change each time this move is used."
			},
			{	Name = "Slap",
				IntentIcons = { "Attack3" },
				Text = "Deals 17 ({{Asc2|9|18}}) damage.",
				AscText = {
					"Deals 17 damage.",
					"Deals {{Asc2|9|18}} damage."
				}
			},
			{	Name = "Knowledge Overwhelming",
				IntentIcons = { "Attack4" },
				Text = "Deals 8 ({{Asc2|9|9}}) damage ×3.",
				AscText = {
					"Deals 8 damage ×3.",
					"Deals {{Asc2|9|9}} damage ×3."
				}
			},
			{	Name = "Ponder",
				IntentIcons = { "Attack3", "Heal", "Buff" },
				Text = "Deals 11 ({{Asc2|9|13}}) damage. Heals 30 HP per player. Gains 2 ({{Asc2|9|3}}) {{BD2|Strength}}.",
				AscText = {
					"Deals 11 damage. Heals 30 HP per player. Gains 2 {{BD2|Strength}}.",
					"Deals {{Asc2|9|13}} damage. Heals 30 HP per player. Gains {{Asc2|9|3}} {{BD2|Strength}}."
				}
			},
		}
	},
	["Crusher"] = {
		Type = "Boss",
		BaseHP = "209",
		AscHP = "219",
		Image = "StS2_Crusher.png",
		Icon = "StS2 Icon KaiserCrabBoss.png",
		Link = "Kaiser Crab#Crusher",
		Debut = "{{2|Hive}}",
		StartsWith = "{{BD2|Back Attack}}<br>{{BD2|Crab Rage}}",
		Intents = {
			{	Name = "Thrash",
				IntentIcons = { "Attack3" },
				Text = "Deals 12 ({{Asc2|9|14}}) damage.",
				AscText = {
					"Deals 12 damage.",
					"Deals {{Asc2|9|14}} damage."
				}
			},
			{	Name = "Enlarging Strike",
				IntentIcons = { "Attack1" },
				Text = "Deals 4 damage."
			},
			{	Name = "Bug Sting",
				IntentIcons = { "Attack3", "Debuff" },
				Text = "Deals 6x2 ({{Asc2|9|7x2}}) damage. Applies 2 {{BD2|Weak}} and 2 {{BD2|Frail}}.",
				AscText = {
					"Deals 6x2 damage. Applies 2 {{BD2|Weak}} and 2 {{BD2|Frail}}.",
					"Deals {{Asc2|9|7x2}} damage. Applies 2 {{BD2|Weak}} and 2 {{BD2|Frail}}."
				}
			},
			{	Name = "Adapt",
				IntentIcons = { "Buff" },
				Text = "Gains 2 ({{Asc2|9|3}}) {{BD2|Strength}}.",
				AscText = {
					"Gains 2 {{BD2|Strength}}.",
					"Gains {{Asc2|9|3}} {{BD2|Strength}}."
				}
			},
			{	Name = "Guarded Strike",
				IntentIcons = { "Attack3", "Defend" },
				Text = "Deals 12 ({{Asc2|9|14}}) damage. Gains 18 {{KW2|Block}}.",
				AscText = {
					"Deals 12 damage. Gains 18 {{KW2|Block}}.",
					"Deals {{Asc2|9|14}} damage. Gains 18 {{KW2|Block}}."
				}
			},
		}
	},
	["Rocket"] = {
		Type = "Boss",
		BaseHP = "199",
		AscHP = "209",
		Image = "StS2_Rocket.png",
		Icon = "StS2 Icon KaiserCrabBoss.png",
		Link = "Kaiser Crab#Rocket",
		Debut = "{{2|Hive}}",
		StartsWith = "{{BD2|Back Attack}}<br>{{BD2|Crab Rage}}",
		Intents = {
			{	Name = "Targeting Reticle",
				IntentIcons = { "Attack1" },
				Text = "Deals 3 ({{Asc2|9|4}}) damage.",
				AscText = {
					"Deals 3 damage.",
					"Deals {{Asc2|9|4}} damage."
				}
			},
			{	Name = "Precision Beam",
				IntentIcons = { "Attack3" },
				Text = "Deals 18 ({{Asc2|9|20}}) damage.",
				AscText = {
					"Deals 18 damage.",
					"Deals {{Asc2|9|20}} damage."
				}
			},
			{	Name = "Charge Up",
				IntentIcons = { "Buff" },
				Text = "Gains 2 ({{Asc2|9|3}}) {{BD2|Strength}}.",
				AscText = {
					"Gains 2 {{BD2|Strength}}.",
					"Gains {{Asc2|9|3}} {{BD2|Strength}}."
				}
			},
			{	Name = "Laser",
				IntentIcons = { "Attack4" },
				Text = "Deals 31 ({{Asc2|9|35}}) damage.",
				AscText = {
					"Deals 31 damage.",
					"Deals {{Asc2|9|35}} damage."
				}
			},
			{	Name = "Recharge",
				IntentIcons = { "Sleep" },
				Text = "Does nothing."
			},
		}
	},
	-- Glory Bosses
	-- Doormaker boss encounter: Door spawns first, Doormaker appears when Door dies
	["Doormaker"] = {
		Type = "Boss",
		BaseHP = "489",
		AscHP = "512",
		Image = "StS2_Doormaker.png",
		Icon = "StS2 Icon DoormakerBoss.png",
		Debut = "{{2|Glory}}",
		Intents = {
			{	Name = "Dramatic Open",
				IntentIcons = { "Summon" },
				Text = "Transforms into the Doormaker. Sets current buff to {{BD2|Hunger}}."
			},
			{	Name = "Hunger",
				IntentIcons = { "Attack4" },
				Text = "Deals 30 ({{Asc2|9|35}}) damage. Swaps current buff to {{BD2|Scrutiny}}.",
				AscText = {
					"Deals 30 damage. Swaps current buff to {{BD2|Scrutiny}}.",
					"Deals {{Asc2|9|35}} damage. Swaps current buff to {{BD2|Scrutiny}}."
				}
			},
			{	Name = "Scrutiny",
				IntentIcons = { "Attack4"},
				Text = "Deals 24 ({{Asc2|9|26}}) damage. Swaps current buff to {{BD2|Grasp}}.",
				AscText = {
					"Deals 24 damage. Swaps current buff to {{BD2|Grasp}}.",
					"Deals {{Asc2|9|26}} damage. Swaps current buff to {{BD2|Grasp}}."
				}
			},
			{	Name = "Grasp",
				IntentIcons = { "Attack4", "Buff"},
				Text = "Deals 10x2 ({{Asc2|9|11x2}}) damage. Gains 3 {{BD2|Strength}}. Swaps current buff to {{BD2|Hunger}}.",
				AscText = {
					"Deals 10x2 damage. Gains 3 {{BD2|Strength}}. Swaps current buff to {{BD2|Hunger}}.",
					"Deals {{Asc2|9|11x2}} damage. Gains 3 {{BD2|Strength}}. Swaps current buff to {{BD2|Hunger}}."
				}
			}
		}
	},
	["Queen"] = {
		Type = "Boss",
		BaseHP = "400",
		AscHP = "419",
		Image = "StS2_Queen.png",
		Icon = "StS2 Icon QueenBoss.png",
		Debut = "{{2|Glory}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Glory</span><br>* {{M|Torch Head Amalgam}}",
		Intents = {
			{	Name = "Puppet Strings",
				IntentIcons = { "CardDebuff" },
				Text = "Applies 3 {{BD2|Chains of Binding}} to all players."
			},
			{	Name = "You're Mine",
				IntentIcons = { "Debuff" },
				Text = "Applies 99 {{BD2|Frail}}, 99 {{BD2|Weak}}, and 99 {{BD2|Vulnerable}} to all players."
			},
			{	Name = "Burn Bright for Me",
				IntentIcons = { "Buff", "Defend" },
				Text = "Gives 1 {{BD2|Strength}} to {{M|Torch Head Amalgam||2}}. Gains 20 {{KW2|Block}}."
			},
			{	Name = "Off with Your Head",
				IntentIcons = { "Attack3" },
				Text = "Deals 3 ({{Asc2|9|4}}) damage x5.",
				AscText = {
					"Deals 3 damage x5.",
					"Deals {{Asc2|9|4}} damage x5."
				}
			},
			{	Name = "Execution",
				IntentIcons = { "Attack3" },
				Text = "Deals 15 ({{Asc2|9|18}}) damage.",
				AscText = {
					"Deals 15 damage.",
					"Deals {{Asc2|9|18}} damage."
				}
			},
			{	Name = "Enrage",
				IntentIcons = { "Buff" },
				Text = "Gains 2 {{BD2|Strength}}."
			}
		}
	},
	["Torch Head Amalgam"] = {
		Type = "Minion",
		BaseHP = "199",
		AscHP = "211",
		Image = "StS2_Torch Head Amalgam.png",
		Icon = "StS2 Icon QueenBoss.png",
		Link = "Queen#Torch Head Amalgam",
		Debut = "{{2|Glory}}",
		InPartyWith = "<span class='enemy-infobox-party-header'>Glory</span><br>* {{M|Queen}}",
		StartsWith = "{{BD2|Minion}}",
		Intents = {
			{	Name = "Strong Tackle",
				IntentIcons = { "Attack3" },
				Text = "Deals 26 ({{Asc2|9|32}}) damage.",
				AscText = {
					"Deals 26 damage.",
					"Deals {{Asc2|9|32}} damage."
				}
			},
			{	Name = "Tackle",
				IntentIcons = { "Attack3" },
				Text = "Deals 18 ({{Asc2|9|22}}) damage.",
				AscText = {
					"Deals 18 damage.",
					"Deals {{Asc2|9|22}} damage."
				}
			},
			{	Name = "Beam",
				IntentIcons = { "Attack3" },
				Text = "Deals 8 damage x3."
			},
			{	Name = "Weak Tackle",
				IntentIcons = { "Attack3" },
				Text = "Deals 14 ({{Asc2|9|16}}) damage.",
				AscText = {
					"Deals 14 damage.",
					"Deals {{Asc2|9|16}} damage."
				}
			}
		}
	},
	-- Test Subject: 3-phase boss, one entry per phase
	["Test Subject"] = {
		Type = "Boss",
		BaseHP = "100",
		AscHP = "111",
		Image = "StS2_Test Subject.png",
		Icon = "StS2 Icon TestSubjectBoss.png",
		Link = "Test Subject#Phase 1",
		Debut = "{{2|Glory}}",
		StartsWith = "{{BD2|Adaptable}}, {{BD2|Enrage}} 2 ({{Asc2|9|3}})",
		Intents = {
			{	Name = "Bite",
				IntentIcons = { "Attack3" },
				Text = "Deals 20 ({{Asc2|9|22}}) damage.",
				AscText = {
					"Deals 20 damage.",
					"Deals {{Asc2|9|22}} damage."
				}
			},
			{	Name = "Skull Bash",
				IntentIcons = { "Attack3", "Debuff" },
				Text = "Deals 14 ({{Asc2|9|16}}) damage. Applies 1 {{BD2|Vulnerable}}.",
				AscText = {
					"Deals 14 damage. Applies 1 {{BD2|Vulnerable}}.",
					"Deals {{Asc2|9|16}} damage. Applies 1 {{BD2|Vulnerable}}."
				}
			},
		}
	},
	["Test Subject (Phase 2)"] = {
		Type = "Boss",
		BaseHP = "200",
		AscHP = "212",
		Image = "StS2_Test Subject_Phase_2.png",
		Icon = "StS2 Icon TestSubjectBoss.png",
		Link = "Test Subject#Phase 2",
		Debut = "{{2|Glory}}",
		StartsWith = "{{BD2|Adaptable}}, {{BD2|Painful Stabs}}",
		Intents = {
			{	Name = "Multi-Claw",
				IntentIcons = { "Attack4" },
				Text = "Deals 10 ({{Asc2|9|11}}) damage x3 (increases by 1 hit each use).",
				AscText = {
					"Deals 10 damage x3 (increases by 1 hit each use).",
					"Deals {{Asc2|9|11}} damage x3 (increases by 1 hit each use)."
				}
			},
		}
	},
	["Test Subject (Phase 3)"] = {
		Type = "Boss",
		BaseHP = "300",
		AscHP = "313",
		Image = "StS2_Test Subject_Phase_3.png",
		Icon = "StS2 Icon TestSubjectBoss.png",
		Link = "Test Subject#Phase 3",
		Debut = "{{2|Glory}}",
		StartsWith = "{{BD2|Nemesis}}",
		Intents = {
			{	Name = "Lacerate",
				IntentIcons = { "Attack4" },
				Text = "Deals 10 ({{Asc2|9|11}}) damage x3.",
				AscText = {
					"Deals 10 damage x3.",
					"Deals {{Asc2|9|11}} damage x3."
				}
			},
			{	Name = "Big Pounce",
				IntentIcons = { "Attack5" },
				Text = "Deals 45 damage."
			},
			{	Name = "Burning Growl",
				IntentIcons = { "StatusCard", "Buff" },
				Text = "Shuffles 3 ({{Asc2|9|5}}) {{C2|Burn}} into discard pile. Gains 2 ({{Asc2|9|3}}) {{BD2|Strength}}.",
				AscText = {
					"Shuffles 3 {{C2|Burn}} into discard pile. Gains 2 {{BD2|Strength}}.",
					"Shuffles {{Asc2|9|5}} {{C2|Burn}} into discard pile. Gains {{Asc2|9|3}} {{BD2|Strength}}."
				}
			},
		}
	},
	["Aeonglass"] = {
		Type = "Boss",
		BaseHP = "512",
		AscHP = "535",
		Image = "StS2_Aeonglass.png",
		Icon = "StS2 Icon AeonglassBoss.png",
		Debut = "{{2|Glory}}",
		StartsWith = "{{BD2|Withering Presence|<span style='text-wrap: wrap'>Withering Presence</span>}}<br>{{BD2|Artifact}} 3",
		Intents = {
			{	Name = "Ebb",
				IntentIcons = { "Attack4", "Defend" },
				Text = "Deals 22 ({{Asc2|9|26}}) damage. Gains 33 {{KW2|Block}}.",
				AscText = {
					"Deals 22 damage. Gains 33 {{KW2|Block}}.",
					"Deals {{Asc2|9|26}} damage. Gains 33 {{KW2|Block}}."
				}
			},
			{	Name = "Eye Lasers",
				IntentIcons = { "Attack4" },
				Text = "Deals 11 ({{Asc2|9|12}}) damage x2.",
				AscText = {
					"Deals 11 damage x2.",
					"Deals {{Asc2|9|12}} damage x2."
				}
			},
			{	Name = "Increasing Intensity",
				IntentIcons = { "StatusCard", "Buff"},
				Text = "Shuffles 1 ({{Asc2|9|2}}) {{C2|Wither|Wither+X}} into your discard pile. Gains 2({{Asc2|9|3}}) + X {{BD2|Strength}}. Upgrade all {{C2|Wither|Withers}}. {{BD2|Withering Presence}} effect now creates {{C2|Wither|Withers + X}}.",
				AscText = {
					"Shuffles 1 {{C2|Wither|Wither+X}} into your discard pile. Gains 2 + X {{BD2|Strength}}. Upgrade all {{C2|Wither|Withers}}. {{BD2|Withering Presence}} effect now creates {{C2|Wither|Withers + X}}.",
					"Shuffles {{Asc2|9|2}} {{C2|Wither|Wither+X}} into your discard pile. Gains {{Asc2|9|3}} + X {{BD2|Strength}}. Upgrade all {{C2|Wither|Withers}}.  {{BD2|Withering Presence}} effect now creates {{C2|Wither|Withers + X}}."
				}
			},
		}
	},
}

local formatted = {}
for name, enemy in pairs(all_data) do
	enemy.EditLink = "Module:Enemies/StS2_data/Bosses"
	formatted[name] = enemy
end

return formatted