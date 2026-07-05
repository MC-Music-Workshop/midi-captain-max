# MIDI Captain MAX Home Page — Design

**Date:** 2026-07-04
**Status:** Approved (brainstormed interactively)

## Goal

Public landing page for the MIDI Captain MAX project. Purpose: explain + hook visitors, show off the editor and device. Modern, minimal, fun.

## Decisions

- **Scope:** MIDI Captain MAX project page (not org-wide).
- **Hosting:** GitHub Pages from this repo, deployed via GitHub Actions. URL: `mc-music-workshop.github.io/midi-captain-max`.
- **Stack:** Single self-contained `site/index.html` — vanilla HTML/CSS/JS, zero dependencies, no build step.
- **Vibe:** Stage-dark theme with neon LED-glow accents (cyan/magenta), echoing the device's footswitch LED rings.

## Layout

1. **Hero** (full viewport, dark `#0a0a0f`):
   - Title "MIDI CAPTAIN MAX", tagline, subtle animated glow gradient.
   - **Interactive footswitch strip**: stylized device in HTML/CSS — mini screen labels + footswitch circles with LED rings. Clicking a switch lights its ring and updates screen labels, mimicking real page-switching. Pure CSS/JS.
   - CTAs: "Get started" (scroll to features) and "GitHub" (repo link).
2. **Feature cards** (3): bidirectional MIDI, visual config editor, open + hackable.
3. **Show-off band:** `docs/img/MCM-config-editor.png` (compressed copy in `site/img/`), framed with glow shadow.
4. **Footer:** repo/docs links, Helmut Keller attribution (license requirement), "not affiliated with Paint Audio" disclaimer.

## Files

```
site/
  index.html      # all CSS/JS inline
  img/editor.png  # compressed screenshot
.github/workflows/pages.yml
```

## Deploy

`pages.yml` on push to `main`: `actions/checkout@v7` → `actions/configure-pages@v6` → `actions/upload-pages-artifact@v5` (path `site/`) → `actions/deploy-pages@v5`.

**Manual one-time step:** repo Settings → Pages → Source = "GitHub Actions".

## Accessibility / responsive

- Relative units; footswitch strip wraps on narrow screens.
- `prefers-reduced-motion` disables glow pulse animations.
- Semantic landmarks, alt text, keyboard-operable footswitches (buttons).
