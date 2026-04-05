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
        st.write(" ")
        
        # 3.1 CUSTOM SETTINGS TOGGLE
        cust_active = st.toggle("Custom Settings", value=False)
        selected_formats = []
        final_cx, final_cy = 0.5, 0.5

        if cust_active:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
                cust_w = c1.number_input("Width", value=1080, key="cust_w")
                cust_h = c2.number_input("Height", value=1080, key="cust_h")
                cust_ext = c3.selectbox("Format", ["WebP", "JPEG"], key="cust_ext")
                cust_q = c4.slider("Export Quality", 10, 100, 95, key="cust_q")

                with st.expander("👁️ Preview & Alignment Controls", expanded=False):
                    aspect = cust_w / cust_h
                    sw, sh = (500, int(500/aspect)) if aspect > 1 else (int(500*aspect), 500)
                    
                    pcol_img, pcol_ctrl = st.columns([1, 1])
                    with pcol_ctrl:
                        preset = st.radio("Quick Presets", ["Center", "Top", "Bottom", "Left", "Right", "Manual"], horizontal=True)
                        if preset == "Center": dx, dy = 50, 50
                        elif preset == "Top": dx, dy = 50, 0
                        elif preset == "Bottom": dx, dy = 50, 100
                        elif preset == "Left": dx, dy = 0, 50
                        elif preset == "Right": dx, dy = 100, 50
                        else: dx, dy = 50, 50

                        mx = st.slider("Left ← Alignment → Right", 0, 100, dx)
                        my = st.slider("Top ← Alignment → Bottom", 0, 100, dy)
                        final_cx, final_cy = mx / 100, my / 100

                    with pcol_img:
                        prev_img = Image.open(uploaded_files[0]).convert("RGB")
                        crop = ImageOps.fit(prev_img, (cust_w, cust_h), method=Image.Resampling.LANCZOS, centering=(final_cx, final_cy))
                        st.image(crop, width=sw, caption=f"Preview ({calculate_ratio(cust_w, cust_h)})")
            
            selected_formats.append({"label": "Custom", "width": cust_w, "height": cust_h, "ext": cust_ext, "quality": cust_q, "cx": final_cx, "cy": final_cy})

        # 3.2 TEMPLATES & LOSSLESS TOGGLES
        st.write(" ")
        show_templates = st.toggle("Templates", value=False)
        # New Toggle for Lossless Export
        disable_compression = st.toggle("Lossless Export (Print Mode)", value=False)

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
        if st.button("GENERATE ALL ASSETS", use_container_width=True):
            if selected_formats:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zf:
                    for up in uploaded_files:
                        img = Image.open(up).convert("RGB")
                        bn = sanitize(os.path.splitext(up.name)[0])
                        for sp in selected_formats:
                            cx, cy = sp.get('cx', 0.5), sp.get('cy', 0.5)
                            res = ImageOps.fit(img, (sp['width'], sp['height']), method=Image.Resampling.LANCZOS, centering=(cx, cy))
                            ext = sp.get('ext', 'WebP').upper()
                            
                            # Determine final quality based on toggle
                            final_q = 100 if disable_compression else sp.get('quality', 95)
                            
                            fn = f"PSAM_{bn}_{sanitize(sp['label'])}_{sp['width']}x{sp['height']}.{ext.lower()}"
                            buf = io.BytesIO()
                            
                            # High fidelity save logic
                            if ext == "JPEG":
                                # subsampling=0 (4:4:4) provides max color detail for print
                                res.save(buf, format="JPEG", quality=final_q, subsampling=0 if disable_compression else 'outer', optimize=True)
                            else:
                                # Lossless WebP if toggle is ON and quality is 100
                                res.save(buf, format="WEBP", quality=final_q, lossless=disable_compression, method=6)
                                
                            zf.writestr(fn, buf.getvalue())
                st.success("Batch Generated (Lossless Active)" if disable_compression else "Batch Generated."); st.download_button("DOWNLOAD ZIP", data=zip_buffer.getvalue(), file_name=f"{sanitize(st.session_state.proj_name)}.zip", mime="application/zip")

# --- TAB 2 & 3: FORMATS & SETTINGS [LOCKED] ---
# ... (Full tabs preserved as per last update) ...
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
