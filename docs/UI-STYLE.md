# UI style — "Mission control"

North star: **warm, restrained mission control**. An analyst watches the agent work and checks its evidence. The surfaces are calm. Color carries meaning only, numbers read as numbers, and motion appears only when something actually happens (a tool call starts or ends, an answer lands).

This file is the visual target (there is no generated mock-up). The `ui-taste` skill drives the process, and this file drives the look.

## Tokens (define once as CSS variables in `frontend/app/tokens.css`; all colors are aliases of these)

| Token | Dark (default) | Light |
|---|---|---|
| `--ground` | `#0f0e0c` | `#f7f6f2` |
| `--card` | `#171613` | `#ffffff` |
| `--ink` | `#f2f0ea` | `#1b1a17` |
| `--ink-muted` | ink at 62% | ink at 60% |
| `--hairline` | ink at 10% | ink at 10% |
| `--live` | `#0a6cff` | `#0a6cff` |
| `--ok` / `--warn` / `--bad` | distinct green / amber / red, readable in both themes | same |

- **Primary action** = ink inverted on ground (an ink button with ground text). **Live blue only marks active work** (a running tool step, a streaming answer, an active call), never a default button.
- **Data Confidence badge:** High = ok, Medium = warn, Low = bad, always with its text label and never color alone.
- **Pillar colors:** three muted, distinct hues for Momentum / Pressure / Scale, used consistently in every chart and bar. They avoid live blue and the status hues.

## Type

| Role | Font | Size / weight |
|---|---|---|
| Display (welcome question only) | Instrument Serif | 44px / 400, lh 1.08 |
| Title | Manrope | 20px / 600 |
| Body | Manrope | 14px / 400, lh 1.5 |
| Control | Manrope | 13px |
| Caption | Manrope | 12px |
| Numbers, ids, IATA codes, as-of dates, table headers, eyebrows | JetBrains Mono | 12–14px, eyebrow 12px / 500, letter-spacing 0.06em |

Language uses Manrope and machine values use mono. Numeric table columns are right-aligned with tabular numbers. Load the fonts via `next/font/google`.

## Shape and space

Radii: 6 (badges), 10 (buttons/inputs), 16 (cards), 22 (rail items), 28 (composer). Spacing: control gap 12, header gap 16, card padding 20, page gutter 24 (16 below 768px). Separation comes from tonal steps and hairlines first, with one soft shadow for cards and a stronger one for floating elements (popovers, sheets, composer focus).

## Layout

```
┌────┬──────────────┬──────────────────────────────┬─────────────────────────┐
│rail│ recent chats │   conversation (max 720px)   │  Mission panel (≈380px) │
│76px│ 272px (≥1100)│                              │  ▾ Progress             │
│ ⌂  │ • New England│  user msg (tinted surface)   │    ● rank_airports 1.2s │
│ ☰  │ • SFO unmet  │  ▸ 3 tool steps · 4.1s       │  ▾ Evidence             │
│ ◐  │              │  Answer table / prose        │    ranking + pillar bars│
│    │              │  [Data conf.: Medium]       │    Data conf. · As-of   │
│    │              │  (chip) (chip) (chip)        │    Assumptions list     │
│    │              │ ┌──────────────────────────┐ │  ▸ Trace                │
│    │              │ │ Ask about US airports… 📞│ │                         │
└────┴──────────────┴─┴──────────────────────────┴─┴─────────────────────────┘
```

- **Rail:** 76px icons, widening to 248px with labels on hover or focus without moving the workspace. Below 768px it becomes a drawer with a scrim.
- **Recent chats:** a 272px column at ≥ 1100px wide, a drawer below that.
- **Conversation:** 720px content, a 760px composer, and the welcome state centred: the serif question "Where should the next terminal go?" with the 4 exam questions as starter chips.
- **Mission panel:** beside the conversation on desktop (the conversation keeps ≥ 400px and the panel gives way first). On a phone it is a full-screen sheet. It opens by itself after the first tool call of a chat unless the user closed it.
- **Inline steps:** a collapsed "▸ N steps · Ts" row per answer that expands to the tool list, with a live-blue pulse while running. Reasoning text is secondary ink.

## Motion

- One-shot transitions on state change only (a step starts or completes, the answer lands, the panel opens).
- Nothing loops idly.
- `prefers-reduced-motion` keeps the state and removes the movement.

## Accessibility floor

Every chart has its values available as a table; focus rings are visible; icon buttons have labels; contrast is AA in both themes; the full keyboard path works (composer → chips → panel sections).
