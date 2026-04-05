import streamlit as st
from PIL import Image, ImageOps
import json, os, math, re, io, zipfile

# --- 1. INITIALIZATION ---
if 'specs' not in st.session_state:
    if os.path.exists("transformer_specs.json"):
        with open("transformer_specs.json", "r") as f:
            st.session_state.specs = json.load(f).get('formats', [])
    else:
        st.session_state.specs = []

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
def calculate_ratio(w, h):
    gcd = math.gcd(w, h)
    return f"{w//gcd}:{h//gcd}"

def sanitize(name):
    return re.sub(r'[^a-zA-Z0-9]', '_', name)

def get_svg_rect(ratio_str):
    try:
        r_w, r_h = map(int, ratio_str.split(":"))
        max_d = 40
        w, h = (max_d, int(max_d*(r_h/r_w))) if r_w > r_h else (int(max_d*(r_w/r_h)), max_d)
        return f'<svg width="50" height="50"><rect x="{(50-w)/2}" y="{(50-h)/2}" width="{w}" height="{h}" fill="none" stroke="#f36e2e" stroke-width="2.5"/></svg>'
    except: return ""

# --- 4. INTERFACE ---
tab_run, tab_fmt, tab_set = st.tabs(["TRANSFORMER", "FORMATS", "SETTINGS"])

with tab_run:
    # 4.1 THE TRANSPARENT DROP ZONE
    uploaded_files = st.file_uploader("Drag & Drop Images Here", type=['jpg', 'png', 'webp'], accept_multiple_files=True, label_visibility="collapsed")

    if uploaded_files:
        st.write(" ")
        
        # 4.2 VERTICAL CATEGORY SECTIONS
        categories = ["SOCIAL", "WEB", "EMAIL"]
        selected_formats = []

        for category in categories:
            st.markdown(f'<p class="cat-header">{category}</p>', unsafe_allow_html=True)
            
            cat_specs = [s for s in st.session_state.specs if s.get('category') == category]
            
            for spec in cat_specs:
                # Custom Flexbox Card
                # Wrapping in a div so our CSS 'format-card' can take over
                st.markdown(f'''
                    <div class="format-card">
                        <div class="card-left">
                            <div class="card-icon">{get_svg_rect(spec['ratio'])}</div>
                            <div class="card-info">
                                <div class="format-label">{spec["label"]}</div>
                                <div class="format-subline">{spec['width']}x{spec['height']} — {spec.get('ext', 'WebP').upper()} @ {spec.get('quality', 85)}% Quality</div>
                            </div>
                        </div>
                ''', unsafe_allow_html=True)
                
                # Use a unique key and align the checkbox to the right
                # We use negative margin trick to pull the widget into the div
                st.markdown('<div style="margin-top: -65px; text-align: right; padding-right: 20px;">', unsafe_allow_html=True)
                if st.checkbox("", value=True, key=f"run_{spec['label']}", label_visibility="collapsed"):
                    selected_formats.append(spec)
                st.markdown('</div></div>', unsafe_allow_html=True)

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
                            f_ext = spec.get('ext', 'WebP').upper()
                            f_name = f"PSAM_{sanitize(spec['label'])}.{f_ext.lower()}"
                            img_io = io.BytesIO()
                            res.save(img_io, format=f_ext, quality=spec.get('quality', 85))
                            zip_file.writestr(f"{base_n}/{f_name}", img_io.getvalue())
                
                st.success(f"Generated {len(uploaded_files)} images.")
                st.download_button("DOWNLOAD ZIP", data=zip_buffer.getvalue(), file_name=f"{sanitize(st.session_state.proj_name)}.zip", mime="application/zip")

# ... (Keep FORMATS and SETTINGS tabs as they were) ...
