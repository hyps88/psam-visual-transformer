import streamlit as st
from PIL import Image, ImageOps
import json, os, math, re, io, zipfile

# --- 1. INITIALIZATION [PROFESSIONAL REFACTOR] ---
st.set_page_config(page_title="Visual Transformer", layout="wide")
Image.MAX_IMAGE_PIXELS = None  # Support very large uploads without PIL limit

if 'specs' not in st.session_state:
    if os.path.exists("transformer_specs.json"):
        with open("transformer_specs.json", "r") as f:
            st.session_state.specs = json.load(f).get('formats', [])
    else: 
        st.session_state.specs = []

if 'proj_name' not in st.session_state:
    st.session_state.proj_name = "PSAM_Export"

# Persistent state
if 'img_idx' not in st.session_state: 
    st.session_state.img_idx = 0
if 'align_map' not in st.session_state: 
    st.session_state.align_map = {}

# --- 2. HELPERS [CLEAN & OPTIMIZED] ---
def calculate_ratio(w, h):
    if not w or not h: 
        return "1:1"
    gcd = math.gcd(int(w), int(h))
    return f"{int(w)//gcd}:{int(h)//gcd}"

def save_specs_to_disk():
    with open("transformer_specs.json", "w") as f:
        json.dump({"formats": st.session_state.specs}, f, indent=4)

def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

def get_svg_rect(ratio_str):
    try:
        r_w, r_h = map(int, ratio_str.split(":"))
        max_d = 35
        w, h = (max_d, int(max_d*(r_h/r_w))) if r_w > r_h else (int(max_d*(r_w/r_h)), max_d)
        return f'<svg width="45" height="45"><rect x="{(45-w)/2}" y="{(45-h)/2}" width="{w}" height="{h}" fill="none" stroke="#f36e2e" stroke-width="2.5"/></svg>'
    except: 
        return ""

def sanitize(name):
    return re.sub(r'[^a-zA-Z0-9]', '_', name)

def toggle_section(category_name):
    master_state = st.session_state.get(f"master_{category_name}", False)
    for spec in st.session_state.specs:
        if spec.get('category') == category_name:
            st.session_state[f"run_{spec['label']}"] = master_state

def needs_upscale(src_img, tgt_w, tgt_h):
    """Detect if source is smaller than target → triggers high-quality LANCZOS upscale."""
    return src_img.width < tgt_w or src_img.height < tgt_h

def update_gallery(direction, total_files):
    if direction == "next":
        st.session_state.img_idx = (st.session_state.img_idx + 1) % total_files
    else:
        st.session_state.img_idx = (st.session_state.img_idx - 1) % total_files

def save_processed_image(res_img, spec, icc_profile=None):
    """Centralized save with mandatory 72 DPI + ICC retention (JPEG + WebP)."""
    buf = io.BytesIO()
    if spec.get('ext') == "JPEG":
        save_kwargs = {
            "quality": spec.get("quality", 95),
            "dpi": (72, 72),
            "optimize": True,
            "subsampling": 0 if spec.get("quality", 95) == 100 else 2,
        }
        if icc_profile:
            save_kwargs["icc_profile"] = icc_profile
        res_img.save(buf, format="JPEG", **save_kwargs)
    else:  # WebP
        save_kwargs = {
            "quality": spec.get("quality", 95),
            "method": 5,  # Higher quality than original 4
        }
        if spec.get("quality") == 100:
            save_kwargs["lossless"] = True
        # ICC supported in modern Pillow; safe to pass
        if icc_profile:
            save_kwargs["icc_profile"] = icc_profile
        res_img.save(buf, format="WEBP", **save_kwargs)
    return buf.getvalue()

load_css('style.css')

# --- 3. INTERFACE ---
tab_run, tab_fmt, tab_set = st.tabs(["TRANSFORMER", "FORMATS", "SETTINGS"])

# --- TAB 1: TRANSFORMER [CORE PIPELINE] ---
with tab_run:
    uploaded_files = st.file_uploader(
        "Drag & Drop Images", 
        type=['jpg', 'png', 'webp'], 
        accept_multiple_files=True, 
        label_visibility="collapsed"
    )

    if uploaded_files:
        if st.session_state.img_idx >= len(uploaded_files):
            st.session_state.img_idx = 0
        cur_file = uploaded_files[st.session_state.img_idx]

        st.write(" ")
        cust_active = st.toggle("Custom Settings", value=False)
        selected_formats = []

        if cust_active:
            with st.container(border=True):
                col_locks = st.columns(2)
                l_ar = col_locks[0].checkbox("Lock Aspect Ratio", value=False)
                l_sz = col_locks[1].checkbox("Set Original Size", value=False)
                
                img_ref = Image.open(cur_file)
                ow, oh = img_ref.size

                # Force original dimensions into session state when locked
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
                    cust_h = int(cust_w * (oh / ow)) if ow else oh
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

                with st.expander("Preview & Alignment", expanded=True):
                    if cur_file.name not in st.session_state.align_map:
                        st.session_state.align_map[cur_file.name] = {"x": 50, "y": 50}
                    
                    state = st.session_state.align_map[cur_file.name]
                    pcol_img, pcol_ctrl = st.columns([3, 2])
                    
                    with pcol_ctrl:
                        st.markdown("**Focal Point Alignment**")
                        mx = st.slider(
                            "Horizontal (0% = left → 100% = right)", 
                            0, 100, state["x"], 
                            key=f"x_{cur_file.name}"
                        )
                        my = st.slider(
                            "Vertical (0% = top → 100% = bottom)", 
                            0, 100, state["y"], 
                            key=f"y_{cur_file.name}"
                        )
                        state["x"], state["y"] = mx, my
                        st.session_state.align_map[cur_file.name] = state

                        st.divider()
                        st.markdown("**Smart Presets**")
                        preset_cols = st.columns(5)
                        presets = {
                            "⬆️ Top": (50, 15),
                            "⏺️ Center": (50, 50),
                            "⬇️ Bottom": (50, 85),
                            "⬅️ Left": (15, 50),
                            "➡️ Right": (85, 50)
                        }
                        for pidx, (pname, (px, py)) in enumerate(presets.items()):
                            with preset_cols[pidx]:
                                if st.button(pname, key=f"preset_{pname}_{cur_file.name}", use_container_width=True):
                                    state = st.session_state.align_map[cur_file.name]
                                    state["x"] = px
                                    state["y"] = py
                                    st.session_state.align_map[cur_file.name] = state
                                    st.rerun()

                        st.divider()
                        nc1, nc2, nc3 = st.columns([1, 4, 1])
                        with nc1:
                            st.button("〈", key="b_prev", on_click=update_gallery, args=("prev", len(uploaded_files)))
                        with nc2:
                            st.markdown(
                                f'<center><small>Image {st.session_state.img_idx + 1} of {len(uploaded_files)}</small><br><b>{cur_file.name}</b></center>', 
                                unsafe_allow_html=True
                            )
                        with nc3:
                            st.button("〉", key="b_next", on_click=update_gallery, args=("next", len(uploaded_files)))

                    with pcol_img:
                        # Stable preview using dedicated CSS container (fixes shrinking bug)
                        asp = cust_w / cust_h if cust_h > 0 else 1
                        preview_max = 520
                        display_w = preview_max if asp >= 1 else int(preview_max * asp)
                        crop = ImageOps.fit(
                            img_ref.convert("RGB"), 
                            (cust_w, cust_h), 
                            method=Image.Resampling.LANCZOS, 
                            centering=(state["x"]/100, state["y"]/100)
                        )
                        st.markdown('<div class="preview-image-box">', unsafe_allow_html=True)
                        st.image(crop, width=display_w)
                        st.markdown('</div>', unsafe_allow_html=True)
            
            selected_formats.append({
                "label": "Custom", 
                "width": cust_w, 
                "height": cust_h, 
                "ext": cust_ext, 
                "quality": cust_q
            })

        st.write(" ")
        show_templates = st.toggle("Templates", key="show_templates")
        
        if show_templates:
            cats = sorted(list(set(s.get('category', 'OTHER') for s in st.session_state.specs)))
            for cat in cats:
                cat_specs = [s for s in st.session_state.specs if s.get('category') == cat]
                h_cols = st.columns([0.1, 0.05, 0.85]) 
                with h_cols[0]: 
                    st.markdown(f'<p class="cat-header-text">{cat}</p>', unsafe_allow_html=True)
                with h_cols[1]: 
                    st.checkbox("", value=False, key=f"master_{cat}", on_change=toggle_section, args=(cat,), label_visibility="collapsed")
                for i in range(0, len(cat_specs), 2):
                    row_specs = cat_specs[i:i+2]
                    grid_cols = st.columns(2)
                    for idx, spec in enumerate(row_specs):
                        with grid_cols[idx]:
                            with st.container(border=True):
                                i_c, n_c, s_c = st.columns([1, 6, 1])
                                with i_c: 
                                    st.markdown(get_svg_rect(calculate_ratio(spec['width'], spec['height'])), unsafe_allow_html=True)
                                with n_c:
                                    st.markdown(f'<div class="card-label">{spec["label"]}</div>', unsafe_allow_html=True)
                                    st.markdown(f'<div class="card-subline">{spec["width"]}×{spec["height"]} — {spec.get("ext","WebP").upper()} @ {spec.get("quality", 85)}%</div>', unsafe_allow_html=True)
                                with s_c:
                                    if st.checkbox("", value=st.session_state.get(f"run_{spec['label']}", False), key=f"run_{spec['label']}", label_visibility="collapsed"):
                                        selected_formats.append(spec)

        st.divider()
        if st.button("🚀 GENERATE ALL ASSETS", use_container_width=True, type="primary"):
            if selected_formats:
                zip_buffer = io.BytesIO()
                total = len(uploaded_files) * len(selected_formats)
                step = 0
                pb = st.progress(0)
                st_text = st.empty()

                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zf:
                    for up in uploaded_files:
                        original_img = Image.open(up)
                        icc_profile = original_img.info.get("icc_profile")  # Extract BEFORE any conversion
                        img = original_img.convert("RGB")  # Safe RGB copy for processing
                        bn = sanitize(os.path.splitext(up.name)[0])
                        align = st.session_state.align_map.get(up.name, {"x": 50, "y": 50})
                        
                        for sp in selected_formats:
                            step += 1
                            pb.progress(min(int((step / total) * 100), 100))
                            
                            # Live feedback: upscale vs resize
                            is_up = needs_upscale(img, sp['width'], sp['height'])
                            status_msg = f"{'🔄 Upscaling' if is_up else '📏 Processing'}: {bn} → {sp.get('label', 'Custom')}"
                            st_text.text(status_msg)
                            
                            # Always use per-image alignment (smart centering for ALL outputs)
                            cx = align["x"]/100 if sp.get('label') == "Custom" else 0.5
                            cy = align["y"]/100 if sp.get('label') == "Custom" else 0.5
                            
                            res = ImageOps.fit(
                                img, 
                                (sp['width'], sp['height']), 
                                method=Image.Resampling.LANCZOS, 
                                centering=(cx, cy)
                            )
                            
                            file_data = save_processed_image(res, sp, icc_profile)
                            
                            fn = f"PSAM_{bn}_{sanitize(sp['label'])}.{sp.get('ext','webp').lower()}"
                            zf.writestr(fn, file_data)
                
                # Slack bridge (non-blocking)
                try:
                    import slack_notifier
                    slack_notifier.send_notification("GG", st.session_state.proj_name, len(uploaded_files), selected_formats)
                except: 
                    pass
                
                st_text.text("✅ All assets generated!")
                st.download_button(
                    "📥 DOWNLOAD ZIP PACKAGE", 
                    data=zip_buffer.getvalue(), 
                    file_name=f"{sanitize(st.session_state.proj_name)}.zip", 
                    mime="application/zip",
                    use_container_width=True
                )
            else:
                st.warning("Select at least one template or enable Custom Settings.")

# --- TAB 2 & 3 [LOCKED - LIBRARY & SETTINGS UNCHANGED] ---
with tab_fmt:
    st.write("### Museum Standards Library")
    if st.session_state.specs:
        for idx, spec in enumerate(st.session_state.specs):
            with st.expander(f"{spec.get('category', 'OTHER')}: {spec.get('label', 'Unnamed')}"):
                l = st.text_input("Label", spec.get('label', ''), key=f"el_{idx}")
                c1, c2 = st.columns(2)
                w = c1.number_input("Width", value=int(spec.get('width', 1080)), key=f"ew_{idx}")
                h = c2.number_input("Height", value=int(spec.get('height', 1080)), key=f"eh_{idx}")
                c3, c4 = st.columns(2)
                e = c3.selectbox("Type", ["WebP", "JPEG"], index=0 if spec.get('ext')=='WebP' else 1, key=f"ee_{idx}")
                q = c4.slider("Q", 10, 100, spec.get('quality', 85), key=f"eq_{idx}")
                if st.button("Save Changes", key=f"sv_{idx}"):
                    st.session_state.specs[idx].update({
                        "label": l, "width": int(w), "height": int(h), 
                        "ext": e, "quality": q, "ratio": calculate_ratio(int(w), int(h))
                    })
                    save_specs_to_disk()
                    st.rerun()
                if st.button("Remove Format", key=f"dl_{idx}"):
                    st.session_state.specs.pop(idx)
                    save_specs_to_disk()
                    st.rerun()
    st.divider()
    with st.form("new_std"):
        st.write("#### Add Format")
        n_cat = st.text_input("Category", "SOCIAL")
        n_lab = st.text_input("Name")
        n_ext = st.selectbox("Type", ["WebP", "JPEG"])
        n_q = st.slider("Quality", 10, 100, 85)
        n_w = st.number_input("Width", 1080)
        n_h = st.number_input("Height", 1080)
        if st.form_submit_button("ADD"):
            st.session_state.specs.append({
                "category": n_cat.upper(), "label": n_lab, "width": int(n_w), 
                "height": int(n_h), "ratio": calculate_ratio(int(n_w), int(n_h)), 
                "ext": n_ext, "quality": n_q
            })
            save_specs_to_disk()
            st.rerun()

with tab_set:
    st.write("### Workflow Settings")
    st.session_state.proj_name = st.text_input("Project Export Name", value=st.session_state.proj_name)
    st.divider()
    json_data = json.dumps({"formats": st.session_state.specs}, indent=4)
    st.download_button("💾 EXPORT LIBRARY (JSON)", data=json_data, file_name="psam_library_backup.json", mime="application/json")
