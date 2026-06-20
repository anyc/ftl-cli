#!/usr/bin/env python3
"""
ftl-profile-cli: a command-line tool for inspecting (and, eventually, editing)
FTL "ae_prof.sav" files.

Step 1: show the enabled ships and achievements of a profile.
Step 2: export profile data as JSON.

Usage:
	python ftl-cli.py show /path/to/ae_prof.sav
	python ftl-cli.py show /path/to/ae_prof.sav --all-ships
	python ftl-cli.py show /path/to/ae_prof.sav --json
	python ftl-cli.py ships /path/to/ae_prof.sav
	python ftl-cli.py achievements /path/to/ae_prof.sav
	python ftl-cli.py export /path/to/ae_prof.sav
	python ftl-cli.py export /path/to/ae_prof.sav out.json --indent 4
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Optional

from ftlprofile import (
	read_profile,
	write_profile,
	make_max_profile,
	derive_layout_b_unlocked,
	resolve_ship_id,
	set_ship_unlock,
	set_achievement,
	clear_achievement,
)
from ftlprofile.profile import ship_display_name, profile_from_dict, Difficulty
from ftlprofile.binary import ProfileFormatError
from ftlprofile.tui import run_tui
from ftlprofile.locate import find_existing_profiles


def _json_default(obj):
	"""json.dumps() default= hook: handles Enum members (dataclasses are
	converted up-front via asdict, so they don't reach here)."""
	if isinstance(obj, Enum):
		return obj.value
	raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def profile_to_dict(profile) -> dict:
	"""Convert a Profile (and nested dataclasses) into a plain JSON-able dict."""
	data = asdict(profile)
	layout_b = derive_layout_b_unlocked(profile)

	# Add a couple of human-friendly derived fields without disturbing the
	# raw structure, so the JSON is still a faithful 1:1 dump of the profile.
	for ship_id, ship in data.get("ship_unlock_map", {}).items():
		ship["display_name"] = ship_display_name(ship_id)
		ship["unlocked_b"] = layout_b.get(ship_id)
		ship["unlocked"] = ship["unlocked_a"] or ship["unlocked_c"]

	for rec in data.get("achievements", []):
		rec["is_victory_achievement"] = rec["achievement_id"].endswith("_VICTORY")

	return data


def dump_json(profile, indent: int = 2) -> str:
	return json.dumps(profile_to_dict(profile), indent=indent, default=_json_default)


def _print_header(text: str) -> None:
	print(text)
	print("-" * len(text))


def cmd_ships(profile, show_all: bool, as_json: bool = False) -> None:
	ships = list(profile.ship_unlock_map.values())
	if not show_all:
		ships = [s for s in ships if s.unlocked]

	layout_b = derive_layout_b_unlocked(profile)

	if as_json:
		data = [
			{
				"ship_id": s.ship_id,
				"display_name": ship_display_name(s.ship_id),
				"unlocked_a": s.unlocked_a,
				"unlocked_b": layout_b.get(s.ship_id),
				"unlocked_c": s.unlocked_c,
				"unlocked": s.unlocked,
			}
			for s in ships
		]
		print(json.dumps(data, indent=2))
		return

	_print_header(f"Ships ({'all' if show_all else 'unlocked'}: {len(ships)})")
	if not ships:
		print("  (none)")
		return

	for s in ships:
		name = ship_display_name(s.ship_id)
		layouts = []
		if s.unlocked_a:
			layouts.append("A")
		b = layout_b.get(s.ship_id)
		if b:
			layouts.append("B")
		elif b is None:
			layouts.append("B?")
		if s.unlocked_c:
			layouts.append("C")
		layout_str = "/".join(layouts) if layouts else "-"
		print(f"  {name:<24} [{s.ship_id:<22}]  layouts unlocked: {layout_str}")

	print(
		"\n  (\"B\" is derived, not stored: unlocked once layout A is unlocked and "
		"2/3 ship achievements are done. \"B?\" means this tool doesn't know that "
		"ship's achievements, so it can't tell.)"
	)


def cmd_achievements(profile, as_json: bool = False) -> None:
	achs = profile.achievements

	if as_json:
		data = [
			{
				"achievement_id": rec.achievement_id,
				"difficulty": rec.difficulty.value,
				"is_victory_achievement": rec.is_victory_achievement,
				"completed_with_type_a": rec.completed_with_type_a.value if rec.completed_with_type_a else None,
				"completed_with_type_b": rec.completed_with_type_b.value if rec.completed_with_type_b else None,
				"completed_with_type_c": rec.completed_with_type_c.value if rec.completed_with_type_c else None,
			}
			for rec in achs
		]
		print(json.dumps(data, indent=2))
		return

	_print_header(f"Achievements ({len(achs)})")
	if not achs:
		print("  (none)")
		return

	for rec in achs:
		line = f"  {rec.achievement_id:<40} difficulty: {rec.difficulty.value}"
		if rec.is_victory_achievement:
			variants = []
			for label, diff in (
				("A", rec.completed_with_type_a),
				("B", rec.completed_with_type_b),
				("C", rec.completed_with_type_c),
			):
				variants.append(f"{label}={diff.value if diff else 'N/A'}")
			line += "  [" + ", ".join(variants) + "]"
		print(line)


def cmd_show(profile, show_all_ships: bool, as_json: bool = False) -> None:
	if as_json:
		print(dump_json(profile))
		return

	print(f"Profile format: {profile.file_format}"
		  f" ({'FTL 1.5.4+ / Advanced Edition' if profile.file_format == 9 else 'FTL 1.0-1.03.3'})")
	if profile.newbie_tip_level:
		print(f"Newbie tip level: {profile.newbie_tip_level.value}")
	print()
	cmd_ships(profile, show_all_ships)
	print()
	cmd_achievements(profile)


def cmd_export(profile, out_path: Path, indent: int) -> None:
	text = dump_json(profile, indent=indent)
	out_path.write_text(text, encoding="utf-8")
	print(f"Wrote {out_path}")


def cmd_generate_max(out_path: Path, file_format: int, indent: int) -> None:
	profile = make_max_profile(file_format)
	text = dump_json(profile, indent=indent)
	out_path.write_text(text, encoding="utf-8")
	print(f"Wrote {out_path}")
	print(
		"Note: the achievement list is a best-effort curated list (not pulled "
		"from the game's own data files) -- edit the JSON if your version of "
		"FTL needs different ids."
	)


def _default_profile_filename(file_format: int) -> str:
	return "ae_prof.sav" if file_format == 9 else "prof.sav"


def cmd_update(json_path: Path, out_path: Optional[Path], backup: bool) -> int:
	try:
		data = json.loads(json_path.read_text(encoding="utf-8"))
	except (OSError, json.JSONDecodeError) as e:
		print(f"Error: could not read JSON file \"{json_path}\": {e}", file=sys.stderr)
		return 1

	try:
		profile = profile_from_dict(data)
	except (ProfileFormatError, KeyError, ValueError) as e:
		print(f"Error: JSON in \"{json_path}\" doesn't look like a valid profile export: {e}", file=sys.stderr)
		return 1

	if out_path is None:
		out_path = json_path.parent / _default_profile_filename(profile.file_format)

	backup_path = out_path.with_suffix(out_path.suffix + ".bak") if backup else None
	if backup_path is not None and out_path.exists():
		backup_path.write_bytes(out_path.read_bytes())
		print(f"Backed up existing profile to {backup_path}")

	try:
		write_profile(out_path, profile)
	except ProfileFormatError as e:
		print(f"Error: could not write profile: {e}", file=sys.stderr)
		return 1

	print(f"Wrote {out_path}")
	return 0


def _save_profile(profile, profile_path: Path, out_path: Optional[Path], backup: bool) -> Path:
	"""Write `profile` to out_path (default: overwrite profile_path), backing
	up the destination first if requested. Returns the path written."""
	final_path = out_path or profile_path
	if backup and final_path.exists():
		backup_path = final_path.with_suffix(final_path.suffix + ".bak")
		backup_path.write_bytes(final_path.read_bytes())
		print(f"Backed up existing file to {backup_path}")
	write_profile(final_path, profile)
	return final_path


def cmd_set_ship(profile, profile_path: Path, ship_query: str, layout: str, unlocked: bool,
				  out_path: Optional[Path], backup: bool) -> int:
	try:
		ship_id = resolve_ship_id(profile, ship_query)
		set_ship_unlock(profile, ship_id, layout, unlocked)
	except ProfileFormatError as e:
		print(f"Error: {e}", file=sys.stderr)
		return 1

	final_path = _save_profile(profile, profile_path, out_path, backup)
	verb = "Unlocked" if unlocked else "Locked"
	print(f"{verb} {ship_display_name(ship_id)} ({ship_id}) layout {layout.upper()}. Wrote {final_path}")
	return 0


def cmd_set_achievement(profile, profile_path: Path, achievement_id: str, difficulty: Difficulty,
						 layout: Optional[str], out_path: Optional[Path], backup: bool) -> int:
	try:
		rec = set_achievement(profile, achievement_id, difficulty, layout)
	except ProfileFormatError as e:
		print(f"Error: {e}", file=sys.stderr)
		return 1

	final_path = _save_profile(profile, profile_path, out_path, backup)
	detail = f" (layout {layout.upper()} at {difficulty.value})" if layout else f" ({difficulty.value})"
	print(f"Unlocked {rec.achievement_id}{detail}. Wrote {final_path}")
	return 0


def cmd_clear_achievement(profile, profile_path: Path, achievement_id: str, layout: Optional[str],
						   out_path: Optional[Path], backup: bool) -> int:
	try:
		changed = clear_achievement(profile, achievement_id, layout)
	except ProfileFormatError as e:
		print(f"Error: {e}", file=sys.stderr)
		return 1

	if not changed:
		print(f"\"{achievement_id}\" wasn't set on this profile; nothing to do.")
		return 0

	final_path = _save_profile(profile, profile_path, out_path, backup)
	detail = f" (layout {layout.upper()})" if layout else ""
	print(f"Locked {achievement_id}{detail}. Wrote {final_path}")
	return 0


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		prog="ftl-profile-cli",
		description="Inspect and edit FTL ae_prof.sav files.",
	)
	subparsers = parser.add_subparsers(dest="command", required=True)

	common_args = argparse.ArgumentParser(add_help=False)
	common_args.add_argument(
		"profile", type=Path, nargs="?", default=None,
		help="path to ae_prof.sav (omit to auto-detect common install locations)",
	)

	p_show = subparsers.add_parser(
		"show", parents=[common_args], help="show unlocked ships and achievements"
	)
	p_show.add_argument(
		"--all-ships", action="store_true", help="show all ship slots, including locked ones"
	)
	p_show.add_argument("--json", dest="as_json", action="store_true", help="output as JSON")

	p_ships = subparsers.add_parser("ships", parents=[common_args], help="show ship unlock status")
	p_ships.add_argument(
		"--all", dest="all_ships", action="store_true", help="show all ship slots, including locked ones"
	)
	p_ships.add_argument("--json", dest="as_json", action="store_true", help="output as JSON")

	p_achievements = subparsers.add_parser(
		"achievements", parents=[common_args], help="show earned achievements"
	)
	p_achievements.add_argument("--json", dest="as_json", action="store_true", help="output as JSON")

	p_export = subparsers.add_parser(
		"export", parents=[common_args], help="export the full profile as a JSON file"
	)
	p_export.add_argument(
		"output", type=Path, nargs="?", default=None,
		help="output .json path (default: <profile-name>.json next to the profile)",
	)
	p_export.add_argument(
		"--indent", type=int, default=2, help="JSON indent width (default: 2)"
	)

	p_update = subparsers.add_parser(
		"update",
		help="write an ae_prof.sav from a JSON file (e.g. one produced by 'export')",
	)
	p_update.add_argument("json_file", type=Path, help="path to the JSON file to read")
	p_update.add_argument(
		"output", type=Path, nargs="?", default=None,
		help="path to write (default: ae_prof.sav or prof.sav, matching the JSON's "
			 "file_format, next to the JSON file)",
	)
	p_update.add_argument(
		"--backup", action="store_true",
		help="back up the existing output file (as '<output>.bak') before overwriting it",
	)

	out_args = argparse.ArgumentParser(add_help=False)
	out_args.add_argument(
		"--output", type=Path, default=None,
		help="write to this path instead of overwriting the input profile",
	)
	out_args.add_argument(
		"--backup", action="store_true",
		help="back up the file being overwritten (as '<file>.bak') first",
	)

	p_ship = subparsers.add_parser("ship", help="unlock or lock a single ship layout")
	ship_sub = p_ship.add_subparsers(dest="ship_action", required=True)

	p_ship_unlock = ship_sub.add_parser(
		"unlock", parents=[common_args, out_args], help="unlock a ship's layout A and/or C"
	)
	p_ship_unlock.add_argument(
		"ship", help="ship id (e.g. PLAYER_SHIP_HARD) or display name (e.g. 'kestrel', partial ok)"
	)
	p_ship_unlock.add_argument(
		"--layout", choices=("a", "c", "both"), default="a",
		help="which layout to unlock (default: a). 'c' is ignored on pre-AE (format 4) profiles.",
	)

	p_ship_lock = ship_sub.add_parser(
		"lock", parents=[common_args, out_args], help="lock a ship's layout A and/or C"
	)
	p_ship_lock.add_argument(
		"ship", help="ship id (e.g. PLAYER_SHIP_HARD) or display name (e.g. 'kestrel', partial ok)"
	)
	p_ship_lock.add_argument(
		"--layout", choices=("a", "c", "both"), default="a",
		help="which layout to lock (default: a). 'c' is ignored on pre-AE (format 4) profiles.",
	)

	p_ach = subparsers.add_parser("achievement", help="unlock or lock a single achievement")
	ach_sub = p_ach.add_subparsers(dest="achievement_action", required=True)

	p_ach_unlock = ach_sub.add_parser(
		"unlock", parents=[common_args, out_args], help="mark an achievement completed"
	)
	p_ach_unlock.add_argument("achievement_id", help="achievement id, e.g. ACH_SECTOR_5")
	p_ach_unlock.add_argument(
		"--difficulty", choices=("EASY", "NORMAL", "HARD"), default="HARD",
		help="difficulty to record the completion at (default: HARD)",
	)
	p_ach_unlock.add_argument(
		"--layout", choices=("a", "b", "c"), default=None,
		help="for ship-victory achievements (ids ending in _VICTORY) only: which ship "
			 "layout earned the flagship victory",
	)

	p_ach_lock = ach_sub.add_parser(
		"lock", parents=[common_args, out_args], help="undo an achievement"
	)
	p_ach_lock.add_argument("achievement_id", help="achievement id, e.g. ACH_SECTOR_5")
	p_ach_lock.add_argument(
		"--layout", choices=("a", "b", "c"), default=None,
		help="for ship-victory achievements only: clear just this layout's completion "
			 "instead of removing the whole achievement",
	)

	p_tui = subparsers.add_parser(
		"tui", parents=[common_args],
		help="interactive terminal UI for toggling ships and achievements",
	)

	p_genmax = subparsers.add_parser(
		"generate-max",
		help="create a JSON file with every ship unlocked and every achievement completed",
	)
	p_genmax.add_argument(
		"output", type=Path, nargs="?", default=Path("max_profile.json"),
		help="output .json path (default: max_profile.json)",
	)
	p_genmax.add_argument(
		"--format", type=int, choices=(4, 9), default=9, dest="file_format",
		help="profile file format to target: 9 = FTL 1.5.4+/Advanced Edition (default), "
			 "4 = FTL 1.0-1.03.3",
	)
	p_genmax.add_argument(
		"--indent", type=int, default=2, help="JSON indent width (default: 2)"
	)

	return parser


def resolve_profile_path(given: Optional[Path]) -> Optional[Path]:
	"""If `given` is set, just return it. Otherwise search common install
	locations (native, Steam/Proton, Steam-via-Flatpak) and either return
	the one match found, prompt to choose among several, or print guidance
	and return None if nothing was found."""
	if given is not None:
		return given

	found = find_existing_profiles()

	if not found:
		print(
			"No profile path given, and no profile save (prof.sav / ae_prof.sav) found "
			"in any common install location (native, Steam/Proton, or Steam via Flatpak).\n"
			"Pass the path explicitly, e.g.:\n"
			"  python3 ftl-cli.py show /path/to/ae_prof.sav",
			file=sys.stderr,
		)
		return None

	if len(found) == 1:
		print(f"Auto-detected profile: {found[0]}")
		return found[0]

	print("Multiple profile save files found:")
	for i, p in enumerate(found, start=1):
		print(f"  {i}. {p}")
	while True:
		choice = input(f"Which one? [1-{len(found)}]: ").strip()
		if choice.isdigit() and 1 <= int(choice) <= len(found):
			return found[int(choice) - 1]
		print("Invalid choice, try again.")


def main(argv=None) -> int:
	parser = build_parser()
	args = parser.parse_args(argv)

	if hasattr(args, "profile"):
		resolved = resolve_profile_path(args.profile)
		if resolved is None:
			return 1
		args.profile = resolved

	if args.command == "update":
		if not args.json_file.exists():
			print(f"Error: file not found: {args.json_file}", file=sys.stderr)
			return 1

		out_path = args.output  # may be None; cmd_update picks the right default filename
		return cmd_update(args.json_file, out_path, args.backup)

	if args.command == "generate-max":
		cmd_generate_max(args.output, args.file_format, args.indent)
		return 0

	if args.command == "tui":
		if not args.profile.exists():
			print(f"Error: file not found: {args.profile}", file=sys.stderr)
			return 1
		try:
			run_tui(args.profile)
		except ProfileFormatError as e:
			print(f"Error: could not parse \"{args.profile}\" as an FTL profile: {e}", file=sys.stderr)
			return 1
		return 0

	if not args.profile.exists():
		print(f"Error: file not found: {args.profile}", file=sys.stderr)
		return 1

	try:
		profile = read_profile(args.profile)
	except ProfileFormatError as e:
		print(f"Error: could not parse \"{args.profile}\" as an FTL profile: {e}", file=sys.stderr)
		return 1

	if args.command == "show":
		cmd_show(profile, args.all_ships, args.as_json)
	elif args.command == "ships":
		cmd_ships(profile, args.all_ships, args.as_json)
	elif args.command == "achievements":
		cmd_achievements(profile, args.as_json)
	elif args.command == "export":
		out_path = args.output or args.profile.with_suffix(".json")
		cmd_export(profile, out_path, args.indent)
	elif args.command == "ship":
		if args.ship_action == "unlock":
			return cmd_set_ship(profile, args.profile, args.ship, args.layout, True, args.output, args.backup)
		else:
			return cmd_set_ship(profile, args.profile, args.ship, args.layout, False, args.output, args.backup)
	elif args.command == "achievement":
		if args.achievement_action == "unlock":
			difficulty = Difficulty(args.difficulty)
			return cmd_set_achievement(
				profile, args.profile, args.achievement_id, difficulty, args.layout, args.output, args.backup
			)
		else:
			return cmd_clear_achievement(
				profile, args.profile, args.achievement_id, args.layout, args.output, args.backup
			)

	return 0


if __name__ == "__main__":
	raise SystemExit(main())
