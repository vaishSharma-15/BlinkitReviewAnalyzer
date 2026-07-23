---
name: Luminous Data Systems
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
  on-surface-variant: '#4c4732'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#7e775f'
  outline-variant: '#cfc6ab'
  surface-tint: '#6e5d00'
  primary: '#6e5d00'
  on-primary: '#ffffff'
  primary-container: '#f9d507'
  on-primary-container: '#6d5c00'
  inverse-primary: '#e6c500'
  secondary: '#5f5e5e'
  on-secondary: '#ffffff'
  secondary-container: '#e2dfde'
  on-secondary-container: '#636262'
  tertiary: '#505f76'
  on-tertiary: '#ffffff'
  tertiary-container: '#c7d8f2'
  on-tertiary-container: '#4e5e74'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffe261'
  primary-fixed-dim: '#e6c500'
  on-primary-fixed: '#221b00'
  on-primary-fixed-variant: '#534600'
  secondary-fixed: '#e5e2e1'
  secondary-fixed-dim: '#c8c6c5'
  on-secondary-fixed: '#1c1b1b'
  on-secondary-fixed-variant: '#474746'
  tertiary-fixed: '#d3e4fe'
  tertiary-fixed-dim: '#b7c8e1'
  on-tertiary-fixed: '#0b1c30'
  on-tertiary-fixed-variant: '#38485d'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  display-sm:
    fontFamily: Inter
    fontSize: 30px
    fontWeight: '700'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  title-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
  title-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  container-padding: 24px
  gutter: 16px
  element-gap-sm: 8px
  element-gap-md: 16px
  section-gap: 32px
---

## Brand & Style
The design system is engineered for high-performance desktop environments where speed of insight is paramount. It merges a professional, corporate aesthetic with a high-energy "Discovery" pulse, utilizing a signature yellow accent to draw immediate attention to critical data points and primary actions. 

The style is **Corporate Modern** with a focus on **Precision Minimalism**. It prioritizes clarity through heavy use of whitespace within condensed modules, crisp borders, and a logical information hierarchy. The emotional response is one of reliability, efficiency, and mental clarity, ensuring users feel in total control of complex analytical workflows.

## Colors
The palette is anchored by a high-visibility Primary Yellow (`#F9D507`), used sparingly for interactive highlights, notifications, and primary calls to action. 

The foundation of the UI relies on a sophisticated range of Neutrals. The background is a clean `slate-50`, while surfaces use pure white to create separation. Borders are kept subtle to maintain a light feel even in high-density views. Secondary and Tertiary colors are reserved for typography and iconography to ensure a clear visual scale. Data visualization should utilize a distinct, color-blind friendly categorical palette that complements the primary yellow without competing for visual priority.

## Typography
This design system utilizes **Inter** exclusively to leverage its exceptional legibility at small sizes. The typographic scale is optimized for information density, favoring smaller body sizes (`13px`-`14px`) to maximize screen real estate.

Headlines use tighter letter spacing and heavier weights to provide structural anchors for the eye. Labels use uppercase styling for secondary metadata to create a clear visual distinction from primary body content. Line heights are kept tight but functional to support multi-line data entries without vertical bloat.

## Layout & Spacing
The layout follows a **Fluid Grid** model optimized for wide-screen desktop viewing. The global navigation resides in a slim left-hand sidebar (collapsible) or a persistent top bar. 

Main content areas are organized into a 12-column system. To maintain high density, the system utilizes a 4px baseline grid. Padding within cards and modules is disciplined (standardized at `16px` or `24px`) to ensure the UI feels rigorous and organized. 

- **Desktop (1440px+):** 12 columns, 24px margins, 16px gutters.
- **Tablet (768px - 1024px):** 6 columns, 16px margins, 12px gutters.
- **Content Reflow:** Analytical widgets should span 3, 4, 6, or 12 columns depending on data complexity.

## Elevation & Depth
Depth in this design system is achieved through **Tonal Layers and Low-Contrast Outlines** rather than heavy shadows. 

- **Base Layer:** Background in Slate-50.
- **Surface Layer:** White cards with a 1px border (`#E2E8F0`). 
- **Active State:** A subtle 2px Primary Yellow left-border or bottom-border is used to indicate selection or focus.
- **Shadows:** Restricted to temporary overlays like dropdowns or tooltips. Use a single, crisp "Ambient Shadow": `0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)`.
- **Interactions:** Hover states on interactive cards should lift slightly via a subtle border color change (`#CBD5E1`) rather than a shadow increase.

## Shapes
The shape language is **Soft and Precise**. A 4px (`0.25rem`) corner radius is applied to buttons, input fields, and small UI components to provide a modern feel without sacrificing the professional "square" aesthetic of a data-heavy tool. Large containers and dashboard cards use an 8px (`0.5rem`) radius to soften the overall layout.

## Components
- **Buttons:** Primary buttons are Solid Yellow with Black text for maximum contrast. Secondary buttons are Ghost-style with a Slate border. 
- **Tabs:** Underline-style navigation. Active tabs feature a 2px Yellow bottom border and Bold weights.
- **Data Tables:** High-density layout. Headers are light gray (`Slate-50`) with `label-md` typography. Rows use alternating zebra-stripes or subtle borders for readability.
- **Input Fields:** Flat design with a 1px border. Focus state is indicated by a Primary Yellow border glow (1px) and no shadow.
- **Chips/Badges:** Small, 2px rounded corners. Used for status (Success = Green, Warning = Yellow, Error = Red) with low-opacity background tints.
- **Cards:** White background, 1px Slate border. Headers should be separated by a subtle horizontal rule.
- **Navigation Sidebar:** Dark-themed (`#1A1A1A`) to contrast with the light workspace, using Yellow for the "active" indicator.