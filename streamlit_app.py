import streamlit as st
from PIL import Image, ImageOps, ImageEnhance
import json, os, math, re, io, zipfile
import rawpy

# --- INITIALIZATION ---
st.set_page_config(page_title="PSAM Visual Transformer Pro", layout="wide")
with open("style.css") as f: st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Persistent State Logic
for key in ['specs', 'aligns', 'tags', 'img_idx', 'proj_name', 'wm_config']:
    if key not in st.session_state:
        if key == 'specs': st.session_state[key] = []
        elif key == 'proj_name': st.session_state[key] = "PSAM_Export"
        elif key == 'img_idx': st.session_state[key] = 0
        elif key == 'wm_config': st.session_state[key] = {'size': 20, 'x': 95, 'y': 95, 'opacity': 1.0}
        else: st.session_state[key] = {}

# --- CORE PROCESSING ENGINE ---
def load_img(file):
    ext = file.name.split('.')[-1].lower()
    if ext in ['arw', 'cr2', 'nef', 'dng']:
        with rawpy.imread(file) as raw: return Image.fromarray(raw.postprocess(use_camera_wb=True))
    return Image.open(file).convert("RGBA")

def get_svg_rect(w, h):
    gcd = math.gcd(int(w), int(h))
    rw, rh = int(w)//gcd, int(h)//gcd
    md = 35
    sw, sh = (md, int(md*(rh/rw))) if rw > rh else (int(md*(rw/rh)), md)
    return f'<svg width="45" height="45"><rect x="{(45-sw)/2}" y="{(45-sh)/2}" width="{sw}" height="{sh}" fill="none" stroke="#666" stroke-width="2"/></svg>'

# --- UI TABS ---
t_trans, t_lib, t_set = st.tabs(["TRANSFORMER", "LIBRARY", "SETTINGS"])

# --- TAB 1: TRANSFORMER ---
with t_trans:
    files = st.file_uploader("Drop Zone", type=['jpg','png','webp','arw','cr2','nef','dng'], accept_multiple_files=True, label_visibility="collapsed")
    
    if files:
        if st.session_state.img_idx >= len(files): st.session_state.img_idx = 0
        cur = files[st.session_state.img_idx]
        img_raw = load_img(cur)
        
        # 1. VIEWPORT (FIXED 500PX)
        if cur.name not in st.session_state.aligns: st.session_state.aligns[cur.name] = {'x': 50, 'y': 50}
        al = st.session_state.aligns[cur.name]
        
        # Dynamic Target Size from Template selection or Manual
        tw = st.number_input("Target W", value=1080, key="main_w")
        th = st.number_input("Target H", value=1350, key="main_h")
        
        st.markdown('<div class="viewport-wrapper">', unsafe_allow_html=True)
        # Apply Crop
        preview = ImageOps.fit(img_raw, (tw, th), centering=(al['x']/100, al['y']/100))
        
        # Apply Watermark if exists
        if 'wm_file' in st.session_state:
            wm = st.session_state.wm_file.copy()
            wm_w = int(preview.width * (st.session_state.wm_config['size']/100))
            wm_h = int(wm.height * (wm_w / wm.width))
            wm = wm.resize((wm_w, wm_h), Image.Resampling.LANCZOS)
            preview.paste(wm, (int(preview.width * st.session_state.wm_config['x']/100) - wm_w, 
                               int(preview.height * st.session_state.wm_config['y']/100) - wm_h), wm)
            
        st.image(preview)
        
        # Insta Overlay Logic
        if st.checkbox("Show Insta Safe Zone"):
            st.markdown(f'<div class="insta-overlay" style="width:{400*(tw/th) if tw<th else 400}px; height:400px;"></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # 2. CONTROLS
        c1, c2, c3 = st.columns([1, 4, 1])
        with c1: 
            if st.button("〈"): st.session_state.img_idx = (st.session_state.img_idx - 1) % len(files); st.rerun()
        with c2:
            al['x'] = st.slider("X Alignment", 0, 100, al['x'])
            al['y'] = st.slider("Y Alignment", 0, 100, al['y'])
        with c3:
            if st.button("〉"): st.session_state.img_idx = (st.session_state.img_idx + 1) % len(files); st.rerun()

        # 3. TAGGING & EXPORT TOGGLES
        with st.expander("TAGS & METADATA"):
            st.session_state.tags[cur.name] = st.text_area("Manual Alt-Text / Keywords", value=st.session_state.tags.get(cur.name, ""))
        
        with st.expander("EXPORT SETTINGS"):
            custom_fn = st.text_input("Filename Override", placeholder="Artist_Title_Year")
            ext = st.selectbox("Format", ["WebP", "JPEG", "PNG"])
            qual = st.slider("Compression Quality", 10, 100, 95)
            # Size Preview
            test_buf = io.BytesIO()
            preview.save(test_buf, format=ext, quality=qual)
            st.metric("Estimated Size", f"{len(test_buf.getvalue())/1024:.1f} KB")

        if st.button("GENERATE BATCH EXPORT", type="primary", use_container_width=True):
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w") as zf:
                for f in files:
                    f_img = load_img(f)
                    f_al = st.session_state.aligns.get(f.name, {'x':50, 'y':50})
                    final = ImageOps.fit(f_img, (tw, th), centering=(f_al['x']/100, f_al['y']/100))
                    f_buf = io.BytesIO()
                    final.save(f_buf, format=ext, quality=qual)
                    fn = custom_fn if custom_fn else f.name.split('.')[0]
                    zf.writestr(f"PSAM_{fn}.{ext.lower()}", f_buf.getvalue())
            st.download_button("Download Zip", data=zip_buf.getvalue(), file_name="PSAM_Batch.zip")

# --- TAB 2: LIBRARY ---
with t_lib:
    st.write("### Standards & Templates")
    # Category Master Select
    with st.form("add_template"):
        st.write("Add New Template")
        n_l, n_w, n_h, n_c = st.columns(4)
        l = n_l.text_input("Label")
        w = n_w.number_input("Width", 100)
        h = n_h.number_input("Height", 100)
        cat = n_c.text_input("Category", "SOCIAL")
        if st.form_submit_button("ADD"):
            st.session_state.specs.append({'label': l, 'width': w, 'height': h, 'category': cat})
            st.rerun()

    # Display Templates with SVG
    for i, spec in enumerate(st.session_state.specs):
        with st.container(border=True):
            sc1, sc2, sc3 = st.columns([1, 6, 1])
            sc1.markdown(get_svg_rect(spec['width'], spec['height']), unsafe_allow_html=True)
            sc2.write(f"**{spec['label']}** — {spec['width']}x{spec['height']}")
            if sc3.button("DEL", key=f"del_{i}"):
                st.session_state.specs.pop(i); st.rerun()

# --- TAB 3: SETTINGS ---
with t_set:
    # 1. Watermark Tab
    with st.expander("WATERMARK CONFIGURATION"):
        wm_up = st.file_uploader("Upload Logo (PNG)", type=['png'])
        if wm_up: st.session_state.wm_file = Image.open(wm_up).convert("RGBA")
        
        st.session_state.wm_config['size'] = st.slider("Logo Size (%)", 5, 50, st.session_state.wm_config['size'])
        st.session_state.wm_config['x'] = st.slider("Logo X Position", 0, 100, st.session_state.wm_config['x'])
        st.session_state.wm_config['y'] = st.slider("Logo Y Position", 0, 100, st.session_state.wm_config['y'])

    # 2. JSON Import/Export
    with st.expander("DATA MANAGEMENT (JSON)"):
        st.download_button("Export Config", data=json.dumps(st.session_state.specs), file_name="psam_specs.json")
        in_json = st.file_uploader("Import Config")
        if in_json:
            st.session_state.specs = json.load(in_json)
            st.success("Config Loaded")

    # 3. DPI Upscaler
    upscale = st.toggle("Museum Signage Mode (2x DPI Upscale)")
