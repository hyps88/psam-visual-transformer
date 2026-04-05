import streamlit as st
from PIL import Image, ImageOps
import json, os, math, re, io, zipfile, base64
from datetime import datetime

# --- CONFIG & STYLING ---
ACCENT_COLOR = "#f36e2e"       # PSAM Orange
SECONDARY_BORDER = "#444444"    # Muted Grey for unselected
BG_CARD = "#1a1c1e"
BG_ACTIVE = "#25282c"

st.set_page_config(page_title="Visual Transformer", page_icon="🖼️", layout="wide")

# --- CSS: THE "SOLID TILE" ENGINE ---
def inject_css():
    st.markdown(f"""
        <style>
        .stApp {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #0e1117; }}
        
        /* Category Headers: Pro Gallery Spacing */
        .category-header {{
            font-size: 14px;
            font-weight: 800;
            color: #666 !important;
            letter-spacing: 4px;
            margin-top: 100px !important; 
            margin-bottom: 40px !important;
            text-transform: uppercase;
            border-bottom: 1px solid #222;
            padding-bottom: 10px;
        }}

        /* The Button-as-a-Card */
        div.stButton > button {{
            width: 100% !important;
            height: 130px !important;
            background-color: {BG_CARD} !important;
            border: 1px solid {SECONDARY_BORDER} !important;
            border-radius: 14px !important;
            color: white !important;
            padding-left: 90px !important; /* Space for the background icon */
            text-align: left !important;
            display: block !important;
            transition: all 0.2s ease-in-out !important;
            white-space: pre-wrap !important; /* Allows \n for title/size split */
            font-size: 20px !important;
            font-weight: 700 !important;
            line-height: 1.2 !important;
        }}

        /* Icon background injection */
        .tile-active button {{
            border: 2px solid {ACCENT_COLOR} !important;
            background-color: {BG_ACTIVE} !important;
            box-shadow: 0 4px 20px {ACCENT_COLOR}15 !important;
        }}

        div.stButton > button:hover {{
            border-color: {ACCENT_COLOR}88 !important;
            background-color: #222 !important;
        }}

        /* Utility Buttons (Select All/None) */
        .utility-btn button {{
            height: 2.5em !important;
            padding: 0 15px !important;
            font-size: 12px !important;
            background: transparent !important;
            color: #777 !important;
            border: 1px solid #333 !important;
        }}
        .utility-btn button:hover {{ border-color: white !important; color: white !important; }}
        </style>
    """, unsafe_allow_html=True)

# --- UTILITIES ---
def calculate_ratio(w, h):
    gcd = math.gcd(w, h)
    return f"{w//gcd}:{h//gcd}"

def sanitize_filename(name):
    return re.sub(r'[^a-zA-Z0-9]', '_', name)

def get_base64_svg(ratio_str, active=False):
    """ Encodes SVG for button background """
    color = ACCENT_COLOR if active else "#555"
    try:
        r_w, r_h = map(int, ratio_str.split(":"))
        max_dim = 35
        w, h = (max_dim, int(max_dim * (r_h / r_w))) if r_w > r_h else (int(max_dim * (r_w / r_h)), max_dim)
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50">
                  <rect x="{(50-w)/2}" y="{(50-h)/2}" width="{w}" height="{h}" fill="none" stroke="{color}" stroke-width="2.5"/>
                  </svg>'''
        return base64.b64encode(svg.encode()).decode()
    except: return ""

# --- APP START ---
inject_css()

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
        st.info("Import images in the sidebar to visualize assets.")
    else:
        # 1. Selection Tools
        tcol1, tcol2, _ = st.columns([1, 1, 6])
        with tcol1:
            st.markdown('<div class="utility-btn">', unsafe_allow_html=True)
            if st.button("SELECT ALL", key="all"): 
                st.session_state.selected_indices = {i for i in range(len(st.session_state.specs))}; st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        with tcol2:
            st.markdown('<div class="utility-btn">', unsafe_allow_html=True)
            if st.button("SELECT NONE", key="none"): 
                st.session_state.selected_indices = set(); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        # 2. Format Columns
        mcol1, mcol2, mcol3 = st.columns(3)
        cats = ["SOCIAL", "WEB", "EMAIL"]
        cat_cols = {"SOCIAL": mcol1, "WEB": mcol2, "EMAIL": mcol3}

        for cat in cats:
            with cat_cols[cat]:
                st.markdown(f'<p class="category-header">{cat}</p>', unsafe_allow_html=True)
                
                for idx, spec in enumerate(st.session_state.specs):
                    if spec['category'] == cat:
                        active = idx in st.session_state.selected_indices
                        icon_b64 = get_base64_svg(spec['ratio'], active)
                        
                        # Style the specific button with its icon background
                        st.markdown(f"""
                            <style>
                            div.stButton:has(button[key="tile_{idx}"]) button {{
                                background-image: url(data:image/svg+xml;base64,{icon_b64}) !important;
                                background-repeat: no-repeat !important;
                                background-position: 25px center !important;
                                background-size: 45px 45px !important;
                            }}
                            </style>
                        """, unsafe_allow_html=True)
                        
                        # Wrapper for Active Glow
                        st.markdown(f'<div class="{"tile-active" if active else ""}">', unsafe_allow_html=True)
                        
                        # The "Solid" clickable button
                        # We use \n for a clean title/subtitle split inside the button
                        label_text = f"{spec['label']}\n{spec['width']}x{spec['height']}"
                        if st.button(label_text, key=f"tile_{idx}"):
                            if active: st.session_state.selected_indices.remove(idx)
                            else: st.session_state.selected_indices.add(idx)
                            st.rerun()
                        
                        st.markdown('</div>', unsafe_allow_html=True)

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
            
            st.success("Batch Complete!")
            st.download_button(label="📂 DOWNLOAD ZIP", data=zip_buffer.getvalue(), 
                               file_name=f"{sanitize_filename(project_name)}.zip", mime="application/zip")

with tab_manage:
    st.write("### Library Management")
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
