# Recap Desktop UI Reference

This folder is the visual source of truth for the Tauri desktop UI.

Open `index.html` in a browser. Use the top reference switcher to view:

- `01 Main running`
- `02 Partial success`
- `03 Settings`

Rules for agents:

- Match this HTML reference more closely than the generated PNG mockups.
- Treat layout dimensions, spacing, density, colors, typography, and component hierarchy as intentional.
- Do not implement app logic here.
- Do not add this folder as a runtime dependency.
- Use it only as a static visual reference when implementing the React/Tauri UI.

Key dimensions:

- App frame: 1180x760 reference viewport.
- Sidebar: 240px.
- Inspector: 288px.
- Main content padding: 16px.
- Settings nav: 192px.
- Border radius: 6-8px.

Pipeline rule:

- Use the circular stepper from `01 Main running`: one horizontal line, one round icon per step, and a conic/ring progress indicator around the active step.
- Do not replace it with flat rectangular step cards.

The selected brand/icon direction is `docs/mockups/icons/recap-icon-dimensional-1.png`.
