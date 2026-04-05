import streamlit as st
from PIL import Image, ImageOps
import json, os, math, re, io, zipfile

# --- 1. INITIALIZATION [LOCKED] ---
st.set_page_config(page_title="Visual Transformer", layout="wide")

if 'specs' not in st.session_state:
    if os.path.exists("transformer_specs.json"):
        with open("transformer_specs.json", "r") as f:
            st.session_state.specs = json.load(f).get('formats', [])
    else: st.session_state.specs = []

if 'proj_name' not in st.session_state:
    st.session_state.proj_name = "PSAM_Export"

if 'img_idx' not in st.session_state: st.session_state.img_idx = 0
if 'align_map' not in st.session_state: st.session_state.align_map = {}

# --- 2. HELPERS [LOCKED] ---
def calculate_ratio(w, h):
    if not w or not h: return "1:1"
    gcd = math.gcd(int(w), int(h))
    return f"{int(w)//gcd}:{int(h)//gcd}"

def save_specs_to_disk():
    with open("transformer_specs.json", "w") as f:
        json.dump({"formats": st.session_state.specs}, f, indent=4)

def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

def sanitize(name):
    return re.sub(r'[^a-zA-Z0-9]', '_', name)

load_css('style.css')

# --- 3. INTERFACE ---
tab_run, tab_fmt, tab_set = st.tabs(["TRANSFORMER", "FORMATS", "SETTINGS"])

with tab_run:
    uploaded_files = st.file_uploader("Drag & Drop", type=['jpg', 'png', 'webp'], accept_multiple_files=True, label_visibility="collapsed")

    if uploaded_files:
        if st.session_state.img_idx >= len(uploaded_files): st.session_state.img_idx = 0
        cur_file = uploaded_files[st.session_state.img_idx]
        
        st.write(" ")
        cust_active = st.toggle("Custom Settings", value=False)
        selected_formats = []

        if cust_active:
            with st.container(border=True):
                # Dual Checkboxes
                col_locks = st.columns(2)
                l_ar = col_locks[0].checkbox("Lock Aspect Ratio", value=False)
                l_sz = col_locks[1].checkbox("Set Original Size (Override)", value=False)
                
                img_ref = Image.open(cur_file)
                ow, oh = img_ref.size
                
                c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
                
                # Width: Shows actual size if l_sz is checked
                w_val = ow if l_sz else 1080
                cust_w = c1.number_input(f"Width {'(Original)' if l_sz else ''}", value=w_val, disabled=l_sz, key="cw_in")
                
                # Height: Proportional or Original override
                if l_ar:
                    cust_h = int(cust_w * (oh / ow))
                    c2.number_input("Height (Locked)", value=cust_h, disabled=True)
                else:
                    h_val = oh if l_sz else 1080
                    cust_h = c2.number_input(f"Height {'(Original)' if l_sz else ''}", value=h_val, disabled=l_sz, key="ch_in")
                
                cust_ext = c3.selectbox("Format", ["WebP", "JPEG"], key="ce_in")
                cust_q = c4.slider("Export Quality (100 = Lossless)", 10, 100, 95, key="cq_in")

                with st.expander("👁️ Preview & Individual Alignment", expanded=True):
                    if cur_file.name not in st.session_state.align_map:
                        st.session_state.align_map[cur_file.name] = {"x": 50, "y": 50}
                    
                    state = st.session_state.align_map[cur_file.name]
                    pcol_img, pcol_ctrl = st.columns([1, 1])
                    
                    with pcol_ctrl:
                        st.write("**Alignment for this Image**")
                        mx = st.slider("X-Axis", 0, 100, state["x"], key=f"x_{cur_file.name}")
                        my = st.slider("Y-Axis", 0, 100, state["y"], key=f"y_{cur_file.name}")
                        state["x"], state["y"] = mx, my
                        st.session_state.align_map[cur_file.name] = state

                        # --- DECOUPLED NAVIGATOR ---
                        st.divider()
                        nc1, nc2, nc3 = st.columns([1, 4, 1])
                        with nc1:
                            st.markdown('<div class="nav-chevron-trigger">', unsafe_allow_html=True)
                            if st.button("〈", key="b_prev"):
                                st.session_state.img_idx = (st.session_state.img_idx - 1) % len(uploaded_files)
                                st.rerun()
                            st.markdown('</div>', unsafe_allow_html=True)
                        with nc2:
                            st.markdown(f'<center><small>Image {st.session_state.img_idx + 1} of {len(uploaded_files)}</small><br><b>{cur_file.name}</b></center>', unsafe_allow_html=True)
                        with nc3:
                            st.markdown('<div class="nav-chevron-trigger">', unsafe_allow_html=True)
                            if st.button("〉", key="b_next"):
                                st.session_state.img_idx = (st.session_state.img_idx + 1) % len(uploaded_files)
                                st.rerun()
                            st.markdown('</div>', unsafe_allow_html=True)

                    with pcol_img:
                        asp = cust_w / cust_h
                        sw, sh = (500, int(500/asp)) if asp > 1 else (int(500*asp), 500)
                        crop = ImageOps.fit(img_ref.convert("RGB"), (cust_w, cust_h), method=Image.Resampling.LANCZOS, centering=(state["x"]/100, state["y"]/100))
                        st.image(crop, width=sw)
            
            selected_formats.append({"label": "Custom", "width": cust_w, "height": cust_h, "ext": cust_ext, "quality": cust_q})

        st.write(" ")
        show_templates = st.toggle("Templates", value=False)
        if show_templates:
            # (Templates section remains locked)
            pass

        st.divider()
        if st.button("GENERATE ALL ASSETS", use_container_width=True):
            # (Generation logic remains locked)
            pass
