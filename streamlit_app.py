import streamlit as st
from PIL import Image, ImageOps
import json, os, math, re, io, zipfile

# --- CORE CONFIG ---
st.set_page_config(page_title="Visual Transformer", layout="wide")

def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

load_css('style.css')

# ... (Keep your standard helpers: calculate_ratio, sanitize, save_specs_to_disk) ...

# --- INTERFACE ---
tab_run, tab_fmt, tab_set = st.tabs(["TRANSFORMER", "FORMATS", "SETTINGS"])

with tab_run:
    # Use label_visibility="collapsed" to let the CSS-styled instructions be the "title"
    uploaded_files = st.file_uploader("Drag & Drop Images Here", type=['jpg', 'png', 'webp'], accept_multiple_files=True, label_visibility="collapsed")

    if uploaded_files:
        st.write(" ")
        mcol1, mcol2, mcol3 = st.columns(3)
        cats = {"SOCIAL": mcol1, "WEB": mcol2, "EMAIL": mcol3}
        selected_formats = []

        for category, col in cats.items():
            with col:
                st.markdown(f'<p class="cat-header">{category}</p>', unsafe_allow_html=True)
                cat_specs = [s for s in st.session_state.specs if s['category'] == category]
                
                for spec in cat_specs:
                    # RENDER THE CARD: [Icon | Info | Checkbox]
                    with st.container(border=True):
                        c_icon, c_info, c_check = st.columns([1, 5, 1])
                        
                        with c_icon:
                            st.markdown(get_svg_rect(spec['ratio']), unsafe_allow_html=True)
                        
                        with c_info:
                            st.markdown(f'<div class="format-label">{spec["label"]}</div>', unsafe_allow_html=True)
                            # Unified Subline: Size | Format | Quality
                            sub_text = f"{spec['width']}x{spec['height']} — {spec.get('ext', 'WebP').upper()} @ {spec.get('quality', 85)}% Quality"
                            st.markdown(f'<div class="format-subline">{sub_text}</div>', unsafe_allow_html=True)
                        
                        with c_check:
                            # Pushed to the right via the column layout
                            if st.checkbox("", value=True, key=f"run_{spec['label']}", label_visibility="collapsed"):
                                selected_formats.append(spec)

        st.divider()
        if st.button("GENERATE ASSETS", use_container_width=True):
            # ... (Keep your existing PIL processing logic here) ...
            pass
