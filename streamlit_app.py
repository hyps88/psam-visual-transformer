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
    gcd = math.gcd(w, h); return f"{w//gcd}:{h//gcd}"

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

with tab_run:
    uploaded_files = st.file_uploader("Drag & Drop Images Here", type=['jpg', 'png', 'webp'], accept_multiple_files=True, label_visibility="collapsed")

    if uploaded_files:
        st.write(" ")
        
        # 3.1 CUSTOM SETTINGS TOGGLE (Default OFF)
        cust_active = st.toggle("Custom Settings", value=False)
        selected_formats = []
        
        if cust_active:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
                cust_w = c1.number_input("Width", value=1080, key="cust_w")
                cust_h = c2.number_input("Height", value=1080, key="cust_h")
                cust_ext = c3.selectbox("Format", ["WebP", "JPEG"], key="cust_ext")
                cust_q = c4.slider("Export Quality", 10, 100, 95, key="cust_q")

                # Nested Preview Toggle
                with st.expander("👁️ Preview & Alignment Controls", expanded=False):
                    preview_img = Image.open(uploaded_files[0]).convert("RGB")
                    pcol_img, pcol_ctrl = st.columns([2, 1])
                    
                    with pcol_ctrl:
                        preset = st.radio("Quick Presets", ["Center", "Top", "Bottom", "Left", "Right", "Manual"], horizontal=True)
                        if preset == "Center": def_x, def_y = 50, 50
                        elif preset == "Top": def_x, def_y = 50, 0
                        elif preset == "Bottom": def_x, def_y = 50, 100
                        elif preset == "Left": def_x, def_y = 0, 50
                        elif preset == "Right": def_x, def_y = 100, 50
                        else: def_x, def_y = 50, 50

                        man_x = st.slider("X-Axis Offset", 0, 100, def_x)
                        man_y = st.slider("Y-Axis Offset", 0, 100, def_y)
                        final_cx, final_cy = man_x / 100, man_y / 100

                    with pcol_img:
                        res_preview = ImageOps.fit(preview_img, (cust_w, cust_h), centering=(final_cx, final_cy))
                        st.image(res_preview, width=500, caption=f"Proportional Preview ({calculate_ratio(cust_w, cust_h)})")
            
            # Add to export batch immediately if toggled on
            selected_formats.append({
                "label": "Custom", "width": cust_w, "height": cust_h, 
                "ext": cust_ext, "quality": cust_q, "cx": final_cx, "cy": final_cy
            })
        else:
            # Default centering for logic safety
            final_cx, final_cy = 0.5, 0.5

        # 3.2 TEMPLATES TOGGLE (Default OFF)
        st.write(" ")
        show_templates = st.toggle("Templates", value=False)

        if show_templates:
            categories = sorted(list(set(s.get('category', 'OTHER') for s in st.session_state.specs)))
            for category in categories:
                cat_specs = [s for s in st.session_state.specs if s.get('category') == category]
                h_cols = st.columns([0.1, 0.05, 0.85]) 
                with h_cols[0]: st.markdown(f'<p class="cat-header-text" style="padding-top: 5px;">{category}</p>', unsafe_allow_html=True)
                with h_cols[1]: st.checkbox("", value=False, key=f"master_{category}", on_change=toggle_section, args=(category,), label_visibility="collapsed")
                
                for i in range(0, len(cat_specs), 2):
                    row_specs = cat_specs[i:i+2]
                    grid_cols = st.columns(2)
                    for idx, spec in enumerate(row_specs):
                        with grid_cols[idx]:
                            with st.container(border=True):
                                c_icon, c_info, c_check = st.columns([1, 6, 1])
                                with c_icon: st.markdown(get_svg_rect(spec['ratio']), unsafe_allow_html=True)
                                with c_info:
                                    st.markdown(f'<div class="card-label">{spec["label"]}</div>', unsafe_allow_html=True)
                                    sub_text = f"{spec['width']}x{spec['height']} — {spec.get('ext', 'WebP').upper()} @ {spec.get('quality', 85)}%"
                                    st.markdown(f'<div class="card-subline">{sub_text}</div>', unsafe_allow_html=True)
                                with c_check:
                                    if st.checkbox("", value=st.session_state.get(f"run_{spec['label']}", False), key=f"run_{spec['label']}", label_visibility="collapsed"):
                                        selected_formats.append(spec)

        st.divider()
        if st.button("GENERATE ALL ASSETS", use_container_width=True):
            if selected_formats:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                    for up_file in uploaded_files:
                        img = Image.open(up_file).convert("RGB")
                        base_n = sanitize(os.path.splitext(up_file.name)[0])
                        for spec in selected_formats:
                            cx = spec.get('cx', 0.5); cy = spec.get('cy', 0.5)
                            res = ImageOps.fit(img, (spec['width'], spec['height']), method=Image.Resampling.LANCZOS, centering=(cx, cy))
                            
                            f_ext = spec.get('ext', 'WebP').upper()
                            label_slug = sanitize(spec['label'])
                            f_name = f"PSAM_{label_slug}_{spec['width']}x{spec['height']}.{f_ext.lower()}"
                            
                            img_io = io.BytesIO()
                            if f_ext == "JPEG":
                                res.save(img_io, format="JPEG", quality=spec.get('quality', 95), subsampling=0, optimize=True)
                            else:
                                res.save(img_io, format="WEBP", quality=spec.get('quality', 95), lossless=(spec.get('quality')==100), method=6)
                            
                            zip_file.writestr(f"{base_n}/{f_name}", img_io.getvalue())
                st.success(f"Generated {len(uploaded_files)} image batches."); st.download_button("DOWNLOAD ZIP", data=zip_buffer.getvalue(), file_name=f"{sanitize(st.session_state.proj_name)}.zip", mime="application/zip")

# --- 4. FORMATS & SETTINGS [LOCKED] ---
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
