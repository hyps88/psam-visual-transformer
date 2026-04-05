import streamlit as st
from PIL import Image, ImageOps
import json, os, math, re, io, zipfile

# --- 1. INITIALIZATION [LOCKED] ---
st.set_page_config(page_title="Visual Transformer", layout="wide")

if 'specs' not in st.session_state:
    if os.path.exists("transformer_specs.json"):
        with open("transformer_specs.json", "r") as f:
            st.session_state.specs = json.load(f).get('formats', [])
    else: st.session_state.specs = []

if 'proj_name' not in st.session_state:
    st.session_state.proj_name = "PSAM_Export"

# --- PER-IMAGE ALIGNMENT STATE ---
if 'img_idx' not in st.session_state: st.session_state.img_idx = 0
if 'align_map' not in st.session_state: st.session_state.align_map = {}

# --- 2. HELPERS [LOCKED] ---
def calculate_ratio(w, h):
    if not w or not h: return "1:1"
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
        r_w, r_h = map(int, ratio_str.split(":")); max_d = 35
        w, h = (max_d, int(max_d*(r_h/r_w))) if r_w > r_h else (int(max_d*(r_w/r_h)), max_d)
        return f'<svg width="45" height="45"><rect x="{(45-w)/2}" y="{(45-h)/2}" width="{w}" height="{h}" fill="none" stroke="#f36e2e" stroke-width="2.5"/></svg>'
    except: return ""

def sanitize(name):
    return re.sub(r'[^a-zA-Z0-9]', '_', name)

def toggle_section(category_name):
    master_state = st.session_state[f"master_{category_name}"]
    for spec in st.session_state.specs:
        if spec.get('category') == category_name:
            st.session_state[f"run_{spec['label']}"] = master_state

load_css('style.css')

# --- 3. INTERFACE ---
tab_run, tab_fmt, tab_set = st.tabs(["TRANSFORMER", "FORMATS", "SETTINGS"])

# --- TAB 1: TRANSFORMER ---
with tab_run:
    uploaded_files = st.file_uploader("Drag & Drop", type=['jpg', 'png', 'webp'], accept_multiple_files=True, label_visibility="collapsed")

    if uploaded_files:
        # Reset navigation index if it goes out of bounds
        if st.session_state.img_idx >= len(uploaded_files): st.session_state.img_idx = 0
        
        st.write(" ")
        cust_active = st.toggle("Custom Settings", value=False)
        selected_formats = []

        if cust_active:
            with st.container(border=True):
                lock_ar = st.checkbox("Force Original Aspect Ratio & Size", value=False, key="lock_ar_check")
                
                # Aspect Ratio logic based on CURRENT selected image
                cur_img_file = uploaded_files[st.session_state.img_idx]
                orig_img_ref = Image.open(cur_img_file)
                ow, oh = orig_img_ref.size
                
                c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
                if lock_ar:
                    cust_w = c1.number_input("Width (Original)", value=ow, key="cust_w_orig")
                    cust_h = int(cust_w * (oh / ow))
                    c2.number_input("Height (Original)", value=cust_h, disabled=True, key="cust_h_orig")
                else:
                    cust_w = c1.number_input("Width", value=1080, key="cust_w_manual")
                    cust_h = c2.number_input("Height", value=1080, key="cust_h_manual")
                
                cust_ext = c3.selectbox("Format", ["WebP", "JPEG"], key="cust_ext")
                # 100% Quality handles Lossless automatically
                cust_q = c4.slider("Export Quality (100 = Lossless)", 10, 100, 95, key="cust_q")

                with st.expander("👁️ Preview & Individual Alignment", expanded=True):
                    aspect_val = cust_w / cust_h
                    sw, sh = (500, int(500/aspect_val)) if aspect_val > 1 else (int(500*aspect_val), 500)
                    
                    pcol_img, pcol_ctrl = st.columns([1, 1])
                    
                    with pcol_img:
                        st.markdown('<div class="preview-image-box">', unsafe_allow_html=True)
                        # Fetch saved alignment or default to 50/50
                        current_align = st.session_state.align_map.get(cur_img_file.name, {"x": 50, "y": 50})
                        crop = ImageOps.fit(orig_img_ref.convert("RGB"), (cust_w, cust_h), method=Image.Resampling.LANCZOS, centering=(current_align["x"]/100, current_align["y"]/100))
                        st.image(crop, width=sw, caption=f"Individual Preview ({calculate_ratio(cust_w, cust_h)})")
                        st.markdown('</div>', unsafe_allow_html=True)

                    with pcol_ctrl:
                        st.markdown('<div class="preview-controls-box">', unsafe_allow_html=True)
                        st.write("**Alignment for this Image**")
                        
                        preset = st.radio("Quick Presets", ["Center", "Top", "Bottom", "Left", "Right", "Manual"], horizontal=True, key=f"pre_{cur_img_file.name}")
                        
                        if preset == "Center": dx, dy = 50, 50
                        elif preset == "Top": dx, dy = 50, 0
                        elif preset == "Bottom": dx, dy = 50, 100
                        elif preset == "Left": dx, dy = 0, 50
                        elif preset == "Right": dx, dy = 100, 50
                        else: dx, dy = current_align["x"], current_align["y"]

                        mx = st.slider("Left ← Alignment → Right", 0, 100, dx, key=f"mx_{cur_img_file.name}")
                        my = st.slider("Top ← Alignment → Bottom", 0, 100, dy, key=f"my_{cur_img_file.name}")
                        
                        # Save current image alignment to session state
                        st.session_state.align_map[cur_img_file.name] = {"x": mx, "y": my}

                        # --- MINIMALIST TEXT NAVIGATOR ---
                        st.divider()
                        nc1, nc2, nc3 = st.columns([1, 4, 1])
                        with nc1:
                            st.markdown('<div class="nav-link">', unsafe_allow_html=True)
                            if st.button("←", key="prev_img"):
                                st.session_state.img_idx = (st.session_state.img_idx - 1) % len(uploaded_files)
                                st.rerun()
                            st.markdown('</div>', unsafe_allow_html=True)
                        with nc2:
                            st.markdown(f'<div class="img-info-text"><center>Image {st.session_state.img_idx + 1} of {len(uploaded_files)}<br><b>{cur_img_file.name}</b></center></div>', unsafe_allow_html=True)
                        with nc3:
                            st.markdown('<div class="nav-link">', unsafe_allow_html=True)
                            if st.button("→", key="next_img"):
                                st.session_state.img_idx = (st.session_state.img_idx + 1) % len(uploaded_files)
                                st.rerun()
                            st.markdown('</div>', unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)
            
            selected_formats.append({"label": "Custom", "width": cust_w, "height": cust_h, "ext": cust_ext, "quality": cust_q})

        st.write(" ")
        show_templates = st.toggle("Templates", value=False)
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
                                with i_c: st.markdown(get_svg_rect(spec['ratio']), unsafe_allow_html=True)
                                with n_c:
                                    st.markdown(f'<div class="card-label">{spec["label"]}</div>', unsafe_allow_html=True)
                                    st.markdown(f'<div class="card-subline">{spec["width"]}x{spec["height"]} — {spec.get("ext","WebP").upper()} @ {spec.get("quality",85)}%</div>', unsafe_allow_html=True)
                                with s_c:
                                    if st.checkbox("", value=st.session_state.get(f"run_{spec['label']}", False), key=f"run_{spec['label']}", label_visibility="collapsed"):
                                        selected_formats.append(spec)

        st.divider()
        # ENHANCED GENERATE BUTTON WITH PROGRESS
        if st.button("GENERATE ALL ASSETS", use_container_width=True):
            if selected_formats:
                zip_buffer = io.BytesIO()
                total_steps = len(uploaded_files) * len(selected_formats)
                current_step = 0
                
                # PSAM-Branded Progress Bar
                progress_bar = st.progress(0)
                status_text = st.empty()

                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zf:
                    for up in uploaded_files:
                        img = Image.open(up).convert("RGB")
                        bn = sanitize(os.path.splitext(up.name)[0])
                        
                        # Apply individual alignment memory
                        align_data = st.session_state.align_map.get(up.name, {"x": 50, "y": 50})
                        cx_final, cy_final = align_data["x"]/100, align_data["y"]/100

                        for sp in selected_formats:
                            current_step += 1
                            progress_bar.progress(min(int((current_step / total_steps) * 100), 100))
                            status_text.text(f"Processing: {bn} — {sp['label']}")

                            # Custom crops use saved alignment; templates default to center
                            t_cx = cx_final if sp['label'] == "Custom" else 0.5
                            t_cy = cy_final if sp['label'] == "Custom" else 0.5

                            res = ImageOps.fit(img, (sp['width'], sp['height']), method=Image.Resampling.LANCZOS, centering=(t_cx, t_cy))
                            ext_v = sp.get('ext', 'WebP').upper()
                            q_v = sp.get('quality', 95)
                            
                            fn = f"PSAM_{bn}_{sanitize(sp['label'])}_{sp['width']}x{sp['height']}.{ext_v.lower()}"
                            buf = io.BytesIO()
                            
                            # OPTIMIZED LOSSLESS LOGIC
                            if ext_v == "JPEG":
                                # 100 quality + subsampling=0 (4:4:4) for maximum fidelity
                                res.save(buf, format="JPEG", quality=q_v, subsampling=0 if q_v == 100 else 2, optimize=True)
                            else:
                                # Memory-safe WebP Lossless (Method 4)
                                res.save(buf, format="WEBP", quality=q_v, lossless=(q_v == 100), method=4)
                            
                            zf.writestr(fn, buf.getvalue())
                
                status_text.text("Export Ready!")
                st.success("Batch Generated successfully.")
                st.download_button("DOWNLOAD ZIP", data=zip_buffer.getvalue(), file_name=f"{sanitize(st.session_state.proj_name)}.zip", mime="application/zip")

# --- TAB 2 & 3: FORMATS & SETTINGS [LOCKED] ---
with tab_fmt:
    st.write("### Museum Standards Library")
    if st.session_state.specs:
        for idx, spec in enumerate(st.session_state.specs):
            with st.expander(f"{spec.get('category', 'OTHER')}: {spec.get('label', 'Unnamed')}"):
                l = st.text_input("Label", spec.get('label', ''), key=f"edit_l_{idx}")
                c1, c2 = st.columns(2); w = c1.number_input("Width", value=int(spec.get('width', 1080)), key=f"w_{idx}"); h = c2.number_input("Height", value=int(spec.get('height', 1080)), key=f"h_{idx}")
                c3, c4 = st.columns(2); cur_ext = 0 if spec.get('ext', 'WebP') == 'WebP' else 1; e = c3.selectbox("File Type", ["WebP", "JPEG"], index=cur_ext, key=f"e_{idx}"); q = c4.slider("Quality", 10, 100, spec.get('quality', 85), key=f"q_{idx}")
                b1, b2 = st.columns([1, 4])
                if b1.button("Save Changes", key=f"upd_{idx}"):
                    st.session_state.specs[idx].update({"label": l, "width": int(w), "height": int(h), "ext": e, "quality": q, "ratio": calculate_ratio(int(w), int(h))}); save_specs_to_disk(); st.rerun()
                if b2.button("Remove Format", key=f"del_{idx}"): st.session_state.specs.pop(idx); save_specs_to_disk(); st.rerun()
    st.divider()
    with st.form("new_standard"):
        st.write("#### Add New Permanent Format"); n_cat = st.text_input("Category", value="SOCIAL")
        nc1, nc2, nc3 = st.columns(3); n_lab = nc1.text_input("Format Name"); n_ext = nc2.selectbox("File Type", ["WebP", "JPEG"]); n_q = nc3.slider("Quality", 10, 100, 85)
        nc4, nc5 = st.columns(2); n_w = nc4.number_input("Width", 1080); n_h = nc5.number_input("Height", 1080)
        if st.form_submit_button("ADD TO SYSTEM"):
            st.session_state.specs.append({"category": n_cat.upper(), "label": n_lab, "width": int(n_w), "height": int(n_h), "ratio": calculate_ratio(int(n_w), int(n_h)), "ext": n_ext, "quality": n_q}); save_specs_to_disk(); st.rerun()

with tab_set:
    st.write("### Workflow Settings")
    st.session_state.proj_name = st.text_input("Project Export Name", value=st.session_state.proj_name)
    st.divider()
    json_data = json.dumps({"formats": st.session_state.specs}, indent=4)
    st.download_button(label="💾 EXPORT LIBRARY (JSON)", data=json_data, file_name="psam_library_backup.json", mime="application/json")
