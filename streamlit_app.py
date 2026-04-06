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

# Discreet Branding
st.markdown("""
    <style>
    .stButton > button {
        background-color: #f8f9fa;
        color: #444;
        border: 1px solid #ddd !important;
        border-radius: 4px;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        border-color: #f36e2e !important;
        color: #f36e2e;
    }
    </style>
""", unsafe_allow_html=True)

# Session State Setup
for key in ['specs', 'proj_name', 'img_idx', 'align_map', 'ai_grade']:
    if key not in st.session_state:
        if key == 'specs' and os.path.exists("transformer_specs.json"):
            with open("transformer_specs.json", "r") as f: st.session_state[key] = json.load(f).get('formats', [])
        elif key == 'specs': st.session_state[key] = []
        elif key == 'proj_name': st.session_state[key] = "PSAM_Export"
        elif key == 'img_idx': st.session_state[key] = 0
        else: st.session_state[key] = {}

# --- HELPERS ---
def calculate_ratio(w, h):
    if not w or not h: return "1:1"
    gcd = math.gcd(int(w), int(h))
    return f"{int(w)//gcd}:{int(h)//gcd}"

def get_svg_rect(ratio_str):
    try:
        r_w, r_h = map(int, ratio_str.split(":")); max_d = 35
        w, h = (max_d, int(max_d*(r_h/r_w))) if r_w > r_h else (int(max_d*(r_w/r_h)), max_d)
        return f'<svg width="45" height="45"><rect x="{(45-w)/2}" y="{(45-h)/2}" width="{w}" height="{h}" fill="none" stroke="#444" stroke-width="2.5"/></svg>'
    except: return ""

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

        # FIXED LOADING LOGIC
        try:
            if ext in ['.arw', '.cr2', '.nef', '.dng'] and rawpy:
                # Use rawpy to "develop" the file before Pillow sees it
                with rawpy.imread(cur_file) as raw:
                    rgb = raw.postprocess(use_camera_wb=True, bright=1.0, no_auto_bright=True)
                    img_ref = Image.fromarray(rgb)
            else:
                img_ref = Image.open(cur_file).convert("RGB")
        except Exception as e:
            st.error(f"Could not load {cur_file.name}. Ensure 'rawpy' is in requirements.txt.")
            img_ref = Image.new('RGB', (100, 100), color='gray')

        # Live Preview Section
        st.write("### Live Preview")
        with st.container(border=True):
            if cur_file.name not in st.session_state.align_map: st.session_state.align_map[cur_file.name] = {"x":50, "y":50}
            al = st.session_state.align_map[cur_file.name]
            
            # Apply grading for real-time visual
            graded_img = apply_grading(img_ref, st.session_state.ai_grade.get(cur_file.name, {}))
            
            pcol_img, pcol_nav = st.columns([2, 1])
            with pcol_nav:
                st.write(f"**{cur_file.name}**")
                al["x"] = st.slider("X-Axis", 0, 100, al["x"], key=f"x_{cur_file.name}")
                al["y"] = st.slider("Y-Axis", 0, 100, al["y"], key=f"y_{cur_file.name}")
                c1, c2, c3 = st.columns([1,1,1])
                c1.button("〈", on_click=update_gallery, args=("prev", len(uploaded_files)))
                c2.markdown(f"<center><small>{st.session_state.img_idx+1}/{len(uploaded_files)}</small></center>", unsafe_allow_html=True)
                c3.button("〉", on_click=update_gallery, args=("next", len(uploaded_files)))
            with pcol_img:
                st.image(ImageOps.fit(graded_img, (1280, 720), centering=(al["x"]/100, al["y"]/100)), use_container_width=True)

        st.divider()

        # REORDERED TOGGLES
        if st.toggle("Image Settings"):
            with st.container(border=True):
                l_ar = st.checkbox("Lock Ratio")
                l_sz = st.checkbox("Original Size")
                ow, oh = img_ref.size
                c1, c2, c3, c4 = st.columns(4)
                w = c1.number_input("Width", value=ow if l_sz else 1080, disabled=l_sz)
                h = int(w*(oh/ow)) if l_ar else c2.number_input("Height", value=oh if l_sz else 1080, disabled=l_sz)
                st.session_state.cust_format = {"label":"Custom","width":w,"height":h,"ext":c3.selectbox("Ext",["WebP","JPEG"]),"quality":c4.slider("Q",10,100,95)}

        if st.toggle("Color Studio"):
            if cur_file.name not in st.session_state.ai_grade: st.session_state.ai_grade[cur_file.name] = {'bright':1.0,'cont':1.0,'sat':1.0,'temp':0,'tint':0}
            g = st.session_state.ai_grade[cur_file.name]
            with st.container(border=True):
                c1, c2, c3 = st.columns(3)
                g['temp'] = c1.slider("Temp", -100, 100, g['temp'])
                g['tint'] = c2.slider("Tint", -100, 100, g['tint'])
                g['bright'] = c3.slider("Exp", 0.5, 2.0, g['bright'])
                c4, c5 = st.columns(2)
                g['cont'] = c4.slider("Cont", 0.5, 2.0, g['cont'])
                g['sat'] = c5.slider("Sat", 0.0, 2.0, g['sat'])

        selected_templates = []
        if st.toggle("Templates"):
            for spec in st.session_state.specs:
                with st.container(border=True):
                    i, n, s = st.columns([1,6,1])
                    i.markdown(get_svg_rect(calculate_ratio(spec['width'], spec['height'])), unsafe_allow_html=True)
                    n.write(f"**{spec['label']}** — {spec['width']}x{spec['height']}")
                    if s.checkbox("", key=f"run_{spec['label']}", label_visibility="collapsed"): selected_templates.append(spec)

        if st.button("GENERATE BATCH EXPORT", use_container_width=True):
            queue = selected_templates
            if st.session_state.get('t_custom'): queue.append(st.session_state.cust_format)
            if queue:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zf:
                    for up in uploaded_files:
                        # Batch process needs to handle RAW too
                        ext_up = os.path.splitext(up.name)[1].lower()
                        if ext_up in ['.arw','.cr2','.nef','.dng'] and rawpy:
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
                st.download_button("Download ZIP", data=zip_buffer.getvalue(), file_name=f"{st.session_state.proj_name}.zip")
