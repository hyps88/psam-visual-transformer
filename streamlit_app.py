import streamlit as st
from PIL import Image, ImageOps
import json, os, math, re, io, zipfile

# --- 1. INITIALIZATION: Run this before EVERYTHING else ---
if 'specs' not in st.session_state:
    if os.path.exists("transformer_specs.json"):
        with open("transformer_specs.json", "r") as f:
            st.session_state.specs = json.load(f).get('formats', [])
    else:
        st.session_state.specs = []

if 'proj_name' not in st.session_state:
    st.session_state.proj_name = "PSAM_Export"

# --- 2. THEME & CORE HELPERS ---
st.set_page_config(page_title="Visual Transformer", layout="wide")

def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

load_css('style.css')

def save_specs_to_disk():
    with open("transformer_specs.json", "w") as f:
        json.dump({"formats": st.session_state.specs}, f, indent=4)

def calculate_ratio(w, h):
    gcd = math.gcd(w, h)
    return f"{w//gcd}:{h//gcd}"

def sanitize(name):
    return re.sub(r'[^a-zA-Z0-9]', '_', name)

def get_svg_rect(ratio_str):
    try:
        r_w, r_h = map(int, ratio_str.split(":"))
        max_d = 35
        w, h = (max_d, int(max_d*(r_h/r_w))) if r_w > r_h else (int(max_d*(r_w/r_h)), max_d)
        return f'<svg width="45" height="45"><rect x="{(45-w)/2}" y="{(45-h)/2}" width="{w}" height="{h}" fill="none" stroke="#f36e2e" stroke-width="2"/></svg>'
    except: return ""

# --- 3. INTERFACE TABS ---
tab_run, tab_fmt, tab_set = st.tabs(["TRANSFORMER", "FORMATS", "SETTINGS"])

with tab_run:
    # 3.1 THE CENTERED DROP ZONE
    uploaded_files = st.file_uploader("Drag & Drop Images Here", type=['jpg', 'png', 'webp'], accept_multiple_files=True, label_visibility="collapsed")

    if uploaded_files:
        st.write(" ")
        mcol1, mcol2, mcol3 = st.columns(3)
        cats = {"SOCIAL": mcol1, "WEB": mcol2, "EMAIL": mcol3}
        selected_formats = []

        for category, col in cats.items():
            with col:
                st.markdown(f'<p class="cat-header">{category}</p>', unsafe_allow_html=True)
                # ERROR FIX: accessing state safely
                cat_specs = [s for s in st.session_state.specs if s.get('category') == category]
                
                for spec in cat_specs:
                    # RENDER THE CARD: [Icon (1) | Info (6) | Checkbox (1)]
                    with st.container(border=True):
                        c_icon, c_info, c_check = st.columns([1, 6, 1])
                        
                        with c_icon:
                            st.markdown(get_svg_rect(spec['ratio']), unsafe_allow_html=True)
                        
                        with c_info:
                            st.markdown(f'<div class="format-label">{spec["label"]}</div>', unsafe_allow_html=True)
                            # Size + Compression on one subline
                            sub_text = f"{spec['width']}x{spec['height']} — {spec.get('ext', 'WebP').upper()} @ {spec.get('quality', 85)}% Quality"
                            st.markdown(f'<div class="format-subline">{sub_text}</div>', unsafe_allow_html=True)
                        
                        with c_check:
                            # Selection checkbox pushed to the far right
                            if st.checkbox("", value=True, key=f"run_{spec['label']}", label_visibility="collapsed"):
                                selected_formats.append(spec)

        st.divider()
        if st.button("GENERATE ASSETS", use_container_width=True):
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

with tab_fmt:
    st.write("### Museum Standards Library")
    for idx, spec in enumerate(st.session_state.specs):
        with st.expander(f"✎ {spec['category']}: {spec['label']}"):
            l = st.text_input("Label", spec['label'], key=f"l_{idx}")
            c1, c2 = st.columns(2)
            w = c1.number_input("Width", value=int(spec['width']), key=f"w_{idx}")
            h = c2.number_input("Height", value=int(spec['height']), key=f"h_{idx}")
            if st.button("Save Changes", key=f"upd_{idx}"):
                st.session_state.specs[idx].update({"label": l, "width": int(w), "height": int(h), "ratio": calculate_ratio(int(w), int(h))})
                save_specs_to_disk(); st.rerun()

with tab_set:
    st.write("### Settings")
    st.session_state.proj_name = st.text_input("Project Name", value=st.session_state.proj_name)
