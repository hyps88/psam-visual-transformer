import streamlit as st
from PIL import Image, ImageOps
import json, os, math, re, io, zipfile

# --- 1. CORE INITIALIZATION ---
st.set_page_config(page_title="Visual Transformer", layout="wide")

if 'specs' not in st.session_state:
    if os.path.exists("transformer_specs.json"):
        with open("transformer_specs.json", "r") as f:
            st.session_state.specs = json.load(f).get('formats', [])
    else:
        st.session_state.specs = []

if 'proj_name' not in st.session_state:
    st.session_state.proj_name = "PSAM_Export"

# --- 2. THEME LOADING ---
def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

load_css('style.css')

# --- 3. HELPERS ---
def save_specs_to_disk():
    with open("transformer_specs.json", "w") as f:
        json.dump({"formats": st.session_state.specs}, f, indent=4)

def sanitize(name):
    return re.sub(r'[^a-zA-Z0-9]', '_', name)

def get_svg_rect(ratio_str):
    try:
        r_w, r_h = map(int, ratio_str.split(":"))
        max_d = 35
        w, h = (max_d, int(max_d*(r_h/r_w))) if r_w > r_h else (int(max_d*(r_w/r_h)), max_d)
        return f'<svg width="45" height="45"><rect x="{(45-w)/2}" y="{(45-h)/2}" width="{w}" height="{h}" fill="none" stroke="#f36e2e" stroke-width="2.5"/></svg>'
    except: return ""

# --- 4. INTERFACE ---
tab_run, tab_fmt, tab_set = st.tabs(["TRANSFORMER", "FORMATS", "SETTINGS"])

with tab_run:
    # 4.1 DROP ZONE
    uploaded_files = st.file_uploader("Drag & Drop Images Here", type=['jpg', 'png', 'webp'], accept_multiple_files=True, label_visibility="collapsed")

    if uploaded_files:
        st.write(" ")
        
        categories = ["SOCIAL", "WEB", "EMAIL"]
        selected_formats = []

        for category in categories:
            cat_specs = [s for s in st.session_state.specs if s.get('category') == category]
            if not cat_specs: continue

            st.markdown(f'<p class="cat-header">{category}</p>', unsafe_allow_html=True)
            
            # Chunk the specs into groups of 3 for the grid
            for i in range(0, len(cat_specs), 3):
                row_specs = cat_specs[i:i+3]
                cols = st.columns(3)
                
                for idx, spec in enumerate(row_specs):
                    with cols[idx]:
                        # The Card Container
                        with st.container(border=True):
                            # Internal Split: Icon | Text | Checkbox
                            inner_icon, inner_text, inner_check = st.columns([1, 5, 1])
                            
                            with inner_icon:
                                st.markdown(get_svg_rect(spec['ratio']), unsafe_allow_html=True)
                            
                            with inner_text:
                                st.markdown(f'<div class="card-label">{spec["label"]}</div>', unsafe_allow_html=True)
                                subline = f"{spec['width']}x{spec['height']} — {spec.get('ext', 'WebP').upper()} @ {spec.get('quality', 85)}%"
                                st.markdown(f'<div class="card-subline">{subline}</div>', unsafe_allow_html=True)
                                
                            with inner_check:
                                # Checkbox is now inside the container and pinned right
                                if st.checkbox("", value=True, key=f"run_{spec['label']}", label_visibility="collapsed"):
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
                
                st.success(f"Generated {len(uploaded_files)} images.")
                st.download_button("DOWNLOAD ZIP", data=zip_buffer.getvalue(), file_name=f"{sanitize(st.session_state.proj_name)}.zip", mime="application/zip")

with tab_fmt:
    # (Keep your existing Management logic here)
    st.write("### Manage Library")
    for idx, spec in enumerate(st.session_state.specs):
        with st.expander(f"{spec['category']}: {spec['label']}"):
            l = st.text_input("Label", spec['label'], key=f"l_{idx}")
            if st.button("Save", key=f"save_{idx}"):
                st.session_state.specs[idx]['label'] = l
                save_specs_to_disk(); st.rerun()

with tab_set:
    st.write("### Settings")
    st.session_state.proj_name = st.text_input("Project Name", value=st.session_state.proj_name)
