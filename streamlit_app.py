import streamlit as st
from PIL import Image, ImageOps
import json, os, math, re, io, zipfile
from datetime import datetime

# --- 1. SETTINGS & THEME ---
ACCENT_COLOR = "#f36e2e"
st.set_page_config(page_title="Visual Transformer", page_icon="🖼️", layout="wide")

st.markdown(f"""
    <style>
    .stApp {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #0e1117; }}
    
    /* Category Headers: Pro Spacing */
    .cat-header {{
        font-size: 13px;
        font-weight: 800;
        color: #555;
        letter-spacing: 3px;
        margin-top: 80px !important;
        margin-bottom: 25px;
        text-transform: uppercase;
        border-bottom: 1px solid #222;
        padding-bottom: 8px;
    }}

    /* Format Card: Deep & Dark */
    .format-card {{
        background-color: #1a1c1e;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 15px;
        border: 1px solid #2b2b2b;
    }}
    
    .stCheckbox [data-testid="stMarkdownContainer"] p {{
        font-size: 16px !important;
        font-weight: 600 !important;
        color: white !important;
    }}

    .stButton>button {{
        background-color: {ACCENT_COLOR};
        color: white;
        border-radius: 8px;
        border: none;
        font-weight: bold;
        height: 3em;
    }}
    </style>
""", unsafe_allow_html=True)

# --- 2. HELPERS ---
def calculate_ratio(w, h):
    gcd = math.gcd(w, h)
    return f"{w//gcd}:{h//gcd}"

def sanitize(name):
    return re.sub(r'[^a-zA-Z0-9]', '_', name)

def get_svg_rect(ratio_str, color=ACCENT_COLOR):
    try:
        r_w, r_h = map(int, ratio_str.split(":"))
        max_d = 35
        w, h = (max_d, int(max_d*(r_h/r_w))) if r_w > r_h else (int(max_d*(r_w/r_h)), max_d)
        return f'<svg width="45" height="45"><rect x="{(45-w)/2}" y="{(45-h)/2}" width="{w}" height="{h}" fill="none" stroke="{color}" stroke-width="2"/></svg>'
    except: return ""

# --- 3. STATE & DATA ---
if 'specs' not in st.session_state:
    if os.path.exists("transformer_specs.json"):
        with open("transformer_specs.json", "r") as f:
            st.session_state.specs = json.load(f)['formats']
    else:
        st.session_state.specs = []

# --- 4. SIDEBAR ---
st.sidebar.title("Visual Transformer")
uploaded_files = st.sidebar.file_uploader("BATCH IMPORT", type=['jpg', 'png', 'webp'], accept_multiple_files=True)
project_name = st.sidebar.text_input("PROJECT NAME", value="PSAM_Export")

st.sidebar.divider()
st.sidebar.subheader("Global Override")
use_global = st.sidebar.toggle("Enable Global Compression", value=False, help="When ON, ignores individual format settings.")

# Global Controls (Only active if toggle is ON)
g_quality = st.sidebar.slider("GLOBAL QUALITY", 10, 100, 85, disabled=not use_global)
g_engine_label = st.sidebar.selectbox("GLOBAL ENGINE", ["LANCZOS (High Quality)", "BILINEAR", "BICUBIC"], disabled=not use_global)
g_engine = Image.Resampling.LANCZOS if "LANCZOS" in g_engine_label else Image.Resampling.BILINEAR

# --- 5. MAIN UI ---
tab_run, tab_lib = st.tabs(["TRANSFORMER", "LIBRARY MANAGEMENT"])

with tab_run:
    if not uploaded_files:
        st.info("Import master images in the sidebar to visualize assets.")
    else:
        st.write("### Select Target Formats")
        
        mcol1, mcol2, mcol3 = st.columns(3)
        cats = {"SOCIAL": mcol1, "WEB": mcol2, "EMAIL": mcol3}
        selected_formats = []

        for category, col in cats.items():
            with col:
                st.markdown(f'<p class="cat-header">{category}</p>', unsafe_allow_html=True)
                cat_specs = [s for idx, s in enumerate(st.session_state.specs) if s['category'] == category]
                
                for spec in cat_specs:
                    # Individual Setting Display
                    q_val = g_quality if use_global else spec.get('quality', 80)
                    ext_val = spec.get('ext', 'WebP')
                    
                    with st.container():
                        st.markdown('<div class="format-card">', unsafe_allow_html=True)
                        c_icon, c_check = st.columns([1, 4])
                        with c_icon:
                            st.markdown(get_svg_rect(spec['ratio']), unsafe_allow_html=True)
                        with c_check:
                            check_label = f"{spec['label']} ({spec['width']}x{spec['height']})"
                            if st.checkbox(check_label, value=True, key=f"run_{spec['label']}"):
                                selected_formats.append(spec)
                            st.markdown(f'<span style="color: #666; font-size: 11px;">SETTING: {ext_val.upper()} @ {q_val}% Quality</span>', unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)

        st.divider()
        if st.button("🚀 GENERATE ALL BATCH ASSETS", use_container_width=True):
            if not selected_formats:
                st.warning("Please select at least one format.")
            else:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                    for up_file in uploaded_files:
                        img = Image.open(up_file).convert("RGB")
                        base_n = sanitize(os.path.splitext(up_file.name)[0])
                        
                        for spec in selected_formats:
                            # LOGIC: Override or Individual?
                            final_q = g_quality if use_global else spec.get('quality', 80)
                            final_ext = spec.get('ext', 'WebP').upper()
                            
                            res = ImageOps.fit(img, (spec['width'], spec['height']), g_engine)
                            f_name = f"PSAM_{sanitize(spec['label'])}.{final_ext.lower()}"
                            
                            img_io = io.BytesIO()
                            res.save(img_io, format=final_ext, quality=final_q)
                            zip_file.writestr(f"{base_n}/{f_name}", img_io.getvalue())
                
                st.success(f"Batch Complete: {len(uploaded_files)} images processed.")
                st.download_button("📂 DOWNLOAD ZIP ARCHIVE", data=zip_buffer.getvalue(), 
                                   file_name=f"{sanitize(project_name)}.zip", mime="application/zip")

with tab_lib:
    st.write("### Museum Standards Library")
    st.caption("Edit individual format 'DNA' here. These values are used when Global Override is OFF.")
    
    for idx, spec in enumerate(st.session_state.specs):
        with st.expander(f"✎ {spec['category']}: {spec['label']}"):
            c1, c2, c3 = st.columns(3)
            l = c1.text_input("Label", spec['label'], key=f"edit_l_{idx}")
            w = c2.number_input("Width", value=int(spec['width']), key=f"edit_w_{idx}")
            h = c3.number_input("Height", value=int(spec['height']), key=f"edit_h_{idx}")
            
            c4, c5 = st.columns(2)
            e = c4.selectbox("Default Format", ["WebP", "JPEG"], index=0 if spec.get('ext', 'WebP') == "WebP" else 1, key=f"edit_e_{idx}")
            q = c5.slider("Default Quality", 10, 100, spec.get('quality', 80), key=f"edit_q_{idx}")
            
            if st.button("Save Changes", key=f"upd_{idx}"):
                st.session_state.specs[idx].update({
                    "label": l, "width": int(w), "height": int(h), 
                    "ext": e, "quality": q, "ratio": calculate_ratio(int(w), int(h))
                })
                st.rerun()
            if st.button("Remove Format", key=f"del_{idx}", type="secondary"):
                st.session_state.specs.pop(idx)
                st.rerun()
    
    st.divider()
    with st.form("new_standard"):
        st.write("#### Add New Permanent Format")
        nc1, nc2, nc3 = st.columns(3)
        n_cat = nc1.selectbox("Category", ["SOCIAL", "WEB", "EMAIL"])
        n_lab = nc2.text_input("Format Name")
        n_ext = nc3.selectbox("File Type", ["WebP", "JPEG"])
        nc4, nc5, nc6 = st.columns(3)
        n_w = nc4.number_input("Width", 1080)
        n_h = nc5.number_input("Height", 1080)
        n_q = nc6.slider("Quality", 10, 100, 85)
        if st.form_submit_button("ADD TO SYSTEM"):
            st.session_state.specs.append({
                "category": n_cat, "label": n_lab, "width": int(n_w), "height": int(n_h),
                "ratio": calculate_ratio(int(n_w), int(n_h)), "ext": n_ext, "quality": n_q
            })
            st.rerun()
