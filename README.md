# kitty_themes

Cycle through favorite kitty + Starship theme combos with live preview.

## What it does

- TAB through saved themes with instant live preview (colors change as you cycle)
- Applies both the kitty color palette and the matching Starship prompt config on Enter
- `themes record` saves whatever kitty theme + Starship preset you currently have — no manual config editing

## Setup

1. Copy `cycle-themes.py` to `~/.config/kitty/`
2. Copy `theme-favs.json` to `~/.config/kitty/` (or start fresh — it gets created on first `themes record`)
3. Add to `~/.zshrc`:

```zsh
alias themes="python3 ~/.config/kitty/cycle-themes.py"
```

4. Kitty must have remote control enabled. Add to `kitty.conf`:

```
allow_remote_control yes
```

## Usage

```
themes              # cycle through favorites (TAB/→ next, ←/Shift-TAB prev, Enter apply, q cancel)
themes record       # save current kitty theme + Starship config as a favorite
themes record "My Name"   # save with a custom display name
themes list         # show all saved favorites
themes remove Nord  # remove a favorite by name
```

## Workflow

1. Pick a kitty color theme: `kitten themes`
2. Pick a Starship prompt style: `starship preset <name> > ~/.config/starship.toml`
3. Save the combo: `themes record`

Next time, just run `themes` to cycle through everything you've saved.

## Requirements

- [kitty](https://sw.kovidgoyal.net/kitty/) terminal
- [Starship](https://starship.rs/) prompt (`brew install starship`)
- A Nerd Font for powerline glyphs (e.g. `brew install --cask font-jetbrains-mono-nerd-font`)
