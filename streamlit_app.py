import streamlit as st
from PIL import Image, ImageOps
import json, os, math, re, io, zipfile
from datetime import datetime

# --- 1. SETTINGS & THEME ---
ACCENT_COLOR = "#f36e2e"
st.set_page_config(page_title="Visual Transformer", page_icon="🖼️", layout="wide")

def save_specs_to_disk():
    """ Keeps your museum standards persistent across refreshes """
    with open("transformer_specs.json", "w") as f:
        json.dump({"formats": st.session_state.specs}, f, indent=4)

st.markdown(f"""
    <style>
    .stApp {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #0e1117; }}
    
    /* Category Headers: Clean & High-End */
    .cat-header {{
        font-size: 13px;
        font-weight: 800;
        color: #555;
        letter-spacing: 3px;
        margin-top: 40px !important;
        margin-bottom: 20px !important;
        text-transform: uppercase;
        border-bottom: 1px solid #222;
        padding-bottom: 8px;
    }}

    /* Action Buttons */
    .stButton>button {{
        background-color: {ACCENT_COLOR};
        color: white;
        border-radius: 6px;
        border: none;
        font-weight: bold;
        transition: 0.2s;
    }}
    
    .mgmt-btn button {{
        padding: 0px 20px !important;
        height: 2.2em !important;
        width: auto !important;
        font-size: 13px !important;
    }}
    
    .remove-btn button {{
        background-color: transparent !important;
        border: 1px solid #444 !important;
        color: #DA3633 !important;
    }}

    /* Main File Uploader Polish */
    [data-testid="stFileUploader"] {{
        background-color: #1a1c1e;
        padding: 20px;
        border-radius: 15px;
        border: 2px dashed #333;
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
    else: st.session_state.specs = []

# --- 4. TOP-LEVEL INPUTS (REPLACED SIDEBAR) ---
st.title("VISUAL TRANSFORMER")
uploaded_files = st.file_uploader("DRAG & DROP MASTER IMAGES FOR BATCH PROCESSING", type=['jpg', 'png', 'webp'], accept_multiple_files=True)

pcol1, pcol2 = st.columns([1, 2])
with pcol1:
    project_name = st.text_input("PROJECT NAME", value="PSAM_Export")

st.divider()

# --- 5. MAIN UI TABS ---
tab_run, tab_lib = st.tabs(["TRANSFORMER", "LIBRARY MANAGEMENT"])

with tab_run:
    if not uploaded_files:
        st.info("Upload images above to begin generating museum assets.")
    else:
        # Quick Selection Tools
        t_col1, t_col2, _ = st.columns([1, 1, 5])
        if t_col1.button("SELECT ALL"): 
            st.session_state.update({f"run_{s['label']}": True for s in st.session_state.specs}); st.rerun()
        if t_col2.button("SELECT NONE"): 
            st.session_state.update({f"run_{s['label']}": False for s in st.session_state.specs}); st.rerun()

        st.write(" ")
        mcol1, mcol2, mcol3 = st.columns(3)
        cats = {"SOCIAL": mcol1, "WEB": mcol2, "EMAIL": mcol3}
        selected_formats = []

        for category, col in cats.items():
            with col:
                st.markdown(f'<p class="cat-header">{category}</p>', unsafe_allow_html=True)
                cat_specs = [s for s in st.session_state.specs if s['category'] == category]
                
                for spec in cat_specs:
                    with st.container(border=True):
                        c_icon, c_check = st.columns([1, 4])
                        with c_icon:
                            st.markdown(get_svg_rect(spec['ratio']), unsafe_allow_html=True)
                        with c_check:
                            # Respecting individual format compression
                            if st.checkbox(f"{spec['label']} ({spec['width']}x{spec['height']})", value=True, key=f"run_{spec['label']}"):
                                selected_formats.append(spec)
                            st.markdown(f'<span style="color: #666; font-size: 11px;">{spec.get("ext", "WebP").upper()} @ {spec.get("quality", 85)}% Quality</span>', unsafe_allow_html=True)

        st.divider()
        # Full-width Generation Button
        if st.button("🚀 GENERATE ALL BATCH ASSETS", use_container_width=True):
            if selected_formats:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                    for up_file in uploaded_files:
                        img = Image.open(up_file).convert("RGB")
                        base_n = sanitize(os.path.splitext(up_file.name)[0])
                        for spec in selected_formats:
                            # Highest quality resampling locked
                            res = ImageOps.fit(img, (spec['width'], spec['height']), Image.Resampling.LANCZOS)
                            f_ext = spec.get('ext', 'WebP').upper()
                            f_name = f"PSAM_{sanitize(spec['label'])}.{f_ext.lower()}"
                            
                            img_io = io.BytesIO()
                            res.save(img_io, format=f_ext, quality=spec.get('quality', 85))
                            zip_file.writestr(f"{base_n}/{f_name}", img_io.getvalue())
                
                st.success(f"Batch Ready: {len(uploaded_files)} images processed.")
                st.download_button("📂 DOWNLOAD ZIP ARCHIVE", data=zip_buffer.getvalue(), file_name=f"{sanitize(project_name)}.zip", mime="application/zip")

with tab_lib:
    st.write("### Museum Standards Library")
    for idx, spec in enumerate(st.session_state.specs):
        with st.expander(f"✎ {spec['category']}: {spec['label']}"):
            l = st.text_input("Label", spec['label'], key=f"edit_l_{idx}")
            c1, c2 = st.columns(2)
            w = c1.number_input("Width", value=int(spec['width']), key=f"edit_w_{idx}")
            h = c2.number_input("Height", value=int(spec['height']), key=f"edit_h_{idx}")
            c3, c4 = st.columns(2)
            e = c3.selectbox("File Format", ["WebP", "JPEG"], index=0 if spec.get('ext', 'WebP') == "WebP" else 1, key=f"edit_e_{idx}")
            q = c4.slider("Compression Quality", 10, 100, spec.get('quality', 85), key=f"edit_q_{idx}")
            
            btn_row = st.columns([1, 1, 3]) 
            with btn_row[0]:
                st.markdown('<div class="mgmt-btn">', unsafe_allow_html=True)
                if st.button("Save Changes", key=f"upd_{idx}"):
                    st.session_state.specs[idx].update({"label": l, "width": int(w), "height": int(h), "ext": e, "quality": q, "ratio": calculate_ratio(int(w), int(h))})
                    save_specs_to_disk(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            with btn_row[1]:
                st.markdown('<div class="mgmt-btn remove-btn">', unsafe_allow_html=True)
                if st.button("Remove Format", key=f"del_{idx}"):
                    st.session_state.specs.pop(idx); save_specs_to_disk(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
    
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
            st.session_state.specs.append({"category": n_cat, "label": n_lab, "width": int(n_w), "height": int(n_h), "ratio": calculate_ratio(int(n_w), int(n_h)), "ext": n_ext, "quality": n_q})
            save_specs_to_disk(); st.rerun()
