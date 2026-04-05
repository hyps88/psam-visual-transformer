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

# --- 2. HELPERS ---
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
        
        # 3.1 CUSTOM SETTINGS (The "One-Off" Override)
        st.markdown('<p class="cat-header-text">Custom Settings</p>', unsafe_allow_html=True)
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
            cust_w = c1.number_input("Width", value=1080, key="cust_w")
            cust_h = c2.number_input("Height", value=1080, key="cust_h")
            cust_ext = c3.selectbox("Format", ["WebP", "JPEG"], key="cust_ext")
            cust_q = c4.slider("Compression / Quality", 10, 100, 85, key="cust_q")
            
            cust_active = st.checkbox("Apply Custom Settings to Export", value=False)

        # 3.2 TEMPLATES TOGGLE
        st.write(" ")
        show_templates = st.toggle("Templates", value=True)

        selected_formats = []
        
        # If user checked "Custom Settings", add that virtual spec to the list
        if cust_active:
            selected_formats.append({
                "label": "Custom", "width": cust_w, "height": cust_h, 
                "ext": cust_ext, "quality": cust_q
            })

        if show_templates:
            categories = sorted(list(set(s.get('category', 'OTHER') for s in st.session_state.specs)))
            for category in categories:
                cat_specs = [s for s in st.session_state.specs if s.get('category') == category]
                
                h_cols = st.columns([0.1, 0.05, 0.85]) 
                with h_cols[0]:
                    st.markdown(f'<p class="cat-header-text" style="padding-top: 5px;">{category}</p>', unsafe_allow_html=True)
                with h_cols[1]:
                    st.checkbox("", value=True, key=f"master_{category}", on_change=toggle_section, args=(category,), label_visibility="collapsed")
                
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
                                    if st.checkbox("", value=st.session_state.get(f"run_{spec['label']}", True), key=f"run_{spec['label']}", label_visibility="collapsed"):
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
                            f_ext = spec.get('ext', 'WebP').upper()
                            # Use custom label for custom settings to avoid naming collision
                            label_slug = sanitize(spec['label'])
                            f_name = f"PSAM_{label_slug}_{spec['width']}x{spec['height']}.{f_ext.lower()}"
                            
                            img_io = io.BytesIO()
                            res.save(img_io, format=f_ext, quality=spec.get('quality', 85))
                            zip_file.writestr(f"{base_n}/{f_name}", img_io.getvalue())
                st.success(f"Generated {len(uploaded_files)} images.")
                st.download_button("DOWNLOAD ZIP", data=zip_buffer.getvalue(), file_name=f"{sanitize(st.session_state.proj_name)}.zip", mime="application/zip")

# --- (Keep FORMATS and SETTINGS tabs as they were) ---
