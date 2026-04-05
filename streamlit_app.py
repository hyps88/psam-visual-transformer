import streamlit as st
from PIL import Image, ImageOps
import json, os, math, re, io, zipfile
from datetime import datetime

# --- CONFIG & STYLING ---
ACCENT_COLOR = "#f36e2e"
BG_CARD = "#1a1c1e"

st.set_page_config(page_title="Visual Transformer", page_icon="🖼️", layout="wide")

st.markdown(f"""
    <style>
    /* Global Styles */
    .stApp {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #0e1117; }}
    
    /* Category Headers: Extreme Padding for Clearness */
    .category-header {{
        font-size: 13px;
        font-weight: 800;
        color: #555 !important;
        letter-spacing: 3px;
        margin-top: 100px !important; 
        margin-bottom: 40px !important;
        text-transform: uppercase;
        border-bottom: 1px solid #222;
        padding-bottom: 10px;
    }}

    /* The Interactive Tile */
    .tile-container {{
        background-color: {BG_CARD};
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 15px;
        display: flex;
        align-items: center;
        border: 1px solid #2b2b2b;
        transition: all 0.2s ease;
    }}
    
    .tile-active {{
        border: 2px solid {ACCENT_COLOR} !important;
        background-color: #25282c !important;
    }}

    /* Sidebar Cleanliness */
    section[data-testid="stSidebar"] {{ background-color: #121212; }}
    
    /* Button Polish */
    div.stButton > button {{
        border-radius: 8px;
        height: 3em;
        font-weight: 600;
        transition: 0.2s;
    }}
    </style>
""", unsafe_allow_html=True)

# --- UTILITIES ---
def calculate_ratio(w, h):
    gcd = math.gcd(w, h)
    return f"{w//gcd}:{h//gcd}"

def sanitize_filename(name):
    return re.sub(r'[^a-zA-Z0-9]', '_', name)

def get_ratio_svg(ratio_str, active=False):
    """ Standard SVG Rectangle """
    color = ACCENT_COLOR if active else "#444"
    try:
        r_w, r_h = map(int, ratio_str.split(":"))
        max_dim = 35
        if r_w > r_h: w, h = max_dim, int(max_dim * (r_h / r_w))
        else: h, w = max_dim, int(max_dim * (r_w / r_h))
        return f'<svg width="45" height="45"><rect x="{(45-w)/2}" y="{(45-h)/2}" width="{w}" height="{h}" fill="none" stroke="{color}" stroke-width="2"/></svg>'
    except: return ""

# --- DATA ---
if 'specs' not in st.session_state:
    if os.path.exists("transformer_specs.json"):
        with open("transformer_specs.json", "r") as f: st.session_state.specs = json.load(f)['formats']
    else: st.session_state.specs = []

if 'selected_indices' not in st.session_state:
    st.session_state.selected_indices = {i for i in range(len(st.session_state.specs))}

# --- SIDEBAR ---
st.sidebar.title("VISUAL TRANSFORMER")
uploaded_files = st.sidebar.file_uploader("BATCH IMPORT", type=['jpg', 'jpeg', 'png', 'webp'], accept_multiple_files=True)
project_name = st.sidebar.text_input("PROJECT NAME", value="PSAM_Batch")

st.sidebar.divider()
st.sidebar.subheader("Compression Settings")
global_quality = st.sidebar.slider("QUALITY", 10, 100, 85)
resampling_choice = st.sidebar.selectbox("ENGINE", ["LANCZOS (High Quality)", "BILINEAR (Fast)", "BICUBIC (Smooth)"])

# --- MAIN ---
tab_main, tab_manage = st.tabs(["TRANSFORMER", "MANAGE LIBRARY"])

with tab_main:
    if not uploaded_files:
        st.info("Import images in the sidebar to begin.")
    else:
        # Selection Tools
        col_a, col_b, _ = st.columns([1, 1, 5])
        if col_a.button("SELECT ALL"): 
            st.session_state.selected_indices = {i for i in range(len(st.session_state.specs))}; st.rerun()
        if col_b.button("DESELECT ALL"): 
            st.session_state.selected_indices = set(); st.rerun()

        mcol1, mcol2, mcol3 = st.columns(3)
        cats = ["SOCIAL", "WEB", "EMAIL"]
        cat_cols = {"SOCIAL": mcol1, "WEB": mcol2, "EMAIL": mcol3}

        for cat in cats:
            with cat_cols[cat]:
                st.markdown(f'<p class="category-header">{cat}</p>', unsafe_allow_html=True)
                
                for idx, spec in enumerate(st.session_state.specs):
                    if spec['category'] == cat:
                        active = idx in st.session_state.selected_indices
                        
                        # Tile Rendering
                        card_class = "tile-container tile-active" if active else "tile-container"
                        st.markdown(f"""
                            <div class="{card_class}">
                                <div style="margin-right: 20px;">{get_ratio_svg(spec['ratio'], active)}</div>
                                <div style="flex-grow: 1;">
                                    <div style="font-weight: 700; color: white; font-size: 15px;">{spec['label']}</div>
                                    <div style="color: #666; font-size: 12px;">{spec['width']} x {spec['height']}</div>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)

                        # The Clickable Action
                        if st.button("✓ SELECTED" if active else "SELECT", key=f"btn_{idx}", use_container_width=True):
                            if active: st.session_state.selected_indices.remove(idx)
                            else: st.session_state.selected_indices.add(idx)
                            st.rerun()
                        st.write("") # Spacer

        st.divider()
        if st.button("🚀 GENERATE ALL BATCH ASSETS", use_container_width=True):
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for f_idx, uploaded_file in enumerate(uploaded_files):
                    img = Image.open(uploaded_file)
                    if img.mode != 'RGB': img = img.convert('RGB')
                    orig_name = sanitize_filename(os.path.splitext(uploaded_file.name)[0])
                    for s_idx in st.session_state.selected_indices:
                        spec = st.session_state.specs[s_idx]
                        res = ImageOps.fit(img, (spec['width'], spec['height']), Image.Resampling.LANCZOS)
                        f_name = f"PSAM_{sanitize_filename(spec['label'])}.{spec['ext'].lower()}"
                        img_io = io.BytesIO()
                        res.save(img_io, spec['ext'].upper(), quality=global_quality)
                        zip_file.writestr(f"{orig_name}/{f_name}", img_io.getvalue())
            
            st.success("Batch Processing Complete!")
            st.download_button(label="📂 DOWNLOAD ZIP", data=zip_buffer.getvalue(), 
                               file_name=f"{sanitize_filename(project_name)}.zip", mime="application/zip")

with tab_manage:
    st.write("### Library Management")
    # (Management code remains standard for safety)
    for idx, spec in enumerate(st.session_state.specs):
        with st.expander(f"✎ {spec['category']}: {spec['label']}"):
            c1, c2, c3, c4 = st.columns(4)
            new_label = c1.text_input("Label", spec['label'], key=f"edit_l_{idx}")
            new_w = c2.number_input("Width", value=int(spec['width']), key=f"edit_w_{idx}")
            new_h = c3.number_input("Height", value=int(spec['height']), key=f"edit_h_{idx}")
            new_ext = c4.selectbox("Format", ["WebP", "JPEG"], index=0 if spec['ext'] == "WebP" else 1, key=f"edit_e_{idx}")
            if st.button("Save Changes", key=f"save_{idx}"):
                st.session_state.specs[idx].update({"label": new_label, "width": int(new_w), "height": int(new_h), "ext": new_ext, "ratio": calculate_ratio(int(new_w), int(new_h))})
                st.rerun()
            if st.button("Remove Format", key=f"del_{idx}"):
                st.session_state.specs.pop(idx); st.rerun()
