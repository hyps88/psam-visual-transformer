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

def toggle_section(category_name):
    master_state = st.session_state[f"master_{category_name}"]
    for spec in st.session_state.specs:
        if spec.get('category') == category_name:
            st.session_state[f"run_{spec['label']}"] = master_state

load_css('style.css')

# --- 3. INTERFACE ---
tab_run, tab_fmt, tab_set = st.tabs(["TRANSFORMER", "FORMATS", "SETTINGS"])

with tab_run:
    uploaded_files = st.file_uploader("Drag & Drop", type=['jpg', 'png', 'webp'], accept_multiple_files=True, label_visibility="collapsed")

    if uploaded_files:
        if st.session_state.img_idx >= len(uploaded_files): st.session_state.img_idx = 0
        cur_img_file = uploaded_files[st.session_state.img_idx]
        
        st.write(" ")
        cust_active = st.toggle("Custom Settings", value=False)
        selected_formats = []

        if cust_active:
            with st.container(border=True):
                # --- SEPARATED CONTROLS ---
                col_locks = st.columns(2)
                with col_locks[0]:
                    lock_ar = st.checkbox("Lock Aspect Ratio", value=False, key="lock_ar")
                with col_locks[1]:
                    lock_size = st.checkbox("Set Original Size", value=False, key="lock_size")
                
                orig_img_ref = Image.open(cur_img_file)
                ow, oh = orig_img_ref.size
                
                c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
                
                # Logic for Width
                val_w = ow if lock_size else 1080
                cust_w = c1.number_input("Width", value=val_w, key="cust_w_input")
                
                # Logic for Height
                if lock_ar:
                    cust_h = int(cust_w * (oh / ow))
                    c2.number_input("Height (Locked)", value=cust_h, disabled=True, key="cust_h_locked")
                elif lock_size:
                    cust_h = c2.number_input("Height", value=oh, key="cust_h_orig")
                else:
                    cust_h = c2.number_input("Height", value=1080, key="cust_h_manual")
                
                cust_ext = c3.selectbox("Format", ["WebP", "JPEG"], key="cust_ext")
                cust_q = c4.slider("Export Quality (100 = Lossless)", 10, 100, 95, key="cust_q")

                with st.expander("👁️ Preview & Individual Alignment", expanded=True):
                    # --- ALIGNMENT STATE SYNC ---
                    if cur_img_file.name not in st.session_state.align_map:
                        st.session_state.align_map[cur_img_file.name] = {"x": 50, "y": 50, "preset": "Center"}
                    state = st.session_state.align_map[cur_img_file.name]

                    pcol_img, pcol_ctrl = st.columns([1, 1])
                    
                    with pcol_ctrl:
                        st.write("**Alignment for this Image**")
                        preset = st.radio("Quick Presets", ["Center", "Top", "Bottom", "Left", "Right", "Manual"], 
                                          index=["Center", "Top", "Bottom", "Left", "Right", "Manual"].index(state["preset"]),
                                          horizontal=True, key=f"pre_{cur_img_file.name}")
                        
                        # Handle Preset Selection
                        if preset != state["preset"] and preset != "Manual":
                            if preset == "Center": state["x"], state["y"] = 50, 50
                            elif preset == "Top": state["x"], state["y"] = 50, 0
                            elif preset == "Bottom": state["x"], state["y"] = 50, 100
                            elif preset == "Left": state["x"], state["y"] = 0, 50
                            elif preset == "Right": state["x"], state["y"] = 100, 50
                            state["preset"] = preset

                        mx = st.slider("Left ← Alignment → Right", 0, 100, state["x"], key=f"mx_{cur_img_file.name}")
                        my = st.slider("Top ← Alignment → Bottom", 0, 100, state["y"], key=f"my_{cur_img_file.name}")
                        
                        # Check if user moved sliders
                        if mx != state["x"] or my != state["y"]:
                            state["x"], state["y"] = mx, my
                            state["preset"] = "Manual"
                        
                        st.session_state.align_map[cur_img_file.name] = state

                        # --- MINIMALIST CHEVRON NAV ---
                        st.divider()
                        nc1, nc2, nc3 = st.columns([1, 4, 1])
                        with nc1:
                            st.markdown('<div class="nav-link">', unsafe_allow_html=True)
                            if st.button("〈", key="prev_img"): # Using Chevron character
                                st.session_state.img_idx = (st.session_state.img_idx - 1) % len(uploaded_files)
                                st.rerun()
                            st.markdown('</div>', unsafe_allow_html=True)
                        with nc2:
                            st.markdown(f'<div class="img-info-text"><center>Image {st.session_state.img_idx + 1} of {len(uploaded_files)}<br><b>{cur_img_file.name}</b></center></div>', unsafe_allow_html=True)
                        with nc3:
                            st.markdown('<div class="nav-link">', unsafe_allow_html=True)
                            if st.button("〉", key="next_img"): # Using Chevron character
                                st.session_state.img_idx = (st.session_state.img_idx + 1) % len(uploaded_files)
                                st.rerun()
                            st.markdown('</div>', unsafe_allow_html=True)

                    with pcol_img:
                        aspect_val = cust_w / cust_h
                        sw, sh = (500, int(500/aspect_val)) if aspect_val > 1 else (int(500*aspect_val), 500)
                        crop = ImageOps.fit(orig_img_ref.convert("RGB"), (cust_w, cust_h), method=Image.Resampling.LANCZOS, centering=(state["x"]/100, state["y"]/100))
                        st.image(crop, width=sw, caption=f"Individual Preview ({calculate_ratio(cust_w, cust_h)})")
            
            selected_formats.append({"label": "Custom", "width": cust_w, "height": cust_h, "ext": cust_ext, "quality": cust_q})

        st.write(" ")
        show_templates = st.toggle("Templates", value=False)
        if show_templates:
            # ... (Templates Section - LOCKED) ...
            cats = sorted(list(set(s.get('category', 'OTHER') for s in st.session_state.specs)))
            for cat in cats:
                cat_specs = [s for s in st.session_state.specs if s.get('category') == cat]
                for sp in cat_specs:
                    if st.session_state.get(f"run_{sp['label']}", False):
                        selected_formats.append(sp)

        st.divider()
        if st.button("GENERATE ALL ASSETS", use_container_width=True):
            if selected_formats:
                zip_buffer = io.BytesIO()
                total_steps = len(uploaded_files) * len(selected_formats)
                current_step = 0
                progress_bar = st.progress(0)
                status_text = st.empty()

                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zf:
                    for up in uploaded_files:
                        img = Image.open(up).convert("RGB")
                        bn = sanitize(os.path.splitext(up.name)[0])
                        align = st.session_state.align_map.get(up.name, {"x": 50, "y": 50})

                        for sp in selected_formats:
                            current_step += 1
                            progress_bar.progress(min(int((current_step / total_steps) * 100), 100))
                            status_text.text(f"Processing: {bn} — {sp['label']}")
                            
                            t_cx, t_cy = (align["x"]/100, align["y"]/100) if sp['label'] == "Custom" else (0.5, 0.5)
                            res = ImageOps.fit(img, (sp['width'], sp['height']), method=Image.Resampling.LANCZOS, centering=(t_cx, t_cy))
                            
                            fn = f"PSAM_{bn}_{sanitize(sp['label'])}_{sp['width']}x{sp['height']}.{sp.get('ext','webp').lower()}"
                            buf = io.BytesIO()
                            if sp.get('ext') == "JPEG":
                                res.save(buf, format="JPEG", quality=sp.get('quality', 95), subsampling=0 if sp.get('quality')==100 else 2, optimize=True)
                            else:
                                res.save(buf, format="WEBP", quality=sp.get('quality', 95), lossless=(sp.get('quality')==100), method=4)
                            zf.writestr(fn, buf.getvalue())
                
                status_text.text("Export Ready!")
                st.success("Batch Generated."); st.download_button("DOWNLOAD ZIP", data=zip_buffer.getvalue(), file_name=f"{sanitize(st.session_state.proj_name)}.zip", mime="application/zip")

# --- TAB 2 & 3: FORMATS & SETTINGS [LOCKED] ---
# ... (Preserve exactly from your last script) ...
