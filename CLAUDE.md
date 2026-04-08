# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository. It defines the "Museum-Grade" standards and the strict milestone-based refactor process.

## Running the App

```bash
streamlit run streamlit_app.py
```

No build step needed. Requires `transformer_specs.json` and `style.css` in the same directory.

## Dependencies

```bash
pip install -r requirements.txt
# macOS: brew install libraw  (required by rawpy)
```

Current dependencies: `streamlit`, `Pillow`, `pandas`, `piexif`, `rawpy`, `numpy`

## Configuration

- **Slack notifications**: Add `SLACK_WEBHOOK_URL` to `.streamlit/secrets.toml`. Silently disabled if missing.
- **Format specs**: Stored in `transformer_specs.json` (auto-created with defaults if missing, saved on in-app edits via the FORMATS tab).

---

## Architecture

The app is a **single-file Streamlit application**. There is no separate module or processing engine file — all logic lives in `streamlit_app.py`.

| File | Role |
|------|------|
| `streamlit_app.py` | Everything: UI, session state, helper functions, processing pipeline, ZIP export |
| `transformer_specs.json` | Predefined format templates (SOCIAL, WEB, EMAIL categories) |
| `slack_notifier.py` | Posts Block Kit messages to a Slack webhook after batch export |
| `style.css` | Custom dark-theme CSS injected via `st.markdown` |
| `requirements.txt` | Python dependencies |

### Internal structure of `streamlit_app.py`

The file is divided into three logical sections:

**Section 1 — Initialization:** Session state bootstrap on first load. Sets defaults for `specs`, `proj_name`, `img_idx`, `align_map`.

**Section 2 — Helpers:** Pure functions with no Streamlit calls. Safe to call from any context.

| Helper | Purpose |
|--------|---------|
| `load_image(file)` | Single entry point for all image loading. Returns `(img, icc_profile, dpi)`. Handles JPEG/PNG/WebP and RAW (CR2, NEF, ARW, DNG, ORF, RW2) via `rawpy`. |
| `zoom_crop(img, tw, th, ax, ay, zoom)` | Crops to target size with zoom (100–200%) and alignment (0–100). Falls back to `ImageOps.fit` when source is smaller than the crop box (upscale territory). |
| `prepare_for_format(img, ext)` | Format-aware mode conversion. JPEG: composites alpha over white, returns RGB. WebP: preserves alpha as RGBA. |
| `resolve_dpi(source_dpi)` | Returns `max(source_dpi, 72)` per axis — enforces 72 DPI minimum without reducing higher-DPI sources. |
| `build_exif_with_dpi(dpi)` | Builds a `piexif` Exif blob for embedding DPI in WebP exports. |
| `calculate_ratio(w, h)` | Returns GCD-reduced ratio string e.g. `"16:9"`. |
| `sanitize(name)` | Strips non-alphanumeric characters for safe filenames. |

**Section 3 — Interface:** Three Streamlit tabs rendered sequentially.

### Processing pipeline (generate loop)

```
load_image(up)                          → img (native mode), icc_profile, dpi_info
  ↓
zoom_crop / ImageOps.fit                → res (cropped + resized)
  Custom mode:  zoom_crop(...)          ← respects zoom + alignment from align_map
  Template mode: ImageOps.fit(..., centering=(0.5, 0.5))
  ↓
prepare_for_format(res, ext)            → res (correct color mode for codec)
  ↓
resolve_dpi(dpi_info)                   → final_dpi
  ↓
res.save(buf, ..., dpi=final_dpi, icc_profile=icc_profile)
  ↓
zf.writestr(fn, buf.getvalue())         → written to temp ZIP on disk
  ↓
st.download_button(data=f.read())       → served; temp file deleted in finally block
```

### ZIP strategy

The ZIP accumulator uses `tempfile.NamedTemporaryFile` — it is written to disk during generation, not held in RAM. Per-image encode buffers (`io.BytesIO`) remain in memory; they are transient and bounded to one image at a time.

---

## Core Operating Principles

These are non-negotiable on every export path, not optional requirements.

### 72 DPI Minimum
Every exported file must carry DPI metadata ≥ 72. Source DPI is read at load time via `img.info.get('dpi', (72, 72))`. `resolve_dpi()` applies `max(source, 72)` per axis — a 300 DPI scan stays at 300 DPI. JPEG: passed as `dpi=` kwarg. WebP: embedded via `piexif` Exif blob (`build_exif_with_dpi()`).

### ICC Color Profile Retention
The source ICC profile is extracted at load time (`img.info.get('icc_profile')`) and re-embedded in every save call via `icc_profile=icc_profile`. Passing `None` is safe — Pillow omits the tag silently. RAW files have no ICC profile; they default to `None`.

### Alpha Channel Handling
Images are loaded in their native mode (no premature `convert("RGB")`). Format-aware conversion happens at save time only via `prepare_for_format()`:
- **WebP output**: alpha is preserved (RGBA passthrough)
- **JPEG output**: alpha is composited over a white `(255, 255, 255)` background before encoding — never black-fill or artifacts

### Resampling Filter
All resize operations use `Image.Resampling.LANCZOS`. This is the highest-quality classical filter Pillow offers. No AI super-resolution is in use; upscaling is standard interpolation.

---

## Key Session State Keys

| Key | Type | Purpose |
|-----|------|---------|
| `specs` | `list[dict]` | Loaded format library |
| `proj_name` | `str` | ZIP export filename base |
| `custom_filename` | `str` | Optional override for per-file base name in exports |
| `img_idx` | `int` | Current gallery image index |
| `align_map` | `dict[str, dict]` | Per-filename alignment + zoom: `{"x": 50, "y": 50, "zoom": 100}` |
| `show_upscale_warnings` | `bool` | Whether to display upscale warnings after batch (default `True`) |
| `cw_in`, `ch_in` | `int` | Custom Settings width/height widget state |
| `ce_in`, `cq_in` | `str/int` | Custom Settings format/quality widget state |
| `run_<label>` | `bool` | Per-template-card checkbox state |
| `master_<category>` | `bool` | Category-level select-all checkbox state |

### Format spec schema

```json
{
  "FORMAT_NAME": {
    "category": "SOCIAL",
    "label": "Instagram / FB Post",
    "width": 1080,
    "height": 1080,
    "ratio": "1:1",
    "ext": "JPEG",
    "quality": 85
  }
}
```

---

## Refactor Phase 2: Documentation (START HERE)

Before any code is modified, the following documents must be generated and reconciled:
1. **spec.md**: Detailed requirements, constraints, and acceptance criteria for Phase 2 features.
2. **plan.md**: Technical roadmap with small, isolated milestones and proposed changes.



## Multi-File Reconciliation Rule

**Requirement:** 

When editing more than one planning or specification file in a single step (especially spec.md and plan.md), you must perform a reconciliation pass before presenting the result.

Reconciliation requirements:
1. Compare all edited files against each other
2. Check for:
   - contradictions
   - outdated or leftover wording
   - dependency mismatches
   - formula inconsistencies
   - scope drift
   - milestone order conflicts
3. Fix any inconsistencies before presenting

Required response format:
- Files edited
- Reconciliation check result (pass/fail)
- Conflicts found (if any)
- Fixes applied
- Final confirmation that files are aligned

## 🏛️ Museum-Grade Standards
All code changes must respect the Core Operating Principles above (72 DPI, ICC retention, alpha handling) in addition to any new Phase 2 requirements.

## 📋 Operational Rules
- **Small Milestones**: Implement one milestone at a time from `plan.md`. Run and verify after every change.
- **State Management**: Optimize `st.session_state` to minimize unnecessary `st.rerun()` calls.
- **Debug Protocol**: Analyze full error codes before suggesting fixes.
