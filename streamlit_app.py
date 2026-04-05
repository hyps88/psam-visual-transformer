import streamlit as st
from PIL import Image, ImageOps, ImageDraw
import json, os, math, re, io, zipfile
from datetime import datetime

# --- CONFIG & STYLING ---
ACCENT_COLOR = "#f36e2e"
st.markdown(f"""
    <style>
    .stApp {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }}
    .stButton>button {{ background-color: {ACCENT_COLOR}; color: white; border-radius: 8px; height: 3em; width: 100%; font-weight: bold; }}
    .stCheckbox [data-testid="stMarkdownContainer"] {{ font-size: 14px; }}
    h1, h2, h3 {{ color: white !important; font-family: 'Helvetica Neue', Helvetica, sans-serif; }}
    </style>
""", unsafe_allow_html=True)

# --- MATH & UTILITY ---
def calculate_ratio(w, h):
    gcd = math.gcd(w, h)
    return f"{w//gcd}:{h//gcd}"

def sanitize_filename(name):
    return re.sub(r'[^a-zA-Z0-9]', '_', name)

def get_ratio_svg(ratio_str):
    """ Generates a small visual rectangle for the UI """
    try:
        r_w, r_h = map(int, ratio_str.split(":"))
        # Scale for 50px box
        max_dim = 40
        if r_w > r_h:
            w, h = max_dim, int(max_dim * (r_h / r_w))
        else:
            h, w = max_dim, int(max_dim * (r_w / r_h))
        return f'<svg width="50" height="50"><rect x="{(50-w)/2}" y="{(50-h)/2}" width="{w}" height="{h}" fill="none" stroke="{ACCENT_COLOR}" stroke-width="2"/></svg>'
    except: return ""

# --- SESSION STATE MANAGEMENT ---
if 'specs' not in st.session_state:
    if os.path.exists("transformer_specs.json"):
        with open("transformer_specs.json", "r") as f:
            st.session_state.specs = json.load(f)['formats']
    else:
        st.session_state.specs = []

# --- SIDEBAR: INPUT & SETTINGS ---
st.sidebar.title("VISUAL TRANSFORMER")
st.sidebar.caption("PSAM COMMAND CENTER // 2026")

# Bulk Upload
uploaded_files = st.sidebar.file_uploader("IMPORT MASTER IMAGES", type=['jpg', 'jpeg', 'png', 'webp'], accept_multiple_files=True)

project_name = st.sidebar.text_input("PROJECT NAME", value="PSAM_Marketing_Batch")

st.sidebar.divider()
st.sidebar.subheader("SQUOOSH SETTINGS")
global_quality = st.sidebar.slider("GLOBAL QUALITY OVERRIDE", 10, 100, 80)
resampling_method = st.sidebar.selectbox("RESAMPLING ENGINE", ["LANCZOS (High Quality)", "BILINEAR (Fast)", "BICUBIC (Smooth)"])

# --- MAIN INTERFACE ---
tab_main, tab_manage = st.tabs(["TRANSFORMER", "MANAGE FORMATS"])

with tab_main:
    if not uploaded_files:
        st.info("Please upload one or more master images in the sidebar to begin.")
    else:
        st.write(f"### Select Target Formats")
        cols = st.columns(3)
        categories = ["SOCIAL", "WEB", "EMAIL"]
        selected_formats = []

        for i, cat in enumerate(categories):
            with cols[i]:
                st.markdown(f"#### {cat}")
                cat_specs = [s for s in st.session_state.specs if s['category'] == cat]
                for spec in cat_specs:
                    col_icon, col_check = st.columns([1, 4])
                    with col_icon:
                        st.markdown(get_ratio_icon_svg(spec['ratio']), unsafe_allow_html=True)
                    with col_check:
                        if st.checkbox(f"{spec['label']} ({spec['width']}x{spec['height']})", value=True, key=f"chk_{spec['label']}"):
                            selected_formats.append(spec)

        if st.button("🚀 GENERATE ALL ASSETS"):
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for uploaded_file in uploaded_files:
                    img = Image.open(uploaded_file)
                    if img.mode != 'RGB': img = img.convert('RGB')
                    
                    orig_name = os.path.splitext(uploaded_file.name)[0]
                    
                    for spec in selected_formats:
                        # Smart-Crop Logic
                        res = ImageOps.fit(img, (spec['width'], spec['height']), Image.Resampling.LANCZOS)
                        
                        safe_label = sanitize_filename(spec['label'])
                        f_name = f"{orig_name}_{safe_label}.{spec['ext'].lower()}"
                        
                        img_io = io.BytesIO()
                        # Use global quality override if set
                        quality = global_quality if global_quality != 80 else spec['quality']
                        
                        if spec['ext'].upper() == "JPEG":
                            res.convert("RGB").save(img_io, "JPEG", quality=quality)
                        else:
                            res.save(img_io, "WEBP", quality=quality)
                        
                        zip_file.writestr(f"{orig_name}/{f_name}", img_io.getvalue())
            
            st.success(f"Processing Complete! Generated {len(uploaded_files) * len(selected_formats)} images.")
            st.download_button(
                label="📂 DOWNLOAD ZIP ARCHIVE",
                data=zip_buffer.getvalue(),
                file_name=f"{sanitize_filename(project_name)}_{datetime.now().strftime('%H%M')}.zip",
                mime="application/zip"
            )

with tab_manage:
    st.write("### Format Library")
    # CRUD Operations
    for idx, spec in enumerate(st.session_state.specs):
        with st.expander(f"{spec['category']}: {spec['label']} ({spec['ratio']})"):
            c1, c2, c3, c4 = st.columns(4)
            new_label = c1.text_input("Label", spec['label'], key=f"l_{idx}")
            new_w = c2.number_input("Width", value=spec['width'], key=f"w_{idx}")
            new_h = c3.number_input("Height", value=spec['height'], key=f"h_{idx}")
            new_ext = c4.selectbox("Format", ["WebP", "JPEG"], index=0 if spec['ext'] == "WebP" else 1, key=f"e_{idx}")
            
            if st.button("Update", key=f"upd_{idx}"):
                st.session_state.specs[idx].update({
                    "label": new_label, "width": new_w, "height": new_h, 
                    "ext": new_ext, "ratio": calculate_ratio(new_w, new_h)
                })
                st.rerun()
            if st.button("Delete", key=f"del_{idx}", type="secondary"):
                st.session_state.specs.pop(idx)
                st.rerun()

    st.divider()
    st.write("### Add New Format")
    with st.form("new_spec"):
        nc1, nc2, nc3 = st.columns(3)
        n_cat = nc1.selectbox("Category", ["SOCIAL", "WEB", "EMAIL"])
        n_lab = nc2.text_input("Label")
        n_ext = nc3.selectbox("Format", ["WebP", "JPEG"])
        nc4, nc5, nc6 = st.columns(3)
        n_w = nc4.number_input("Width", value=1080)
        n_h = nc5.number_input("Height", value=1080)
        n_q = nc6.slider("Default Quality", 10, 100, 75)
        
        if st.form_submit_button("➕ ADD TO LIBRARY"):
            st.session_state.specs.append({
                "category": n_cat, "label": n_lab, "width": int(n_w), "height": int(n_h),
                "ratio": calculate_ratio(int(n_w), int(n_h)), "ext": n_ext, "quality": n_q
            })
            st.rerun()
