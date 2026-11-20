---
name: DocMorph Design System
colors:
  surface: '#faf8ff'
  surface-dim: '#d2d9f4'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f3ff'
  surface-container: '#eaedff'
  surface-container-high: '#e2e7ff'
  surface-container-highest: '#dae2fd'
  on-surface: '#131b2e'
  on-surface-variant: '#464554'
  inverse-surface: '#283044'
  inverse-on-surface: '#eef0ff'
  outline: '#777586'
  outline-variant: '#c7c4d7'
  surface-tint: '#5148d7'
  primary: '#2a14b4'
  on-primary: '#ffffff'
  primary-container: '#4338ca'
  on-primary-container: '#c1beff'
  inverse-primary: '#c3c0ff'
  secondary: '#712ae2'
  on-secondary: '#ffffff'
  secondary-container: '#8a4cfc'
  on-secondary-container: '#fffbff'
  tertiary: '#4700ab'
  on-tertiary: '#ffffff'
  tertiary-container: '#6029c9'
  on-tertiary-container: '#cfbaff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e3dfff'
  primary-fixed-dim: '#c3c0ff'
  on-primary-fixed: '#100069'
  on-primary-fixed-variant: '#372abf'
  secondary-fixed: '#eaddff'
  secondary-fixed-dim: '#d2bbff'
  on-secondary-fixed: '#25005a'
  on-secondary-fixed-variant: '#5a00c6'
  tertiary-fixed: '#e9ddff'
  tertiary-fixed-dim: '#d0bcff'
  on-tertiary-fixed: '#23005c'
  on-tertiary-fixed-variant: '#5516be'
  background: '#faf8ff'
  on-background: '#131b2e'
  surface-variant: '#dae2fd'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 30px
    fontWeight: '700'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: -0.005em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0.005em
  label-lg:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Inter
    fontSize: 10px
    fontWeight: '700'
    lineHeight: 12px
    letterSpacing: 0.05em
rounded:
  sm: 0.5rem
  DEFAULT: 1rem
  md: 1.5rem
  lg: 2rem
  xl: 3rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-mobile: 0.75rem
  margin: 1.25rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1.25rem
  space-xl: 2rem
---

## Brand & Style

This design system delivers a tactile, high-precision document engine built for local mobile execution. Blending executive productivity with modern tactile glass aesthetics, the interface communicates uncompromising security, performance, and craftsmanship. 

The styling borrows from iOS-inspired Liquid Glass and contemporary desktop publishing software:
- **Surface Reality:** Crisp white editorial cards suspended over cool structural neutral canvases.
- **Glass Optics:** Floating controls, sticky review actions, and navigation capsules utilize multi-pass blur surfaces with hyper-delicate edge-lit specular boundaries.
- **Optical Contrast:** Intense deep indigo grounding elements offset by fluid violet specular highlights that suggest computational power without visual clutter.

## Colors

The palette establishes high contrast readability against dense document layers, anchored by calibrated indigo primaries and radiant violet accents.

### Application Rules
- **Base Canvas (`#F8FAFC`):** Used strictly for structural margins, page track backdrops, and viewer canvases.
- **Surface Default (`#FFFFFF`):** High-opacity containment surfaces, modal sheets, and individual document card elements with `#E2E8F0` hairline separation.
- **Floating Controls (`rgba(255, 255, 255, 0.82)`):** Reserved for contextual toolbars, bottom sheets, and the central navigation capsule; paired with `backdrop-filter: blur(24px)` and specular border treatment `rgba(255, 255, 255, 0.6)`.
- **Primary Interactive (`#4338CA` to `#4F46E5`):** Reserved for primary workflow completions (e.g., Export, Process Local File, Apply Personalization).
- **Violet Accent (`#7C3AED` to `#8B5CF6`):** Emphasizes automated transformations, personalization engines, and dynamic badge selections.
- **Content Hierarchy:** Base text defaults to `#0F172A` (900 slate). Secondary details, metadata, and byte counts use `#64748B` (500 slate).

## Typography

Typography relies on a disciplined Inter-driven structural scale. Systemic tracking tightened across headings provides an authoritative editorial rhythm, while calibrated x-heights maintain legible document metrics, metadata, and token keys on mobile viewports.

### Style Directives
- **Case Formatting:** Use uppercase only for `label-sm` when indicating document statuses, mime-types (e.g., `PDF`, `OCR`), or active privacy badges (`LOCAL EXECUTION`).
- **Tabular Figures:** When presenting page indices (e.g., `Page 12 of 140`) and byte weights, enforce tabular numbers (`font-variant-numeric: tabular-nums`) to prevent optical shifts during continuous scrolling.

## Layout & Spacing

The workspace uses a fluid vertical-first layout model configured around mobile touch boundaries, viewport safe areas, and dynamic glass layers.

### Layout Principles
- **Continuous Viewer Canvas:** The main document viewport operates on a vertically continuous, centered scroll model with standard canvas gutters (`1rem`). PDF pages sit on an isolated layer with uniform 16px bottom separation.
- **Clearance Insets:** To accommodate floating glass navigation and bottom action bars without occluding interactive content, all terminal scrolling views must include a dedicated bottom padding buffer of `6rem` (96px).
- **Navigation Placement:** Fixed capsules float `1rem` above the bottom safe area, auto-centering horizontally within the device frame.

## Elevation & Depth

Depth is defined by optical diffraction and directional luminescence rather than simple darkened drop-shadows.

### Hierarchy of Planes
1. **Canvas (Level 0):** Background surface (`#F8FAFC`). Flat, unshadowed.
2. **Document Layer (Level 1):** Solid white card boundaries (`#FFFFFF`) with a hairline border (`1px solid #E2E8F0`) and a diffused contextual shadow (`0 2px 8px -2px rgba(15, 23, 42, 0.06), 0 1px 4px -1px rgba(15, 23, 42, 0.04)`).
3. **Floating Glass Surfaces (Level 2):** Contextual toolbars, floating navigation bars, and workflow modules. Rendered with `rgba(255, 255, 255, 0.82)`, `backdrop-filter: blur(20px) saturate(180%)`, and dual-layer border definition: an outer subtle shadow (`0 10px 25px -5px rgba(15, 23, 42, 0.08), 0 8px 10px -6px rgba(15, 23, 42, 0.04)`) and an inner specular perimeter stroke (`1px solid rgba(255, 255, 255, 0.65)`).
4. **Primary Touch Targets (Level 3):** Floating actionable CTAs and iridescent central buttons utilize deep color casting: `box-shadow: 0 10px 20px -5px rgba(67, 56, 202, 0.35), 0 4px 6px -2px rgba(124, 58, 237, 0.25)`.

## Shapes

The geometric vernacular uses high-radius pill architectures for floating interactions contrasted against softer, structured containers for page assets.

### Radius System
- **Floating Controls & Interactive Pills:** Enforce maximum circular curvature (radius `9999px` / `rounded-full`). All floating navigation bars, filter chips, primary buttons, and floating quick-actions use pill shapes.
- **Cards, Sheets, and Panels:** Implement `rounded-xl` (1.5rem / 24px) for bottom sheets, contextual menus, and modal dialogs.
- **Document Page Canvas:** Maintain structured `rounded-md` (0.5rem / 8px) on rendered document page frames to reflect physical media properties.

## Components

### Buttons
- **Primary CTA:** Pill-shaped, deep indigo fill (`#4338CA`) to violet accent (`#7C3AED`) gradient, high-contrast white text (`#FFFFFF`). Displays a directional inner ring highlight (`inset 0 1px 0 rgba(255, 255, 255, 0.3)`) and an external glow (`rgba(124, 58, 237, 0.35)`).
- **Secondary / Ghost:** Translucent neutral layer (`rgba(241, 245, 249, 0.7)`), 1px subtle border (`#E2E8F0`), text in `#0F172A`. On active state, shifts to deep indigo tint.
- **Floating Add Button (+):** Elevated 56px circular target situated within or above the capsule dock. Decorated with an iridescent violet aura, white icon, and distinct touch-scale damping.

### Liquid Glass Navigation Capsule
- **Container:** Suspended floating pill navigation. Base height: 64px. Fill: `rgba(255, 255, 255, 0.82)`. Rim: `1px solid rgba(255, 255, 255, 0.7)`. Filter: `blur(20px)`.
- **Items:** Symmetrical icon-and-label units with `#64748B` unselected states that transition to `#4338CA` with micro-pill illumination indicators upon selection.

### Action Bars (Preview, Review, Export)
- **Container:** Edge-to-edge or floating docked bottom bar. Glassmorphic composition, hosting secondary cancellation or page counters on the left and the primary step action on the right.
- **Interaction:** Automatically shifts elevation during drag/scroll events, dimming slightly when underlying PDF text intersects.

### Chips & Filters
- **Structure:** Pill-shaped (`rounded-full`), height: 32px, text style: `label-md`.
- **Default State:** Transparent fill with `1px solid #E2E8F0`, muted slate text (`#64748B`).
- **Selected State:** Fill `#4338CA`, foreground `#FFFFFF`, border-transparent, accompanied by an iridescent trailing indicator.

### Input Fields & Search Bars
- **Surface:** Recessed pill or high-radius container (`rounded-xl`), background `#F1F5F9` at 80% opacity, border `1px solid #E2E8F0`.
- **Focus State:** Background shifts to crisp `#FFFFFF`, border color resolves to `#4F46E5` with a subtle 3px outer ring: `rgba(79, 70, 229, 0.15)`.

### Cards & Document Containers
- **Display Surfaces:** Solid `#FFFFFF`, hairline perimeter `1px solid #E2E8F0`, radius `rounded-xl`. 
- **States:** In multi-page selection view, active cards gain an interior 2px perimeter border of `#4F46E5` and a translucent indigo overlay.

### Checkboxes & Radio Controls
- **Geometry:** Radio elements are circular pills; checkboxes feature soft-square radiuses (6px).
- **Colors:** Checked state activates `#4338CA` background fill with a crisp white check glyph and localized `rgba(67, 56, 202, 0.2)` highlight rings.