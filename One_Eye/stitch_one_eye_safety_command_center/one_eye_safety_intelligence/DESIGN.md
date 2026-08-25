---
name: One_Eye Safety Intelligence
colors:
  surface: '#0f131c'
  surface-dim: '#0f131c'
  surface-bright: '#353943'
  surface-container-lowest: '#0a0e17'
  surface-container-low: '#181b25'
  surface-container: '#1c2029'
  surface-container-high: '#262a34'
  surface-container-highest: '#31353f'
  on-surface: '#dfe2ef'
  on-surface-variant: '#c2c6d6'
  inverse-surface: '#dfe2ef'
  inverse-on-surface: '#2c303a'
  outline: '#8c909f'
  outline-variant: '#424754'
  surface-tint: '#adc6ff'
  primary: '#adc6ff'
  on-primary: '#002e6a'
  primary-container: '#4d8eff'
  on-primary-container: '#00285d'
  inverse-primary: '#005ac2'
  secondary: '#bcc7de'
  on-secondary: '#263143'
  secondary-container: '#3e495d'
  on-secondary-container: '#aeb9d0'
  tertiary: '#ffb786'
  on-tertiary: '#502400'
  tertiary-container: '#df7412'
  on-tertiary-container: '#461f00'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#d8e2ff'
  primary-fixed-dim: '#adc6ff'
  on-primary-fixed: '#001a42'
  on-primary-fixed-variant: '#004395'
  secondary-fixed: '#d8e3fb'
  secondary-fixed-dim: '#bcc7de'
  on-secondary-fixed: '#111c2d'
  on-secondary-fixed-variant: '#3c475a'
  tertiary-fixed: '#ffdcc6'
  tertiary-fixed-dim: '#ffb786'
  on-tertiary-fixed: '#311400'
  on-tertiary-fixed-variant: '#723600'
  background: '#0f131c'
  on-background: '#dfe2ef'
  surface-variant: '#31353f'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  data-metric:
    fontFamily: Geist Mono
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.05em
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-mono:
    fontFamily: Geist Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
  label-mono-bold:
    fontFamily: Geist Mono
    fontSize: 12px
    fontWeight: '700'
    lineHeight: 16px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 16px
  margin-page: 24px
  panel-padding: 12px
---

## Brand & Style
The design system is engineered for high-stakes industrial surveillance and safety monitoring. It adopts a **Technical Minimalism** aesthetic, blending the precision of a command-center interface with modern SaaS usability. 

The personality is authoritative, vigilant, and highly functional. The UI prioritizes information density and ocular focus, reducing visual noise to ensure that safety alerts are immediately actionable. The style utilizes deep layering, subtle luminescence for active states, and a rigid structural grid to evoke a sense of controlled, real-time intelligence.

## Colors
The color palette is optimized for dark-room environments to reduce eye fatigue during long shifts.

- **Base Surfaces:** The primary background is a deep charcoal (#0f131c). Use #1e293b for panel borders and secondary containers to create clear structural separation without high-contrast jarring.
- **Brand Action:** Electric Blue (#3b82f6) is reserved for primary actions, active navigation states, and focus indicators.
- **Severity System:** This is the most critical aspect of the design system. Use these colors for status badges, alert borders, and data visualizations. For CRITICAL states, use the hex value with a 10% outer glow to simulate an "alarm" state on the hardware.
- **Text:** Primary text should be Off-White (#f8fafc) for readability, with secondary metadata in a muted Slate (#94a3b8).

## Typography
The typographic system uses a dual-font approach to distinguish between narrative content and technical data.

- **Inter:** Used for all UI chrome, navigational elements, and descriptive text. It provides a clean, neutral foundation that stays legible at small sizes.
- **Geist Mono:** Used exclusively for "hard data"—timestamps, GPS coordinates, FPS counters, risk scores, and sensor readings. The monospaced nature ensures that numerical values do not "jump" when updating in real-time.
- **Hierarchy:** Critical metrics (like Risk Scores) should use `data-metric`. All secondary telemetry should use `label-mono`.

## Layout & Spacing
The layout follows a **Fixed-Grid Command Model**. The screen is divided into a modular 12-column grid system designed for high density.

- **Modular Panels:** Content is housed in "Surveillance Cells." These cells should snap to the grid. 
- **Density:** Use a tight 4px base unit. Internal padding within panels should be kept to 12px to maximize the "data-to-ink" ratio.
- **Breakpoints:**
    - **Desktop (1440px+):** Full 12-column multi-panel view.
    - **Tablet (768px-1439px):** 6-column view, secondary telemetry panels collapse into tabs.
    - **Mobile:** Single-column critical alert stream only.

## Elevation & Depth
This design system avoids traditional drop shadows in favor of **Tonal Layering** and **Luminescent Borders**.

- **Level 0 (Background):** #0f131c.
- **Level 1 (Panels):** #161b22 with a 1px solid border of #1e293b.
- **Level 2 (Modals/Popovers):** #1e293b with a 1px solid border of #334155.
- **Active State:** Use a 1px inner stroke of the Brand Color (#3b82f6) to indicate panel focus.
- **Alert State:** For HIGH or CRITICAL panels, apply a subtle 4px outer bloom (glow) using the respective severity color at 20% opacity.

## Shapes
To maintain an industrial and precise feel, the design system utilizes **Soft-Square geometry**. 

- **Standard Radius:** 4px (0.25rem). This applies to buttons, input fields, and panels.
- **Sharp Elements:** Video feeds and data charts should have 0px radius to maximize the edge-to-edge viewing area.
- **Interactive Elements:** Buttons use the standard 4px radius. Avoid pill shapes as they appear too consumer-oriented for a safety intelligence platform.

## Components

- **Buttons:**
    - **Primary:** Solid #3b82f6 with white text. 4px radius.
    - **Ghost:** Transparent background with 1px border of #1e293b. Used for secondary telemetry controls.
- **Status Chips:** Small, rectangular badges with a background opacity of 15% and a solid 1px border of the severity color. Text must be Geist Mono Bold.
- **Data Tables:** No vertical lines. Horizontal lines should be #1e293b. Row height should be compact (32px) to allow for high data density.
- **Input Fields:** Dark background (#0f131c), 1px border (#1e293b). On focus, the border changes to the Brand Color with a subtle glow.
- **Video Feeds:** Housed in Level 1 panels. Include a top-left overlay using `label-mono` for Camera ID and a top-right overlay for live FPS/Bitrate metrics.
- **Alert Cards:** High-contrast containers. When CRITICAL, the entire left border (4px width) should be the severity color to catch the eye in peripheral vision.