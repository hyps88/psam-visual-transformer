import streamlit as st
from PIL import Image, ImageOps, ImageEnhance
import json, os, math, re, io, zipfile

# RAW Support
try:
    import rawpy
except ImportError:
    rawpy = None

# --- 1. INITIALIZATION ---
st.set_page_config(page_title="Visual Transformer Pro", layout="wide")

# Discreet Button Styling
st.markdown("""
    <style>
    .stButton > button {
        background-color: #f8f9fa;
        color: #444;
        border: 1px solid #ddd !important;
        border-radius: 4px;
        padding: 0.4rem 1rem;
        font-weight: 400;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        border-color: #f36e2e !important;
        color: #f36e2e;
        background-color: #fff;
    }
    /* Action Button Styling */
    div[data-testid="stFormSubmitButton"] button, 
    button[kind="primary"] {
        background-color: #444 !important;
        color: white !important;
        border: none !important;
    }
    </style>
""", unsafe_allow_html=True)

if 'specs' not in st.session_state:
    if os.path.exists("transformer_specs.json"):
        with open("transformer_specs.json", "r") as f:
            st.session_state.specs = json.load(f).get('formats', [])
    else: st.session_state.specs = []

if 'proj_name' not in st.session_state: st.session_state.proj_name = "PSAM_Export"
if 'img_idx' not in st.session_state: st.session_state.img_idx = 0
if 'align_map' not in st.session_state: st.session_state.align_map = {}
if 'ai_grade' not in st.session_state: st.session_state.ai_grade = {}

# --- 2. HELPERS ---
def calculate_ratio(w, h):
    if not w or not h: return "1:1"
    gcd = math.gcd(int(w), int(h))
    return f"{int(w)//gcd}:{int(h)//gcd}"

def save_specs_to_disk():
    with open("transformer_specs.json", "w") as f:
        json.dump({"formats": st.session_state.specs}, f, indent=4)

def get_svg_rect(ratio_str):
    try:
        r_w, r_h = map(int, ratio_str.split(":")); max_d = 35
        w, h = (max_d, int(max_d*(r_h/r_w))) if r_w > r_h else (int(max_d*(r_w/r_h)), max_d)
        return f'<svg width="45" height="45"><rect x="{(45-w)/2}" y="{(45-h)/2}" width="{w}" height="{h}" fill="none" stroke="#444" stroke-width="2.5"/></svg>'
    except: return ""

def sanitize(name):
    return re.sub(r'[^a-zA-Z0-9]', '_', name)

def update_gallery(direction, total_files):
    if direction == "next": st.session_state.img_idx = (st.session_state.img_idx + 1) % total_files
    else: st.session_state.img_idx = (st.session_state.img_idx - 1) % total_files

def apply_grading(img, g):
    if not g: return img
    curr = ImageEnhance.Brightness(img).enhance(g.get('bright', 1.0))
    curr = ImageEnhance.Contrast(curr).enhance(g.get('cont', 1.0))
    curr = ImageEnhance.Color(curr).enhance(g.get('sat', 1.0))
    temp, tint = g.get('temp', 0), g.get('tint', 0)
    matrix = [1.0 + (temp/200), 0, (tint/200), 0, 0, 1.0, 0, 0, -(tint/200), 0, 1.0 - (temp/200), 0]
    return curr.convert("RGB", matrix) if (temp != 0 or tint != 0) else curr

# --- 3. INTERFACE ---
tab_run, tab_fmt, tab_set = st.tabs(["TRANSFORMER", "FORMATS", "SETTINGS"])

with tab_run:
    uploaded_files = st.file_uploader("Drag & Drop Box", type=['jpg', 'png', 'webp', 'arw', 'cr2', 'nef', 'dng'], accept_multiple_files=True, label_visibility="collapsed")

    if uploaded_files:
        if st.session_state.img_idx >= len(uploaded_files): st.session_state.img_idx = 0
        cur_file = uploaded_files[st.session_state.img_idx]
        file_ext = os.path.splitext(cur_file.name)[1].lower()

        # Image Loading
        if file_ext in ['.arw', '.cr2', '.nef', '.dng'] and rawpy:
            with rawpy.imread(cur_file) as raw:
                img_ref = Image.fromarray(raw.postprocess(use_camera_wb=True, bright=1.0))
        else:
            img_ref = Image.open(cur_file).convert("RGB")
        
        # Apply current grading to reference for preview
        if cur_file.name in st.session_state.ai_grade:
            img_ref = apply_grading(img_ref, st.session_state.ai_grade[cur_file.name])

        # --- LIVE PREVIEW (TOP SECTION) ---
        st.write("### Live Preview")
        preview_container = st.container(border=True)
        with preview_container:
            pcol_img, pcol_nav = st.columns([2, 1])
            
            # Setup default alignment for preview
            if cur_file.name not in st.session_state.align_map:
                st.session_state.align_map[cur_file.name] = {"x": 50, "y": 50}
            state = st.session_state.align_map[cur_file.name]
            
            with pcol_nav:
                st.write(f"**{cur_file.name}**")
                state["x"] = st.slider("X-Axis", 0, 100, state["x"], key=f"x_{cur_file.name}")
                state["y"] = st.slider("Y-Axis", 0, 100, state["y"], key=f"y_{cur_file.name}")
                
                st.write(" ")
                nc1, nc2, nc3 = st.columns([1, 2, 1])
                with nc1: st.button("〈", key="b_prev", on_click=update_gallery, args=("prev", len(uploaded_files)))
                with nc2: st.markdown(f"<center><small>{st.session_state.img_idx + 1} / {len(uploaded_files)}</small></center>", unsafe_allow_html=True)
                with nc3: st.button("〉", key="b_next", on_click=update_gallery, args=("next", len(uploaded_files)))

            with pcol_img:
                # Default preview crop (16:9 for wide viewing)
                crop_prev = ImageOps.fit(img_ref, (1280, 720), centering=(state["x"]/100, state["y"]/100))
                st.image(crop_prev, use_container_width=True)

        st.divider()

        # --- REORDERED TOGGLES ---
        # 1. Image Settings (formerly Custom Settings)
        if st.toggle("Image Settings", key="t_custom"):
            with st.container(border=True):
                l_ar = st.checkbox("Lock Aspect Ratio", value=False)
                l_sz = st.checkbox("Original Size Overide", value=False)
                ow, oh = img_ref.size
                c1, c2, c3, c4 = st.columns(4)
                w_val = ow if l_sz else 1080
                cust_w = c1.number_input("Width", value=w_val, disabled=l_sz)
                cust_h = int(cust_w * (oh/ow)) if l_ar else c2.number_input("Height", value=(oh if l_sz else 1080), disabled=l_sz)
                cust_ext = c3.selectbox("Format", ["WebP", "JPEG"])
                cust_q = c4.slider("Quality", 10, 100, 95)
                # This adds 'Custom' to the processing queue if active
                st.session_state.cust_format = {"label": "Custom", "width": cust_w, "height": cust_h, "ext": cust_ext, "quality": cust_q}

        # 2. Color Studio
        if st.toggle("Color Studio", key="t_studio"):
            if cur_file.name not in st.session_state.ai_grade:
                st.session_state.ai_grade[cur_file.name] = {'bright':1.0, 'cont':1.0, 'sat':1.0, 'temp':0, 'tint':0}
            g = st.session_state.ai_grade[cur_file.name]
            with st.container(border=True):
                c1, c2, c3 = st.columns(3)
                g['temp'] = c1.slider("Temperature", -100, 100, g['temp'])
                g['tint'] = c2.slider("Tint", -100, 100, g['tint'])
                g['bright'] = c3.slider("Exposure", 0.5, 2.0, g['bright'])
                c4, c5 = st.columns(2)
                g['cont'] = c4.slider("Contrast", 0.5, 2.0, g['cont'])
                g['sat'] = c5.slider("Saturation", 0.0, 2.0, g['sat'])
                if st.button("Reset Color"):
                    st.session_state.ai_grade[cur_file.name] = {'bright':1.0, 'cont':1.0, 'sat':1.0, 'temp':0, 'tint':0}
                    st.rerun()

        # 3. Templates
        selected_templates = []
        if st.toggle("Templates", key="show_templates"):
            for spec in st.session_state.specs:
                with st.container(border=True):
                    ic, nc, sc = st.columns([1, 6, 1])
                    with ic: st.markdown(get_svg_rect(calculate_ratio(spec['width'], spec['height'])), unsafe_allow_html=True)
                    with nc: st.markdown(f"**{spec['label']}** — {spec['width']}x{spec['height']}")
                    with sc:
                        if st.checkbox("", key=f"run_{spec['label']}", label_visibility="collapsed"):
                            selected_templates.append(spec)

        st.divider()
        
        # Action Buttons (Discreet)
        if st.button("GENERATE BATCH EXPORT", use_container_width=True):
            queue = selected_templates
            if st.session_state.get('t_custom'): queue.append(st.session_state.cust_format)
            
            if queue:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zf:
                    for up in uploaded_files:
                        img = Image.open(up).convert("RGB")
                        img = apply_grading(img, st.session_state.ai_grade.get(up.name, {}))
                        bn = sanitize(os.path.splitext(up.name)[0])
                        align = st.session_state.align_map.get(up.name, {"x": 50, "y": 50})
                        for sp in queue:
                            t_cx, t_cy = (align["x"]/100, align["y"]/100)
                            res = ImageOps.fit(img, (sp['width'], sp['height']), centering=(t_cx, t_cy))
                            buf = io.BytesIO()
                            if sp.get('ext') == "JPEG": res.save(buf, format="JPEG", quality=sp.get('quality', 95))
                            else: res.save(buf, format="WEBP", quality=sp.get('quality', 95))
                            zf.writestr(f"PSAM_{bn}_{sanitize(sp['label'])}.{sp.get('ext','webp').lower()}", buf.getvalue())
                
                st.success("Assets Prepared.")
                st.download_button("Download ZIP Package", data=zip_buffer.getvalue(), file_name=f"{sanitize(st.session_state.proj_name)}.zip")

# TABS 2 & 3 remain for management logic
