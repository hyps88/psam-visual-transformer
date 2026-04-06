import streamlit as st
from PIL import Image, ImageOps, ImageEnhance
import json, os, math, re, io, zipfile
import numpy as np

# --- 1. CORE ENGINES ---
try:
    import rawpy
except ImportError:
    rawpy = None

# --- 2. STATE MANAGEMENT (The "Brain") ---
def init_state():
    if 'specs' not in st.session_state:
        if os.path.exists("transformer_specs.json"):
            with open("transformer_specs.json", "r") as f:
                st.session_state.specs = json.load(f).get('formats', [])
        else: st.session_state.specs = []
    
    defaults = {
        'img_idx': 0,
        'proj_name': "PSAM_Export",
        'align_map': {},   # Per-image {x, y}
        'grade_map': {},   # Per-image {temp, tint, exp, cont, sat}
        'cust_w': 1080,
        'cust_h': 1080,
        'cust_ext': "WebP",
        'cust_q': 95
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_state()

# --- 3. PROCESSING HELPERS ---
def apply_ai_grading(img, g):
    """Applies the AI Color Studio stack."""
    if not g: return img
    # Basic Enhancements
    curr = ImageEnhance.Brightness(img).enhance(g.get('exp', 1.0))
    curr = ImageEnhance.Contrast(curr).enhance(g.get('cont', 1.0))
    curr = ImageEnhance.Color(curr).enhance(g.get('sat', 1.0))
    # Temp/Tint Matrix
    t, n = g.get('temp', 0), g.get('tint', 0)
    if t != 0 or n != 0:
        matrix = [1.0 + (t/200), 0, (n/200), 0, 0, 1.0, 0, 0, -(n/200), 0, 1.0 - (t/200), 0]
        curr = curr.convert("RGB", matrix)
    return curr

def load_museum_file(uploaded_file):
    """Handles RAW (ARW/CR2/NEF) and Standard files."""
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    try:
        if ext in ['.arw', '.cr2', '.nef', '.dng'] and rawpy:
            with rawpy.imread(uploaded_file) as raw:
                # postprocess handles the 'Auto' development of RAW data
                rgb = raw.postprocess(use_camera_wb=True, bright=1.0, no_auto_bright=True)
                return Image.fromarray(rgb)
        return Image.open(uploaded_file).convert("RGB")
    except Exception:
        return Image.new('RGB', (100, 100), color='gray')

def get_svg_icon(w, h):
    gcd = math.gcd(int(w), int(h))
    r_w, r_h = int(w)//gcd, int(h)//gcd
    max_d = 35
    sw, sh = (max_d, int(max_d*(r_h/r_w))) if r_w > r_h else (int(max_d*(r_w/r_h)), max_d)
    return f'<svg width="45" height="45"><rect x="{(45-sw)/2}" y="{(45-sh)/2}" width="{sw}" height="{sh}" fill="none" stroke="#666" stroke-width="2"/></svg>'

# --- 4. UI LAYOUT ---
st.set_page_config(page_title="Visual Transformer Pro", layout="wide")
with open("style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

tab_trans, tab_lib, tab_set = st.tabs(["TRANSFORMER", "LIBRARY", "SETTINGS"])

# --- TAB 1: TRANSFORMER ---
with tab_trans:
    files = st.file_uploader("Drop Zone", type=['jpg','png','webp','arw','cr2','nef','dng'], accept_multiple_files=True, label_visibility="collapsed")

    if files:
        # Gallery Navigation Logic
        if st.session_state.img_idx >= len(files): st.session_state.img_idx = 0
        cur_file = files[st.session_state.img_idx]
        
        # 1. LOAD & GRADE
        base_img = load_museum_file(cur_file)
        
        # Initialize memory for this specific image
        if cur_file.name not in st.session_state.align_map: st.session_state.align_map[cur_file.name] = {'x':50, 'y':50}
        if cur_file.name not in st.session_state.grade_map: st.session_state.grade_map[cur_file.name] = {'temp':0, 'tint':0, 'exp':1.0, 'cont':1.0, 'sat':1.0}
        
        graded_img = apply_ai_grading(base_img, st.session_state.grade_map[cur_file.name])
        
        # 2. HERO VIEWPORT (STABILIZED)
        st.markdown('<div class="viewport-frame">', unsafe_allow_html=True)
        # The Viewport reflects the 'Custom' dimensions live
        viewport_img = ImageOps.fit(graded_img, (st.session_state.cust_w, st.session_state.cust_h), 
                                    centering=(st.session_state.align_map[cur_file.name]['x']/100, 
                                               st.session_state.align_map[cur_file.name]['y']/100))
        st.image(viewport_img, use_container_width=False)
        st.markdown('</div>', unsafe_allow_html=True)

        # 3. NAVIGATION & ALIGNMENT
        c_nav1, c_nav2, c_nav3 = st.columns([1, 4, 1])
        with c_nav1: 
            if st.button("〈", key="prev"): 
                st.session_state.img_idx = (st.session_state.img_idx - 1) % len(files)
                st.rerun()
        with c_nav2:
            st.markdown(f"<center><b>{cur_file.name}</b> — {st.session_state.img_idx+1}/{len(files)}</center>", unsafe_allow_html=True)
            st.session_state.align_map[cur_file.name]['x'] = st.slider("X-Axis", 0, 100, st.session_state.align_map[cur_file.name]['x'], key=f"sx_{cur_file.name}")
            st.session_state.align_map[cur_file.name]['y'] = st.slider("Y-Axis", 0, 100, st.session_state.align_map[cur_file.name]['y'], key=f"sy_{cur_file.name}")
        with c_nav3: 
            if st.button("〉", key="next"): 
                st.session_state.img_idx = (st.session_state.img_idx + 1) % len(files)
                st.rerun()

        st.write(" ")

        # 4. CONTROL TOGGLES (REORDERED)
        # --- IMAGE SETTINGS ---
        with st.expander("⚙️ IMAGE SETTINGS", expanded=True):
            s1, s2, s3, s4 = st.columns(4)
            st.session_state.cust_w = s1.number_input("Width", value=st.session_state.cust_w, step=1)
            st.session_state.cust_h = s2.number_input("Height", value=st.session_state.cust_h, step=1)
            st.session_state.cust_ext = s3.selectbox("Format", ["WebP", "JPEG"], index=0 if st.session_state.cust_ext=="WebP" else 1)
            st.session_state.cust_q = s4.slider("Quality", 10, 100, st.session_state.cust_q)

        # --- COLOR STUDIO ---
        if st.toggle("🎨 COLOR STUDIO"):
            g = st.session_state.grade_map[cur_file.name]
            with st.container(border=True):
                ca1, ca2 = st.columns([1, 4])
                with ca1:
                    if st.button("✨ AUTO SCAN"):
                        g.update({'exp':1.05, 'cont':1.15, 'sat':1.1})
                        st.rerun()
                    if st.button("🔄 RESET"):
                        st.session_state.grade_map[cur_file.name] = {'temp':0, 'tint':0, 'exp':1.0, 'cont':1.0, 'sat':1.0}
                        st.rerun()
                with ca2:
                    cs1, cs2, cs3 = st.columns(3)
                    g['temp'] = cs1.slider("Temperature", -100, 100, g['temp'], key=f"t_{cur_file.name}")
                    g['tint'] = cs2.slider("Tint", -100, 100, g['tint'], key=f"n_{cur_file.name}")
                    g['exp'] = cs3.slider("Exposure", 0.5, 2.0, g['exp'], key=f"e_{cur_file.name}")
                    cs4, cs5 = st.columns(2)
                    g['cont'] = cs4.slider("Contrast", 0.5, 2.0, g['cont'], key=f"c_{cur_file.name}")
                    g['sat'] = cs5.slider("Saturation", 0.0, 2.0, g['sat'], key=f"s_{cur_file.name}")

        # --- TEMPLATES ---
        selected_specs = []
        if st.toggle("📋 TEMPLATES"):
            cats = sorted(list(set(s.get('category', 'OTHER') for s in st.session_state.specs)))
            for cat in cats:
                st.markdown(f'<p class="cat-header-text">{cat}</p>', unsafe_allow_html=True)
                cat_specs = [s for s in st.session_state.specs if s.get('category') == cat]
                for i in range(0, len(cat_specs), 2):
                    row = cat_specs[i:i+2]
                    cols = st.columns(2)
                    for idx, spec in enumerate(row):
                        with cols[idx]:
                            with st.container(border=True):
                                c_i, c_n, c_s = st.columns([1, 6, 1])
                                c_i.markdown(get_svg_icon(spec['width'], spec['height']), unsafe_allow_html=True)
                                c_n.markdown(f"**{spec['label']}**\n<small>{spec['width']}x{spec['height']} — {spec.get('ext','WebP')}</small>", unsafe_allow_html=True)
                                if c_s.checkbox("", key=f"run_{spec['label']}", label_visibility="collapsed"):
                                    selected_specs.append(spec)

        st.divider()

        # 5. GENERATION
        if st.button("GENERATE BATCH EXPORT", use_container_width=True):
            # Compile the processing list
            process_list = selected_specs + [{"label":"Custom", "width":st.session_state.cust_w, "height":st.session_state.cust_h, "ext":st.session_state.cust_ext, "quality":st.session_state.cust_q}]
            
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "a", zipfile.ZIP_DEFLATED) as zf:
                for f_up in files:
                    img = load_museum_file(f_up)
                    img = apply_ai_grading(img, st.session_state.grade_map.get(f_up.name))
                    bn = re.sub(r'[^a-zA-Z0-9]', '_', os.path.splitext(f_up.name)[0])
                    align = st.session_state.align_map.get(f_up.name, {'x':50, 'y':50})
                    
                    for sp in process_list:
                        out = ImageOps.fit(img, (sp['width'], sp['height']), centering=(align['x']/100, align['y']/100))
                        out_buf = io.BytesIO()
                        fmt = sp.get('ext', 'WebP').upper()
                        if fmt == "JPEG": out.save(out_buf, format="JPEG", quality=sp.get('quality', 95), optimize=True)
                        else: out.save(out_buf, format="WEBP", quality=sp.get('quality', 95))
                        
                        fn = f"PSAM_{bn}_{re.sub(r'[^a-zA-Z0-9]', '_', sp['label'])}.{fmt.lower()}"
                        zf.writestr(fn, out_buf.getvalue())
            
            # Silent Slack Hook
            try:
                import slack_notifier
                slack_notifier.send_notification("GG", st.session_state.proj_name, len(files), process_list)
            except: pass

            st.success(f"Batch Complete: {len(files)} Images processed.")
            st.download_button("DOWNLOAD ZIP PACKAGE", data=zip_buf.getvalue(), file_name=f"{st.session_state.proj_name}.zip", mime="application/zip")

# --- TAB 2: LIBRARY (LOCKED) ---
with tab_lib:
    st.write("### Museum Standards Library")
    # Library management logic remains identical for data consistency
    for idx, spec in enumerate(st.session_state.specs):
        with st.expander(f"{spec.get('category','OTHER')}: {spec['label']}"):
            c1, c2, c3 = st.columns(3)
            nl = c1.text_input("Label", spec['label'], key=f"lib_l_{idx}")
            nw = c2.number_input("Width", value=spec['width'], key=f"lib_w_{idx}")
            nh = c3.number_input("Height", value=spec['height'], key=f"lib_h_{idx}")
            if st.button("Save Changes", key=f"lib_s_{idx}"):
                st.session_state.specs[idx].update({"label":nl, "width":int(nw), "height":int(nh)})
                with open("transformer_specs.json", "w") as f: json.dump({"formats":st.session_state.specs}, f)
                st.rerun()

# --- TAB 3: SETTINGS ---
with tab_set:
    st.session_state.proj_name = st.text_input("Project Export Name", value=st.session_state.proj_name)
    if st.button("WIPE ALL IMAGE MEMORY (CACHE)"):
        st.session_state.align_map = {}
        st.session_state.grade_map = {}
        st.rerun()
