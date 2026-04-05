import streamlit as st
from PIL import Image, ImageOps, ImageDraw
import json, os, math, re, io, zipfile
from datetime import datetime

# --- CONFIG & DYNAMIC STYLING ---
ACCENT_COLOR = "#f36e2e"
BG_CARD = "#1e1e1e"
BG_SELECTED = "#2d2d2d"

st.set_page_config(page_title="Visual Transformer", page_icon="🖼️", layout="wide")

# Custom CSS to make buttons look like large Sleek Tiles
st.markdown(f"""
    <style>
    .stApp {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #0e1117; }}
    
    /* Center the titles and add breathing room */
    h4 {{ 
        margin-bottom: 25px !important; 
        letter-spacing: 1px; 
        border-left: 3px solid {ACCENT_COLOR}; 
        padding-left: 15px; 
    }}

    /* Tile Button Styling */
    div.stButton > button {{
        width: 100%;
        border-radius: 12px;
        padding: 40px 20px !important;
        background-color: {BG_CARD};
        border: 1px solid #333;
        transition: all 0.3s ease;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        margin-bottom: 10px;
    }}

    div.stButton > button:hover {{
        border-color: {ACCENT_COLOR};
        background-color: #252525;
    }}
    
    /* Responsive Spacing */
    [data-testid="column"] {{ padding: 0 25px !important; }}
    </style>
""", unsafe_allow_html=True)

# --- MATH & UTILITY ---
def calculate_ratio(w, h):
    gcd = math.gcd(w, h)
    return f"{w//gcd}:{h//gcd}"

def sanitize_filename(name):
    return re.sub(r'[^a-zA-Z0-9]', '_', name)

def get_ratio_icon_svg(ratio_str, active=False):
    """ Generates the visual rectangle with state-aware coloring """
    color = ACCENT_COLOR if active else "#555"
    try:
        r_w, r_h = map(int, ratio_str.split(":"))
        max_dim = 40
        if r_w > r_h: w, h = max_dim, int(max_dim * (r_h / r_w))
        else: h, w = max_dim, int(max_dim * (r_w / r_h))
        return f'<svg width="50" height="50"><rect x="{(50-w)/2}" y="{(50-h)/2}" width="{w}" height="{h}" fill="none" stroke="{color}" stroke-width="2.5"/></svg>'
    except: return ""

# --- SESSION STATE ---
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
resampling_map = {"LANCZOS (High Quality)": Image.Resampling.LANCZOS, "BILINEAR (Fast)": Image.Resampling.BILINEAR, "BICUBIC (Smooth)": Image.Resampling.BICUBIC}
resampling_choice = st.sidebar.selectbox("ENGINE", list(resampling_map.keys()))

# --- MAIN INTERFACE ---
tab_main, tab_manage = st.tabs(["TRANSFORMER", "MANAGE LIBRARY"])

with tab_main:
    if not uploaded_files:
        st.info("Import images in the sidebar to begin processing.")
    else:
        # Selection Tools
        bcol1, bcol2, _ = st.columns([1, 1, 4])
        if bcol1.button("SELECT ALL"): 
            st.session_state.selected_indices = {i for i in range(len(st.session_state.specs))}; st.rerun()
        if bcol2.button("DESELECT ALL"): 
            st.session_state.selected_indices = set(); st.rerun()

        st.write(" ") 

        # Format Grid
        mcol1, mcol2, mcol3 = st.columns(3)
        categories = ["SOCIAL", "WEB", "EMAIL"]
        cat_columns = {"SOCIAL": mcol1, "WEB": mcol2, "EMAIL": mcol3}

        for cat in categories:
            with cat_columns[cat]:
                st.markdown(f"#### {cat}")
                for idx, spec in enumerate(st.session_state.specs):
                    if spec['category'] == cat:
                        is_selected = idx in st.session_state.selected_indices
                        
                        # Visual Presentation Card
                        border_style = f"2px solid {ACCENT_COLOR}" if is_selected else "1px solid #333"
                        bg_style = BG_SELECTED if is_selected else BG_CARD
                        
                        st.markdown(f"""
                            <div style="background: {bg_style}; border: {border_style}; padding: 20px; border-radius: 12px; display: flex; align-items: center; margin-bottom: 10px;">
                                <div style="margin-right: 20px;">{get_ratio_icon_svg(spec['ratio'], is_selected)}</div>
                                <div style="color: white;">
                                    <div style="font-weight: bold; font-size: 15px;">{spec['label']}</div>
                                    <div style="color: #888; font-size: 12px;">{spec['width']} x {spec['height']}</div>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        # The invisible "Action" button
                        if st.button("✓ SELECTED" if is_selected else "SELECT", key=f"btn_{idx}"):
                            if is_selected: st.session_state.selected_indices.remove(idx)
                            else: st.session_state.selected_indices.add(idx)
                            st.rerun()

        st.divider()
        if st.button("🚀 GENERATE ALL BATCH ASSETS", use_container_width=True):
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                progress_text = st.empty()
                progress_bar = st.progress(0)
                
                for f_idx, uploaded_file in enumerate(uploaded_files):
                    img = Image.open(uploaded_file)
                    if img.mode != 'RGB': img = img.convert('RGB')
                    orig_name = sanitize_filename(os.path.splitext(uploaded_file.name)[0])
                    progress_text.text(f"Processing: {orig_name}...")

                    for s_idx in st.session_state.selected_indices:
                        spec = st.session_state.specs[s_idx]
                        res = ImageOps.fit(img, (spec['width'], spec['height']), resampling_map[resampling_choice])
                        
                        safe_label = sanitize_filename(spec['label'])
                        f_name = f"PSAM_{safe_label}.{spec['ext'].lower()}"
                        
                        img_io = io.BytesIO()
                        res.save(img_io, spec['ext'].upper(), quality=global_quality)
                        zip_file.writestr(f"{orig_name}/{f_name}", img_io.getvalue())
                    
                    progress_bar.progress((f_idx + 1) / len(uploaded_files))
            
            st.success(f"Batch Complete: {len(uploaded_files) * len(st.session_state.selected_indices)} assets created.")
            st.download_button(
                label="📂 DOWNLOAD ZIP ARCHIVE",
                data=zip_buffer.getvalue(),
                file_name=f"{sanitize_filename(project_name)}_{datetime.now().strftime('%Y%m%d')}.zip",
                mime="application/zip"
            )

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

    st.divider()
    with st.form("add_new"):
        st.write("#### Add New Standard")
        nc1, nc2, nc3 = st.columns(3)
        n_cat = nc1.selectbox("Category", ["SOCIAL", "WEB", "EMAIL"])
        n_lab = nc2.text_input("Format Name")
        n_ext = nc3.selectbox("File Type", ["WebP", "JPEG"])
        nc4, nc5 = st.columns(2)
        n_w = nc4.number_input("Width (px)", value=1080)
        n_h = nc5.number_input("Height (px)", value=1080)
        if st.form_submit_button("ADD TO SYSTEM"):
            st.session_state.specs.append({"category": n_cat, "label": n_lab, "width": int(n_w), "height": int(n_h), "ratio": calculate_ratio(int(n_w), int(n_h)), "ext": n_ext, "quality": 85})
            st.rerun()
