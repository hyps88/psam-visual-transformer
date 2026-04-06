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
    .viewport-container img {
        max-height: 500px !important;
        max-width: 100% !important;
        object-fit: contain;
    }
    </style>
""", unsafe_allow_html=True)

# Persistent Session State
if 'specs' not in st.session_state:
    if os.path.exists("transformer_specs.json"):
        with open("transformer_specs.json", "r") as f:
            st.session_state.specs = json.load(f).get('formats', [])
    else: st.session_state.specs = []

for key in ['img_idx', 'align_map', 'ai_grade', 'proj_name']:
    if key not in st.session_state:
        st.session_state[key] = 0 if key == 'img_idx' else ("PSAM_Export" if key == 'proj_name' else {})

if 'cust_w' not in st.session_state: st.session_state.cust_w = 1080
if 'cust_h' not in st.session_state: st.session_state.cust_h = 1080

# --- HELPERS ---
def sanitize(name): return re.sub(r'[^a-zA-Z0-9]', '_', name)

def save_specs():
    with open("transformer_specs.json", "w") as f:
        json.dump({"formats": st.session_state.specs}, f, indent=4)

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

# --- TAB 1: TRANSFORMER ---
with tab_run:
    uploaded_files = st.file_uploader("Upload", type=['jpg','png','webp','arw','cr2','nef','dng'], accept_multiple_files=True, label_visibility="collapsed")

    if uploaded_files:
        if st.session_state.img_idx >= len(uploaded_files): st.session_state.img_idx = 0
        cur_file = uploaded_files[st.session_state.img_idx]
        ext = os.path.splitext(cur_file.name)[1].lower()

        # RAW vs Standard Loading
        try:
            if ext in ['.arw', '.cr2', '.nef', '.dng'] and rawpy:
                with rawpy.imread(cur_file) as raw:
                    img_ref = Image.fromarray(raw.postprocess(use_camera_wb=True, bright=1.0))
            else:
                img_ref = Image.open(cur_file).convert("RGB")
        except:
            img_ref = Image.new('RGB', (100, 100), color='gray')

        # Global Viewport Logic
        if cur_file.name not in st.session_state.align_map: st.session_state.align_map[cur_file.name] = {"x":50, "y":50}
        al = st.session_state.align_map[cur_file.name]
        graded_img = apply_grading(img_ref, st.session_state.ai_grade.get(cur_file.name, {}))
        
        # PREVIEW BOX
        st.markdown('<div class="viewport-container">', unsafe_allow_html=True)
        # Live refresh based on session state
        final_preview = ImageOps.fit(graded_img, (st.session_state.cust_w, st.session_state.cust_h), centering=(al["x"]/100, al["y"]/100))
        st.image(final_preview, use_container_width=False) 
        st.markdown('</div>', unsafe_allow_html=True)

        # NAV & SLIDERS
        ncol1, ncol2, ncol3 = st.columns([1, 4, 1])
        with ncol1: st.button("〈", key="b_prev", on_click=update_gallery, args=("prev", len(uploaded_files)))
        with ncol2: 
             st.markdown(f"<center><b>{cur_file.name}</b> — {st.session_state.img_idx+1}/{len(uploaded_files)}</center>", unsafe_allow_html=True)
             al["x"] = st.slider("X-Axis", 0, 100, al["x"], key=f"x_{cur_file.name}")
             al["y"] = st.slider("Y-Axis", 0, 100, al["y"], key=f"y_{cur_file.name}")
        with ncol3: st.button("〉", key="b_next", on_click=update_gallery, args=("next", len(uploaded_files)))

        st.divider()

        # TOGGLES (RESTORED)
        with st.expander("⚙️ Image Settings", expanded=True):
            c1, c2, c3, c4 = st.columns(4)
            # Link Width/Height to trigger rerun on change
            st.session_state.cust_w = c1.number_input("Width", value=st.session_state.cust_w, step=1)
            st.session_state.cust_h = c2.number_input("Height", value=st.session_state.cust_h, step=1)
            ext_type = c3.selectbox("Format", ["WebP", "JPEG"])
            quality = c4.slider("Quality", 10, 100, 95)
            st.session_state.cust_format = {"label":"Custom","width":st.session_state.cust_w,"height":st.session_state.cust_h,"ext":ext_type,"quality":quality}

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

        selected_templates = []
        if st.toggle("Templates"):
            for spec in st.session_state.specs:
                with st.container(border=True):
                    tcol1, tcol2 = st.columns([6,1])
                    tcol1.write(f"**{spec['label']}** ({spec['width']}x{spec['height']})")
                    # If clicked, update the live preview to match this template's size
                    if tcol2.checkbox("", key=f"run_{spec['label']}"):
                        selected_templates.append(spec)
                        if st.button(f"Preview {spec['label']}"):
                            st.session_state.cust_w, st.session_state.cust_h = spec['width'], spec['height']
                            st.rerun()

        st.divider()

        if st.button("GENERATE BATCH EXPORT", type="primary"):
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
            st.download_button("Download ZIP Package", data=zip_buffer.getvalue(), file_name=f"{st.session_state.proj_name}.zip")

# --- TAB 2: FORMATS (RESTORED) ---
with tab_fmt:
    st.write("### Museum Standards Library")
    if st.session_state.specs:
        for idx, spec in enumerate(st.session_state.specs):
            with st.expander(f"{spec.get('label', 'Unnamed')}"):
                l = st.text_input("Label", spec['label'], key=f"l_{idx}")
                w = st.number_input("W", value=spec['width'], key=f"w_{idx}")
                h = st.number_input("H", value=spec['height'], key=f"h_{idx}")
                if st.button("Update", key=f"up_{idx}"):
                    st.session_state.specs[idx].update({"label":l, "width":int(w), "height":int(h)})
                    save_specs(); st.rerun()
                if st.button("Remove", key=f"rm_{idx}"):
                    st.session_state.specs.pop(idx); save_specs(); st.rerun()
    
    with st.form("new_fmt"):
        st.write("Add New Standard")
        n_l = st.text_input("Name")
        n_w = st.number_input("Width", 1080)
        n_h = st.number_input("Height", 1080)
        if st.form_submit_button("ADD"):
            st.session_state.specs.append({"label":n_l, "width":int(n_w), "height":int(n_h)})
            save_specs(); st.rerun()

# --- TAB 3: SETTINGS (RESTORED) ---
with tab_set:
    st.session_state.proj_name = st.text_input("Project Name", value=st.session_state.proj_name)
    if st.button("Clear All Cache"):
        st.session_state.align_map = {}
        st.session_state.ai_grade = {}
        st.rerun()
