import streamlit as st
from PIL import Image, ImageOps, ImageEnhance
import json, os, math, re, io, zipfile

# 1. RAW Support Engine
try:
    import rawpy
except ImportError:
    rawpy = None

# --- INITIALIZATION ---
st.set_page_config(page_title="Visual Transformer Pro", layout="wide")

# Dark Theme Discreet Branding
st.markdown("""
    <style>
    /* Dark Mode Buttons with Orange Accents */
    .stButton > button {
        background-color: #262730;
        color: #efefef;
        border: 1px solid #444 !important;
        border-radius: 4px;
        transition: all 0.2s;
        width: 100%;
    }
    .stButton > button:hover {
        border-color: #f36e2e !important;
        color: #f36e2e;
    }
    /* STABLE VIEWPORT: Forces the preview to stay in a 500px box */
    .viewport-container {
        height: 500px;
        width: 100%;
        background-color: #0e1117;
        border: 1px solid #333;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        margin-bottom: 20px;
    }
    /* Ensure the Streamlit image stays contained */
    .viewport-container img {
        max-height: 500px !important;
        max-width: 100% !important;
        object-fit: contain;
    }
    </style>
""", unsafe_allow_html=True)

# Session State Management
if 'specs' not in st.session_state: st.session_state.specs = []
if 'img_idx' not in st.session_state: st.session_state.img_idx = 0
if 'align_map' not in st.session_state: st.session_state.align_map = {}
if 'ai_grade' not in st.session_state: st.session_state.ai_grade = {}
if 'cust_w' not in st.session_state: st.session_state.cust_w = 1080
if 'cust_h' not in st.session_state: st.session_state.cust_h = 1080

# --- HELPERS ---
def sanitize(name): return re.sub(r'[^a-zA-Z0-9]', '_', name)
def update_gallery(direction, total):
    if direction == "next": st.session_state.img_idx = (st.session_state.img_idx + 1) % total
    else: st.session_state.img_idx = (st.session_state.img_idx - 1) % total

def apply_grading(img, g):
    if not g: return img
    curr = ImageEnhance.Brightness(img).enhance(g.get('bright', 1.0))
    curr = ImageEnhance.Contrast(curr).enhance(g.get('cont', 1.0))
    curr = ImageEnhance.Color(curr).enhance(g.get('sat', 1.0))
    t, n = g.get('temp', 0), g.get('tint', 0)
    matrix = [1.0 + (t/200), 0, (n/200), 0, 0, 1.0, 0, 0, -(n/200), 0, 1.0 - (t/200), 0]
    return curr.convert("RGB", matrix) if (t != 0 or n != 0) else curr

# --- INTERFACE ---
tab_run, tab_fmt, tab_set = st.tabs(["TRANSFORMER", "FORMATS", "SETTINGS"])

with tab_run:
    uploaded_files = st.file_uploader("Upload", type=['jpg','png','webp','arw','cr2','nef','dng'], accept_multiple_files=True, label_visibility="collapsed")

    if uploaded_files:
        if st.session_state.img_idx >= len(uploaded_files): st.session_state.img_idx = 0
        cur_file = uploaded_files[st.session_state.img_idx]
        ext = os.path.splitext(cur_file.name)[1].lower()

        # RAW Handling
        try:
            if ext in ['.arw', '.cr2', '.nef', '.dng'] and rawpy:
                with rawpy.imread(cur_file) as raw:
                    img_ref = Image.fromarray(raw.postprocess(use_camera_wb=True, bright=1.0))
            else:
                img_ref = Image.open(cur_file).convert("RGB")
        except:
            img_ref = Image.new('RGB', (100, 100), color='gray')

        # --- THE FIXED VIEWPORT ---
        if cur_file.name not in st.session_state.align_map: st.session_state.align_map[cur_file.name] = {"x":50, "y":50}
        al = st.session_state.align_map[cur_file.name]
        
        graded_img = apply_grading(img_ref, st.session_state.ai_grade.get(cur_file.name, {}))
        
        # Pull dimensions from settings (Defaults to 1080x1080)
        tw, th = st.session_state.cust_w, st.session_state.cust_h
        
        # Anchor the container with Markdown
        st.markdown('<div class="viewport-container">', unsafe_allow_html=True)
        # Create the exact crop based on current settings
        final_preview = ImageOps.fit(graded_img, (tw, th), centering=(al["x"]/100, al["y"]/100))
        st.image(final_preview, use_container_width=False) 
        st.markdown('</div>', unsafe_allow_html=True)

        # --- NAV & ALIGNMENT ---
        ncol1, ncol2, ncol3 = st.columns([1, 4, 1])
        with ncol1: st.button("〈", key="b_prev", on_click=update_gallery, args=("prev", len(uploaded_files)))
        with ncol2: 
             st.markdown(f"<center><b>{cur_file.name}</b> — {st.session_state.img_idx+1}/{len(uploaded_files)}</center>", unsafe_allow_html=True)
             al["x"] = st.slider("X-Axis", 0, 100, al["x"], key=f"x_{cur_file.name}")
             al["y"] = st.slider("Y-Axis", 0, 100, al["y"], key=f"y_{cur_file.name}")
        with ncol3: st.button("〉", key="b_next", on_click=update_gallery, args=("next", len(uploaded_files)))

        st.divider()

        # --- TOGGLES ---
        # 1. IMAGE SETTINGS
        with st.expander("⚙️ Image Settings", expanded=True):
            c1, c2, c3, c4 = st.columns(4)
            st.session_state.cust_w = c1.number_input("Width", value=st.session_state.cust_w, key="in_w")
            st.session_state.cust_h = c2.number_input("Height", value=st.session_state.cust_h, key="in_h")
            ext_type = c3.selectbox("Format", ["WebP", "JPEG"])
            quality = c4.slider("Quality", 10, 100, 95)
            st.session_state.cust_format = {"label":"Custom","width":st.session_state.cust_w,"height":st.session_state.cust_h,"ext":ext_type,"quality":quality}

        # 2. COLOR STUDIO
        if st.toggle("Color Studio"):
            if cur_file.name not in st.session_state.ai_grade: st.session_state.ai_grade[cur_file.name] = {'bright':1.0,'cont':1.0,'sat':1.0,'temp':0,'tint':0}
            g = st.session_state.ai_grade[cur_file.name]
            with st.container(border=True):
                s1, s2, s3 = st.columns(3)
                g['temp'] = s1.slider("Temperature", -100, 100, g['temp'])
                g['tint'] = s2.slider("Tint", -100, 100, g['tint'])
                g['bright'] = s3.slider("Exposure", 0.5, 2.0, g['bright'])
                s4, s5 = st.columns(2)
                g['cont'] = s4.slider("Contrast", 0.5, 2.0, g['cont'])
                g['sat'] = s5.slider("Saturation", 0.0, 2.0, g['sat'])

        # 3. TEMPLATES
        selected_templates = []
        if st.toggle("Templates"):
            for spec in st.session_state.specs:
                with st.container(border=True):
                    tcol1, tcol2 = st.columns([6,1])
                    tcol1.write(f"**{spec['label']}** ({spec['width']}x{spec['height']})")
                    if tcol2.checkbox("", key=f"run_{spec['label']}", label_visibility="collapsed"): 
                        selected_templates.append(spec)

        st.divider()

        if st.button("GENERATE BATCH EXPORT"):
            queue = selected_templates + [st.session_state.cust_format]
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zf:
                for up in uploaded_files:
                    up_ext = os.path.splitext(up.name)[1].lower()
                    if up_ext in ['.arw','.cr2','.nef','.dng'] and rawpy:
                        with rawpy.imread(up) as r: img = Image.fromarray(r.postprocess(use_camera_wb=True))
                    else: img = Image.open(up).convert("RGB")
                    
                    img = apply_grading(img, st.session_state.ai_grade.get(up.name, {}))
                    align = st.session_state.align_map.get(up.name, {"x":50, "y":50})
                    for sp in queue:
                        res = ImageOps.fit(img, (sp['width'], sp['height']), centering=(align["x"]/100, align["y"]/100))
                        buf = io.BytesIO()
                        res.save(buf, format=sp.get('ext','WEBP').upper(), quality=sp.get('quality', 95))
                        zf.writestr(f"PSAM_{sanitize(os.path.splitext(up.name)[0])}_{sanitize(sp['label'])}.{sp.get('ext','webp').lower()}", buf.getvalue())
            
            st.success("Batch Complete.")
            st.download_button("Download ZIP Package", data=zip_buffer.getvalue(), file_name="psam_export.zip")
