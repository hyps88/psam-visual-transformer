import streamlit as st
from PIL import Image, ImageOps
import json, os, math, re, io, zipfile

# --- 1. INITIALIZATION ---
st.set_page_config(page_title="Visual Transformer", layout="wide")

if 'specs' not in st.session_state:
    if os.path.exists("transformer_specs.json"):
        with open("transformer_specs.json", "r") as f:
            st.session_state.specs = json.load(f).get('formats', [])
    else: st.session_state.specs = []

if 'proj_name' not in st.session_state:
    st.session_state.proj_name = "PSAM_Export"

# --- 2. LOGIC: SECTION TOGGLE ---
def toggle_section(category_name):
    master_state = st.session_state[f"master_{category_name}"]
    for spec in st.session_state.specs:
        if spec.get('category') == category_name:
            st.session_state[f"run_{spec['label']}"] = master_state

# --- 3. THEME & STORAGE ---
def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

load_css('style.css')

def save_specs_to_disk():
    with open("transformer_specs.json", "w") as f:
        json.dump({"formats": st.session_state.specs}, f, indent=4)

# --- 4. HELPERS ---
def calculate_ratio(w, h):
    gcd = math.gcd(w, h)
    return f"{w//gcd}:{h//gcd}"

def get_svg_rect(ratio_str):
    try:
        r_w, r_h = map(int, ratio_str.split(":")); max_d = 35
        w, h = (max_d, int(max_d*(r_h/r_w))) if r_w > r_h else (int(max_d*(r_w/r_h)), max_d)
        return f'<svg width="45" height="45"><rect x="{(45-w)/2}" y="{(45-h)/2}" width="{w}" height="{h}" fill="none" stroke="#f36e2e" stroke-width="2.5"/></svg>'
    except: return ""

def sanitize(name):
    return re.sub(r'[^a-zA-Z0-9]', '_', name)

# --- 5. INTERFACE ---
tab_run, tab_fmt, tab_set = st.tabs(["TRANSFORMER", "FORMATS", "SETTINGS"])

with tab_run:
    uploaded_files = st.file_uploader("Drag & Drop Images Here", type=['jpg', 'png', 'webp'], accept_multiple_files=True, label_visibility="collapsed")

    if uploaded_files:
        st.write(" ")
        # Build dynamic category list from your JSON
        categories = sorted(list(set(s.get('category', 'OTHER') for s in st.session_state.specs)))
        selected_formats = []

        for category in categories:
            cat_specs = [s for s in st.session_state.specs if s.get('category') == category]
            
            # HEADER: Title then Checkbox
            # Use fixed-width micro columns to prevent stacking
            h_cols = st.columns([0.1, 0.05, 0.85]) 
            with h_cols[0]:
                st.markdown(f'<p class="cat-header-text" style="padding-top: 5px;">{category}</p>', unsafe_allow_html=True)
            with h_cols[1]:
                st.checkbox("", value=True, key=f"master_{category}", 
                            on_change=toggle_section, args=(category,), 
                            label_visibility="collapsed")
            st.divider() # Visual break for the header
            
            # 2-COLUMN GRID
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
                                subline = f"{spec['width']}x{spec['height']} — {spec.get('ext', 'WebP').upper()} @ {spec.get('quality', 85)}%"
                                st.markdown(f'<div class="card-subline">{subline}</div>', unsafe_allow_html=True)
                            with c_check:
                                if st.checkbox("", value=st.session_state.get(f"run_{spec['label']}", True), 
                                               key=f"run_{spec['label']}", label_visibility="collapsed"):
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
                            res = ImageOps.fit(img, (spec['width'], spec['height']), Image.Resampling.LANCZOS)
                            f_name = f"PSAM_{sanitize(spec['label'])}.{spec.get('ext', 'webp').lower()}"
                            img_io = io.BytesIO()
                            res.save(img_io, format=spec.get('ext', 'WebP').upper(), quality=spec.get('quality', 85))
                            zip_file.writestr(f"{base_n}/{f_name}", img_io.getvalue())
                st.success(f"Generated {len(uploaded_files)} images."); st.download_button("DOWNLOAD ZIP", data=zip_buffer.getvalue(), file_name=f"{sanitize(st.session_state.proj_name)}.zip", mime="application/zip")

with tab_fmt:
    st.write("### Museum Standards Library")
    for idx, spec in enumerate(st.session_state.specs):
        with st.expander(f"{spec['category']}: {spec['label']}"):
            l = st.text_input("Label", spec['label'], key=f"edit_l_{idx}")
            c1, c2 = st.columns(2); w = c1.number_input("Width", value=int(spec['width']), key=f"w_{idx}"); h = c2.number_input("Height", value=int(spec['height']), key=f"h_{idx}")
            if st.button("Save Changes", key=f"upd_{idx}"):
                st.session_state.specs[idx].update({"label": l, "width": int(w), "height": int(h), "ratio": calculate_ratio(int(w), int(h))}); save_specs_to_disk(); st.rerun()
            if st.button("Remove Format", key=f"del_{idx}"): st.session_state.specs.pop(idx); save_specs_to_disk(); st.rerun()
    
    st.divider()
    with st.form("new_standard"):
        st.write("#### Add New Permanent Format")
        n_cat = st.text_input("Category (e.g. SOCIAL, PRINT, WEB)", value="SOCIAL")
        nc1, nc2, nc3 = st.columns(3); n_lab = nc1.text_input("Format Name"); n_ext = nc2.selectbox("File Type", ["WebP", "JPEG"]); n_q = nc3.slider("Quality", 10, 100, 85)
        nc4, nc5 = st.columns(2); n_w = nc4.number_input("Width", 1080); n_h = nc5.number_input("Height", 1080)
        if st.form_submit_button("ADD TO SYSTEM"):
            # FIX: Included all required fields to match initialization
            st.session_state.specs.append({"category": n_cat.upper(), "label": n_lab, "width": int(n_w), "height": int(n_h), "ratio": calculate_ratio(int(n_w), int(n_h)), "ext": n_ext, "quality": n_q}); save_specs_to_disk(); st.rerun()

with tab_set:
    st.session_state.proj_name = st.text_input("Project Export Name", value=st.session_state.proj_name)
