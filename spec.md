# spec.md — Visual Transformer Phase 2

**Status:** DECISIONS LOCKED — Pending GO signal  
**Prepared by:** Atlas (Claude Code)  
**Phase:** 2 — Stability, UX, and Library Management  

---

## 1. Product Overview

Visual Transformer is a Streamlit-based batch image processing tool for museum marketing teams. It accepts standard and RAW image files, applies crop/resize/alignment operations, and exports format-matched asset packages as ZIP files.

Phase 1 established the core processing engine: 72 DPI enforcement, ICC profile retention, PNG transparency pipeline, RAW support, zoom-aware cropping, temp-file ZIP export, and upscale detection.

Phase 2 addresses accumulated bugs, UX friction, format library reliability, and lays groundwork for multi-user workflows and advanced features.

---

## 2. Phase 2 Scope

**In scope:** B1–B6 (all bugs), F1 (naming patterns), F2 (template preset), F3 (JSON import), F5 (named JSON profiles — Option A), and UX improvements.  
**Deferred — not Phase 2:** F4 (AI focal point detection), F6 (Real-ESRGAN upscale). These will not be implemented in Phase 2 under any circumstance.

---

## 3. Bugs

### B1 — Custom Size Fields Default to 1080×1080 Instead of Source Dimensions
**Type:** Bug / UX  
**Priority:** High  

**Current behavior:** When Custom Settings is opened, the Width and Height fields always default to 1080×1080 regardless of the uploaded image size.

**Expected behavior:** Width and Height fields should default to the original dimensions of the currently selected image (`ow`, `oh`). This is already available in scope at the time the widgets are rendered.

**Implementation note:** The session state keys `cw_in` and `ch_in` persist across images. The fix must reset these keys whenever the selected image changes — not just when "Set Original Size" is checked. Tie the reset to `cur_file.name`.

**Acceptance criteria:**
- Upload a 2400×1600 image → open Custom Settings → Width shows 2400, Height shows 1600
- Switch to a different image (toggle OFF) → dimensions reset to the new image's source size
- Switch to a different image (toggle ON: "Apply custom size to all images") → dimensions remain unchanged
- Values are still editable after defaulting

---

### B2 — Alignment Preview Expander Is Open by Default
**Type:** UX Issue  
**Priority:** Medium  

**Current behavior:** The "Preview & Alignment" expander inside Custom Settings is `expanded=True` and opens automatically, creating visual clutter.

**Expected behavior:** Collapsed by default (`expanded=False`). User opens it intentionally when needed.

**Acceptance criteria:**
- Open Custom Settings → expander is closed
- Clicking the expander opens it normally
- State does not persist between reruns (Streamlit default behavior is acceptable)

---

### B6 — Custom Mode Uses Pixel Crop Instead of Fill-to-Frame Scaling
**Type:** UX / Behavior Correction  
**Priority:** High  

**Current behavior:** At zoom = 100%, `zoom_crop` treats the crop window as exactly `target_width × target_height` source pixels. A 3000×2000 source exported to 1080×1080 cuts out a 1080×1080 pixel region from the center — making the image look heavily zoomed in, as if viewed through a small punch-in window.

**Expected behavior:** At zoom = 100%, the image should scale to fill the target frame — the same feel as a fill resize. The source is scaled up or down until it covers the entire target in both dimensions, with no empty space and no letterboxing. Cropping only occurs as the natural overflow from that fill scale. The result should feel like a scale-to-fill, not a zoom-in.

**Fill-to-frame model:**

The scale factor is `fill_scale = max(tw / src_w, th / src_h)`. At this scale:
- One axis fits exactly — those two edges meet the frame perfectly
- The other axis overflows — the excess is cropped

**Natural overflow at zoom = 100 (reference):**

| Condition | Fits exactly | Overflows at zoom=100 |
|---|---|---|
| `tw/src_w > th/src_h` | Left + Right edges | Top + Bottom |
| `th/src_h > tw/src_w` | Top + Bottom edges | Left + Right |
| `tw/src_w == th/src_h` | All four edges (perfect fit) | None |

**Alignment control order and visibility:**

Controls are always rendered in fixed order: **Zoom → X → Y**. Sliders never appear or disappear. Active/inactive state is communicated by enable/disable, not by presence.

Overflow is computed from the effective scale at the current zoom level, in source-pixel space:

```
effective_scale = fill_scale × (zoom / 100)
h_overflow = src_w − (tw / effective_scale)   # source pixels available to pan horizontally
v_overflow = src_h − (th / effective_scale)   # source pixels available to pan vertically
```

`tw / effective_scale` is identical to `crop_w` inside `zoom_crop`, and `h_overflow` is identical to `max_cx`. The UI and the crop function share the same geometry.

- `h_overflow > 0.5` → X slider is **enabled**; user can pan left–right
- `v_overflow > 0.5` → Y slider is **enabled**; user can pan top–bottom
- Overflow = 0 on an axis → slider is **disabled**, locked at 50, no additional messaging
- Both sliders can be enabled simultaneously when zoom creates overflow on both axes
- The layout does not shift when slider states change

At 0% the crop sits at one extreme of the overflow range; at 50% it is centered; at 100% it is at the other extreme.

**Zoom behavior:**

Zoom multiplies the effective scale beyond the fill baseline. Zoom = 150% means 1.5× the fill scale:
- At zoom = 100%: exactly one axis has overflow (or none for a perfect-fit ratio) — at most one slider is enabled
- As zoom increases past 100%: the previously zero-overflow axis gains overflow and its slider becomes enabled
- At high zoom: both axes typically have overflow and both sliders are enabled
- Slider ranges grow as zoom increases, reflecting the larger overflow on each axis

**Square source / perfect-fit ratio at zoom = 100:** Both alignment sliders are rendered but disabled. No caption is shown. As soon as zoom > 100%, overflow appears and the relevant sliders become enabled.

**Image preview container:**

- Display width follows the output aspect ratio, bounded at 500 px; portrait outputs are narrower than the column
- Height is bounded at approximately 380 px — portrait, square, and landscape outputs all stay within the same vertical band and do not push content below unpredictably
- Image fits inside the display area while maintaining its exact output aspect ratio (equivalent to `object-fit: contain`)
- Rendered via `st.image()` in a placeholder slot; the crop is scaled in Python to fit within a 500×380 px bounding box before display, preserving aspect ratio and never upscaling
- Below the preview: a caption showing the estimated export file size as `~X KB` or `~X MB` — no extra wording
- If the current custom settings would produce an upscale (`effective_scale > 1.0`), a `⚠ upscale` indicator appears inline with the size caption

**Preview update timing:**

- The preview is rendered from the current render cycle's slider values, not from the previous render's saved state
- A placeholder slot is declared in the left column before the controls column runs; the preview fills that slot after the controls have captured the current zoom, X, and Y values
- This eliminates the one-render lag: the preview always reflects the current slider position

**Navigation placement:**

- Navigation sits in the **controls column (right)**, above the Zoom slider
- Structure: `[ ‹ ]  [ Image N of N · filename ]  [ › ]`, centered
- Visually secondary to the image (compact, small text)

**Acceptance criteria:**
- Upload a 3000×2000 image, target 1080×1080: at zoom=100% the preview looks like a fill resize (image fills frame, left/right edges touch, top/bottom slightly cropped) — not a pixel-level punch-in
- At zoom=100%: one slider is enabled, the other is simply disabled (greyed out), no caption
- At zoom=150%: if both axes have overflow, both sliders are enabled
- A disabled slider does not move the image — value is fixed at 50
- Moving a slider updates the preview on the same interaction — no second click required
- Preview and export produce identical results

---

### B3 — Category Field Is Free Text and Causes Input Errors
**Type:** Bug / Data Management  
**Priority:** High  

**Current behavior:** The Category field in the "Add Format" form is a plain `st.text_input`. Users can type anything, causing inconsistent category names (e.g., "social", "Social", "SOCIAL" all appear as separate groups in the TRANSFORMER tab).

**Expected behavior:** Category is a managed dropdown populated from a defined category list. Default categories: **SOCIAL, WEB, EMAIL**. The system must also allow adding and deleting categories.

**Behavior spec:**
- Category dropdown in "Add Format" form shows all existing categories
- A separate "Manage Categories" section (in FORMATS tab or SETTINGS tab) allows:
  - Adding a new category name
  - Deleting an unused category (warn if formats still use it)
  - Renaming is out of scope for Phase 2 (see §8 deferred items)
- Category list is persisted — stored alongside or within `transformer_specs.json`

**Storage:** Add a top-level `"categories"` key to `transformer_specs.json`:
```json
{
  "categories": ["SOCIAL", "WEB", "EMAIL"],
  "formats": [...]
}
```

**Acceptance criteria:**
- "Add Format" shows a dropdown of all defined categories
- A new category can be added and immediately appears in the dropdown
- Deleting a category that has assigned formats shows a warning
- Category names are stored consistently in uppercase
- No free-text category entry remains

---

### B4 — Duplicate Format Names Are Allowed and Cause Errors
**Type:** Bug / Validation  
**Priority:** High  

**Current behavior:** The "Add Format" form allows saving a format with the same label as an existing one. This causes broken behavior in the TRANSFORMER tab because format card checkbox keys (`run_<label>`) collide.

**Expected behavior:** Validate the label on submit. If a format with the same label already exists, block the save and show a clear error message.

**Acceptance criteria:**
- Attempt to add a format named "Instagram / FB Post" when one already exists → error message shown, nothing saved
- Error message: `"A format named '[name]' already exists. Please use a unique name."`
- After correcting the name, save proceeds normally

---

### B5 — Upscale Warning Ignores Zoom Setting
**Type:** Bug  
**Priority:** Medium  

**Current behavior:** The upscale warning compares raw source dimensions (`src_w`, `src_h`) against target dimensions. It does not account for the zoom level set in alignment controls.

**Why this is wrong:** At Zoom=200%, the effective crop area is half the source dimensions. A 2000×2000 source image zoomed 200% into a 1080×1080 target is actually using a 540×540 pixel crop area — which is being upscaled. The current warning would not trigger because `src_w (2000) > target (1080)`.

**Expected behavior:** The warning should compare the **effective crop dimensions** (accounting for zoom) against the target size.

**Upscale detection formula (fill-to-frame model):**
```
fill_scale = max(target_w / src_w, target_h / src_h)
effective_scale = fill_scale * (zoom / 100)
is_upscale = effective_scale > 1.0
```
`effective_scale > 1.0` means the source is being stretched beyond its native resolution to fill the target frame. This accounts for both the fill scaling and any additional zoom.

**Scope:** This only applies to Custom mode (zoom is not available in Template mode). Template mode warning logic is unchanged.

**Acceptance criteria:**
- 2000×2000 source, target 1080×1080, zoom 100%: `fill_scale = 0.54`, `effective_scale = 0.54` → no warning
- 2000×2000 source, target 1080×1080, zoom 200%: `fill_scale = 0.54`, `effective_scale = 1.08 > 1.0` → warning triggered
- 800×800 source, target 1080×1080, zoom 100%: `fill_scale = 1.35`, `effective_scale = 1.35 > 1.0` → warning triggered
- Warning persists across reruns (stored in session state) until the next export run clears it

---

## 4. Features

### F1 — Batch Renaming Patterns
**Type:** Feature  
**Priority:** Medium  

**Description:** Allow exported file names to be constructed from configurable tokens rather than the fixed `PSAM_<base>_<format>.<ext>` pattern.

**Proposed tokens:**
| Token | Output example |
|-------|---------------|
| `[Date]` | `2026-04-06` |
| `[Artist]` | User-defined field |
| `[Format]` | Format label (e.g., `Instagram_FB_Post`) |
| `[Project]` | Project Export Name from Settings |
| `[Filename]` | Source file base name |

**UI:** A text input in the SETTINGS tab with a live preview of the resulting filename. Example: `[Date]_[Artist]_[Format]` → `2026-04-06_Dupont_Instagram_FB_Post.jpg`.

**Notes:**
- `[Artist]` requires a new "Artist / Creator" field in Settings
- Pattern is applied globally to all exports in a batch
- **Decision (OQ-1 locked):** The Phase 1 "Custom Output Filename" field is removed and fully replaced by this pattern system. It is the single source of truth for output naming. No dual-field approach.

**Default pattern:** `[Project]_[Filename]_[Format]`

**Acceptance criteria:**
- Pattern input defaults to `[Project]_[Filename]_[Format]` on first load
- Pattern input accepts any combination of tokens and free text
- Unknown tokens are passed through literally (no silent failure)
- Live preview shows example output below the input field
- Pattern is saved in session state and persists across the session

---

### F2 — Template Preset Dropdown Inside Custom Settings
**Type:** Feature / UX Improvement  
**Priority:** Medium  

**Description:** Add a dropdown inside the Custom Settings block that lists all available templates. Selecting one pre-fills Width, Height, Format, and Quality with that template's values. Alignment tools remain active and editable after the preset is applied.

**Design decision (locked):** The dropdown is a one-time loader, not a persistent mode. It has no ongoing relationship with the fields after applying. The user fully owns the fields once a preset is loaded.

**Behavior spec:**
- The top of the Custom Settings block contains a single row of four controls in order: **Load from Template · Apply custom size to all images · Set Original Size · Lock Aspect Ratio**
- Column proportions approximately `[3, 2, 2, 2]`; all three boolean controls use `st.toggle` with explicit session state keys
- Dropdown label: "Load from Template (optional)"; default state: empty / no selection
- Each dropdown option displays as: `name — W×H · Format @ Q%` (e.g. `Instagram / FB Post — 1080×1080 · WebP @ 85%`); the stored value remains the template label so the callback lookup is unaffected
- On selection: writes `cw_in`, `ch_in`, `ce_in`, `cq_in` from the template's values via an `on_change` callback, then resets the dropdown to blank and reruns
- The dropdown is always blank between uses — it is a trigger, not a state holder
- After apply: user can still freely modify any field and use alignment/zoom controls
- Alignment state (`align_map`) is not reset when a preset is loaded — zoom and positioning persist per image
- Selecting a template does NOT activate Template mode or add the format to the selected template list
- No inter-control disabling logic — all four controls are always active regardless of each other's state

**Acceptance criteria:**
- Dropdown shows all formats with the full `name — W×H · Format @ Q%` display string
- Selecting a template updates all four input fields immediately and resets the dropdown to blank
- The same template can be re-selected and re-applied multiple times
- All three boolean controls render as toggles in a consistent visual style
- Alignment and zoom sliders remain fully functional after preset is applied
- Selecting the blank default is a no-op

---

### F3 — JSON Import for Format Library
**Type:** Feature  
**Priority:** Low-Medium  

**Description:** Add an import mechanism in the SETTINGS tab that accepts a JSON file upload and merges or replaces the current format library.

**Behavior spec:**
- File uploader (`.json` only) in SETTINGS tab, below the existing Export Library button
- Two import modes (radio or toggle):
  - **Merge**: Add new formats from the file; skip duplicates (by label). Categories are merged by union: existing categories are preserved and any new categories from the imported file are appended.
  - **Replace**: Replace the entire library with the imported file
- Validate the JSON structure before applying (must have a `"formats"` key with an array)
- Show a success/error message after import

**Acceptance criteria:**
- Upload a valid JSON → library updates and persists to `transformer_specs.json`
- Upload an invalid JSON → error shown, library unchanged
- Merge mode: existing formats are preserved, duplicates skipped with a count shown; new categories from the file are appended to the category list
- Replace mode: confirmation prompt before overwriting

---

### F5 — Per-User Template Storage / Profile System
**Type:** Feature  
**Priority:** Medium  
**Architecture (OQ-2 locked):** Option A — Named JSON Profile Files. No authentication, no cloud sync, no backend. Local-first.

**Core requirement:** Different team members can access their own saved format libraries without losing the shared museum defaults.

**Behavior spec:**
- Each profile is a separate `specs_<ProfileName>.json` file in the project directory
- A `specs_default.json` is always present, always protected — it cannot be deleted or overwritten
- SETTINGS tab shows an "Active Profile" selectbox populated by scanning `specs_*.json` files
- "New Profile" button creates a copy of the current library under a new name
- Switching profiles loads that profile's formats and categories into session state
- All saves write to the active profile file, not always `transformer_specs.json`

**Acceptance criteria:**
- Create a new profile → it appears in the selector immediately
- Switch profiles → format library updates to that profile's contents
- Attempt to delete the default profile → action is blocked
- Formats saved in one profile do not appear in another

---

## 5. UX Improvements (already captured in bugs above)

- **B1** covers the dimension defaulting issue
- **B2** covers the collapsed preview
- **F2** addresses Custom Settings workflow speed

---

## 6. Locked Product Decisions

### OQ-1 — Naming System ✅ LOCKED
**Decision:** The Phase 1 "Custom Output Filename" field is removed and replaced by the F1 pattern system. The pattern system is the single source of truth for output naming. No dual-field approach.

---

### OQ-2 — Profile / Per-User Template Storage ✅ LOCKED
**Decision:** Option A — Named JSON Profile Files.  
- Profiles stored as `specs_<ProfileName>.json` in the project directory
- No authentication, no cloud sync, no backend required
- Default profile always exists and is protected from deletion
- System is local-first and simple

---

### OQ-3 — AI Features Scope ✅ LOCKED
**Decision:** F4 (AI Focal Point Detection) and F6 (Real-ESRGAN Upscale) are deferred out of Phase 2. They will not be implemented in this phase. Focus remains on stability, UX, and library management.

---

## 7. Acceptance Criteria Summary

| ID | Item | Key Test |
|----|------|----------|
| B1 | Dimension defaults | Upload 2400×1600 → fields show 2400 and 1600 |
| B2 | Collapsed preview | Open Custom Settings → expander is closed |
| B3 | Category dropdown | Add Format shows dropdown; new categories persist |
| B4 | Duplicate names | Adding duplicate label shows error, nothing saved |
| B5 | Zoom-aware warning | 2000px source, 1080px target, zoom 200% → warning fires |
| B6 | Fill-to-frame crop | 3000×2000 → 1080×1080: image fills frame at zoom=100%, not punched in |
| F1 | Naming patterns | `[Date]_[Artist]_[Format]` produces correct filename |
| F2 | Template preset | Select template → fields update, alignment still works |
| F3 | JSON import | Valid JSON merges/replaces library; invalid JSON shows error |

---

## 8. Out of Scope / Deferred

| Item | Reason |
|------|--------|
| F4 — AI focal point detection | Locked out of Phase 2. High complexity, vision model dependency. Revisit in a later phase. |
| F6 — Real-ESRGAN upscale | Locked out of Phase 2. Heavy dependency, performance risk. Revisit in a later phase. |
| Category renaming | Cascading update to all formats using that category; add/delete is sufficient for Phase 2 |
| Authentication / login system | Locked out. Option A profile system is the chosen approach. |
| PNG as export format | Not requested; JPEG and WebP cover current needs |
| Video/GIF support | Out of scope for this tool |
