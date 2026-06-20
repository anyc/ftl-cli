"""
Data model and binary parser for FTL's "ae_prof.sav" file.

Ported from net.blerf.ftl.parser.ProfileParser / net.blerf.ftl.model.Profile
in the Java "FTL Profile Editor" project. Only reading is implemented for now;
writing will come in a later step once editing commands are added.

Supported file formats (the int at byte 0 of the file):
	4 -> FTL 1.0 - 1.03.3
	9 -> FTL 1.5.4+ (Advanced Edition and later, including 1.6.1's UTF-8 strings)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional, Union

from . import binary


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Difficulty(Enum):
	EASY = "EASY"
	NORMAL = "NORMAL"
	HARD = "HARD"


class NewbieTipLevel(Enum):
	SHIPS_UNLOCKED = "SHIPS_UNLOCKED"
	SHIP_LIST_INTRO = "SHIP_LIST_INTRO"
	VETERAN = "VETERAN"


# ---------------------------------------------------------------------------
# Ship id tables (order matters -- it's positional in the binary format)
# ---------------------------------------------------------------------------

# Friendly names for the internal ship ids. FTL's own internal names don't
# always match what's shown in-game (e.g. "JELLY" -> Slug, "ENERGY" -> Zoltan).
SHIP_NAMES: Dict[str, str] = {
	"PLAYER_SHIP_HARD": "Kestrel",
	"PLAYER_SHIP_STEALTH": "Stealth Cruiser",
	"PLAYER_SHIP_MANTIS": "Mantis Cruiser",
	"PLAYER_SHIP_CIRCLE": "Engi Cruiser",
	"PLAYER_SHIP_FED": "Federation Cruiser",
	"PLAYER_SHIP_JELLY": "Slug Cruiser",
	"PLAYER_SHIP_ROCK": "Rock Cruiser",
	"PLAYER_SHIP_ENERGY": "Zoltan Cruiser",
	"PLAYER_SHIP_CRYSTAL": "Crystal Cruiser",
	"PLAYER_SHIP_ANAEROBIC": "Lanius Cruiser",
	"UNKNOWN_ALPHA": "Unknown Alpha (unused slot)",
	"UNKNOWN_BETA": "Unknown Beta (unused slot)",
	"UNKNOWN_GAMMA": "Unknown Gamma (unused slot)",
}


def _ship_ids_for_format(file_format: int) -> List[str]:
	ids = [
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
	if file_format == 4:
		ids += ["UNKNOWN_ALPHA", "UNKNOWN_BETA", "UNKNOWN_GAMMA"]
	elif file_format == 9:
		ids += ["PLAYER_SHIP_ANAEROBIC", "UNKNOWN_BETA", "UNKNOWN_GAMMA"]
	else:
		raise binary.ProfileFormatError(f"Unsupported file format: {file_format}")
	return ids


def ship_display_name(ship_id: str) -> str:
	return SHIP_NAMES.get(ship_id, ship_id)


# ---------------------------------------------------------------------------
# Achievement "is this a victory achievement" heuristic
# ---------------------------------------------------------------------------
#
# The real game ships an achievements.xml that flags each achievement as a
# victory/quest/normal achievement; the Java editor needs that file loaded
# from FTL's data.dat to know whether to read the 3 per-layout variant flags
# for a given achievement. This CLI doesn't bundle FTL's game data, so it
# uses the well-documented naming convention instead: every ship-victory
# achievement is named "<SHIP_BASE_ID>_VICTORY" (e.g. PLAYER_SHIP_HARD_VICTORY).

def _looks_like_victory_achievement(achievement_id: str) -> bool:
	return achievement_id.endswith("_VICTORY")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class AchievementRecord:
	achievement_id: str
	difficulty: Difficulty
	completed_with_type_a: Optional[Difficulty] = None
	completed_with_type_b: Optional[Difficulty] = None
	completed_with_type_c: Optional[Difficulty] = None

	@property
	def is_victory_achievement(self) -> bool:
		return _looks_like_victory_achievement(self.achievement_id)


@dataclass
class ShipAvailability:
	ship_id: str
	unlocked_a: bool = False
	unlocked_c: bool = False

	@property
	def unlocked(self) -> bool:
		"""True if any layout of this ship is unlocked."""
		return self.unlocked_a or self.unlocked_c


@dataclass
class Score:
	ship_name: str
	ship_id: str
	value: int
	sector: int
	difficulty: Difficulty
	victory: bool
	dlc_enabled: bool = False


@dataclass
class CrewRecord:
	name: str
	race: str
	male: bool
	value: int


@dataclass
class Stats:
	top_scores: List[Score] = field(default_factory=list)
	ship_best: List[Score] = field(default_factory=list)
	int_records: Dict[str, int] = field(default_factory=dict)
	crew_records: Dict[str, CrewRecord] = field(default_factory=dict)


@dataclass
class Profile:
	file_format: int
	newbie_tip_level: Optional[NewbieTipLevel] = None
	achievements: List[AchievementRecord] = field(default_factory=list)
	ship_unlock_map: Dict[str, ShipAvailability] = field(default_factory=dict)
	stats: Optional[Stats] = None

	def unlocked_ships(self) -> List[ShipAvailability]:
		return [s for s in self.ship_unlock_map.values() if s.unlocked]


STAT_INT_FIELDS = [
	"MOST_SHIPS_DEFEATED",
	"TOTAL_SHIPS_DEFEATED",
	"MOST_BEACONS_EXPLORED",
	"TOTAL_BEACONS_EXPLORED",
	"MOST_SCRAP_COLLECTED",
	"TOTAL_SCRAP_COLLECTED",
	"MOST_CREW_HIRED",
	"TOTAL_CREW_HIRED",
	"TOTAL_GAMES_PLAYED",
	"TOTAL_VICTORIES",
]

STAT_CREW_FIELDS = [
	"MOST_REPAIRS",
	"MOST_COMBAT_KILLS",
	"MOST_PILOTED_EVASIONS",
	"MOST_JUMPS_SURVIVED",
	"MOST_SKILL_MASTERIES",
]


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def _read_difficulty_flag(flag: int, file_format: int, context: str) -> Difficulty:
	if flag == 0:
		return Difficulty.EASY if file_format == 9 else Difficulty.NORMAL
	elif flag == 1:
		return Difficulty.NORMAL if file_format == 9 else Difficulty.EASY
	elif flag == 2 and file_format == 9:
		return Difficulty.HARD
	raise binary.ProfileFormatError(f"Unsupported difficulty flag for {context}: {flag}")


def _read_achievement_difficulty_flag(flag: int, file_format: int, ach_id: str) -> Difficulty:
	# Achievement difficulty flags (unlike score flags) are NOT swapped
	# between format 4 and format 9 in the original parser.
	if flag == 0:
		return Difficulty.EASY
	elif flag == 1:
		return Difficulty.NORMAL
	elif flag == 2 and file_format == 9:
		return Difficulty.HARD
	raise binary.ProfileFormatError(
		f"Unsupported difficulty flag for achievement \"{ach_id}\": {flag}"
	)


def _read_achievements(f: BinaryIO, file_format: int, unicode_strings: bool) -> List[AchievementRecord]:
	count = binary.read_int(f)
	achievements: List[AchievementRecord] = []

	for i in range(count):
		ach_id = binary.read_string(f, unicode_strings)
		diff_flag = binary.read_int(f)
		diff = _read_achievement_difficulty_flag(diff_flag, file_format, ach_id)

		rec = AchievementRecord(achievement_id=ach_id, difficulty=diff)

		if file_format == 9 and _looks_like_victory_achievement(ach_id):
			variant_diffs: List[Optional[Difficulty]] = []
			for _ in range(3):
				variant_flag = binary.read_int(f)
				if variant_flag == -1:
					variant_diffs.append(None)
				elif variant_flag == 0:
					variant_diffs.append(Difficulty.EASY)
				elif variant_flag == 1:
					variant_diffs.append(Difficulty.NORMAL)
				elif variant_flag == 2:
					variant_diffs.append(Difficulty.HARD)
				else:
					raise binary.ProfileFormatError(
						f"Unsupported per-layout difficulty flag for achievement "
						f"{i} (\"{ach_id}\"): {variant_flag}"
					)
			rec.completed_with_type_a = variant_diffs[0]
			rec.completed_with_type_b = variant_diffs[1]
			rec.completed_with_type_c = variant_diffs[2]

		achievements.append(rec)

	return achievements


def _read_ship_unlocks(f: BinaryIO, file_format: int) -> Dict[str, ShipAvailability]:
	ship_ids = _ship_ids_for_format(file_format)
	unlock_map: Dict[str, ShipAvailability] = {}

	for ship_id in ship_ids:
		unlocked_a = binary.read_bool(f)
		unlocked_c = False
		if file_format == 9:
			unlocked_c = binary.read_bool(f)
		unlock_map[ship_id] = ShipAvailability(ship_id, unlocked_a, unlocked_c)

	return unlock_map


def _read_score_list(f: BinaryIO, file_format: int, unicode_strings: bool) -> List[Score]:
	count = binary.read_int(f)
	scores: List[Score] = []

	for i in range(count):
		ship_name = binary.read_string(f, unicode_strings)
		ship_id = binary.read_string(f, unicode_strings)
		value = binary.read_int(f)
		sector = binary.read_int(f)
		victory = binary.read_int(f) == 1
		diff_flag = binary.read_int(f)
		diff = _read_difficulty_flag(diff_flag, file_format, f"score {i} (\"{ship_name}\")")

		dlc_enabled = False
		if file_format == 9:
			dlc_enabled = binary.read_bool(f)

		scores.append(Score(ship_name, ship_id, value, sector, diff, victory, dlc_enabled))

	return scores


def _read_crew_record(f: BinaryIO, unicode_strings: bool) -> CrewRecord:
	value = binary.read_int(f)
	name = binary.read_string(f, unicode_strings)
	race = binary.read_string(f, unicode_strings)
	male = binary.read_bool(f)
	return CrewRecord(name, race, male, value)


def _read_stats(f: BinaryIO, file_format: int, unicode_strings: bool) -> Stats:
	stats = Stats()
	stats.top_scores = _read_score_list(f, file_format, unicode_strings)
	stats.ship_best = _read_score_list(f, file_format, unicode_strings)

	for name in STAT_INT_FIELDS:
		stats.int_records[name] = binary.read_int(f)

	for name in STAT_CREW_FIELDS:
		stats.crew_records[name] = _read_crew_record(f, unicode_strings)

	return stats


def _write_achievements(f: BinaryIO, achievements: List[AchievementRecord], file_format: int, unicode_strings: bool) -> None:
	binary.write_int(f, len(achievements))

	for rec in achievements:
		binary.write_string(f, rec.achievement_id, unicode_strings)

		if rec.difficulty == Difficulty.EASY:
			diff_flag = 0
		elif rec.difficulty == Difficulty.NORMAL:
			diff_flag = 1
		elif rec.difficulty == Difficulty.HARD and file_format == 9:
			diff_flag = 2
		else:
			diff_flag = 0
		binary.write_int(f, diff_flag)

		if file_format == 9 and rec.is_victory_achievement:
			for diff in (rec.completed_with_type_a, rec.completed_with_type_b, rec.completed_with_type_c):
				if diff is None:
					variant_flag = -1
				elif diff == Difficulty.EASY:
					variant_flag = 0
				elif diff == Difficulty.NORMAL:
					variant_flag = 1
				else:
					variant_flag = 2
				binary.write_int(f, variant_flag)


def _write_ship_unlocks(f: BinaryIO, ship_unlock_map: Dict[str, ShipAvailability], file_format: int) -> None:
	ship_ids = _ship_ids_for_format(file_format)

	for ship_id in ship_ids:
		avail = ship_unlock_map.get(ship_id)
		unlocked_a = avail.unlocked_a if avail else False
		unlocked_c = avail.unlocked_c if avail else False

		binary.write_bool(f, unlocked_a)
		if file_format == 9:
			binary.write_bool(f, unlocked_c)


def _write_score_list(f: BinaryIO, scores: List[Score], file_format: int, unicode_strings: bool) -> None:
	binary.write_int(f, len(scores))

	for score in scores:
		binary.write_string(f, score.ship_name, unicode_strings)
		binary.write_string(f, score.ship_id, unicode_strings)
		binary.write_int(f, score.value)
		binary.write_int(f, score.sector)
		binary.write_int(f, 1 if score.victory else 0)

		if score.difficulty == Difficulty.NORMAL and file_format == 4:
			diff_flag = 0
		elif score.difficulty == Difficulty.EASY and file_format == 4:
			diff_flag = 1
		elif score.difficulty == Difficulty.EASY and file_format == 9:
			diff_flag = 0
		elif score.difficulty == Difficulty.NORMAL and file_format == 9:
			diff_flag = 1
		elif score.difficulty == Difficulty.HARD and file_format == 9:
			diff_flag = 2
		else:
			diff_flag = 0
		binary.write_int(f, diff_flag)

		if file_format == 9:
			binary.write_bool(f, score.dlc_enabled)


def _write_crew_record(f: BinaryIO, rec: CrewRecord, unicode_strings: bool) -> None:
	binary.write_int(f, rec.value)
	binary.write_string(f, rec.name, unicode_strings)
	binary.write_string(f, rec.race, unicode_strings)
	binary.write_bool(f, rec.male)


def _write_stats(f: BinaryIO, stats: Stats, file_format: int, unicode_strings: bool) -> None:
	_write_score_list(f, stats.top_scores, file_format, unicode_strings)
	_write_score_list(f, stats.ship_best, file_format, unicode_strings)

	for name in STAT_INT_FIELDS:
		binary.write_int(f, stats.int_records.get(name, 0))

	for name in STAT_CREW_FIELDS:
		rec = stats.crew_records.get(name) or CrewRecord(name="", race="", male=True, value=0)
		_write_crew_record(f, rec, unicode_strings)


def write_profile(dest: Union[str, Path, BinaryIO], profile: Profile) -> None:
	"""Serialize a Profile back out to an ae_prof.sav path or open binary stream."""
	if isinstance(dest, (str, Path)):
		with open(dest, "wb") as f:
			write_profile(f, profile)
		return

	f = dest
	file_format = profile.file_format
	if file_format not in (4, 9):
		raise binary.ProfileFormatError(f"Unsupported file format: {file_format}")

	unicode_strings = file_format >= 9
	binary.write_int(f, file_format)

	if file_format == 9:
		level = profile.newbie_tip_level or NewbieTipLevel.VETERAN
		newbie_flag = {
			NewbieTipLevel.SHIPS_UNLOCKED: 0,
			NewbieTipLevel.SHIP_LIST_INTRO: 1,
			NewbieTipLevel.VETERAN: 2,
		}[level]
		binary.write_int(f, newbie_flag)

	_write_achievements(f, profile.achievements, file_format, unicode_strings)
	_write_ship_unlocks(f, profile.ship_unlock_map, file_format)
	_write_stats(f, profile.stats or Stats(), file_format, unicode_strings)


# ---------------------------------------------------------------------------
# JSON (de)serialization helpers, used by the CLI's "export"/"update" commands
# ---------------------------------------------------------------------------

def _diff_from_str(value: Optional[str]) -> Optional[Difficulty]:
	if value is None:
		return None
	return Difficulty(value)


def achievement_from_dict(d: dict) -> AchievementRecord:
	return AchievementRecord(
		achievement_id=d["achievement_id"],
		difficulty=Difficulty(d["difficulty"]),
		completed_with_type_a=_diff_from_str(d.get("completed_with_type_a")),
		completed_with_type_b=_diff_from_str(d.get("completed_with_type_b")),
		completed_with_type_c=_diff_from_str(d.get("completed_with_type_c")),
	)


def ship_availability_from_dict(ship_id: str, d: dict) -> ShipAvailability:
	return ShipAvailability(
		ship_id=d.get("ship_id", ship_id),
		unlocked_a=bool(d.get("unlocked_a", False)),
		unlocked_c=bool(d.get("unlocked_c", False)),
	)


def score_from_dict(d: dict) -> Score:
	return Score(
		ship_name=d.get("ship_name", ""),
		ship_id=d.get("ship_id", ""),
		value=int(d.get("value", 0)),
		sector=int(d.get("sector", 0)),
		difficulty=Difficulty(d.get("difficulty", "EASY")),
		victory=bool(d.get("victory", False)),
		dlc_enabled=bool(d.get("dlc_enabled", False)),
	)


def crew_record_from_dict(d: dict) -> CrewRecord:
	return CrewRecord(
		name=d.get("name", ""),
		race=d.get("race", ""),
		male=bool(d.get("male", True)),
		value=int(d.get("value", 0)),
	)


def stats_from_dict(d: Optional[dict]) -> Stats:
	d = d or {}
	stats = Stats()
	stats.top_scores = [score_from_dict(s) for s in d.get("top_scores", [])]
	stats.ship_best = [score_from_dict(s) for s in d.get("ship_best", [])]
	stats.int_records = {k: int(v) for k, v in d.get("int_records", {}).items()}
	stats.crew_records = {
		k: crew_record_from_dict(v) for k, v in d.get("crew_records", {}).items()
	}
	return stats


def profile_from_dict(d: dict) -> Profile:
	"""Reconstruct a Profile from the dict produced by the CLI's JSON export.

	Any field absent from the JSON falls back to a sane default, so a
	hand-edited or partially-trimmed export can still be loaded -- as long
	as `file_format` is present, since everything else is positional in the
	binary format and depends on it.
	"""
	if "file_format" not in d:
		raise binary.ProfileFormatError("JSON is missing required field \"file_format\"")

	file_format = int(d["file_format"])

	newbie_tip_level = None
	if d.get("newbie_tip_level"):
		newbie_tip_level = NewbieTipLevel(d["newbie_tip_level"])

	achievements = [achievement_from_dict(a) for a in d.get("achievements", [])]

	ship_unlock_map: Dict[str, ShipAvailability] = {}
	for ship_id, ship_dict in d.get("ship_unlock_map", {}).items():
		ship_unlock_map[ship_id] = ship_availability_from_dict(ship_id, ship_dict)

	stats = stats_from_dict(d.get("stats"))

	return Profile(
		file_format=file_format,
		newbie_tip_level=newbie_tip_level,
		achievements=achievements,
		ship_unlock_map=ship_unlock_map,
		stats=stats,
	)
def derive_layout_b_unlocked(profile: "Profile") -> Dict[str, Optional[bool]]:
	"""For each ship in the profile, work out whether its Type-B layout
	would be unlocked in-game.

	There's no "unlocked_b" flag in ae_prof.sav -- the game grants layout B
	once layout A is unlocked AND at least 2 of the ship's 3 per-ship
	achievements are completed. Returns None for a ship if this tool has no
	achievement data for it (see achievements_data.SHIPS_WITHOUT_KNOWN_ACHIEVEMENTS).
	"""
	from . import achievements_data

	completed_ids = {rec.achievement_id for rec in profile.achievements}
	result: Dict[str, Optional[bool]] = {}

	for ship_id, avail in profile.ship_unlock_map.items():
		if ship_id in achievements_data.SHIPS_WITHOUT_KNOWN_ACHIEVEMENTS:
			result[ship_id] = None
			continue

		ship_ach_ids = achievements_data.ship_achievement_ids(ship_id)
		if not ship_ach_ids:
			result[ship_id] = None
			continue

		completed_count = sum(1 for aid in ship_ach_ids if aid in completed_ids)
		result[ship_id] = avail.unlocked_a and completed_count >= 2

	return result


def resolve_ship_id(profile: "Profile", query: str) -> str:
	"""Resolve a user-typed ship reference (internal id or display name,
	case-insensitive, partial match allowed for display names) to the
	canonical ship id used as a key in profile.ship_unlock_map.

	Raises ProfileFormatError with a helpful message if nothing or more than
	one thing matches.
	"""
	candidates = list(profile.ship_unlock_map.keys())
	q = query.strip().lower()

	# Exact id match (case-insensitive) wins outright.
	for ship_id in candidates:
		if ship_id.lower() == q:
			return ship_id

	# Exact display-name match.
	for ship_id in candidates:
		if ship_display_name(ship_id).lower() == q:
			return ship_id

	# Partial display-name / id match.
	partial = [
		ship_id for ship_id in candidates
		if q in ship_display_name(ship_id).lower() or q in ship_id.lower()
	]
	if len(partial) == 1:
		return partial[0]
	if len(partial) > 1:
		options = ", ".join(f"{ship_display_name(s)} ({s})" for s in partial)
		raise binary.ProfileFormatError(f"\"{query}\" matches multiple ships: {options}")

	options = ", ".join(f"{ship_display_name(s)} ({s})" for s in candidates)
	raise binary.ProfileFormatError(f"No ship matches \"{query}\". Known ships: {options}")


def set_ship_unlock(profile: "Profile", ship_id: str, layout: str, unlocked: bool) -> None:
	"""Set a ship's Type-A and/or Type-C unlock flag. `layout` is 'a', 'c',
	or 'both'. Type-C only applies to format-9 profiles; it's silently
	ignored (a no-op) on format-4 profiles since they have no such flag.
	"""
	avail = profile.ship_unlock_map.get(ship_id)
	if avail is None:
		raise binary.ProfileFormatError(f"Unknown ship id: {ship_id}")

	layout = layout.lower()
	if layout in ("a", "both"):
		avail.unlocked_a = unlocked
	if layout in ("c", "both"):
		if profile.file_format == 9:
			avail.unlocked_c = unlocked
		# else: no Type-C flag exists pre-AE; nothing to set.


def set_achievement(
	profile: "Profile",
	achievement_id: str,
	difficulty: Difficulty = Difficulty.HARD,
	layout: Optional[str] = None,
) -> AchievementRecord:
	"""Mark an achievement completed, creating its record if needed.

	`layout` ('a', 'b', or 'c') only matters for victory achievements
	(ids ending in "_VICTORY"): it records which ship layout the flagship
	victory was earned with, on top of the achievement's overall difficulty.
	"""
	rec = next((r for r in profile.achievements if r.achievement_id == achievement_id), None)
	is_new = rec is None
	if is_new:
		rec = AchievementRecord(achievement_id=achievement_id, difficulty=difficulty)
		profile.achievements.append(rec)
	elif layout is None:
		# No specific layout targeted -- this *is* the overall completion.
		rec.difficulty = difficulty

	if layout is not None:
		if not rec.is_victory_achievement:
			raise binary.ProfileFormatError(
				f"\"{achievement_id}\" doesn't look like a per-layout victory "
				f"achievement (its id doesn't end in \"_VICTORY\"), so --layout doesn't apply."
			)
		layout = layout.lower()
		if layout == "a":
			rec.completed_with_type_a = difficulty
		elif layout == "b":
			rec.completed_with_type_b = difficulty
		elif layout == "c":
			rec.completed_with_type_c = difficulty
		else:
			raise binary.ProfileFormatError(f"Invalid layout \"{layout}\" (expected a, b, or c)")

	return rec


def clear_achievement(profile: "Profile", achievement_id: str, layout: Optional[str] = None) -> bool:
	"""Undo an achievement. With no `layout`, removes the achievement
	record entirely. With a layout ('a'/'b'/'c'), only clears that victory
	achievement's per-layout completion, leaving the rest of the record
	intact. Returns True if anything was actually changed.
	"""
	rec = next((r for r in profile.achievements if r.achievement_id == achievement_id), None)
	if rec is None:
		return False

	if layout is None:
		profile.achievements.remove(rec)
		return True

	if not rec.is_victory_achievement:
		raise binary.ProfileFormatError(
			f"\"{achievement_id}\" doesn't look like a per-layout victory "
			f"achievement (its id doesn't end in \"_VICTORY\"), so --layout doesn't apply."
		)
	layout = layout.lower()
	if layout == "a":
		rec.completed_with_type_a = None
	elif layout == "b":
		rec.completed_with_type_b = None
	elif layout == "c":
		rec.completed_with_type_c = None
	else:
		raise binary.ProfileFormatError(f"Invalid layout \"{layout}\" (expected a, b, or c)")
	return True


def make_max_profile(file_format: int = 9) -> Profile:
	"""Build a Profile with every ship fully unlocked and every known
	achievement completed (at HARD difficulty, with every layout of every
	victory achievement also completed at HARD).

	See ftlprofile.achievements_data for caveats about the achievement list
	not being sourced from the game's own data files.
	"""
	from . import achievements_data  # local import to avoid a cycle at module load

	if file_format not in (4, 9):
		raise binary.ProfileFormatError(f"Unsupported file format: {file_format}")

	profile = Profile(file_format=file_format)
	if file_format == 9:
		profile.newbie_tip_level = NewbieTipLevel.VETERAN

	# Ships: every slot, every layout, fully unlocked.
	ship_unlock_map: Dict[str, ShipAvailability] = {}
	for ship_id in _ship_ids_for_format(file_format):
		ship_unlock_map[ship_id] = ShipAvailability(ship_id, unlocked_a=True, unlocked_c=True)
	profile.ship_unlock_map = ship_unlock_map

	# Achievements: every known id, maxed out. Per-ship VICTORY achievements
	# didn't exist before Advanced Edition (format 9), so skip them for
	# format 4 profiles -- matching ProfileParser's own "format 4 has no
	# quest or victory achievements" rule.
	achievements: List[AchievementRecord] = []
	for ach_id in achievements_data.all_achievement_ids(file_format):
		if file_format == 4 and ach_id.endswith("_VICTORY"):
			continue
		rec = AchievementRecord(achievement_id=ach_id, difficulty=Difficulty.HARD)
		if file_format == 9 and rec.is_victory_achievement:
			rec.completed_with_type_a = Difficulty.HARD
			rec.completed_with_type_b = Difficulty.HARD
			rec.completed_with_type_c = Difficulty.HARD
		achievements.append(rec)
	profile.achievements = achievements

	profile.stats = Stats()
	for name in STAT_INT_FIELDS:
		profile.stats.int_records[name] = 0

	return profile


def read_profile(source: Union[str, Path, BinaryIO]) -> Profile:
	"""Parse an ae_prof.sav file from a path or an already-open binary stream."""
	if isinstance(source, (str, Path)):
		with open(source, "rb") as f:
			return read_profile(f)

	f = source
	file_format = binary.read_int(f)

	# FTL 1.6.1 introduced UTF-8 strings; there's no separate magic number
	# for it, so any format-9 (AE) profile is assumed to be UTF-8.
	unicode_strings = file_format >= 9

	profile = Profile(file_format=file_format)

	if file_format == 4:
		pass  # FTL 1.03.3 and earlier; nothing extra here.
	elif file_format == 9:
		newbie_flag = binary.read_int(f)
		if newbie_flag == 0:
			profile.newbie_tip_level = NewbieTipLevel.SHIPS_UNLOCKED
		elif newbie_flag == 1:
			profile.newbie_tip_level = NewbieTipLevel.SHIP_LIST_INTRO
		elif newbie_flag == 2:
			profile.newbie_tip_level = NewbieTipLevel.VETERAN
		else:
			raise binary.ProfileFormatError(f"Unsupported newbie tip level flag: {newbie_flag}")
	else:
		raise binary.ProfileFormatError(f"Unexpected first byte ({file_format}) for a PROFILE.")

	profile.achievements = _read_achievements(f, file_format, unicode_strings)
	profile.ship_unlock_map = _read_ship_unlocks(f, file_format)
	profile.stats = _read_stats(f, file_format, unicode_strings)

	return profile
