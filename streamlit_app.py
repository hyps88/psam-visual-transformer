import streamlit as st
from PIL import Image, ImageOps
import json, os, math, re, io, zipfile
from datetime import datetime

# --- 1. SETTINGS & THEME ---
ACCENT_COLOR = "#f36e2e"
st.set_page_config(page_title="PSAM Visual Transformer", page_icon="🖼️", layout="wide")

st.markdown(f"""
    <style>
    .stApp {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }}
    
    /* Category Headers: Clean & Spacious */
    .cat-header {{
        font-size: 14px;
        font-weight: 800;
        color: #666;
        letter-spacing: 3px;
        margin-top: 60px !important;
        margin-bottom: 20px;
        text-transform: uppercase;
        border-bottom: 1px solid #333;
        padding-bottom: 8px;
    }}

    /* Format Card: Simple & Robust */
    .format-card {{
        background-color: #1a1c1e;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        border: 1px solid #2b2b2b;
    }}

    /* PSAM Button Style */
    .stButton>button {{
        background-color: {ACCENT_COLOR};
        color: white;
        border-radius: 8px;
        border: none;
        font-weight: bold;
    }}
    </style>
""", unsafe_allow_html=True)

# --- 2. HELPERS ---
def calculate_ratio(w, h):
    gcd = math.gcd(w, h)
    return f"{w//gcd}:{h//gcd}"

def sanitize(name):
    return re.sub(r'[^a-zA-Z0-9]', '_', name)

def get_svg_rect(ratio_str):
    """ Simple SVG rectangle indicator """
    try:
        r_w, r_h = map(int, ratio_str.split(":"))
        max_d = 30
        w, h = (max_d, int(max_d*(r_h/r_w))) if r_w > r_h else (int(max_d*(r_w/r_h)), max_d)
        return f'<svg width="40" height="40"><rect x="{(40-w)/2}" y="{(40-h)/2}" width="{w}" height="{h}" fill="none" stroke="{ACCENT_COLOR}" stroke-width="2"/></svg>'
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
st.sidebar.subheader("Compression Settings")
quality = st.sidebar.slider("QUALITY", 10, 100, 85)
engine_choice = st.sidebar.selectbox("ENGINE", ["LANCZOS (High Quality)", "BILINEAR", "BICUBIC"])
engine = Image.Resampling.LANCZOS if "LANCZOS" in engine_choice else Image.Resampling.BILINEAR

# --- 5. MAIN UI ---
tab_run, tab_lib = st.tabs(["TRANSFORMER", "LIBRARY"])

with tab_run:
    if not uploaded_files:
        st.info("Upload images in the sidebar to get started.")
    else:
        # Selection Tools
        col_a, col_b, _ = st.columns([1, 1, 5])
        # Note: Select All logic is simplified for stability
        
        st.write("### Target Formats")
        
        mcol1, mcol2, mcol3 = st.columns(3)
        cats = {"SOCIAL": mcol1, "WEB": mcol2, "EMAIL": mcol3}
        selected_formats = []

        for category, col in cats.items():
            with col:
                st.markdown(f'<p class="cat-header">{category}</p>', unsafe_allow_html=True)
                cat_specs = [s for s in st.session_state.specs if s['category'] == category]
                
                for spec in cat_specs:
                    # Fusing Icon and Text into the Checkbox Label
                    icon = get_svg_rect(spec['ratio'])
                    label = f"{spec['label']} ({spec['width']}x{spec['height']})"
                    
                    # Layout: Icon on left, Checkbox on right
                    c_icon, c_check = st.columns([1, 4])
                    with c_icon:
                        st.markdown(icon, unsafe_allow_html=True)
                    with c_check:
                        if st.checkbox(label, value=True, key=f"check_{spec['label']}"):
                            selected_formats.append(spec)

        st.divider()
        if st.button("🚀 GENERATE ALL ASSETS", use_container_width=True):
            if not selected_formats:
                st.warning("Please select at least one format.")
            else:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                    for up_file in uploaded_files:
                        img = Image.open(up_file).convert("RGB")
                        base_n = sanitize(os.path.splitext(up_file.name)[0])
                        
                        for spec in selected_formats:
                            res = ImageOps.fit(img, (spec['width'], spec['height']), engine)
                            f_ext = spec['ext'].lower()
                            f_name = f"PSAM_{sanitize(spec['label'])}.{f_ext}"
                            
                            img_io = io.BytesIO()
                            res.save(img_io, format=spec['ext'].upper(), quality=quality)
                            zip_file.writestr(f"{base_n}/{f_name}", img_io.getvalue())
                
                st.success(f"Processed {len(uploaded_files)} images!")
                st.download_button(
                    "📂 DOWNLOAD ZIP ARCHIVE",
                    data=zip_buffer.getvalue(),
                    file_name=f"{sanitize(project_name)}.zip",
                    mime="application/zip"
                )

with tab_lib:
    st.write("### Manage Museum Standards")
    for idx, spec in enumerate(st.session_state.specs):
        with st.expander(f"{spec['category']}: {spec['label']}"):
            c1, c2, c3 = st.columns(3)
            l = c1.text_input("Label", spec['label'], key=f"l_{idx}")
            w = c2.number_input("Width", value=int(spec['width']), key=f"w_{idx}")
            h = c3.number_input("Height", value=int(spec['height']), key=f"h_{idx}")
            
            if st.button("Update", key=f"upd_{idx}"):
                st.session_state.specs[idx].update({"label": l, "width": int(w), "height": int(h), "ratio": calculate_ratio(int(w), int(h))})
                st.rerun()
            if st.button("Delete", key=f"del_{idx}"):
                st.session_state.specs.pop(idx)
                st.rerun()
    
    st.divider()
    st.write("### Add New Format")
    with st.form("new_fmt"):
        nc1, nc2, nc3 = st.columns(3)
        cat = nc1.selectbox("Category", ["SOCIAL", "WEB", "EMAIL"])
        lab = nc2.text_input("Label (e.g. Instagram Square)")
        ext = nc3.selectbox("Format", ["JPEG", "WebP"])
        nc4, nc5 = st.columns(2)
        wid = nc4.number_input("Width", 1080)
        hei = nc5.number_input("Height", 1080)
        if st.form_submit_button("ADD TO LIBRARY"):
            st.session_state.specs.append({
                "category": cat, "label": lab, "width": int(wid), "height": int(hei),
                "ratio": calculate_ratio(int(wid), int(hei)), "ext": ext, "quality": 85
            })
            st.rerun()
