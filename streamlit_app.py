import streamlit as st
from PIL import Image, ImageOps
import json, os, math, re, io, zipfile

# --- 1. INITIALIZATION ---
if 'specs' not in st.session_state:
    if os.path.exists("transformer_specs.json"):
        with open("transformer_specs.json", "r") as f:
            st.session_state.specs = json.load(f).get('formats', [])
    else: st.session_state.specs = []

if 'proj_name' not in st.session_state:
    st.session_state.proj_name = "PSAM_Export"

# --- 2. CORE CONFIG ---
st.set_page_config(page_title="Visual Transformer", layout="wide")

def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

load_css('style.css')

# --- 3. HELPERS ---
def get_svg_rect(ratio_str):
    try:
        r_w, r_h = map(int, ratio_str.split(":"))
        max_d = 35
        w, h = (max_d, int(max_d*(r_h/r_w))) if r_w > r_h else (int(max_d*(r_w/r_h)), max_d)
        return f'<svg width="45" height="45"><rect x="{(45-w)/2}" y="{(45-h)/2}" width="{w}" height="{h}" fill="none" stroke="#f36e2e" stroke-width="2.5"/></svg>'
    except: return ""

def sanitize(name):
    return re.sub(r'[^a-zA-Z0-9]', '_', name)

# --- 4. INTERFACE ---
tab_run, tab_fmt, tab_set = st.tabs(["TRANSFORMER", "FORMATS", "SETTINGS"])

with tab_run:
    # 4.1 DROP ZONE (UNTOUCHED AS REQUESTED)
    uploaded_files = st.file_uploader("Drag & Drop Images Here", type=['jpg', 'png', 'webp'], accept_multiple_files=True, label_visibility="collapsed")

    if uploaded_files:
        st.write(" ")
        
        # 4.2 SECTIONED CATEGORIES
        categories = ["SOCIAL", "WEB", "EMAIL"]
        selected_formats = []

        for category in categories:
            st.markdown(f'<p class="cat-header">{category}</p>', unsafe_allow_html=True)
            
            cat_specs = [s for s in st.session_state.specs if s.get('category') == category]
            
            # Create a 3-column grid for the cards
            cols = st.columns(3)
            
            for i, spec in enumerate(cat_specs):
                # Distribute cards across the 3 columns
                with cols[i % 3]:
                    # The Card "Wrapper"
                    with st.container(border=True):
                        # Nested columns to align Checkbox on the Right
                        c_icon, c_text, c_check = st.columns([1, 4, 1])
                        
                        with c_icon:
                            st.markdown(f'<div class="card-internal">{get_svg_rect(spec["ratio"])}</div>', unsafe_allow_html=True)
                        
                        with c_text:
                            st.markdown(f'<div class="card-label">{spec["label"]}</div>', unsafe_allow_html=True)
                            subline = f"{spec['width']}x{spec['height']} — {spec.get('ext', 'WebP').upper()} @ {spec.get('quality', 85)}%"
                            st.markdown(f'<div class="card-subline">{subline}</div>', unsafe_allow_html=True)
                            
                        with c_check:
                            # Checkbox is now inside the container, aligned right
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

# ... (Keep FORMATS and SETTINGS tabs as they were) ...
