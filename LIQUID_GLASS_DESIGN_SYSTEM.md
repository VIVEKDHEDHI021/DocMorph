# DocMorph Liquid Glass Design System
## iOS-Inspired Liquid Glass UI with Floating Navigation

### 1. Overview
The DocMorph Liquid Glass design system introduces a refined, futuristic, and content-focused visual identity. Inspired by modern iOS translucent aesthetics and hardware-accelerated materials, it balances translucent glass navigation elements with high-contrast, clean solid cards for document review and PDF manipulation.

---

### 2. Design Tokens

#### 2.1 Surfaces & Materials
- **Navigation Capsule (`glass-capsule`):**
  - Background: `rgba(15, 23, 42, 0.82)` (Translucent deep obsidian)
  - Backdrop Blur: `28px` saturate `190%`
  - Border: `1px solid rgba(255, 255, 255, 0.12)`
  - Specular Highlight: `inset 0 1px 1px 0 rgba(255, 255, 255, 0.2)`
  - Shadow: `0 24px 48px -12px rgba(0, 0, 0, 0.45)`
  - Corner Radius: `9999px` (Pill / Capsule)

- **Iridescent Orb / Add PDF Button (`iridescent-btn`):**
  - Geometry: `56px x 56px` circular floating action button
  - Elevation: Elevated `-20px` (`-mt-5`) floating above the capsule horizon
  - Base Gradient: Multi-stop prismatic spectrum `linear-gradient(135deg, #ffffff 0%, #e0e7ff 25%, #fbcfe8 50%, #c7d2fe 75%, #ffffff 100%)`
  - Specular Glare: Radial specular glare at 35% 25% `rgba(255, 255, 255, 0.95)`
  - Chromatic Glow: Dual chromatic shadow `0 10px 28px -4px rgba(99, 102, 241, 0.38), 0 0 24px 2px rgba(244, 114, 182, 0.3)`
  - Icon: Centered `Plus` icon in deep indigo `stroke-[2.4]`

- **Document Surface & Cards (`glass-card`):**
  - Background: `#ffffff`
  - Border: `1px solid rgba(226, 232, 240, 0.8)`
  - Shadow: `0 4px 16px -4px rgba(15, 23, 42, 0.03)`
  - Radius: `16px` (`rounded-2xl`)
  - Hover Interaction: Translates `-1px` with `0 12px 28px -8px rgba(99, 102, 241, 0.08)`

---

### 3. Typography & Hierarchy
- **Header:** `SF Pro Display`, `-apple-system`, `Inter`, `16px` bold with `tracking-tight`
- **Section Titles:** `14px / 16px` semi-bold
- **Labels:** `11px / 12px` font-mono or uppercase tracking-wider
- **Status Pills:** Compact rounded pills with `px-2.5 py-0.5` and `11px` typography

---

### 4. Animations & Micro-Interactions
- **Navigation Capsule Entrance:** Smooth translate-y with spring curve `cubic-bezier(0.16, 1, 0.3, 1)`
- **Add PDF Press:** Scale down to `0.92` with reduced chromatic dispersion on active tap
- **Card Hover:** Subtle elevation lift `translateY(-1px)`
- **Shimmer:** 8-second slow iridescent shimmer on the center action orb
