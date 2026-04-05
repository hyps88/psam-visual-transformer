import streamlit as st
from PIL import Image, ImageOps
import json, os, math, re, io, zipfile
from datetime import datetime

# --- 1. SETTINGS & THEME ---
ACCENT_COLOR = "#f36e2e"
st.set_page_config(page_title="Visual Transformer", layout="wide")

def save_specs_to_disk():
    """ Keeps your museum standards persistent across refreshes """
    with open("transformer_specs.json", "w") as f:
        json.dump({"formats": st.session_state.specs}, f, indent=4)

st.markdown(f"""
    <style>
    .stApp {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #0e1117; }}
    
    /* Category Headers: Tightened Spacing */
    .cat-header {{
        font-size: 11px;
        font-weight: 800;
        color: #444;
        letter-spacing: 3px;
        margin-top: 20px !important; 
        margin-bottom: 20px !important;
        text-transform: uppercase;
    }}

    /* Minimalist Top Menu */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 40px;
        border-bottom: 1px solid #222;
        margin-bottom: 30px;
    }}
    .stTabs [data-baseweb="tab"] {{
        height: 50px;
        background-color: transparent !important;
        border: none !important;
        color: #555 !important;
        font-weight: 700;
        letter-spacing: 1px;
    }}
    .stTabs [aria-selected="true"] {{
        color: {ACCENT_COLOR} !important;
        border-bottom: 2px solid {ACCENT_COLOR} !important;
    }}

    /* Discreet Selection Tools */
    .discreet-btn button {{
        background: transparent !important;
        border: none !important;
        color: #555 !important;
        font-size: 10px !important;
        text-decoration: underline;
        padding: 0 !important;
        height: auto !important;
    }}
    .discreet-btn button:hover {{ color: white !important; }}

    /* Simplified Drag & Drop Zone */
    [data-testid="stFileUploader"] {{
        background-color: transparent;
        padding: 40px 10px;
        border-radius: 12px;
        border: 1px dashed #666;
    }}
    
    /* Hide the default Streamlit uploader icon and secondary text */
    [data-testid="stFileUploader"] section {{
        padding: 0 !important;
    }}
    [data-testid="stFileUploader"] label {{
        display: block;
        text-align: center;
        font-size: 24px !important;
        color: #888 !important;
        font-weight: 400 !important;
        margin-bottom: 0 !important;
    }}
    
    /* Center and style the internal button */
    [data-testid="stFileUploader"] button {{
        background-color: #333 !important;
        color: white !important;
        border: none !important;
        margin: 20px auto 0 auto !important;
        display: block !important;
    }}

    /* Action Buttons */
    .stButton>button {{
        background-color: {ACCENT_COLOR};
        color: white;
        border-radius: 6px;
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

if 'proj_name' not in st.session_state:
    st.session_state.proj_name = "PSAM_Export"

# --- 4. TOP-LEVEL NAVIGATION ---
tab_run, tab_fmt, tab_set = st.tabs(["TRANSFORMER", "FORMATS", "SETTINGS"])

with tab_run:
    # CLEAN DROP ZONE
    uploaded_files = st.file_uploader("Drag & Drop Images Here", type=['jpg', 'png', 'webp'], accept_multiple_files=True, label_visibility="visible")

    if uploaded_files:
        # Discreet Selection Tools
        st.markdown('<div class="discreet-btn">', unsafe_allow_html=True)
        t_col1, t_col2, _ = st.columns([0.8, 1, 8])
        with t_col1:
            if st.button("SELECT ALL"): 
                for s in st.session_state.specs: st.session_state[f"run_{s['label']}"] = True
                st.rerun()
        with t_col2:
            if st.button("SELECT NONE"): 
                for s in st.session_state.specs: st.session_state[f"run_{s['label']}"] = False
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

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
                        with c_icon: st.markdown(get_svg_rect(spec['ratio']), unsafe_allow_html=True)
                        with c_check:
                            if st.checkbox(f"{spec['label']} ({spec['width']}x{spec['height']})", value=True, key=f"run_{spec['label']}"):
                                selected_formats.append(spec)
                            st.markdown(f'<span style="color: #444; font-size: 10px;">{spec.get("ext", "WebP").upper()} @ {spec.get("quality", 85)}%</span>', unsafe_allow_html=True)

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
    st.write("### Permanent Museum Standards")
    for idx, spec in enumerate(st.session_state.specs):
        with st.expander(f"{spec['category']}: {spec['label']}"):
            l = st.text_input("Label", spec['label'], key=f"edit_l_{idx}")
            c1, c2 = st.columns(2)
            w = c1.number_input("Width", value=int(spec['width']), key=f"edit_w_{idx}")
            h = c2.number_input("Height", value=int(spec['height']), key=f"edit_h_{idx}")
            c3, c4 = st.columns(2)
            e = c3.selectbox("File Format", ["WebP", "JPEG"], index=0 if spec.get('ext', 'WebP') == "WebP" else 1, key=f"edit_e_{idx}")
            q = c4.slider("Quality", 10, 100, spec.get('quality', 85), key=f"edit_q_{idx}")
            
            b1, b2 = st.columns([1, 4])
            if b1.button("Save", key=f"upd_{idx}"):
                st.session_state.specs[idx].update({"label": l, "width": int(w), "height": int(h), "ext": e, "quality": q, "ratio": calculate_ratio(int(w), int(h))})
                save_specs_to_disk(); st.rerun()
            if b2.button("Remove", key=f"del_{idx}"):
                st.session_state.specs.pop(idx); save_specs_to_disk(); st.rerun()
    
    st.divider()
    with st.form("new_standard"):
        st.write("#### Add New Standard")
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

with tab_set:
    st.write("### Workflow Settings")
    st.session_state.proj_name = st.text_input("Project Export Name", value=st.session_state.proj_name)
    st.divider()
    json_data = json.dumps({"formats": st.session_state.specs}, indent=4)
    st.download_button(label="EXPORT LIBRARY (JSON)", data=json_data, file_name="transformer_specs_backup.json", mime="application/json")
