# plan.md — Visual Transformer Phase 2 Roadmap

**Status:** DECISIONS LOCKED — Pending GO signal  
**Prepared by:** Atlas (Claude Code)  
**Follows:** Phase 1 (M0–M10 complete)  

---

## Recommended Phase 2 Priorities

Before any implementation begins, address these in order:

1. **B4 first** (duplicate names) — data integrity bug that can corrupt session state; one-line validation fix.
2. **B1 next** (dimension defaults + toggle) — affects every Custom Settings session. High friction, easy fix.
3. **B3 after** (category management) — foundational for F1 and F5; fix library reliability before building on top of it.
4. **B2** (collapse preview) — trivial, no dependencies.
5. **B6** (fill-to-frame crop model) — core crop model rewrite; must land before B5 since B5's upscale formula depends on it.
6. **B5** (zoom-aware upscale warning) — implement after B6; uses fill_scale from the new crop model.
7. **F2 and F3** — workflow improvements that build on a stable library (B3 should land first).
8. **F1** (naming patterns) — OQ-1 locked: removes Custom Output Filename field, replaced by pattern system.
9. **F5** (profiles) — OQ-2 locked: Option A (named JSON profiles); implement after MC1 since they share the JSON storage layer.
10. **F4, F6** — deferred to Phase E. Do not start in Phase 2.

---

## Phase Structure

### Phase A — Stability and Validation
*Goal: Fix bugs that corrupt data or produce incorrect behavior. All items are small and independent.*

#### MA1 — Prevent Duplicate Format Names (B4)
**Effort:** XS  
**Depends on:** Nothing  
**Change:** In the "Add Format" form submit handler, check if any existing spec in `st.session_state.specs` has the same `label` (case-insensitive). If so, call `st.error(...)` and do not save.  
**File:** `streamlit_app.py` — FORMATS tab form submit block  
**Risk:** None  

#### MA2 — Default Custom Size Fields to Source Dimensions (B1)
**Effort:** S  
**Depends on:** Nothing  
**Change:** Add a `st.toggle("Apply custom size to all images", key="lock_custom_dims")` above the dimension inputs. Track the last-seen filename in `st.session_state.last_custom_img`. When `cur_file.name != last_custom_img`, reset `cw_in` and `ch_in` to `ow`/`oh` only if `lock_custom_dims` is False; always update `last_custom_img`. When the toggle is ON, dimensions persist unchanged across image switches.  
**File:** `streamlit_app.py` — Custom Settings block, before the number_input widgets  
**Risk:** Low. Must not conflict with the existing "Set Original Size" checkbox logic which already forcibly writes these keys. Toggle state (`lock_custom_dims`) persists in session state for the duration of the session.

#### MA3 — Zoom-Aware Upscale Warning (B5)
**Effort:** S  
**Depends on:** MB3 (fill-to-frame model). The upscale formula uses fill_scale, which is only meaningful after MB3 rewrites zoom_crop. Do not implement MA3 before MB3 is stable.  
**Change:** In the generate loop, for Custom mode, replace the existing direct dimension comparison with the fill-to-frame upscale condition:
```python
zoom = align.get("zoom", 100)
fill_scale = max(sp['width'] / src_w, sp['height'] / src_h)
effective_scale = fill_scale * (zoom / 100)
is_upscale = effective_scale > 1.0
```
For Template mode, keep the existing direct comparison (zoom is always 100 there).  
Store collected warnings in `st.session_state["last_upscale_warnings"]` at the end of the generate run. Render the `st.warning()` block **outside** the `if st.button():` guard so it persists across reruns. A new generate run resets the list before the loop begins, clearing any stale warning.  
**File:** `streamlit_app.py` — generate loop, warning display block  
**Risk:** Low once MB3 is in place. Formula is a single condition derived from fill_scale and zoom.

---

### Phase B — UX Cleanup
*Goal: Reduce friction and visual clutter. All items are UI-only changes.*

#### MB1 — Collapse Alignment Preview by Default (B2)
**Effort:** XS  
**Depends on:** Nothing  
**Change:** `st.expander("Preview & Alignment", expanded=True)` → `expanded=False`  
**File:** `streamlit_app.py` line ~189  
**Risk:** None  

#### MB2 — Template Preset Dropdown in Custom Settings (F2)
**Effort:** M  
**Depends on:** Nothing (works better after MA2 since fields will default correctly)  
**Change:** Replace the current top-of-container controls with a single 4-column row `st.columns([3,2,2,2])`:

- **Col 1:** `st.selectbox("Load from Template (optional)", key="preset_select", on_change=apply_preset)`. Options list stores label strings as values; `format_func` renders each as `"name — W×H · Format @ Q%"`. Blank option `""` is always first.
- **Col 2:** `st.toggle("Apply custom size to all images", key="lock_custom_dims")`
- **Col 3:** `st.toggle("Set Original Size", key="set_orig_size")` — replaces the previous `st.checkbox`; add explicit key
- **Col 4:** `st.toggle("Lock Aspect Ratio", key="lock_ar")` — replaces the previous `st.checkbox`; add explicit key

`apply_preset` callback (unchanged logic):
1. Read the selected label from `st.session_state["preset_select"]`
2. If non-empty, look up the matching spec and write its values to `cw_in`, `ch_in`, `ce_in`, `cq_in`
3. Write `""` back to `st.session_state["preset_select"]` to reset the dropdown to blank

`format_func` for the selectbox:
```python
_fmt = {s['label']: f"{s['label']} — {s['width']}×{s['height']} · {s['ext']} @ {s['quality']}%" for s in st.session_state.specs}
format_func=lambda x: _fmt.get(x, x) if x else ""
```

All widget reads downstream (`l_sz`, `l_ar`) must reference the new explicit keys. No inter-control disabling logic is added. The alignment state (`align_map`) is not touched.  
**File:** `streamlit_app.py` — top of Custom Settings `with st.container(border=True):` block  
**Risk:** Medium. `on_change` callback must write to session state keys before widgets render. Checkbox → toggle conversion is purely visual; both return a bool. New explicit keys replace position-based keys — both default to `False` so no state migration needed.

#### MB3 — Fill-to-Frame Crop Model + Constrained Alignment (B6)
**Effort:** M-L  
**Depends on:** Nothing. Must land before MA3 (zoom-aware upscale warning), because MA3's effective crop formula must use the new fill-scale model, not the old 1:1 pixel model.  
**Changes:**

1. **Rewrite `zoom_crop`:** Replace the current `crop_w = int(tw / zoom_factor)` model with fill-to-frame scaling:
   ```python
   fill_scale = max(tw / src_w, th / src_h)
   effective_scale = fill_scale * (zoom / 100)
   crop_w = tw / effective_scale   # source pixels to crop
   crop_h = th / effective_scale
   # axis behavior is determined by real-time overflow at the current zoom level
   # axes with no overflow are centered at 50; axes with overflow are user-adjustable
   ```
   The function signature (`img, tw, th, ax, ay, zoom`) does not change. The function uses whatever ax and ay values the caller passes — it has no internal axis-locking logic. The UI is responsible for passing 50 for any axis with no overflow.

2. **Real-time overflow detection (in UI, not in `zoom_crop`):** Before rendering the alignment sliders, compute overflow using the effective scale that includes the current zoom value:
   ```python
   fill_scale = max(cust_w / ow, cust_h / oh)
   zoom_val = state.get("zoom", 100)
   effective_scale = fill_scale * (zoom_val / 100)
   h_overflow = ow - (cust_w / effective_scale)   # source pixels to pan; identical to max_cx in zoom_crop
   v_overflow = oh - (cust_h / effective_scale)   # source pixels to pan; identical to max_cy in zoom_crop
   active_x = h_overflow > 0.5
   active_y = v_overflow > 0.5
   ```
   Render **all sliders always**. When an axis has no overflow: render with `disabled=True`, write 50 into `align_map` for that axis, and reset the widget session state key to 50 (prevents stale value reappearing when the slider re-enables). `zoom_crop` always receives both ax and ay values; the UI ensures the inactive axis value is 50.

3. **UI labels and control order:**
   - Control order (fixed, never changes): **Zoom → X → Y**
   - X slider label: `"Left → Right"`; Y slider label: `"Top → Bottom"`
   - When disabled: greyed out, no caption or additional messaging
   - No slider is ever hidden or conditionally rendered — only `disabled=` state changes.

4. **Navigation, preview rendering, and preview timing:**
   - Navigation (prev/next buttons and image counter) is in `pcol_ctrl` (right column), above the Zoom slider
   - Navigation layout: `[ ‹ ]  [ counter/filename ]  [ › ]`, centered
   - In `pcol_img`, declare `preview_slot = st.empty()` and `size_slot = st.empty()` — these reserve the preview position without rendering content yet
   - In `pcol_ctrl`, render navigation, then Zoom → X → Y sliders; capture current values `mz`, `mx`, `my`; write state
   - After both columns, compute `crop = zoom_crop(..., mx, my, mz)` using the current render's slider values
   - Scale the crop in Python to fit within a 500×380 px bounding box (preserves aspect ratio, never upscales); fill `preview_slot` via `st.image()` with `use_container_width=False`
   - Fill `size_slot` with a caption: `~X KB` or `~X MB` only — no extra wording. If `effective_scale > 1.0` for the current settings, append `⚠ upscale` inline
   - This eliminates the one-render preview lag: the preview always reflects the current slider values, not the previous render's saved state

5. **Upscale detection update:** The `is_upscale` condition for disabling the zoom slider must be recomputed using fill_scale: `is_upscale = fill_scale > 1.0` (i.e., the source is smaller than the target — scaling up to fill). Note: the condition is `> 1.0`, not `< 1.0`.

**File:** `streamlit_app.py` — `zoom_crop` helper, Custom Settings alignment block (preview, navigation, controls)  
**Risk:** Medium-High. Three interconnected changes: crop model rewrite, slider behavior change (show/hide → enable/disable), and layout restructure (navigation moves, preview rendering, placeholder timing). The preview and generate loop both call `zoom_crop` — both change simultaneously, which is correct. Test carefully across landscape/portrait/square sources and targets. Navigation move is structural but isolated to the expander block.

---

### Phase C — Format Library Management
*Goal: Make the format library reliable, well-structured, and importable.*

#### MC1 — Category Management System (B3)
**Effort:** M-L  
**Depends on:** Nothing, but must land before MC2, MD1, MD2  
**Changes:**

1. **JSON schema update:** Add `"categories"` key to `transformer_specs.json`:
   ```json
   { "categories": ["SOCIAL", "WEB", "EMAIL"], "formats": [...] }
   ```
   Update `save_specs_to_disk()` and the INITIALIZATION load block to handle the new key. Default to `["SOCIAL", "WEB", "EMAIL"]` if missing (backwards compatible).

2. **Add Format form:** Replace `st.text_input("Category", "SOCIAL")` with a `st.selectbox` populated from `st.session_state.categories`.

3. **SETTINGS export button:** The inline `json.dumps` on the Export Library button (SETTINGS tab) constructs JSON directly and is not covered by `save_specs_to_disk()`. It must also be updated to include `"categories"` so the exported backup round-trips correctly:
   ```python
   json_data = json.dumps({"categories": st.session_state.categories, "formats": st.session_state.specs}, indent=4)
   ```

4. **Category management UI:** Add a "Manage Categories" expander in the FORMATS tab:
   - Text input + "Add Category" button: validates non-empty, non-duplicate, uppercases, appends, saves.
   - For each existing category: a "Delete" button. If formats still use it, show a warning with confirm/cancel (same two-step pattern as Phase 1 M10).

4. **Session state:** Add `st.session_state.categories` (list of strings).

**File:** `streamlit_app.py` — INITIALIZATION, `save_specs_to_disk()`, FORMATS tab  
**Risk:** Medium. Schema change requires backwards-compatible load. Two-step delete has Streamlit form/button timing nuance.

#### MC2 — JSON Import for Format Library (F3)
**Effort:** S  
**Depends on:** MC1 (so imported JSON categories are handled correctly)  
**Change:** Add a `st.file_uploader` for `.json` files in SETTINGS below the export button. On upload, parse and validate (must have `"formats"` key). Offer Merge or Replace via `st.radio`. Execute and save.  
**File:** `streamlit_app.py` — SETTINGS tab  
**Risk:** Low. Validation gate prevents bad state.

---

### Phase D — Power User Features
*Goal: Structured naming and per-user profiles.*

#### MD1 — Batch Renaming Patterns (F1)
**Effort:** M  
**Depends on:** MC1 (better after library is stable). OQ-1 locked: Custom Output Filename field is removed and replaced by this system.  
**Changes:**
- Remove "Custom Output Filename" field from SETTINGS tab
- Add "Filename Pattern" text input with a live preview line below it
- Add "Artist / Creator" text field in SETTINGS
- Parse pattern at export time: replace `[Date]`, `[Artist]`, `[Format]`, `[Project]`, `[Filename]` tokens. Unknown tokens pass through literally.
- Store `filename_pattern` and `artist_name` in session state

**File:** `streamlit_app.py` — SETTINGS tab, generate loop filename construction  
**Risk:** Low-Medium. Token replacement is straightforward; main risk is breaking existing filename construction.

#### MD2 — Named JSON Profile System (F5)
**Effort:** M  
**Depends on:** MC1 (profiles share the categories + formats JSON structure)  
**Architecture (OQ-2 locked):** Option A — Named JSON Profile Files. No authentication, no cloud sync, no backend.

**Implementation:**
- Profile files stored as `specs_<ProfileName>.json` in the project directory
- `specs_default.json` is created from the current library on first run and protected (delete disabled)
- SETTINGS tab: "Active Profile" selectbox populated by scanning `specs_*.json` files
- "New Profile" button: creates a copy of the current library under a new name
- "Delete Profile" button: disabled for `default`
- Switching profiles loads the corresponding JSON into `st.session_state.specs` and `st.session_state.categories`
- `save_specs_to_disk()` writes to the active profile path, not always `transformer_specs.json`
- Active profile name stored in `st.session_state.active_profile`

**File:** `streamlit_app.py` — INITIALIZATION, `save_specs_to_disk()`, SETTINGS tab  
**Risk:** Medium. File scanning on every rerun should be minimized (cache in session state). `save_specs_to_disk()` refactor must be careful not to break existing save calls.

---

### Phase E — Advanced / AI Features (Deferred)
*Not Phase 2 scope. Documented here for future planning.*

#### ME1 — AI Focal Point Auto Detection (F4)
**Deferred reason:** Requires selecting and integrating a vision model, handling detection failures, and testing on museum content types. Adds a significant new dependency.  
**When to revisit:** After Phase D is stable and alignment workflow is confirmed as the main bottleneck.  
**Likely path:** OpenCV `cv2.CascadeClassifier` for face detection (free, local). Returns bounding box → compute crop center → pre-fill alignment sliders.

#### ME2 — Real-ESRGAN Conditional Upscale (F6)
**Deferred reason:** ~200MB model, GPU dependency, 30–60s CPU fallback per image. The B5 zoom-aware warning already communicates the limitation.  
**When to revisit:** After ME1, or when user demand is documented.  
**Likely path:** `realesrgan` Python package, triggered only when `is_upscale == True` and source shorter edge < 800px, behind an opt-in toggle in SETTINGS.

---

## Dependencies Map

```
MA1 (duplicate names)     — no deps
MA2 (dimension defaults)  — no deps
MA3 (zoom warning)        — must come after MB3 (fill-scale model changes effective crop formula)
MB1 (collapse preview)    — no deps
MB2 (template dropdown)   — better after MA2
MB3 (fill-to-frame crop)  — no deps; blocks MA3
MC1 (category system)     — no deps; blocks MC2, MD1, MD2
MC2 (JSON import)         — requires MC1
MD1 (naming patterns)     — better after MC1; OQ-1 locked (replaces Custom Output Filename)
MD2 (profiles)            — requires MC1
ME1 (focal point AI)      — deferred
ME2 (Real-ESRGAN)         — deferred
```

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Session state write-before-render timing (MB2) | Medium | Medium | Follow the existing "Set Original Size" pattern exactly |
| JSON schema change breaks existing library (MC1) | Low | High | Load with `.get("categories", ["SOCIAL","WEB","EMAIL"])` fallback |
| Profile file scanning slow on every rerun (MD2) | Low | Low | Cache scan result in session state; only rescan on profile switch |
| Token parsing edge cases in filename patterns (MD1) | Low | Low | Unknown tokens pass through literally; no silent failures |
| Category delete with formats still assigned (MC1) | Medium | Medium | Two-step confirm pattern (same as Phase 1 M10) |

---

## Effort Estimates

| Milestone | Effort | Phase |
|-----------|--------|-------|
| MA1 — Duplicate name validation | XS (~15 min) | A |
| MA2 — Dimension defaults | S (~30 min) | A |
| MA3 — Zoom-aware warning | S (~20 min) | A |
| MB1 — Collapse preview | XS (~5 min) | B |
| MB2 — Template dropdown | M (~1–2 hrs) | B |
| MB3 — Fill-to-frame crop + alignment UI + preview layout | M-L (~2–3 hrs) | B |
| MC1 — Category management | M-L (~3–4 hrs) | C |
| MC2 — JSON import | S (~45 min) | C |
| MD1 — Naming patterns | M (~2 hrs) | D |
| MD2 — Named profiles | M (~2–3 hrs) | D |
| ME1 — AI focal point | L (~1–2 days) | E (deferred) |
| ME2 — Real-ESRGAN | L (~1–2 days) | E (deferred) |

---

## Execution Order

```
Phase A:  MA1 → MA2             (MA3 deferred until after MB3)
Phase B:  MB1 → MB3 → MA3 → MB2
          MB1 is trivial; MB3 rewrites the crop model (must land before MA3);
          MA3 is moved here because it depends on MB3's fill-scale formula;
          MB2 is safer after MA2 and MB3 are stable.
Phase C:  MC1 → MC2             (MC2 requires MC1)
Phase D:  MD1 → MD2             (both benefit from MC1 being stable)
Phase E:  ME1 or ME2            (deferred, order TBD)
```

All Phase A milestones can be verified immediately in the browser after each change. MC1 is the most structurally significant change in Phase 2 and should be tested carefully before proceeding to D.
