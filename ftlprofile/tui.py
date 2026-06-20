"""
A simple terminal GUI (curses) for toggling ship unlocks and achievements
in an FTL ae_prof.sav, built on top of ftlprofile.profile's edit helpers.

Navigate with arrow keys / j,k. Space or Enter toggles the selected item.
's' saves. 'q' saves and quits. Esc quits WITHOUT saving.
"""

from __future__ import annotations

import curses
from pathlib import Path
from typing import Callable, List, Optional

from . import achievements_data
from .binary import ProfileFormatError
from .profile import (
	Difficulty,
	Profile,
	clear_achievement,
	derive_layout_b_unlocked,
	read_profile,
	set_achievement,
	set_ship_unlock,
	ship_display_name,
	write_profile,
)


class _Row:
	"""One line in the TUI. `interactive=False` rows (headers/info) are
	skipped by cursor movement and can't be toggled."""

	def __init__(
		self,
		label: str,
		interactive: bool = False,
		is_checked: Optional[Callable[[], bool]] = None,
		toggle: Optional[Callable[[], None]] = None,
	):
		self.label = label
		self.interactive = interactive
		self.is_checked = is_checked
		self.toggle = toggle


def _build_ship_rows(profile: Profile) -> List[_Row]:
	rows: List[_Row] = [_Row("=== SHIPS ===")]
	layout_b = derive_layout_b_unlocked(profile)

	for ship_id, avail in profile.ship_unlock_map.items():
		name = ship_display_name(ship_id)
		b = layout_b.get(ship_id)
		b_text = "unlocked" if b else ("unknown" if b is None else "locked")
		rows.append(_Row(f"-- {name} ({ship_id})  [layout B: {b_text}, auto-derived]"))

		def make_toggle(field: str, sid: str = ship_id, a=avail):
			def _toggle():
				current = getattr(a, field)
				layout = "a" if field == "unlocked_a" else "c"
				set_ship_unlock(profile, sid, layout, not current)
			return _toggle

		rows.append(_Row(
			f"    Layout A",
			interactive=True,
			is_checked=lambda a=avail: a.unlocked_a,
			toggle=make_toggle("unlocked_a"),
		))

		if profile.file_format == 9:
			rows.append(_Row(
				f"    Layout C",
				interactive=True,
				is_checked=lambda a=avail: a.unlocked_c,
				toggle=make_toggle("unlocked_c"),
			))

	return rows


def _build_achievement_rows(profile: Profile) -> List[_Row]:
	known_ids = achievements_data.all_achievement_ids(profile.file_format)
	known_set = set(known_ids)
	present_ids = [r.achievement_id for r in profile.achievements]
	unknown_ids = [aid for aid in present_ids if aid not in known_set]

	general_ids = [i for i in achievements_data.GENERAL_ACHIEVEMENT_IDS if i in known_set]
	ship_ach_ids = [i for i in achievements_data.SHIP_ACHIEVEMENT_IDS if i in known_set]
	victory_ids = [i for i in known_ids if i.endswith("_VICTORY")]

	def is_checked_factory(aid: str):
		return lambda: any(r.achievement_id == aid for r in profile.achievements)

	def toggle_factory(aid: str):
		def _toggle():
			if any(r.achievement_id == aid for r in profile.achievements):
				clear_achievement(profile, aid, layout=None)
			else:
				set_achievement(profile, aid, Difficulty.HARD, layout=None)
		return _toggle

	rows: List[_Row] = []

	def add_section(title: str, ids: List[str]) -> None:
		if not ids:
			return
		rows.append(_Row(f"=== {title} ==="))
		for aid in ids:
			rows.append(_Row(
				f"    {aid}", interactive=True,
				is_checked=is_checked_factory(aid), toggle=toggle_factory(aid),
			))

	add_section("ACHIEVEMENTS — General/Skill", general_ids)
	add_section("ACHIEVEMENTS — Per-ship", ship_ach_ids)
	add_section("ACHIEVEMENTS — Flagship Victory", victory_ids)
	add_section("ACHIEVEMENTS — Unrecognized (found in profile)", unknown_ids)

	return rows


def _build_rows(profile: Profile) -> List[_Row]:
	return _build_ship_rows(profile) + _build_achievement_rows(profile)


def _draw(stdscr, rows: List[_Row], cursor: int, top: int, status: str) -> None:
	stdscr.erase()
	height, width = stdscr.getmaxyx()
	body_height = height - 3

	if cursor < top:
		top = cursor
	elif cursor >= top + body_height:
		top = cursor - body_height + 1

	for i in range(body_height):
		idx = top + i
		if idx >= len(rows):
			break
		row = rows[idx]
		prefix = "  "
		if row.interactive:
			mark = "x" if row.is_checked() else " "
			prefix = f"[{mark}]"
		line = f"{prefix} {row.label}"[: width - 1]

		attr = curses.A_NORMAL
		if idx == cursor:
			attr |= curses.A_REVERSE
		if not row.interactive:
			attr |= curses.A_BOLD

		try:
			stdscr.addstr(i, 0, line, attr)
		except curses.error:
			pass

	try:
		stdscr.addstr(height - 2, 0, "-" * (width - 1))
		stdscr.addstr(
			height - 1, 0,
			"up/down/j/k move  space/enter toggle  s save  q save+quit  esc quit w/o saving"[: width - 1],
		)
		stdscr.addstr(0, max(0, width - len(status) - 1), status[: width - 1], curses.A_DIM)
	except curses.error:
		pass

	stdscr.refresh()
	return top


def _next_interactive(rows: List[_Row], start: int, step: int) -> int:
	i = start
	n = len(rows)
	for _ in range(n):
		i = (i + step) % n
		if rows[i].interactive:
			return i
	return start


def _run(stdscr, profile: Profile, profile_path: Path) -> bool:
	"""Returns True if the profile should be saved."""
	curses.curs_set(0)
	stdscr.keypad(True)

	rows = _build_rows(profile)
	cursor = next((i for i, r in enumerate(rows) if r.interactive), 0)
	top = 0
	status = f"{profile_path.name}  (format {profile.file_format})"
	dirty = False

	while True:
		top = _draw(stdscr, rows, cursor, top, status)
		key = stdscr.getch()

		if key in (curses.KEY_UP, ord("k")):
			cursor = _next_interactive(rows, cursor, -1)
		elif key in (curses.KEY_DOWN, ord("j")):
			cursor = _next_interactive(rows, cursor, 1)
		elif key in (ord(" "), curses.KEY_ENTER, 10, 13):
			if rows[cursor].interactive:
				rows[cursor].toggle()
				dirty = True
		elif key in (ord("s"), ord("S")):
			return True
		elif key in (ord("q"), ord("Q")):
			return True
		elif key == 27:  # Esc
			return False


def run_tui(profile_path: Path) -> None:
	"""Entry point: load a profile, run the interactive editor, save on exit
	(unless the person presses Esc to discard changes)."""
	profile = read_profile(profile_path)

	should_save = curses.wrapper(_run, profile, profile_path)

	if should_save:
		write_profile(profile_path, profile)
		print(f"Saved {profile_path}")
	else:
		print("Discarded changes; profile left unmodified.")
