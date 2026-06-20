"""
A curated, best-effort list of FTL achievement ids.

The real game ships this data in achievements.xml inside its own data.dat,
which isn't bundled with this tool (same reason ProfileParser.java needs
DataManager/Achievement lookups loaded from the game itself). This list was
assembled from FTL's publicly documented achievement set (general
progression/skill achievements, plus three per-ship achievements for each
of the 9 base-game ships) and is meant for generating a "fully unlocked"
starting point -- not guaranteed to be byte-for-byte identical to what your
particular FTL version considers valid. Feel free to edit the JSON output
by hand to add/remove anything specific to your version (e.g. Advanced
Edition quest achievements, Lanius/"ANAEROBIC" ship achievements).
"""

from __future__ import annotations

from typing import Dict, List

# Maps each per-ship "skill" achievement id to the ship base id it belongs
# to. The game auto-unlocks a ship's Type-B layout once its Type-A layout is
# unlocked AND 2 of these 3 achievements are completed -- there's no
# separate "unlocked_b" flag stored in ae_prof.sav itself.
ACHIEVEMENT_SHIP_IDS: Dict[str, str] = {
	# Kestrel
	"ACH_UNITED_FEDERATION": "PLAYER_SHIP_HARD",
	"ACH_FULL_ARSENAL": "PLAYER_SHIP_HARD",
	"ACH_TOUGH_SHIP": "PLAYER_SHIP_HARD",
	# Zoltan (internal name "Energy")
	"ACH_ENERGY_SHIELDS": "PLAYER_SHIP_ENERGY",
	"ACH_ENERGY_POWER": "PLAYER_SHIP_ENERGY",
	"ACH_ENERGY_MANPOWER": "PLAYER_SHIP_ENERGY",
	# Stealth
	"ACH_STEALTH_DESTROY": "PLAYER_SHIP_STEALTH",
	"ACH_STEALTH_AVOID": "PLAYER_SHIP_STEALTH",
	"ACH_STEALTH_TACTICAL": "PLAYER_SHIP_STEALTH",
	# Engi (internal name "Circle")
	"ACH_ROBOTIC": "PLAYER_SHIP_CIRCLE",
	"ACH_ONLY_DRONES": "PLAYER_SHIP_CIRCLE",
	"ACH_IONED": "PLAYER_SHIP_CIRCLE",
	# Rock
	"ACH_ROCK_FIRE": "PLAYER_SHIP_ROCK",
	"ACH_ROCK_MISSILES": "PLAYER_SHIP_ROCK",
	"ACH_ROCK_CRYSTAL": "PLAYER_SHIP_ROCK",
	# Mantis
	"ACH_MANTIS_CREW_DEAD": "PLAYER_SHIP_MANTIS",
	"ACH_MANTIS_SLAUGHTER": "PLAYER_SHIP_MANTIS",
	"ACH_MANTIS_SURVIVOR": "PLAYER_SHIP_MANTIS",
	# Slug (internal name "Jelly")
	"ACH_SLUG_VISION": "PLAYER_SHIP_JELLY",
	"ACH_SLUG_NEBULA": "PLAYER_SHIP_JELLY",
	"ACH_SLUG_BIO": "PLAYER_SHIP_JELLY",
	# Federation
	"ACH_FED_PATIENCE": "PLAYER_SHIP_FED",
	"ACH_FED_DIPLOMACY": "PLAYER_SHIP_FED",
	"ACH_FED_UPGRADE": "PLAYER_SHIP_FED",
	# Crystal
	"ACH_CRYSTAL_SHARD": "PLAYER_SHIP_CRYSTAL",
	"ACH_CRYSTAL_LOCKDOWN": "PLAYER_SHIP_CRYSTAL",
	"ACH_CRYSTAL_CLASH": "PLAYER_SHIP_CRYSTAL",
}

# Ships this tool has no per-ship achievement data for (e.g. the Lanius
# Cruiser's AE-era achievements aren't in our curated list), so layout-B
# status can't be derived for them -- it'll show up as "unknown".
SHIPS_WITHOUT_KNOWN_ACHIEVEMENTS: List[str] = ["PLAYER_SHIP_ANAEROBIC"]


def ship_achievement_ids(ship_base_id: str) -> List[str]:
	"""The (up to 3) per-ship achievement ids known for this ship."""
	return [aid for aid, sid in ACHIEVEMENT_SHIP_IDS.items() if sid == ship_base_id]


# General, non-ship-specific achievements (not tied to a particular ship).
GENERAL_ACHIEVEMENT_IDS: List[str] = [
	"ACH_SECTOR_5",
	"ACH_SECTOR_8",
	"ACH_WIN_EASY",
	"ACH_WIN_NORMAL",
	"ACH_UNLOCK_ALL",
	"ACH_SCRAP",
	"ACH_SHIPS",
	"ACH_NO_UPGRADES",
	"ACH_PACIFIST",
	"ACH_NO_REPAIR",
	"ACH_NO_MISSILES",
	"ACH_NO_DRONES",
	"ACH_NO_BUYING",
	"ACH_NO_DEATH",
	"ACH_BURNING",
	"ACH_BAD_DODGING",
	"ACH_ONE_VOLLEY",
	"ACH_BOARDING_DRONE",
	"ACH_INVADE_SHIP",
	"ACH_SLICE_DICE",
	"ACH_SUFFOCATE",
]

# Three per-ship "skill" achievements for each of the 9 base-game ships.
SHIP_ACHIEVEMENT_IDS: List[str] = [
	# Kestrel
	"ACH_UNITED_FEDERATION",
	"ACH_FULL_ARSENAL",
	"ACH_TOUGH_SHIP",
	# Zoltan (internal name "Energy")
	"ACH_ENERGY_SHIELDS",
	"ACH_ENERGY_POWER",
	"ACH_ENERGY_MANPOWER",
	# Stealth
	"ACH_STEALTH_DESTROY",
	"ACH_STEALTH_AVOID",
	"ACH_STEALTH_TACTICAL",
	# Engi (internal name "Circle")
	"ACH_ROBOTIC",
	"ACH_ONLY_DRONES",
	"ACH_IONED",
	# Rock
	"ACH_ROCK_FIRE",
	"ACH_ROCK_MISSILES",
	"ACH_ROCK_CRYSTAL",
	# Mantis
	"ACH_MANTIS_CREW_DEAD",
	"ACH_MANTIS_SLAUGHTER",
	"ACH_MANTIS_SURVIVOR",
	# Slug (internal name "Jelly")
	"ACH_SLUG_VISION",
	"ACH_SLUG_NEBULA",
	"ACH_SLUG_BIO",
	# Federation
	"ACH_FED_PATIENCE",
	"ACH_FED_DIPLOMACY",
	"ACH_FED_UPGRADE",
	# Crystal
	"ACH_CRYSTAL_SHARD",
	"ACH_CRYSTAL_LOCKDOWN",
	"ACH_CRYSTAL_CLASH",
]

# Per-ship "defeat the flagship" victory achievements. Each one tracks which
# of the ship's three (A/B/C) layouts it was earned with -- this is the
# "_VICTORY" naming convention used elsewhere in this tool to decide whether
# an achievement needs those three extra per-layout fields.
VICTORY_ACHIEVEMENT_BASE_SHIP_IDS: List[str] = [
	"PLAYER_SHIP_HARD",
	"PLAYER_SHIP_STEALTH",
	"PLAYER_SHIP_MANTIS",
	"PLAYER_SHIP_CIRCLE",
	"PLAYER_SHIP_FED",
	"PLAYER_SHIP_JELLY",
	"PLAYER_SHIP_ROCK",
	"PLAYER_SHIP_ENERGY",
	"PLAYER_SHIP_CRYSTAL",
]

# Only present in format-9 (Advanced Edition) profiles.
VICTORY_ACHIEVEMENT_BASE_SHIP_IDS_AE_ONLY: List[str] = [
	"PLAYER_SHIP_ANAEROBIC",
]


def victory_achievement_id(ship_base_id: str) -> str:
	return f"{ship_base_id}_VICTORY"


def all_achievement_ids(file_format: int) -> List[str]:
	"""All known achievement ids appropriate for the given profile format."""
	ids = list(GENERAL_ACHIEVEMENT_IDS) + list(SHIP_ACHIEVEMENT_IDS)

	ship_ids = list(VICTORY_ACHIEVEMENT_BASE_SHIP_IDS)
	if file_format == 9:
		ship_ids += VICTORY_ACHIEVEMENT_BASE_SHIP_IDS_AE_ONLY

	ids += [victory_achievement_id(s) for s in ship_ids]
	return ids
