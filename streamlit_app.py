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

# ... (Keep your calculate_ratio and sanitize helpers here) ...

with tab_run:
    uploaded_files = st.file_uploader("Drag & Drop Images Here", type=['jpg', 'png', 'webp'], accept_multiple_files=True)

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
                    # RENDER THE CUSTOM CARD
                    # We inject the structure as one block so Flexbox can handle it
                    with st.container():
                        icon_html = get_svg_rect(spec['ratio'])
                        subline_text = f"{spec['width']}x{spec['height']} — {spec.get('ext', 'WebP').upper()} @ {spec.get('quality', 85)}% Quality"
                        
                        # Create the layout container
                        st.markdown(f"""
                            <div class="format-card-content">
                                <div class="card-icon">{icon_html}</div>
                                <div class="card-info">
                                    <div class="format-label">{spec['label']}</div>
                                    <div class="format-subline">{subline_text}</div>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        # The checkbox is rendered separately but pushed right by CSS
                        # We use a negative margin-top to "float" it back into the flex container
                        st.markdown('<div class="card-checkbox" style="margin-top: -65px; margin-right: 20px; text-align: right;">', unsafe_allow_html=True)
                        if st.checkbox("", value=True, key=f"run_{spec['label']}", label_visibility="collapsed"):
                            selected_formats.append(spec)
                        st.markdown('</div>', unsafe_allow_html=True)

        # ... (Keep your Generate button logic here) ...
