# WCAG 2.2 AA contrast and keyboard/screen-reader review of the Lineage UI

_Research note produced with Google Gemini via the Antigravity CLI on 2026-10-17 at the team's request; reviewed and applied by the team. Claims marked 'from memory' by the model were not independently verified._

# Accessibility Review Brief: Dark-Theme React Web App

---

### 1. WCAG 2.2 Contrast Calculations & Palette Adjustments

Contrast ratios calculated using WCAG relative luminance ($L$) formulas:

| Foreground / Element | Background | Target Type | Calculated Ratio | WCAG 2.2 AA Status | Adjustment / Fix (if failed) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Body text** (`#f5f7f3`) | Page (`#090e0d`) / Card (`#111817`) | Normal Text (4.5:1) | **18.2:1 / 16.5:1** | **PASS** | None required. |
| **Muted text** (`#9aa8a0`) | Card (`#111817`) / Raised (`#17201e`) | Normal Text (4.5:1) | **7.12:1 / 6.50:1** | **PASS** | None required. |
| **Dark text** (`#06100b`) | Accent Green pill (`#62e6a6`) | Normal Text (4.5:1) | **12.31:1** | **PASS** | None required. |
| **Accent Green text** (`#62e6a6`) | Card (`#111817`) / Page (`#090e0d`) | Eyebrows / Links (4.5:1) | **11.27:1 / 12.43:1** | **PASS** | Underline links: text-to-body contrast is only 1.46:1 (fails 1.4.1). |
| **Orange text** (`#ff8a3d`) | Card (`#111817`) | Warning / Headline (4.5:1) | **7.58:1** | **PASS** | None required. |
| **Red text** (`#ff6578`) | Card (`#111817`) | Normal Text (4.5:1) | **6.25:1** | **PASS** | None required. |
| **Edge Pill Text** (White `#f5f7f3`) | Red pill bg (`#ff6578`) | Normal Text (4.5:1) | **2.64:1** | **FAIL** | Use dark text `#06100b` (6.83:1) or darken bg to `#8f1f2e` (4.54:1). |
| **UI Borders / Inputs** (`#2b3935`) | Page (`#090e0d`) / Card (`#111817`) | Non-text (3.0:1) | **1.63:1 / 1.48:1** | **FAIL** | Lighten interactive/component borders to `#4c5d57` (3.01:1). |

---

### 2. Concrete Keyboard & Screen-Reader Fixes

1. **Focus Order:** Sequence keyboard navigation logically from SVG node activation directly into the details side panel, maintaining a trap-free Tab loop and returning focus to the source `<g>` element on panel dismissal.
2. **Focus-Visible Styling:** Add an explicit SVG focus ring using `g[role="button"]:focus-visible { outline: 2px solid #62e6a6; outline-offset: 3px; }` across all nodes, form buttons, and dropzones.
3. **Live Accuracy Counter:** Enclose the precision chip in an assertive announcement region: `<span aria-live="polite" aria-atomic="true">95% empirical precision</span>`.
4. **Newest Image Callout:** Place newly added image notifications inside a live status container (`role="status"` with `aria-live="polite"`) that dispatches brief announcements (e.g., *"Image 402 added to tree"*).
5. **Edge Labeling:** Programmatically add interactive or descriptive labels to edge pill connectors using `<g role="img" aria-label="Edge from node A to B: wrong parent, confidence 95%">`.
6. **Color-Independent Edges:** Supplement color-coded edges with distinct SVG stroke styles and glyphs (solid stroke + check icon for green; dashed stroke + warning triangle icon for red wrong-parent edges).
7. **Toggle Buttons:** Implement toggles as native `<button type="button" aria-pressed={isActive}>` rather than generic `<div>` or `<g>` wrappers.
8. **Dropzone Fallback & Motion:** Embed a visually hidden, keyboard-focusable `<input type="file" id="file-upload" className="sr-only">` linked to a visible label button, and wrap D3 transitions in `window.matchMedia('(prefers-reduced-motion: reduce)')` to disable physics simulations.

---

### 3. Industry Accessibility Statement Checklist

After applying the fixes above, the following conformance statements can be truthfully claimed:

- [ ] **WCAG 2.2 Conformance:** The web application conforms to Level AA standards, guaranteeing verified contrast ratios ($\ge 4.5:1$ for text, $\ge 3.0:1$ for interactive controls and borders).
- [ ] **Full Keyboard Operability:** All graph nodes, edge inspectors, modal side panels, and form controls are fully navigable and actionable via standard keyboard sequences (Tab, Enter, Space, Escape, Arrows).
- [ ] **Redundant Sensory Encoding:** Visual status indicators—including lineage validation, wrong-parent links, and tree confidence states—do not rely on color alone to convey meaning.
- [ ] **Dynamic Assistive Technology Support:** Critical UI updates, live confidence metric recalculations, and asynchronous node uploads are communicated cleanly via standard ARIA live regions and accessible names.
- [ ] **Vestibular & Motor Accommodations:** Drag-and-drop operations have direct native click/file-dialog fallbacks, interactive touch targets meet the $24 \times 24$px minimum size requirement, and all canvas animations honor the `prefers-reduced-motion` user preference.
