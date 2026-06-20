"""
Best-effort auto-detection of FTL's profile save file location, for when
the person doesn't pass an explicit path.

FTL actually uses two different filenames depending on version, both living
in the same per-user data directory:
  - "prof.sav"    for FTL 1.0 - 1.03.3 (binary format 4)
  - "ae_prof.sav" for FTL 1.5.4+ / Advanced Edition (binary format 9)

Modeled on net.blerf.ftl.parser.FTLUtilities.findUserDataPath() from the
Java FTL Profile Editor, which covers native/GOG/Humble Bundle installs on
Windows/macOS/Linux, extended here to also cover:
  - FTL running under Steam's Proton/Wine compatibility layer on Linux
  - Steam installed via Flatpak (com.valvesoftware.Steam), where the whole
	Steam sandbox (and anything it runs, including FTL through Proton) sees
	a shifted "home" under ~/.var/app/com.valvesoftware.Steam/.

FTL's own save location doesn't actually depend on which storefront you
bought it from (Steam/GOG/Humble all run the same game binary, which always
writes to the same OS-standard per-user data directory) -- the only thing
that changes the path is *how* that binary is being run: directly on the
host, or inside a Proton/Wine prefix, and if so, whether that prefix itself
lives inside a Flatpak sandbox.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import List

STEAM_APP_ID = "212680"
STEAM_SANDBOX_FLATPAK_ID = "com.valvesoftware.Steam"

# Both real FTL profile filenames, newest first (most installs are AE now).
PROFILE_FILENAMES = ["ae_prof.sav", "prof.sav"]


def _profile_paths_in(directory: Path) -> List[Path]:
	return [directory / name for name in PROFILE_FILENAMES]


def _proton_prefix_candidates(steam_root: Path) -> List[Path]:
	"""Given a Steam install root (the dir containing steamapps/), return
	candidate profile paths inside its Proton compatdata prefix for FTL."""
	paths = []
	for steamapps_name in ("steamapps", "SteamApps"):
		prefix = (
			steam_root / steamapps_name / "compatdata" / STEAM_APP_ID
			/ "pfx" / "drive_c" / "users" / "steamuser"
		)
		for docs_name in ("Documents/My Games/FasterThanLight", "My Documents/My Games/FasterThanLight"):
			paths.extend(_profile_paths_in(prefix / docs_name))
	return paths


def find_profile_candidates() -> List[Path]:
	"""All paths worth checking for an FTL profile save, roughly in order
	of how likely they are to be the right one. Doesn't check existence."""
	home = Path.home()
	system = platform.system()
	candidates: List[Path] = []

	if system == "Windows":
		for env_var in ("USERPROFILE",):
			base = os.environ.get(env_var)
			if base:
				candidates.extend(_profile_paths_in(Path(base) / "Documents" / "My Games" / "FasterThanLight"))
				candidates.extend(_profile_paths_in(Path(base) / "My Documents" / "My Games" / "FasterThanLight"))
		candidates.extend(_profile_paths_in(home / "Documents" / "My Games" / "FasterThanLight"))

	elif system == "Darwin":
		candidates.extend(_profile_paths_in(home / "Library" / "Application Support" / "FasterThanLight"))
		# Steam on macOS doesn't use Proton (FTL has a native Mac build), so
		# no extra compatdata-style path is needed here.

	else:
		# Linux and anything else POSIX-like.
		xdg_data_home = os.environ.get("XDG_DATA_HOME")
		native_data_dirs = [Path(xdg_data_home)] if xdg_data_home else []
		native_data_dirs.append(home / ".local" / "share")

		for data_dir in native_data_dirs:
			candidates.extend(_profile_paths_in(data_dir / "FasterThanLight"))

		# Steam on the host, running FTL through Proton (some Steam configs
		# force this even though FTL has a native Linux build).
		for steam_root in (
			home / ".local" / "share" / "Steam",
			home / ".steam" / "steam",
			home / ".steam" / "root",
		):
			candidates.extend(_proton_prefix_candidates(steam_root))

		# Steam installed via Flatpak: the whole sandbox's "home" is shifted
		# to ~/.var/app/com.valvesoftware.Steam, so re-check both the native
		# save path AND the Proton compatdata path under that shifted root.
		flatpak_home = home / ".var" / "app" / STEAM_SANDBOX_FLATPAK_ID
		candidates.extend(_profile_paths_in(flatpak_home / ".local" / "share" / "FasterThanLight"))
		for steam_root in (
			flatpak_home / ".local" / "share" / "Steam",
			flatpak_home / ".steam" / "steam",
		):
			candidates.extend(_proton_prefix_candidates(steam_root))

	# De-duplicate while preserving order (different branches above can
	# legitimately produce the same path).
	seen = set()
	deduped = []
	for p in candidates:
		if p not in seen:
			seen.add(p)
			deduped.append(p)
	return deduped


def find_existing_profiles() -> List[Path]:
	"""Subset of find_profile_candidates() that actually exist on disk."""
	return [p for p in find_profile_candidates() if p.is_file()]
