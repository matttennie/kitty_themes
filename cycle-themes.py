#!/usr/bin/env python3
"""
cycle-themes  —  cycle and record kitty+starship theme favorites.

  themes              cycle through saved favorites
  themes record       save current kitty theme to favorites (auto-colors)
  themes list         list saved favorites
  themes remove NAME  remove a favorite by name

Favorites are stored in ~/.config/kitty/theme-favs.json — edit freely.
"""

import os, sys, tty, termios, select, subprocess, json, re
from pathlib import Path

KITTY_CONF    = Path.home() / ".config/kitty"
CURRENT_THEME = KITTY_CONF / "current-theme.conf"
STARSHIP_CONF = Path.home() / ".config/starship.toml"
FAVS_FILE     = KITTY_CONF / "theme-favs.json"


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_favs():
    if FAVS_FILE.exists():
        return json.loads(FAVS_FILE.read_text("utf-8"))
    return []

def save_favs(favs):
    FAVS_FILE.write_text(json.dumps(favs, indent=2), "utf-8")

def parse_colors(text):
    c = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            c[parts[0]] = parts[1]
    return c

def theme_name_from_conf(text):
    for line in text.splitlines():
        m = re.match(r"^##\s+name:\s+(.+)$", line)
        if m:
            return m.group(1).strip()
    return None

def hex_lum(h):
    h = h.lstrip("#")
    if len(h) != 6:
        return 128
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0.299 * r + 0.587 * g + 0.114 * b

def derive_starship_colors(colors):
    """Auto-pick Starship segment colors from a theme's palette."""
    bg  = colors.get("background", "#000000")
    fg  = colors.get("foreground", "#ffffff")
    c0  = colors.get("color0",  "#333333")
    c5  = colors.get("color5",  "#cc00cc")   # accent (magenta/purple)
    c7  = colors.get("color7",  "#cccccc")
    dark = hex_lum(bg) < 128
    seg_bg = c0 if dark else c7
    seg_fg = fg if dark else c0
    git_bg = c5
    git_fg = bg if hex_lum(c5) > 100 else fg
    return seg_bg, seg_fg, git_bg, git_fg

def get_theme_content(kitty_theme_name):
    r = subprocess.run(
        ["kitty", "+kitten", "themes", "--dump-theme", kitty_theme_name],
        capture_output=True, text=True, timeout=5,
    )
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout
    return None

def apply_osc(colors):
    buf = []
    if "background" in colors:
        buf.append(f"\033]11;{colors['background']}\007")
    if "foreground" in colors:
        buf.append(f"\033]10;{colors['foreground']}\007")
    for i in range(16):
        k = f"color{i}"
        if k in colors:
            buf.append(f"\033]4;{i};{colors[k]}\007")
    sys.stdout.write("".join(buf))
    sys.stdout.flush()

def write_starship(t):
    R = "\ue0b0"
    L = "\ue0b2"
    M = "\ue0b1"
    B = "\ue0a0"
    s, S, g, G = t["seg_bg"], t["seg_fg"], t["git_bg"], t["git_fg"]
    content = (
        f'# Starship \u2014 {t["name"]}\n\n'
        f'format = """\n'
        f'[{R}](fg:{s})\\\n'
        f'[$directory](bg:{s} fg:{S} bold)\\\n'
        f'[{R}](fg:{s})\\\n'
        f'$character"""\n\n'
        f'right_format = """$git_branch"""\n\n'
        f'[directory]\n'
        f'style             = "bold fg:{S} bg:{s}"\n'
        f'format            = "[ $path ]($style)"\n'
        f'truncation_length = 4\n'
        f'truncate_to_repo  = false\n'
        f'home_symbol       = "~"\n'
        f'truncation_symbol = "\u2026/"\n\n'
        f'[directory.substitutions]\n'
        f'"/" = " {M} "\n\n'
        f'[git_branch]\n'
        f'format            = "[{L}](fg:{g})[ {B} $branch ](bold fg:{G} bg:{g})"\n'
        f'symbol            = ""\n'
        f'style             = "bold fg:{G} bg:{g}"\n'
        f'truncation_length = 25\n'
        f'truncation_symbol = "\u2026"\n\n'
        f'[character]\n'
        f'success_symbol = ""\n'
        f'error_symbol   = "[{R}](fg:red)"\n'
        f'format         = "$symbol "\n\n'
        f'[cmd_duration]\ndisabled = true\n'
        f'[username]\ndisabled = true\n'
        f'[hostname]\ndisabled = true\n'
        f'[package]\ndisabled = true\n'
        f'[git_status]\ndisabled = true\n'
    )
    STARSHIP_CONF.write_text(content, encoding="utf-8")

def getch():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = os.read(fd, 1).decode("utf-8", errors="replace")
        if ch == "\x1b":
            ready, _, _ = select.select([fd], [], [], 0.1)
            if ready:
                ch += os.read(fd, 4).decode("utf-8", errors="replace")
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

def redraw(idx, total, name):
    sys.stdout.write(
        f"\r\033[K  \033[1m[{idx+1}/{total}]\033[0m  {name:<30}"
        f"  TAB/\u2192 next  \u2190/Shift-TAB prev  Enter apply  q cancel"
    )
    sys.stdout.flush()


# ── Subcommands ───────────────────────────────────────────────────────────────

def cmd_record(args):
    """Save the current kitty theme to favorites."""
    if not CURRENT_THEME.exists():
        sys.exit("No current theme found (~/.config/kitty/current-theme.conf).")

    content = CURRENT_THEME.read_text("utf-8")
    colors  = parse_colors(content)
    detected_name = theme_name_from_conf(content)

    # Allow override: themes record "My Name"
    name = " ".join(args) if args else detected_name or "Unnamed Theme"
    kitty_theme = detected_name or name

    # Save current starship.toml verbatim so any preset is preserved
    starship_config = STARSHIP_CONF.read_text("utf-8") if STARSHIP_CONF.exists() else ""

    entry = dict(name=name, kitty_theme=kitty_theme, starship_config=starship_config)

    favs = load_favs()
    replaced = False
    for i, f in enumerate(favs):
        if f.get("kitty_theme") == kitty_theme or f.get("name") == name:
            favs[i] = entry
            replaced = True
            break
    if not replaced:
        favs.append(entry)
    save_favs(favs)
    subprocess.run(
        ["kitty", "@", "set-colors", "--all", "--configured", str(CURRENT_THEME)],
        capture_output=True, timeout=3,
    )

    action = "Updated" if replaced else "Saved"
    print(f"  {action}: \033[1m{name}\033[0m")


def cmd_list(_args):
    favs = load_favs()
    if not favs:
        print("  No favorites saved yet. Run: themes record")
        return
    print()
    for i, f in enumerate(favs, 1):
        print(f"  {i}. {f['name']}  (kitty: {f['kitty_theme']})")
    print()


def cmd_remove(args):
    if not args:
        sys.exit("Usage: themes remove <name>")
    target = " ".join(args).lower()
    favs = load_favs()
    new  = [f for f in favs if f["name"].lower() != target]
    if len(new) == len(favs):
        sys.exit(f"  Not found: {target!r}")
    save_favs(new)
    print(f"  Removed: {target}")


def cmd_cycle(_args):
    """Interactive TAB-cycle through favorites with live preview."""
    favs = load_favs()
    if not favs:
        sys.exit("No favorites yet. Set a theme in kitty then run: themes record")

    # Pre-fetch theme content for each favorite
    available = []
    for fav in favs:
        content = get_theme_content(fav["kitty_theme"])
        if content is None:
            # Fall back to current-theme.conf if names match
            ct = CURRENT_THEME.read_text("utf-8") if CURRENT_THEME.exists() else ""
            if theme_name_from_conf(ct) == fav["kitty_theme"]:
                content = ct
        if content:
            available.append((fav, content))
        else:
            print(f"  (skipping {fav['kitty_theme']!r} — not found)", file=sys.stderr)

    if not available:
        sys.exit("No theme files found. Check your favorites: themes list")

    original_theme    = CURRENT_THEME.read_text("utf-8") if CURRENT_THEME.exists() else ""
    original_starship = STARSHIP_CONF.read_text("utf-8") if STARSHIP_CONF.exists() else ""

    idx = 0
    fav, content = available[idx]
    apply_osc(parse_colors(content))
    print()
    redraw(idx, len(available), fav["name"])

    try:
        while True:
            key = getch()
            if key in ("\t", "\x1b[C"):
                idx = (idx + 1) % len(available)
            elif key in ("\x1b[Z", "\x1b[D"):
                idx = (idx - 1) % len(available)
            elif key in ("\r", "\n"):
                fav, content = available[idx]
                CURRENT_THEME.write_text(content, "utf-8")
                if fav.get("starship_config"):
                    STARSHIP_CONF.write_text(fav["starship_config"], "utf-8")
                subprocess.run(
                    ["kitty", "@", "set-colors", "--all", "--configured", str(CURRENT_THEME)],
                    capture_output=True, timeout=3,
                )
                print(f"\n\n  \u2713 {fav['name']} applied.\n")
                break
            elif key in ("q", "Q", "\x1b", "\x03"):
                apply_osc(parse_colors(original_theme))
                if original_theme:
                    CURRENT_THEME.write_text(original_theme, "utf-8")
                if original_starship:
                    STARSHIP_CONF.write_text(original_starship, "utf-8")
                print("\n\n  Cancelled \u2014 original restored.\n")
                break
            fav, content = available[idx]
            apply_osc(parse_colors(content))
            redraw(idx, len(available), fav["name"])
    except KeyboardInterrupt:
        print("\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args:
        cmd_cycle([])
    elif args[0] == "record":
        cmd_record(args[1:])
    elif args[0] == "list":
        cmd_list(args[1:])
    elif args[0] == "remove":
        cmd_remove(args[1:])
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
