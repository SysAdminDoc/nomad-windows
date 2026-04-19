# CSS Architecture

## Load Order (cascade is load-bearing)

### App Layer (`app.css` manifest)
Files load in this exact order. Later files intentionally override earlier ones.

| Order | File | Purpose | Lines |
|-------|------|---------|-------|
| 1 | `00_theme_tokens.css` | Design tokens: colors, typography, spacing, radius, duration, easing, z-index, density | ~440 |
| 2 | `10_shell_layout.css` | Sidebar, tabs, status strip, main content area, shell overlays | ~1,250 |
| 3 | `20_primary_workspaces.css` | AI chat, modals, wizards, cards, buttons, inputs, badges, gauges | ~670 |
| 4 | `30_secondary_workspaces.css` | Notes, maps, toast, alerts, guides, service errors, branches | ~460 |
| 5 | `40_preparedness_media.css` | 25 prep sub-tabs, media player, inventory table, calculators | ~1,230 |
| 6 | `45_situation_room.css` | Situation Room dashboard (largest CSS file) | ~2,600 |
| 7 | `50_home_customize.css` | Home bento grid, customize panel, status pills, copilot dock, sidebar groups | ~1,010 |
| 8 | `60_accessibility_platform.css` | Focus-visible, reduced-motion, battery-saver, RTL, print, touch targets | ~360 |
| 9 | `70_cleanup_utilities.css` | Utility classes, overrides, edge-case fixes | ~800 |

### Premium Layer (`premium.css` manifest)
Visual polish overlay on top of the app layer.

| Order | File | Purpose |
|-------|------|---------|
| 1 | `00_base.css` | Font rendering, scrollbar styling, sidebar glow |
| 2 | `05_motion.css` | **Single source of truth** for keyframe definitions |
| 3 | `10_refresh.css` | Refresh/update styling |
| 4 | `20_workspaces.css` | Workspace-level polish |
| 5 | `30_preparedness_ops.css` | Prep sub-tab polish (1,800 lines) |
| 6 | `40_customize_maps.css` | Map and customize panel polish |
| 7 | `50_settings.css` | Settings panel polish |
| 8 | `60_benchmark_tools.css` | Benchmark and tools polish |
| 9 | `70_layout_hardening.css` | Layout edge-case fixes |
| 10 | `80_dark_theme_overrides.css` | Dark theme specific overrides |
| 11 | `90_theme_consistency.css` | Cross-theme consistency |
| 12 | `95_premium_polish.css` | Tactical typography, button transitions, focus rings |
| 13 | `99_final_polish.css` | **Additive-only** — motion tokens, UI primitives, component polish |
| 14 | `100_extreme_polish.css` | Final detail pass |

## Design Token System (`00_theme_tokens.css`)

### Typography (13-step scale)
`--text-3xs` (7px) → `--text-4xl` (32px)

### Spacing (4px base unit)
`--sp-1` (4px) → `--sp-16` (64px)

### Border Radius (9-step scale)
`--radius-2xs` (2px) → `--radius-full` (999px)

### Durations (8-step scale)
`--duration-micro` (0.1s) → `--duration-slowest` (1.5s)

### Easing (4 functions)
`--easing-standard`, `--easing-decelerate`, `--easing-accelerate`, `--easing-spring`

### Themes
5 themes: `nomad` (light), `nightops` (dark), `redlight` (night), `cyber` (dark), `eink` (high contrast)

### Density
3 modes: default, `comfortable`, `ultra` (via `[data-density]` attribute)

## Rules

1. **Never add inline `style=` attributes** — use CSS classes
2. **Never define new keyframes outside `05_motion.css`** — it's the single source of truth
3. **`99_final_polish.css` is additive-only** — never edit earlier files to integrate polish
4. **Use tokens for all values** — `var(--text-sm, 11px)`, `var(--radius-sm, 6px)`, `var(--duration-fast)`
5. **`!important` is justified** in override layers (80, 90, 95, 99, 100) — that's their purpose
