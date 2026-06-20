# ftl-cli

A command-line tool for inspecting and editing "FTL: Faster Than Light"
profile save files.

This is AI-ported code (Claude Sonnet 4.6) from the original Java-based
[FTL profile editor](https://github.com/Vhati/ftl-profile-editor) to Python
in order to easily reconstruct a lost/damaged profile with unlocked ship and
achievements. Please see the FTL profile editor for a more complete solution.

## Usage

Every command's profile path is optional -- if you omit it, the tool
searches common install locations and uses what it finds (prompting if it
finds more than one):

```bash
python3 ftl-cli.py show
python3 ftl-cli.py ship unlock stealth --layout both
python3 ftl-cli.py tui
```

Auto-detection checks for both `ae_prof.sav` (FTL 1.5.4+/Advanced Edition)
and `prof.sav` (FTL 1.0-1.03.3) in each of these locations, per OS:

- **Windows**: `Documents\My Games\FasterThanLight\`
- **macOS**: `~/Library/Application Support/FasterThanLight/`
- **Linux native**: `$XDG_DATA_HOME/FasterThanLight/` (or `~/.local/share/...`)
- **Linux, Steam via Proton**: `~/.local/share/Steam/steamapps/compatdata/212680/pfx/.../FasterThanLight/`
  (and the `~/.steam/steam/...` equivalent)
- **Linux, Steam installed via Flatpak**: the same native and Proton paths
  above, but rooted under `~/.var/app/com.valvesoftware.Steam/` instead of
  your real home, since Flatpak sandboxes shift where Steam (and anything
  it runs) sees "home"

You can also explicitly specify an ae_prof.sav path:

```bash
# Show everything (unlocked ships + achievements)
python3 ftl-cli.py show /path/to/ae_prof.sav
python3 ftl-cli.py show /path/to/ae_prof.sav --all-ships

# Just ships
python3 ftl-cli.py ships /path/to/ae_prof.sav --all

# Just achievements
python3 ftl-cli.py achievements /path/to/ae_prof.sav

# Print any of the above as JSON instead of a table
python3 ftl-cli.py show /path/to/ae_prof.sav --json
python3 ftl-cli.py ships /path/to/ae_prof.sav --json
python3 ftl-cli.py achievements /path/to/ae_prof.sav --json

# Export the full parsed profile (ships, achievements, and stats) to a file
python3 ftl-cli.py export /path/to/ae_prof.sav                 # writes profile.json next to it
python3 ftl-cli.py export /path/to/ae_prof.sav out.json        # custom path
python3 ftl-cli.py export /path/to/ae_prof.sav out.json --indent 4

# Edit that JSON by hand, then write it back to an ae_prof.sav
python3 ftl-cli.py update profile.json                          # writes ae_prof.sav/prof.sav next to it
python3 ftl-cli.py update profile.json /path/to/ae_prof.sav      # overwrite a specific file
python3 ftl-cli.py update profile.json /path/to/ae_prof.sav --backup   # keep a .bak copy first

# Generate a JSON file with every ship and achievement maxed out
python3 ftl-cli.py generate-max                          # writes max_profile.json (format 9)
python3 ftl-cli.py generate-max max.json --format 4       # target FTL 1.0-1.03.3 instead
python3 ftl-cli.py update max.json                            # writes ae_prof.sav next to it (--format 9)

# Unlock/lock a single ship layout directly on an ae_prof.sav
python3 ftl-cli.py ship unlock /path/to/ae_prof.sav stealth          # layout A (default)
python3 ftl-cli.py ship unlock /path/to/ae_prof.sav stealth --layout both
python3 ftl-cli.py ship lock /path/to/ae_prof.sav PLAYER_SHIP_STEALTH --layout c

# Unlock/lock a single achievement directly on an ae_prof.sav
python3 ftl-cli.py achievement unlock /path/to/ae_prof.sav ACH_SECTOR_5
python3 ftl-cli.py achievement unlock /path/to/ae_prof.sav ACH_SECTOR_5 --difficulty NORMAL
python3 ftl-cli.py achievement unlock /path/to/ae_prof.sav PLAYER_SHIP_HARD_VICTORY --layout a
python3 ftl-cli.py achievement lock /path/to/ae_prof.sav PLAYER_SHIP_HARD_VICTORY --layout a
python3 ftl-cli.py achievement lock /path/to/ae_prof.sav ACH_SECTOR_5    # removes it entirely

# Both of the above accept --output and --backup, like 'update' does
python3 ftl-cli.py ship unlock ae_prof.sav stealth --output new.sav
python3 ftl-cli.py ship unlock ae_prof.sav stealth --backup   # keeps ae_prof.sav.bak first

# Interactive terminal UI: browse and toggle ships/achievements visually
python3 ftl-cli.py tui /path/to/ae_prof.sav
```

## Terminal UI

`tui` opens a full-screen, curses-based checklist of every ship layout and
every achievement this tool knows about, checked/unchecked to match the
profile you opened:

```
[x]     Layout A
[ ]     Layout C
-- Stealth Cruiser (PLAYER_SHIP_STEALTH)  [layout B: locked, auto-derived]
[x]     Layout A
[ ]     Layout C
=== ACHIEVEMENTS — General/Skill ===
[x]     ACH_SECTOR_5
[ ]     ACH_SECTOR_8
```

- **up/down** or **j/k** — move the cursor (skips section headers)
- **space** or **enter** — toggle the selected ship layout or achievement
- **s** or **q** — save and quit
- **Esc** — quit and discard any changes made this session
