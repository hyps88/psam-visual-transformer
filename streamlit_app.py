import streamlit as st
from PIL import Image, ImageOps, ImageEnhance
import json, os, math, re, io, zipfile
import numpy as np

# Try to import rawpy for Museum RAW support
try:
    import rawpy
except ImportError:
    rawpy = None

# --- 1. INITIALIZATION [LOCKED] ---
st.set_page_config(page_title="Visual Transformer Pro", layout="wide")

if 'specs' not in st.session_state:
    if os.path.exists("transformer_specs.json"):
        with open("transformer_specs.json", "r") as f:
            st.session_state.specs = json.load(f).get('formats', [])
    else: st.session_state.specs = []

if 'proj_name' not in st.session_state: st.session_state.proj_name = "PSAM_Export"
if 'img_idx' not in st.session_state: st.session_state.img_idx = 0
if 'align_map' not in st.session_state: st.session_state.align_map = {}
if 'ai_grade' not in st.session_state: st.session_state.ai_grade = {} # Stores AI settings per image

# --- 2. HELPERS [LOCKED] ---
def calculate_ratio(w, h):
    if not w or not h: return "1:1"
    gcd = math.gcd(int(w), int(h))
    return f"{int(w)//gcd}:{int(h)//gcd}"

def save_specs_to_disk():
    with open("transformer_specs.json", "w") as f:
        json.dump({"formats": st.session_state.specs}, f, indent=4)

def sanitize(name):
    return re.sub(r'[^a-zA-Z0-9]', '_', name)

def update_gallery(direction, total_files):
    if direction == "next": st.session_state.img_idx = (st.session_state.img_idx + 1) % total_files
    else: st.session_state.img_idx = (st.session_state.img_idx - 1) % total_files

def apply_ai_enhancements(img, settings):
    """Applies Lightroom-style adjustments based on session state."""
    if not settings: return img
    # Auto-Contrast/Brightness
    if settings.get('auto'):
        img = ImageOps.autocontrast(img, cutoff=0.5)
    # Manual Adjustments
    curr = ImageEnhance.Brightness(img).enhance(settings.get('bright', 1.0))
    curr = ImageEnhance.Contrast(curr).enhance(settings.get('cont', 1.0))
    curr = ImageEnhance.Color(curr).enhance(settings.get('sat', 1.0))
    return curr

# --- 3. INTERFACE ---
tab_run, tab_fmt, tab_set = st.tabs(["TRANSFORMER", "FORMATS", "SETTINGS"])

with tab_run:
    # Expanded file types for RAW support (ARW, CR2, NEF, DNG)
    uploaded_files = st.file_uploader("Upload Images (JPG, PNG, WEBP, RAW)", 
                                     type=['jpg', 'jpeg', 'png', 'webp', 'arw', 'cr2', 'nef', 'dng'], 
                                     accept_multiple_files=True, label_visibility="collapsed")

    if uploaded_files:
        if st.session_state.img_idx >= len(uploaded_files): st.session_state.img_idx = 0
        cur_file = uploaded_files[st.session_state.img_idx]
        file_ext = os.path.splitext(cur_file.name)[1].lower()

        # Handle RAW conversion if necessary
        try:
            if file_ext in ['.arw', '.cr2', '.nef', '.dng'] and rawpy:
                with rawpy.imread(cur_file) as raw:
                    rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=True, bright=1.0)
                    img_ref = Image.fromarray(rgb)
            else:
                img_ref = Image.open(cur_file).convert("RGB")
        except Exception as e:
            st.error(f"Error loading {cur_file.name}: {e}")
            img_ref = Image.new('RGB', (100, 100), color='red')

        st.write(" ")
        
        # --- NEW: AI COLOR STUDIO ---
        show_editor = st.toggle("AI Color Studio & Presets", key="toggle_editor")
        if show_editor:
            with st.container(border=True):
                col_ai1, col_ai2 = st.columns([1, 2])
                if cur_file.name not in st.session_state.ai_grade:
                    st.session_state.ai_grade[cur_file.name] = {'bright': 1.0, 'cont': 1.0, 'sat': 1.0, 'auto': False}
                
                grade = st.session_state.ai_grade[cur_file.name]
                
                with col_ai1:
                    if st.button("✨ AUTO SCAN (AI Balance)"):
                        grade['auto'] = True
                        grade['cont'] = 1.2 # Pop the contrast
                        grade['sat'] = 1.1 # Vivid colors
                        st.session_state.ai_grade[cur_file.name] = grade
                    if st.button("🔄 Reset to Original"):
                        st.session_state.ai_grade[cur_file.name] = {'bright': 1.0, 'cont': 1.0, 'sat': 1.0, 'auto': False}
                        st.rerun()

                with col_ai2:
                    c_b, c_c, c_s = st.columns(3)
                    grade['bright'] = c_b.slider("Exposure", 0.5, 2.0, grade['bright'], 0.1)
                    grade['cont'] = c_c.slider("Contrast", 0.5, 2.0, grade['cont'], 0.1)
                    grade['sat'] = c_s.slider("Saturation", 0.0, 2.0, grade['sat'], 0.1)
                
                # Apply live grading to the reference image
                img_ref = apply_ai_enhancements(img_ref, grade)

        # --- EXISTING: TRANSFORMER SETTINGS [LOCKED] ---
        cust_active = st.toggle("Custom Settings", value=False)
        selected_formats = []

        if cust_active:
            with st.container(border=True):
                col_locks = st.columns(2)
                l_ar = col_locks[0].checkbox("Lock Aspect Ratio", value=False)
                l_sz = col_locks[1].checkbox("Original Size", value=False)
                ow, oh = img_ref.size
                c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
                w_val = ow if l_sz else 1080
                cust_w = c1.number_input("Width", value=w_val, disabled=l_sz, key="cw_in")
                if l_ar:
                    cust_h = int(cust_w * (oh / ow))
                    c2.number_input("Height", value=cust_h, disabled=True)
                else:
                    h_val = oh if l_sz else 1080
                    cust_h = c2.number_input("Height", value=h_val, disabled=l_sz, key="ch_in")
                cust_ext = c3.selectbox("Type", ["WebP", "JPEG"], key="ce_in")
                cust_q = c4.slider("Quality", 10, 100, 95, key="cq_in")

                with st.expander("👁️ Preview & Alignment", expanded=True):
                    if cur_file.name not in st.session_state.align_map:
                        st.session_state.align_map[cur_file.name] = {"x": 50, "y": 50}
                    state = st.session_state.align_map[cur_file.name]
                    pcol_img, pcol_ctrl = st.columns([1, 1])
                    with pcol_ctrl:
                        mx = st.slider("X-Axis", 0, 100, state["x"], key=f"x_{cur_file.name}")
                        my = st.slider("Y-Axis", 0, 100, state["y"], key=f"y_{cur_file.name}")
                        state["x"], state["y"] = mx, my
                        st.divider()
                        nc1, nc2, nc3 = st.columns([1, 4, 1])
                        with nc1: st.button("〈", on_click=update_gallery, args=("prev", len(uploaded_files)))
                        with nc2: st.markdown(f'<center><b>{cur_file.name}</b></center>', unsafe_allow_html=True)
                        with nc3: st.button("〉", on_click=update_gallery, args=("next", len(uploaded_files)))
                    with pcol_img:
                        asp = cust_w / cust_h
                        sw, sh = (500, int(500/asp)) if asp > 1 else (int(500*asp), 500)
                        crop = ImageOps.fit(img_ref, (cust_w, cust_h), centering=(state["x"]/100, state["y"]/100))
                        st.image(crop, width=sw)
            selected_formats.append({"label": "Custom", "width": cust_w, "height": cust_h, "ext": cust_ext, "quality": cust_q})

        if st.toggle("Templates", key="show_templates"):
            for spec in st.session_state.specs:
                if st.checkbox(f"{spec['label']} ({spec['width']}x{spec['height']})", key=f"run_{spec['label']}"):
                    selected_formats.append(spec)

        if st.button("GENERATE ALL ASSETS", use_container_width=True):
            if selected_formats:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zf:
                    for up in uploaded_files:
                        # Process each file with its specific AI Grade
                        grade = st.session_state.ai_grade.get(up.name, {})
                        img = Image.open(up).convert("RGB") # Simplified for batch
                        img = apply_ai_enhancements(img, grade)
                        bn = sanitize(os.path.splitext(up.name)[0])
                        align = st.session_state.align_map.get(up.name, {"x": 50, "y": 50})
                        for sp in selected_formats:
                            t_cx, t_cy = (align["x"]/100, align["y"]/100) if sp['label'] == "Custom" else (0.5, 0.5)
                            res = ImageOps.fit(img, (sp['width'], sp['height']), centering=(t_cx, t_cy))
                            buf = io.BytesIO()
                            if sp.get('ext') == "JPEG": res.save(buf, format="JPEG", quality=sp.get('quality', 95))
                            else: res.save(buf, format="WEBP", quality=sp.get('quality', 95))
                            zf.writestr(f"PSAM_{bn}_{sanitize(sp['label'])}.{sp.get('ext','webp').lower()}", buf.getvalue())
                st.download_button("DOWNLOAD ZIP", data=zip_buffer.getvalue(), file_name=f"{st.session_state.proj_name}.zip")

# --- TABS 2 & 3 ---
with tab_fmt:
    st.write("### Museum Standards")
    # ... [Existing Format Management Code] ...
with tab_set:
    st.write("### Workflow Settings")
    st.session_state.proj_name = st.text_input("Project Name", value=st.session_state.proj_name)
