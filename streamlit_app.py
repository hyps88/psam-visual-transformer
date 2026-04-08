import streamlit as st
from PIL import Image, ImageOps
import json, os, math, re, io, zipfile, piexif, tempfile, numpy as np

# --- PROFILE HELPERS (used by init and SETTINGS tab) ---
def _get_available_profiles():
    """Scan for specs_*.json profile files in the current directory."""
    return sorted([f[6:-5] for f in os.listdir('.') if f.startswith('specs_') and f.endswith('.json')])

def _load_profile_data(name):
    """Load (specs, categories) from specs_{name}.json with backwards-compat recovery."""
    _d = {}
    if os.path.exists(f"specs_{name}.json"):
        with open(f"specs_{name}.json") as f:
            _d = json.load(f)
    _s = _d.get('formats', [])
    _base = _d.get('categories', ["SOCIAL", "WEB", "EMAIL"])
    _extra = [s.get('category', 'OTHER') for s in _s if s.get('category', 'OTHER') not in _base]
    return _s, list(dict.fromkeys(_base + _extra))

# --- 1. INITIALIZATION [LOCKED] ---
st.set_page_config(page_title="Visual Transformer", layout="wide")

if 'active_profile' not in st.session_state:
    _profiles = _get_available_profiles()
    if not _profiles:
        # Bootstrap: migrate transformer_specs.json → specs_default.json
        _legacy = {}
        if os.path.exists("transformer_specs.json"):
            with open("transformer_specs.json") as f:
                _legacy = json.load(f)
        _dc = _legacy.get('categories', ["SOCIAL", "WEB", "EMAIL"])
        _df = _legacy.get('formats', [])
        _de = [s.get('category', 'OTHER') for s in _df if s.get('category', 'OTHER') not in _dc]
        _dc = list(dict.fromkeys(_dc + _de))
        with open("specs_default.json", "w") as f:
            json.dump({"categories": _dc, "formats": _df}, f, indent=4)
        _profiles = ["default"]
    elif "default" not in _profiles:
        # Profile files exist but no default — create a protected empty one
        with open("specs_default.json", "w") as f:
            json.dump({"categories": ["SOCIAL", "WEB", "EMAIL"], "formats": []}, f, indent=4)
        _profiles = sorted(["default"] + _profiles)
    st.session_state.active_profile = "default"
    st.session_state.available_profiles = _profiles
    st.session_state.specs, st.session_state.categories = _load_profile_data("default")
elif 'specs' not in st.session_state or 'categories' not in st.session_state:
    # Defensive: recover if specs/categories lost while active_profile is known
    _s, _c = _load_profile_data(st.session_state.active_profile)
    if 'specs' not in st.session_state: st.session_state.specs = _s
    if 'categories' not in st.session_state: st.session_state.categories = _c

if 'available_profiles' not in st.session_state:
    st.session_state.available_profiles = _get_available_profiles()

if 'proj_name' not in st.session_state:
    st.session_state.proj_name = "PSAM_Export"

# Persistent Navigation and Alignment
if 'img_idx' not in st.session_state: st.session_state.img_idx = 0
if 'align_map' not in st.session_state: st.session_state.align_map = {}
if 'filename_pattern' not in st.session_state: st.session_state.filename_pattern = "[Project]_[Filename]_[Format]"
if 'artist_name' not in st.session_state: st.session_state.artist_name = ""

# --- 2. HELPERS [LOCKED] ---
def calculate_ratio(w, h):
    if not w or not h: return "1:1"
    gcd = math.gcd(int(w), int(h))
    return f"{int(w)//gcd}:{int(h)//gcd}"

def save_specs_to_disk():
    _path = f"specs_{st.session_state.get('active_profile', 'default')}.json"
    with open(_path, "w") as f:
        json.dump({"categories": st.session_state.categories, "formats": st.session_state.specs}, f, indent=4)

def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

def get_svg_rect(ratio_str):
    try:
        r_w, r_h = map(int, ratio_str.split(":")); max_d = 35
        w, h = (max_d, int(max_d*(r_h/r_w))) if r_w > r_h else (int(max_d*(r_w/r_h)), max_d)
        return f'<svg width="45" height="45"><rect x="{(45-w)/2}" y="{(45-h)/2}" width="{w}" height="{h}" fill="none" stroke="#f36e2e" stroke-width="2.5"/></svg>'
    except: return ""

def sanitize(name):
    return re.sub(r'[^a-zA-Z0-9]', '_', name)

def apply_filename_pattern(pattern, bn, label, proj_name, artist_name, ext):
    """Build an export filename from a token pattern.
    Known tokens: [Date], [Artist], [Format], [Project], [Filename].
    Unknown tokens are passed through literally (sanitized with the rest of the result).
    Falls back to the default pattern if pattern is blank.
    """
    from datetime import date as _date
    p = pattern.strip() or "[Project]_[Filename]_[Format]"
    p = p.replace("[Date]",     _date.today().strftime("%Y-%m-%d"))
    p = p.replace("[Artist]",   artist_name.strip())
    p = p.replace("[Format]",   label)
    p = p.replace("[Project]",  proj_name)
    p = p.replace("[Filename]", bn)
    stem = sanitize(p)
    stem = re.sub(r'_+', '_', stem).strip('_')
    return f"{stem}.{ext.lower()}"

def toggle_section(category_name):
    master_state = st.session_state[f"master_{category_name}"]
    for spec in st.session_state.specs:
        if spec.get('category') == category_name:
            st.session_state[f"run_{spec['label']}"] = master_state

def update_gallery(direction, total_files):
    if direction == "next":
        st.session_state.img_idx = (st.session_state.img_idx + 1) % total_files
    else:
        st.session_state.img_idx = (st.session_state.img_idx - 1) % total_files

def resolve_dpi(source_dpi):
    """Return DPI tuple enforcing 72 DPI minimum; preserve higher source DPI."""
    dx = max(source_dpi[0] if source_dpi[0] > 0 else 72, 72)
    dy = max(source_dpi[1] if source_dpi[1] > 0 else 72, 72)
    return (int(dx), int(dy))

def build_exif_with_dpi(dpi):
    """Build a minimal piexif Exif blob carrying only XResolution/YResolution."""
    exif_dict = {"0th": {
        piexif.ImageIFD.XResolution: (dpi[0], 1),
        piexif.ImageIFD.YResolution: (dpi[1], 1),
        piexif.ImageIFD.ResolutionUnit: 2,  # 2 = pixels per inch
    }}
    return piexif.dump(exif_dict)

RAW_EXTENSIONS = {'.cr2', '.nef', '.arw', '.dng', '.orf', '.rw2'}

def load_image(uploaded_file):
    """Load an uploaded file into a PIL Image, returning (img, icc_profile, dpi).
    Handles both standard formats (JPEG, PNG, WebP) and RAW camera files.
    RAW files yield no ICC profile and default to 72 DPI.
    """
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    uploaded_file.seek(0)
    if ext in RAW_EXTENSIONS:
        import rawpy
        raw = rawpy.RawPy()
        raw.open_buffer(uploaded_file)  # open_buffer expects a file-like object, not bytes
        rgb_array = raw.postprocess()
        img = Image.fromarray(np.array(rgb_array))
        return img, None, (72, 72)
    img = Image.open(uploaded_file)
    img.load()  # force eager load while file handle is open
    return img, img.info.get('icc_profile'), img.info.get('dpi', (72, 72))

def zoom_crop(img, tw, th, ax, ay, zoom):
    """Crop img to target size (tw×th) using fill-to-frame scaling with zoom and alignment.
    zoom=100: image scaled to fill the frame (fill-to-frame baseline, no empty space).
    zoom>100: additional punch-in beyond the fill scale.
    ax/ay: 0–100 alignment along each axis. Caller passes 50 for axes with no overflow.
    """
    src_w, src_h = img.size
    fill_scale = max(tw / src_w, th / src_h)
    effective_scale = fill_scale * (zoom / 100)
    # Source-space crop window: how many source pixels to sample
    crop_w = tw / effective_scale
    crop_h = th / effective_scale
    # Clamp to source bounds (guard against floating-point overshoot)
    crop_w = min(crop_w, src_w)
    crop_h = min(crop_h, src_h)
    max_cx = max(0.0, src_w - crop_w)
    max_cy = max(0.0, src_h - crop_h)
    cx = max(0.0, min(ax / 100 * max_cx, max_cx))
    cy = max(0.0, min(ay / 100 * max_cy, max_cy))
    return img.crop((int(cx), int(cy), int(cx + crop_w), int(cy + crop_h))).resize((tw, th), Image.Resampling.LANCZOS)

def prepare_for_format(img, ext):
    """Convert image to the correct mode for the target format.
    - JPEG: flatten any alpha to a white background, return RGB.
    - WebP: preserve alpha, return RGBA (or RGB if source had none).
    """
    if ext.upper() == "JPEG":
        if img.mode in ("RGBA", "LA", "P"):
            if img.mode == "P":
                img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.getchannel("A"))
            return bg
        return img.convert("RGB")
    # WebP supports alpha natively
    if img.mode == "P":
        return img.convert("RGBA")
    if img.mode == "LA":
        return img.convert("RGBA")
    return img

load_css('style.css')

# --- 3. INTERFACE ---
tab_run, tab_fmt, tab_set = st.tabs(["TRANSFORMER", "FORMATS", "SETTINGS"])

# --- TAB 1: TRANSFORMER ---
with tab_run:
    uploaded_files = st.file_uploader("Drag & Drop", type=['jpg', 'png', 'webp', 'cr2', 'nef', 'arw', 'dng', 'orf', 'rw2'], accept_multiple_files=True, label_visibility="collapsed")

    if uploaded_files:
        if st.session_state.img_idx >= len(uploaded_files): st.session_state.img_idx = 0
        cur_file = uploaded_files[st.session_state.img_idx]
        
        st.write(" ")
        cust_active = st.toggle("Custom Settings", value=False)
        selected_formats = []

        if cust_active:
            with st.container(border=True):
                # MB2: one-time preset loader. Callback fires before the next render,
                # writes the four field keys, then resets the dropdown to blank so the
                # same preset can be re-selected. align_map is not touched.
                def apply_preset():
                    label = st.session_state.get("preset_select", "")
                    if not label:
                        return
                    spec = next((s for s in st.session_state.specs if s['label'] == label), None)
                    if spec:
                        st.session_state["cw_in"] = spec['width']
                        st.session_state["ch_in"] = spec['height']
                        st.session_state["ce_in"] = spec['ext']
                        st.session_state["cq_in"] = spec['quality']
                    st.session_state["preset_select"] = ""

                _top = st.columns([3, 2, 2, 2])
                _fmt = {s['label']: f"{s['label']} — {s['width']}×{s['height']} · {s['ext']} @ {s['quality']}%"
                        for s in st.session_state.specs}
                _top[0].selectbox(
                    "Load from Template (optional)",
                    options=[""] + [s['label'] for s in st.session_state.specs],
                    key="preset_select",
                    on_change=apply_preset,
                    format_func=lambda x: _fmt.get(x, x) if x else ""
                )
                _top[1].toggle("Apply custom size to all images", key="lock_custom_dims")
                l_sz = _top[2].toggle("Set Original Size", key="set_orig_size")
                l_ar = _top[3].toggle("Lock Aspect Ratio", key="lock_ar")

                img_ref, _, _ = load_image(cur_file)
                ow, oh = img_ref.size

                # MA2: When the selected image changes, reset the custom size
                # fields to the new image's source dimensions — unless the user
                # has toggled "Apply custom size to all images" (lock_custom_dims).
                if cur_file.name != st.session_state.get("last_custom_img"):
                    if not st.session_state.get("lock_custom_dims", False):
                        st.session_state["cw_in"] = ow
                        st.session_state["ch_in"] = oh
                    st.session_state["last_custom_img"] = cur_file.name

                # FIX: When "Set Original Size" is active, forcibly write the
                # true pixel dimensions into the session state keys BEFORE the
                # number_input widgets are rendered. Streamlit ignores `value=`
                # when a key already exists in session state, so without this
                # step the inputs would keep showing whatever value was last
                # typed rather than the actual uploaded image dimensions.
                if l_sz:
                    st.session_state["cw_in"] = ow
                    st.session_state["ch_in"] = oh

                c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
                cust_w = c1.number_input(
                    f"Width {'(Original)' if l_sz else ''}",
                    value=ow if l_sz else st.session_state.get("cw_in", 1080),
                    disabled=l_sz,
                    key="cw_in"
                )
                
                if l_ar:
                    cust_h = int(cust_w * (oh / ow))
                    c2.number_input("Height (Locked)", value=cust_h, disabled=True)
                else:
                    cust_h = c2.number_input(
                        f"Height {'(Original)' if l_sz else ''}",
                        value=oh if l_sz else st.session_state.get("ch_in", 1080),
                        disabled=l_sz,
                        key="ch_in"
                    )
                
                cust_ext = c3.selectbox("Format", ["WebP", "JPEG"], key="ce_in")
                cust_q = c4.slider("Export Quality", 10, 100, 95, key="cq_in")

                with st.expander("Preview & Alignment", expanded=False):
                    if cur_file.name not in st.session_state.align_map:
                        st.session_state.align_map[cur_file.name] = {"x": 50, "y": 50, "zoom": 100}
                    state = st.session_state.align_map[cur_file.name]
                    if "zoom" not in state:
                        state["zoom"] = 100

                    # Alpha composite prep (done once, used by preview slot after controls run)
                    _prev_src = img_ref
                    if img_ref.mode in ("RGBA", "LA", "P"):
                        _bg = Image.new("RGB", img_ref.size, (255, 255, 255))
                        _rgba = img_ref.convert("RGBA")
                        _bg.paste(_rgba, mask=_rgba.getchannel("A"))
                        _prev_src = _bg
                    elif img_ref.mode != "RGB":
                        _prev_src = img_ref.convert("RGB")

                    pcol_img, pcol_ctrl = st.columns([1, 1])

                    with pcol_img:
                        # Reserve layout positions — filled after controls capture current values
                        preview_slot = st.empty()
                        size_slot = st.empty()

                    with pcol_ctrl:
                        # Navigation above Zoom
                        nc1, nc2, nc3 = st.columns([1, 4, 1])
                        with nc1:
                            st.markdown('<div class="nav-chevron-trigger">', unsafe_allow_html=True)
                            st.button("〈", key="b_prev", on_click=update_gallery, args=("prev", len(uploaded_files)))
                            st.markdown('</div>', unsafe_allow_html=True)
                        with nc2:
                            st.markdown(f'<center><small>Image {st.session_state.img_idx + 1} of {len(uploaded_files)}</small><br><b>{cur_file.name}</b></center>', unsafe_allow_html=True)
                        with nc3:
                            st.markdown('<div class="nav-chevron-trigger">', unsafe_allow_html=True)
                            st.button("〉", key="b_next", on_click=update_gallery, args=("next", len(uploaded_files)))
                            st.markdown('</div>', unsafe_allow_html=True)

                        fill_scale = max(cust_w / ow, cust_h / oh)
                        is_upscale = fill_scale > 1.0

                        # Zoom first — mz available for same-render overflow detection
                        mz = st.slider("Zoom", 100, 200, state["zoom"], step=5, key=f"z_{cur_file.name}", disabled=is_upscale)

                        # Overflow in source-pixel space using current mz (identical to max_cx/max_cy in zoom_crop)
                        effective_scale = fill_scale * (mz / 100)
                        h_overflow = ow - (cust_w / effective_scale)
                        v_overflow = oh - (cust_h / effective_scale)
                        active_x = h_overflow > 0.5
                        active_y = v_overflow > 0.5

                        # Reset stale widget state before rendering disabled sliders
                        if not active_x:
                            st.session_state[f"x_{cur_file.name}"] = 50
                        if not active_y:
                            st.session_state[f"y_{cur_file.name}"] = 50

                        # X slider — always rendered, disabled when no horizontal overflow
                        mx = st.slider("Left → Right", 0, 100, state["x"], key=f"x_{cur_file.name}", disabled=not active_x)
                        if not active_x:
                            mx = 50

                        # Y slider — always rendered, disabled when no vertical overflow
                        my = st.slider("Top → Bottom", 0, 100, state["y"], key=f"y_{cur_file.name}", disabled=not active_y)
                        if not active_y:
                            my = 50

                        state["x"], state["y"], state["zoom"] = mx, my, mz
                        st.session_state.align_map[cur_file.name] = state

                    # Fill preview slot with current render's values — no lag, no extra rerun.
                    crop = zoom_crop(_prev_src, cust_w, cust_h, mx, my, mz)

                    # Scale crop to preview display bounds (h ≤ 380px, w ≤ 500px), aspect ratio
                    # preserved, never upscaled. Equivalent to CSS object-fit:contain in a 500×380
                    # box — done in Python so st.image() receives a correctly-sized display image.
                    _pw, _ph = crop.size
                    _pscale = min(500 / _pw, 380 / _ph, 1.0)
                    _disp = crop.resize((max(1, int(_pw * _pscale)), max(1, int(_ph * _pscale))), Image.Resampling.LANCZOS) if _pscale < 1.0 else crop
                    preview_slot.image(_disp, use_container_width=False)
                    _est_buf = io.BytesIO()
                    prepare_for_format(crop, cust_ext).save(
                        _est_buf,
                        format="JPEG" if cust_ext == "JPEG" else "WEBP",
                        quality=cust_q
                    )
                    _est_kb = len(_est_buf.getvalue()) / 1024
                    _est_label = f"{_est_kb:.0f} KB" if _est_kb < 1024 else f"{_est_kb/1024:.1f} MB"
                    _prev_up = (fill_scale * (mz / 100)) > 1.0
                    size_slot.caption(f"~{_est_label}{'  ⚠ upscale' if _prev_up else ''}")

            selected_formats.append({"label": "Custom", "width": cust_w, "height": cust_h, "ext": cust_ext, "quality": cust_q})

        st.write(" ")
        show_templates = st.toggle("Templates", key="show_templates")
        
        if show_templates:
            cats = sorted(list(set(s.get('category', 'OTHER') for s in st.session_state.specs)))
            for cat in cats:
                cat_specs = [s for s in st.session_state.specs if s.get('category') == cat]
                h_cols = st.columns([0.1, 0.05, 0.85]) 
                with h_cols[0]: st.markdown(f'<p class="cat-header-text" style="padding-top: 5px;">{cat}</p>', unsafe_allow_html=True)
                with h_cols[1]: st.checkbox("", value=False, key=f"master_{cat}", on_change=toggle_section, args=(cat,), label_visibility="collapsed")
                for i in range(0, len(cat_specs), 2):
                    row_specs = cat_specs[i:i+2]
                    grid_cols = st.columns(2)
                    for idx, spec in enumerate(row_specs):
                        with grid_cols[idx]:
                            with st.container(border=True):
                                i_c, n_c, s_c = st.columns([1, 6, 1])
                                with i_c: st.markdown(get_svg_rect(calculate_ratio(spec['width'], spec['height'])), unsafe_allow_html=True)
                                with n_c:
                                    st.markdown(f'<div class="card-label">{spec["label"]}</div>', unsafe_allow_html=True)
                                    st.markdown(f'<div class="card-subline">{spec["width"]}x{spec["height"]} — {spec.get("ext","WebP").upper()} @ {spec.get("quality", 85)}%</div>', unsafe_allow_html=True)
                                with s_c:
                                    if st.checkbox("", value=st.session_state.get(f"run_{spec['label']}", False), key=f"run_{spec['label']}", label_visibility="collapsed"):
                                        selected_formats.append(spec)

        st.divider()
        if st.button("GENERATE ALL ASSETS", use_container_width=True):
            if selected_formats:
                total = len(uploaded_files) * len(selected_formats)
                step = 0
                pb = st.progress(0); st_text = st.empty()

                # M4: write ZIP to a temp file on disk — avoids holding the full
                # batch in RAM via BytesIO, which can exhaust memory on large exports
                tmp_file = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
                tmp_path = tmp_file.name
                tmp_file.close()

                try:
                    upscale_warnings = []
                    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
                        for up in uploaded_files:
                            # M0/M6: load natively via load_image (handles RAW + standard formats)
                            img, icc_profile, dpi_info = load_image(up)
                            # M3: keep native mode — format-aware conversion happens at save time
                            bn = sanitize(os.path.splitext(up.name)[0])
                            align = st.session_state.align_map.get(up.name, {"x": 50, "y": 50})
                            src_w, src_h = img.size
                            for sp in selected_formats:
                                step += 1
                                pb.progress(min(int((step/total)*100), 100))
                                st_text.text(f"Processing: {bn}")
                                # MA3: zoom-aware upscale detection.
                                # Custom mode: fill_scale accounts for how the source fills the
                                # frame; effective_scale folds in zoom. >1.0 means the source is
                                # being stretched beyond its native resolution.
                                # Template mode: no zoom, so the direct dimension comparison is correct.
                                if st.session_state.get('show_upscale_warnings', True):
                                    if sp['label'] == "Custom":
                                        _fill = max(sp['width'] / src_w, sp['height'] / src_h)
                                        _eff = _fill * (align.get("zoom", 100) / 100)
                                        _is_up = _eff > 1.0
                                    else:
                                        _is_up = src_w < sp['width'] or src_h < sp['height']
                                    if _is_up:
                                        upscale_warnings.append(f"**{up.name}** → {sp['label']}: upscaled to {sp['width']}×{sp['height']}px (source: {src_w}×{src_h}px)")
                                # M7b: Custom mode uses zoom_crop (respects zoom + alignment);
                                # template mode uses standard centre-fit
                                if sp['label'] == "Custom":
                                    res = zoom_crop(img, sp['width'], sp['height'], align["x"], align["y"], align.get("zoom", 100))
                                else:
                                    res = ImageOps.fit(img, (sp['width'], sp['height']), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
                                # M3: convert to correct mode for target format after crop/resize
                                res = prepare_for_format(res, sp.get('ext', 'webp'))

                                fn = apply_filename_pattern(
                                    st.session_state.filename_pattern,
                                    bn, sp['label'],
                                    st.session_state.proj_name,
                                    st.session_state.artist_name,
                                    sp.get('ext', 'webp')
                                )
                                buf = io.BytesIO()

                                # M1: resolve DPI (min 72, preserve higher source DPI)
                                final_dpi = resolve_dpi(dpi_info)
                                # M2: pass ICC profile to both formats (None is safe — Pillow omits the tag)
                                if sp.get('ext') == "JPEG":
                                    res.save(buf, format="JPEG", quality=sp.get('quality', 95), subsampling=0 if sp.get('quality')==100 else 2, optimize=True, dpi=final_dpi, icc_profile=icc_profile)
                                else:
                                    res.save(buf, format="WEBP", quality=sp.get('quality', 95), lossless=(sp.get('quality')==100), method=4, exif=build_exif_with_dpi(final_dpi), icc_profile=icc_profile)
                                zf.writestr(fn, buf.getvalue())

                    # Silent Slack notification bridge
                    try:
                        import slack_notifier
                        slack_notifier.send_notification(st.session_state.artist_name.strip() or "Unknown", st.session_state.proj_name, len(uploaded_files), selected_formats)
                    except: pass

                    st_text.text("Done!")
                    st.session_state["last_upscale_warnings"] = upscale_warnings
                    with open(tmp_path, "rb") as f:
                        st.download_button("DOWNLOAD ZIP", data=f.read(), file_name=f"{sanitize(st.session_state.proj_name)}.zip", mime="application/zip")
                finally:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)

        # Persisted upscale warning — rendered outside the button guard so it
        # survives reruns (e.g. clicking download). Cleared on the next generate run.
        if st.session_state.get("last_upscale_warnings"):
            st.warning("**Upscale detected in this batch:**\n\n" + "\n\n".join(f"- {w}" for w in st.session_state["last_upscale_warnings"]))

# --- TAB 2 & 3 [LOCKED] ---
with tab_fmt:
    st.write("### Museum Standards Library")
    if st.session_state.specs:
        for idx, spec in enumerate(st.session_state.specs):
            with st.expander(f"{spec.get('category', 'OTHER')}: {spec.get('label', 'Unnamed')}"):
                l = st.text_input("Label", spec.get('label', ''), key=f"el_{idx}")
                _cur_cat = spec.get('category', 'OTHER')
                _cat_opts = st.session_state.categories if st.session_state.categories else [_cur_cat]
                _cat_idx = _cat_opts.index(_cur_cat) if _cur_cat in _cat_opts else 0
                cat = st.selectbox("Category", options=_cat_opts, index=_cat_idx, key=f"ec_{idx}")
                c1, c2 = st.columns(2); w = c1.number_input("Width", value=int(spec.get('width', 1080)), key=f"ew_{idx}"); h = c2.number_input("Height", value=int(spec.get('height', 1080)), key=f"eh_{idx}")
                c3, c4 = st.columns(2); e = c3.selectbox("Type", ["WebP", "JPEG"], index=0 if spec.get('ext')=='WebP' else 1, key=f"ee_{idx}"); q = c4.slider("Q", 10, 100, spec.get('quality', 85), key=f"eq_{idx}")
                if st.button("Save Changes", key=f"sv_{idx}"):
                    st.session_state.specs[idx].update({"category": cat, "label": l, "width": int(w), "height": int(h), "ext": e, "quality": q, "ratio": calculate_ratio(int(w), int(h))}); save_specs_to_disk(); st.rerun()
                if st.button("Remove Format", key=f"dl_{idx}"): st.session_state.specs.pop(idx); save_specs_to_disk(); st.rerun()
    st.divider()
    with st.form("new_std"):
        st.write("#### Add Format")
        if not st.session_state.categories:
            st.info("Add a category first before creating a format.")
            st.form_submit_button("ADD", disabled=True)
        else:
            n_cat = st.selectbox("Category", options=st.session_state.categories)
            n_lab = st.text_input("Name"); n_ext = st.selectbox("Type", ["WebP", "JPEG"]); n_q = st.slider("Quality", 10, 100, 85); n_w = st.number_input("Width", min_value=1, value=1080); n_h = st.number_input("Height", min_value=1, value=1080)
            if st.form_submit_button("ADD"):
                existing_labels = [s.get("label", "").lower() for s in st.session_state.specs]
                if n_lab.lower() in existing_labels:
                    st.error(f"A format named '{n_lab}' already exists. Please use a unique name.")
                else:
                    st.session_state.specs.append({"category": n_cat, "label": n_lab, "width": int(n_w), "height": int(n_h), "ratio": calculate_ratio(int(n_w), int(n_h)), "ext": n_ext, "quality": n_q}); save_specs_to_disk(); st.rerun()

    with st.expander("Manage Categories"):
        # Add a new category
        mc_cols = st.columns([3, 1])
        new_cat_name = mc_cols[0].text_input("New category name", key="new_cat_input", label_visibility="collapsed", placeholder="New category name")
        if mc_cols[1].button("Add Category", use_container_width=True):
            _nc = new_cat_name.strip().upper()
            if not _nc:
                st.error("Category name cannot be empty.")
            elif _nc in st.session_state.categories:
                st.error(f"'{_nc}' already exists.")
            else:
                st.session_state.categories.append(_nc)
                save_specs_to_disk()
                st.rerun()

        st.write(" ")
        # Delete categories — two-step confirm; blocked if formats still use the category
        for _cat in list(st.session_state.categories):
            _used_by = [s['label'] for s in st.session_state.specs if s.get('category') == _cat]
            _confirm_key = f"confirm_del_cat_{_cat}"
            dc1, dc2 = st.columns([4, 1])
            dc1.markdown(f"**{_cat}**" + (f" — *used by {len(_used_by)} format(s)*" if _used_by else ""))
            if not st.session_state.get(_confirm_key, False):
                if dc2.button("Delete", key=f"del_cat_{_cat}", use_container_width=True):
                    if _used_by:
                        st.warning(f"Cannot delete '{_cat}': still used by {len(_used_by)} format(s): {', '.join(_used_by)}.")
                    else:
                        st.session_state[_confirm_key] = True
                        st.rerun()
            else:
                conf_cols = st.columns([2, 2])
                if conf_cols[0].button("Confirm delete", key=f"conf_del_{_cat}", use_container_width=True):
                    st.session_state.categories.remove(_cat)
                    st.session_state.pop(_confirm_key, None)
                    save_specs_to_disk()
                    st.rerun()
                if conf_cols[1].button("Cancel", key=f"cancel_del_{_cat}", use_container_width=True):
                    st.session_state.pop(_confirm_key, None)
                    st.rerun()

with tab_set:
    st.write("### Workflow Settings")

    # MD2: Profile management
    st.write("#### Active Profile")

    def _on_profile_switch():
        _new = st.session_state["profile_selector"]
        if _new == st.session_state.active_profile:
            return
        # Clear stale template checkbox keys so switched profile starts clean
        for _k in list(st.session_state.keys()):
            if _k.startswith("run_") or _k.startswith("master_"):
                del st.session_state[_k]
        _s, _c = _load_profile_data(_new)
        st.session_state.active_profile = _new
        st.session_state.specs = _s
        st.session_state.categories = _c

    _pidx = st.session_state.available_profiles.index(st.session_state.active_profile) \
        if st.session_state.active_profile in st.session_state.available_profiles else 0
    st.selectbox("Active Profile", options=st.session_state.available_profiles,
                 index=_pidx, key="profile_selector", on_change=_on_profile_switch,
                 label_visibility="collapsed")

    # New profile
    np_c1, np_c2 = st.columns([3, 1])
    _new_prof = np_c1.text_input("New profile name", key="new_prof_input",
                                  label_visibility="collapsed", placeholder="New profile name")
    if np_c2.button("Create Profile", use_container_width=True):
        _np = re.sub(r'[^a-zA-Z0-9_-]', '', _new_prof.strip())
        if not _np:
            st.error("Profile name must contain at least one alphanumeric character.")
        elif _np.lower() == "default":
            st.error("'default' is a reserved profile name.")
        elif _np in st.session_state.available_profiles:
            st.error(f"A profile named '{_np}' already exists.")
        else:
            with open(f"specs_{_np}.json", "w") as _pf:
                json.dump({"categories": st.session_state.categories, "formats": st.session_state.specs}, _pf, indent=4)
            st.session_state.available_profiles = _get_available_profiles()
            st.success(f"Profile '{_np}' created as a copy of the current library.")
            st.rerun()

    # Delete profile (non-default only)
    _deletable = [p for p in st.session_state.available_profiles if p != "default"]
    if _deletable:
        dp_c1, dp_c2 = st.columns([3, 1])
        _del_target = dp_c1.selectbox("Delete profile", options=_deletable,
                                       key="del_prof_select", label_visibility="collapsed")
        _conf_key = "confirm_del_profile"
        if not st.session_state.get(_conf_key):
            if dp_c2.button("Delete", key="del_prof_btn", use_container_width=True):
                if _del_target == st.session_state.active_profile:
                    st.error(f"Cannot delete the active profile '{_del_target}'. Switch to another profile first.")
                else:
                    st.session_state[_conf_key] = _del_target
                    st.rerun()
        else:
            _t = st.session_state[_conf_key]
            st.warning(f"Delete profile '{_t}'? This cannot be undone.")
            dc1, dc2 = st.columns([1, 1])
            if dc1.button("Confirm delete", key="conf_del_prof", use_container_width=True):
                if os.path.exists(f"specs_{_t}.json"):
                    os.remove(f"specs_{_t}.json")
                st.session_state.available_profiles = _get_available_profiles()
                st.session_state.pop(_conf_key, None)
                st.rerun()
            if dc2.button("Cancel", key="cancel_del_prof", use_container_width=True):
                st.session_state.pop(_conf_key, None)
                st.rerun()

    st.divider()
    st.session_state.proj_name = st.text_input("Project Export Name", value=st.session_state.proj_name)
    st.session_state.artist_name = st.text_input("Artist / Creator", value=st.session_state.artist_name, placeholder="Used by [Artist] token")
    st.session_state.filename_pattern = st.text_input(
        "Filename Pattern",
        value=st.session_state.filename_pattern,
        placeholder="[Project]_[Filename]_[Format]",
        help="Tokens: [Date], [Artist], [Format], [Project], [Filename]. Unknown tokens pass through literally."
    )
    _preview_fn = apply_filename_pattern(
        st.session_state.filename_pattern,
        "source_filename", "Format_Name",
        st.session_state.proj_name or "Project",
        st.session_state.artist_name,
        "webp"
    )
    st.caption(f"Preview: `{_preview_fn}`")
    st.divider()
    # M5: upscale warning toggle
    st.session_state.show_upscale_warnings = st.toggle(
        "Show upscale warnings",
        value=st.session_state.get('show_upscale_warnings', True),
        help="When ON, a warning is shown after any batch where a source image was smaller than its target format. The upscale always occurs regardless of this setting."
    )
    st.divider()
    json_data = json.dumps({"categories": st.session_state.categories, "formats": st.session_state.specs}, indent=4)
    st.download_button("💾 EXPORT LIBRARY (JSON)", data=json_data, file_name="psam_library_backup.json", mime="application/json")

    st.divider()
    st.write("#### Import Library (JSON)")
    imported_file = st.file_uploader("Upload a JSON library file", type=["json"], key="import_lib_upload", label_visibility="collapsed")
    import_mode = st.radio("Import mode", ["Merge", "Replace"], horizontal=True, key="import_mode")

    if imported_file is not None:
        # Parse and validate once per uploaded file
        try:
            _raw = json.loads(imported_file.read())
        except Exception:
            st.error("Invalid JSON — file could not be parsed.")
            _raw = None

        if _raw is not None:
            if not isinstance(_raw, dict) or not isinstance(_raw.get("formats"), list):
                st.error("Invalid structure — file must be a JSON object with a \"formats\" array.")
            else:
                # Filter to valid format entries (must be dict with label, width, height)
                _all_entries = _raw["formats"]
                _valid = [e for e in _all_entries if isinstance(e, dict) and all(k in e for k in ("label", "width", "height"))]
                _skipped_invalid = len(_all_entries) - len(_valid)

                # Derive categories from file (handles pre-MC1 files with no "categories" key)
                _file_cats = _raw.get("categories", [])
                if not isinstance(_file_cats, list):
                    _file_cats = []
                _extra_cats = [e.get("category", "OTHER") for e in _valid if e.get("category", "OTHER") not in _file_cats]
                _file_cats = list(dict.fromkeys(_file_cats + _extra_cats))
                if not _file_cats:
                    _file_cats = ["SOCIAL", "WEB", "EMAIL"]

                if import_mode == "Merge":
                    _existing_labels = {s.get("label", "").lower() for s in st.session_state.specs}
                    _new_formats = [e for e in _valid if e.get("label", "").lower() not in _existing_labels]
                    _skipped_dup = len(_valid) - len(_new_formats)
                    _new_cats = [c for c in _file_cats if c not in st.session_state.categories]

                    if st.button("Import (Merge)", key="do_import_merge"):
                        st.session_state.specs.extend(_new_formats)
                        st.session_state.categories.extend(_new_cats)
                        save_specs_to_disk()
                        _msg = f"Imported {len(_new_formats)} format(s)."
                        if _skipped_dup:   _msg += f" {_skipped_dup} skipped (duplicate label)."
                        if _skipped_invalid: _msg += f" {_skipped_invalid} skipped (invalid entry)."
                        if _new_cats:      _msg += f" {len(_new_cats)} new category(ies) added."
                        st.success(_msg)

                else:  # Replace
                    st.warning(f"This will replace all {len(st.session_state.specs)} existing format(s) and all categories.")
                    if not st.session_state.get("confirm_import_replace", False):
                        if st.button("Replace library", key="req_import_replace"):
                            st.session_state["confirm_import_replace"] = True
                            st.rerun()
                    else:
                        rc1, rc2 = st.columns([1, 1])
                        if rc1.button("Confirm replace", key="conf_import_replace", use_container_width=True):
                            st.session_state.specs = _valid
                            st.session_state.categories = _file_cats
                            st.session_state.pop("confirm_import_replace", None)
                            save_specs_to_disk()
                            _msg = f"Library replaced with {len(_valid)} format(s)."
                            if _skipped_invalid: _msg += f" {_skipped_invalid} entry(ies) skipped (invalid)."
                            st.success(_msg)
                        if rc2.button("Cancel", key="cancel_import_replace", use_container_width=True):
                            st.session_state.pop("confirm_import_replace", None)
                            st.rerun()
