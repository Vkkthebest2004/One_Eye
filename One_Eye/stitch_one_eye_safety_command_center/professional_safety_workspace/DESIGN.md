---
name: Professional Safety Workspace
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#434655'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#737686'
  outline-variant: '#c3c6d7'
  surface-tint: '#0053db'
  primary: '#004ac6'
  on-primary: '#ffffff'
  primary-container: '#2563eb'
  on-primary-container: '#eeefff'
  inverse-primary: '#b4c5ff'
  secondary: '#505f76'
  on-secondary: '#ffffff'
  secondary-container: '#d0e1fb'
  on-secondary-container: '#54647a'
  tertiary: '#4d556b'
  on-tertiary: '#ffffff'
  tertiary-container: '#656d84'
  on-tertiary-container: '#eef0ff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dbe1ff'
  primary-fixed-dim: '#b4c5ff'
  on-primary-fixed: '#00174b'
  on-primary-fixed-variant: '#003ea8'
  secondary-fixed: '#d3e4fe'
  secondary-fixed-dim: '#b7c8e1'
  on-secondary-fixed: '#0b1c30'
  on-secondary-fixed-variant: '#38485d'
  tertiary-fixed: '#dae2fd'
  tertiary-fixed-dim: '#bec6e0'
  on-tertiary-fixed: '#131b2e'
  on-tertiary-fixed-variant: '#3f465c'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  display-lg:
    fontFamily: Geist
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Geist
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  space-xs: 4px
  space-sm: 8px
  space-md: 16px
  space-lg: 24px
  space-xl: 32px
  space-2xl: 48px
  container-max: 1440px
  gutter: 24px
  margin-mobile: 16px
---

## Brand & Style

The design system shifts from a high-intensity command center to a **Professional Safety Workspace**. The brand personality is grounded in clarity, reliability, and human-centric safety. It prioritizes information density without the visual fatigue of dark-themed "hacker" aesthetics, opting instead for a clinical yet approachable atmosphere.

The style is **Corporate Modern** with a lean toward **Minimalism**. It utilizes expansive white space, precise alignment, and a systematic approach to color to ensure that critical safety alerts are immediately visible against a calm, neutral backdrop. The emotional response should be one of "controlled oversight"—where the user feels empowered by data rather than overwhelmed by it.

## Colors

This palette is designed for high legibility in well-lit environments. The primary engine of the interface is **Pure White (#FFFFFF)**, providing a clean slate that reduces visual noise. 

- **Primary Blue (#2563EB):** Re-tuned for high contrast against white surfaces, used for primary actions and active states.
- **Surface Dim (#F1F5F9):** Used for sidebars, secondary navigation, or background "wells" to provide subtle structural grouping.
- **Semantic Colors:** Critical, Warning, and Success colors are saturated and dark enough to be readable as text while remaining distinct as status indicators.
- **On-Surface (#0F172A):** A deep slate blue-black is used for maximum text contrast, ensuring compliance with accessibility standards.

## Typography

The typography strategy prioritizes a "Human-Technical" balance. **Geist** is the workhorse for the entire system, providing a clean, geometric sans-serif look that feels modern and approachable.

- **Primary Text:** Geist is used for all headlines and body copy to soften the "industrial" feel of the safety intelligence data.
- **Data Readouts:** **JetBrains Mono** is retained exclusively for critical data points, timestamps, coordinates, and status codes. This ensures that quantitative information remains easily scannable and distinct from qualitative descriptions.
- **Scaling:** Headlines use a tighter letter-spacing to maintain a professional, editorial look, while small labels use increased tracking for better legibility at tiny scales.

## Layout & Spacing

The layout follows a **Fluid Grid** philosophy within a maximum container width of 1440px. A strict 4px base unit (8px standard) ensures consistent rhythm across all components.

- **Desktop:** 12-column grid with 24px gutters. Content is typically organized in cards or modular "widgets" that span 3, 4, or 6 columns.
- **Tablet:** 8-column grid with 16px gutters. Sidebars collapse into drawers to maximize horizontal space for data tables.
- **Mobile:** 4-column grid with 16px margins. Vertical stacking is mandatory for all primary data cards.
- **Density:** The system uses "Comfortable" spacing for administrative tasks (e.g., settings, profile) and "Compact" spacing for monitoring dashboards where high information density is required.

## Elevation & Depth

In this light-themed system, depth is achieved through **Subtle Soft Shadows** and **Tonal Layering** rather than glows or vibrant blurs.

- **Level 0 (Base):** #F8FAFC (Surface Dim) acts as the canvas.
- **Level 1 (Card/Container):** #FFFFFF (Pure White) with a 1px #E2E8F0 border. No shadow.
- **Level 2 (Active/Hover):** #FFFFFF with a soft, diffused shadow: `0px 4px 6px -1px rgba(15, 23, 42, 0.1), 0px 2px 4px -2px rgba(15, 23, 42, 0.05)`.
- **Level 3 (Modals/Popovers):** #FFFFFF with a more pronounced shadow: `0px 20px 25px -5px rgba(15, 23, 42, 0.1), 0px 8px 10px -6px rgba(15, 23, 42, 0.1)`.

By using very low-opacity slate-tinted shadows, the UI feels physical and layered without appearing "heavy" or cluttered.

## Shapes

The shape language is defined by the **Rounded (8px)** standard. This provides a balance between the precision of a professional tool and the approachability of a modern workspace.

- **Components:** Buttons, Input fields, and Chips all utilize the 0.5rem (8px) base radius.
- **Containers:** Dashboard cards and large modals use `rounded-xl` (1.5rem / 24px) to create a clear container hierarchy.
- **Indicators:** Status dots and avatar frames are the only elements that use a full "pill" or "circle" shape to distinguish them from interactive buttons.

## Components

### Buttons
- **Primary:** Solid #2563EB with white text. High-contrast, 8px corners.
- **Secondary:** Outline button with #E2E8F0 border and #0F172A text. 
- **Ghost:** No background/border, becomes #F1F5F9 on hover. Used for utility actions.

### Input Fields
- White background with a 1px #E2E8F0 border.
- **Focus state:** Border changes to #2563EB with a subtle 2px blue outer ring (20% opacity).
- Labels use Geist Sans Semibold; helper text uses Geist Sans Regular.

### Chips & Badges
- **Status Badges:** Use light background tints (e.g., Critical uses 10% opacity Red with solid Red text).
- **Interactive Chips:** Grey #F1F5F9 background, Geist Sans 12px Medium text.

### Cards
- White background, 1px #E2E8F0 border, 8px corner radius.
- Headers within cards should have a subtle bottom border to separate titles from content.

### Tables & Lists
- Use horizontal dividers (#F1F5F9) instead of alternating row colors to maintain a clean aesthetic.
- Headers are in #64748B (Secondary) using JetBrains Mono 10px Bold, all caps, for a technical look.

### Monitoring Widgets
- Real-time data streams use JetBrains Mono for the values to ensure no character-width jitter as numbers change.