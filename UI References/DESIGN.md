# Design System Strategy: Precision Intelligence

This design system is engineered for the "Import Cars" ecosystem—a high-stakes automotive market intelligence environment. Our goal is to bridge the gap between the hyper-dense functionality of a Bloomberg Terminal and the aesthetic prestige of a luxury automotive configurator. We reject the "bubbly" trends of consumer apps in favor of sharp, architectural precision.

---

### 1. Overview & Creative North Star: "The Digital Machinist"

The Creative North Star for this system is **The Digital Machinist**. 

This system treats data as a high-performance engine component: every pixel must be functional, every edge must be sharp, and every interaction must feel mechanically precise. We move beyond generic dashboards by using **intentional asymmetry** and **tonal layering**. 

Rather than a centered, "safe" layout, use wide-spanning horizontal headers contrasted with narrow, dense data columns. Overlap elements slightly—such as a KPI card breaking the boundary of a section header—to create a sense of bespoke engineering rather than a rigid template.

---

### 2. Colors & Surface Logic

We utilize a sophisticated "Midnight Slate" palette. The depth is not flat; it is atmospheric, shifting between deep navies and rich charcoals.

*   **Primary Action (Automotive Blue):** `primary` (#adc6ff) and `primary_container` (#4d8eff). Use this for core data highlights and "Engine Start" actions.
*   **Intelligence Status:** 
    *   `secondary` (#4de082) - High Opportunity / Peak Performance.
    *   `tertiary` (#f9bd22) - Caution / Market Shift.
    *   `error` (#ffb4ab) - Poor Opportunity / Critical Risk.
*   **The "No-Line" Rule:** Prohibit 1px solid borders for sectioning. To separate the "Market Overview" from "Vehicle Details," transition the background from `surface` (#0b1326) to `surface_container_low` (#131b2e). Let the change in value define the architecture.
*   **Glass & Gradient Rule:** For floating modals or "active" states, use `surface_bright` (#31394d) at 80% opacity with a `20px` backdrop-blur. Apply a linear gradient from `primary` to `primary_container` (at 15% opacity) as a subtle "sheen" over key metrics to give them a metallic, premium finish.

---

### 3. Typography: Architectural Hierarchy

We utilize a dual-type system to balance readability with a "technical" aesthetic.

*   **Inter (Display/Headline/Body):** Our workhorse. Used for high-readability data. 
    *   *Headline-LG (2rem):* Use for market totals. Bold weight, tight tracking (-0.02em).
    *   *Body-MD (0.875rem):* The standard for table data. High contrast (`on_surface_variant`).
*   **Space Grotesk (Labels/Metrics):** Used for mono-spaced technical feel.
    *   *Label-MD (0.75rem):* Used for VIN numbers, chassis codes, and match levels (Exact/Near).
*   **Editorial Strategy:** Use extreme scale contrast. Place a `display-lg` metric (3.5rem) next to a `label-sm` technical detail to create an authoritative, "intelligence-first" hierarchy.

---

### 4. Elevation & Depth: Tonal Layering

In a "sharp-edged" system, traditional shadows feel out of place. We use **Tonal Stacking**.

*   **The Layering Principle:** 
    *   Base Layer: `surface` (#0b1326).
    *   Section Layer: `surface_container_low` (#131b2e).
    *   Interaction/Card Layer: `surface_container_highest` (#2d3449).
*   **The "Ghost Border" Fallback:** If a data table requires containment, use `outline_variant` (#424754) at **15% opacity**. This creates a "hairline" suggestion of a border that feels like a laser-etched guide rather than a heavy container.
*   **Zero-Radius Mandate:** Every container, button, and input must use `0px` border-radius. Sharp corners communicate precision, urgency, and professional-grade software.

---

### 5. Components

#### **The Intelligence Card**
*   **Style:** No borders. Background: `surface_container_high`. 
*   **Accent:** A 2px vertical "Intent Line" on the left edge using the `secondary` or `tertiary` color to indicate opportunity level.
*   **Spacing:** `4` (0.9rem) internal padding.

#### **High-Density Data Tables**
*   **Layout:** Forbid divider lines. Use alternating row fills: `surface_container_lowest` and `surface_container_low`.
*   **Header:** `label-md` in `on_surface_variant` with all-caps styling and 0.1rem letter spacing.
*   **Match Badges:** Sharp-edged boxes. `Exact` uses `secondary_container`; `Near` uses `tertiary_container`. Text must be `label-sm`.

#### **Primary "Action" Buttons**
*   **Style:** Background `primary_container`. Text `on_primary_container` (Inter Bold). 
*   **Shape:** `0px` radius. 
*   **Hover:** Shift to `primary_fixed` with a subtle `primary` outer glow (4% opacity).

#### **Input Fields**
*   **Style:** Underline-only or subtle `surface_container_highest` fill. 
*   **Focus:** The bottom border transforms into a 2px `primary` line. No "glow" effect—keep it surgical.

---

### 6. Do’s and Don’ts

**Do:**
*   **Do** use `24` (5.5rem) spacing between major sections to allow the dark theme to "breathe."
*   **Do** use the `secondary` green (#4ADE80) sparingly. It should act as a beacon for profit, not a general decorative color.
*   **Do** align all text to a strict vertical grid. Misalignment is the enemy of precision.

**Don't:**
*   **Don't** use a border-radius > 0px. Even a 2px radius breaks the "Machinist" aesthetic.
*   **Don't** use generic grey shadows. If an element must float, the shadow must be a translucent navy (#060e20).
*   **Don't** use "bubbly" or rounded icons. Use thin-stroke, sharp-angled iconography (1.5px stroke weight).
*   **Don't** use standard scrollbars. Use a customized 4px wide `surface_container_highest` track with a `primary` thumb.

---

### Director's Closing Note
This system is about **Authority**. When a user logs in, they should feel like they are stepping into a high-end command center. Every visual choice must reinforce the idea that the data is accurate, the opportunities are real, and the software is a precision tool. Avoid "friendly" UI; aim for "Indispensable" UI.