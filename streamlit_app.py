import streamlit as st
from PIL import Image, ImageOps
import json, os, math, re, io, zipfile
from datetime import datetime

# --- CONFIG & STYLING ---
ACCENT_COLOR = "#f36e2e"       # PSAM Orange
SECONDARY_BORDER = "#444444"    # Muted Grey for unselected
BG_CARD = "#1a1c1e"
BG_ACTIVE = "#25282c"

st.set_page_config(page_title="Visual Transformer", page_icon="🖼️", layout="wide")

# --- CSS: THE "SOLID TILE" ENGINE ---
st.markdown(f"""
    <style>
    .stApp {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #0e1117; }}
    
    /* Category Headers: Pro Spacing */
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

    /* Global Selection Tools */
    .selection-tool-btn button {{
        background-color: transparent !important;
        border: 1px solid #333 !important;
        color: #888 !important;
        font-size: 12px !important;
        height: 2.5em !important;
    }}
    .selection-tool-btn button:hover {{ border-color: {ACCENT_COLOR} !important; color: white !important; }}

    /* The Fused Card Logic */
    .card-container {{
        position: relative;
        margin-bottom: 15px;
        height: 120px;
    }}

    .visual-tile {{
        position: absolute;
        width: 100%;
        height: 100%;
        background-color: {BG_CARD};
        border-radius: 12px;
        border: 1px solid {SECONDARY_BORDER}; /* Secondary border as default */
        display: flex;
        align-items: center;
        padding: 0 25px;
        pointer-events: none; /* Let clicks pass through to the button */
        z-index: 1;
        transition: all 0.2s ease;
    }}

    .visual-tile.active {{
        border: 2px solid {ACCENT_COLOR} !important;
        background-color: {BG_ACTIVE};
        box-shadow: 0 4px 15px rgba(243, 110, 46, 0.15);
    }}

    .label-text {{ font-size: 20px !important; font-weight: 700; color: white; line-height: 1.1; }}
    .sublabel-text {{ font-size: 12px; color: #666; margin-top: 4px; }}

    /* The Trigger Button: Stretched to cover the tile */
    div.stButton > button {{
        position: relative;
        z-index: 5;
        width: 100% !important;
        height: 120px !important;
        background: transparent !important;
        border: none !important;
        color: transparent !important; /* Hide the label because the tile shows it */
        margin: 0 !important;
    }}
    
    div.stButton > button:hover {{ background: rgba(255,255,255,0.03) !important; }}
    div.stButton > button:active {{ transform: scale(0.98); }}
    </style>
""", unsafe_allow_html=True)

# --- UTILITIES ---
def calculate_ratio(w, h):
    gcd = math.gcd(w, h)
    return f"{w//gcd}:{h//gcd}"

def sanitize_filename(name):
    return re.sub(r'[^a-zA-Z0-9]', '_', name)

def get_ratio_svg(ratio_str, active=False):
    color = ACCENT_COLOR if active else "#555"
    try:
        r_w, r_h = map(int, ratio_str.split(":"))
        max_dim = 40
        w, h = (max_dim, int(max_dim * (r_h / r_w))) if r_w > r_h else (int(max_dim * (r_w / r_h)), max_dim)
        return f'<svg width="50" height="50"><rect x="{(50-w)/2}" y="{(50-h)/2}" width="{w}" height="{h}" fill="none" stroke="{color}" stroke-width="2.5"/></svg>'
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
        # Selection Tools with dedicated styling
        st.markdown('<div class="selection-tool-btn">', unsafe_allow_html=True)
        t_col1, t_col2, _ = st.columns([1, 1, 6])
        if t_col1.button("SELECT ALL"): 
            st.session_state.selected_indices = {i for i in range(len(st.session_state.specs))}; st.rerun()
        if t_col2.button("SELECT NONE"): 
            st.session_state.selected_indices = set(); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        mcol1, mcol2, mcol3 = st.columns(3)
        cats = ["SOCIAL", "WEB", "EMAIL"]
        cat_cols = {"SOCIAL": mcol1, "WEB": mcol2, "EMAIL": mcol3}

        for cat in cats:
            with cat_cols[cat]:
                st.markdown(f'<p class="category-header">{cat}</p>', unsafe_allow_html=True)
                
                for idx, spec in enumerate(st.session_state.specs):
                    if spec['category'] == cat:
                        active = idx in st.session_state.selected_indices
                        
                        # The Solid Tile + Ghost Button Fusion
                        st.markdown(f"""
                            <div class="card-container">
                                <div class="visual-tile {'active' if active else ''}">
                                    <div style="margin-right: 25px;">{get_ratio_svg(spec['ratio'], active)}</div>
                                    <div>
                                        <div class="label-text">{spec['label']}</div>
                                        <div class="sublabel-text">{spec['width']} x {spec['height']} ({spec['ratio']})</div>
                                    </div>
                                </div>
                        """, unsafe_allow_html=True)

                        # This button sits on top but is invisible
                        if st.button(" ", key=f"t_{idx}"):
                            if active: st.session_state.selected_indices.remove(idx)
                            else: st.session_state.selected_indices.add(idx)
                            st.rerun()
                        
                        st.markdown("</div>", unsafe_allow_html=True)

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
