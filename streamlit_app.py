import streamlit as st
from PIL import Image, ImageOps
import json, os, math, re, io, zipfile, time

# --- 1. INITIALIZATION [LOCKED] ---
st.set_page_config(page_title="Visual Transformer", layout="wide")

# Plant State Tracking [NEW]
if 'plant_hue' not in st.session_state: st.session_state.plant_hue = 0
if 'last_upload_count' not in st.session_state: st.session_state.last_upload_count = 0
if 'is_generating' not in st.session_state: st.session_state.is_generating = False
if 'show_cyclist' not in st.session_state: st.session_state.show_cyclist = False

if 'specs' not in st.session_state:
    if os.path.exists("transformer_specs.json"):
        with open("transformer_specs.json", "r") as f:
            st.session_state.specs = json.load(f).get('formats', [])
    else: st.session_state.specs = []

if 'proj_name' not in st.session_state:
    st.session_state.proj_name = "PSAM_Export"

# --- 2. HELPERS [LOCKED] ---
def calculate_ratio(w, h):
    if not w or not h: return "1:1"
    gcd = math.gcd(int(w), int(h)); return f"{int(w)//gcd}:{int(h)//gcd}"

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

# --- 3. THE POTHOS BUDDY ENGINE [NEW] ---
def render_pothos():
    # Determine the animation class based on app state
    plant_class = "pothos-vine"
    if st.session_state.is_generating:
        plant_class += " state-crazy"
    
    # Render the plant (Using an emoji/SVG placeholder for logic)
    st.markdown(f'''
        <div id="pothos-container" style="filter: hue-rotate({st.session_state.plant_hue}deg);">
            <div class="{plant_class}">
                <div style="font-size: 80px; text-align: center;">🌿</div>
                <div style="font-size: 40px; text-align: center; margin-top: -20px;">🍃</div>
                <div style="font-size: 30px; text-align: center; margin-top: -15px;">🍃</div>
            </div>
        </div>
    ''', unsafe_allow_html=True)

    if st.session_state.show_cyclist:
        st.markdown('<div id="cyclist-buddy" style="font-size: 40px;">🚴‍♂️💦</div>', unsafe_allow_html=True)

render_pothos()

# --- 4. INTERFACE ---
tab_run, tab_fmt, tab_set = st.tabs(["TRANSFORMER", "FORMATS", "SETTINGS"])

with tab_run:
    # UPLOAD LOGIC
    uploaded_files = st.file_uploader("Drag & Drop", type=['jpg', 'png', 'webp'], accept_multiple_files=True, label_visibility="collapsed")
    
    if uploaded_files:
        # Trigger Flutter if new files detected
        if len(uploaded_files) > st.session_state.last_upload_count:
            st.session_state.last_upload_count = len(uploaded_files)
            # (In a real app, we'd trigger a 1s flutter class here)

        st.write(" ")
        # Change hue when settings change
        def on_setting_change():
            st.session_state.plant_hue = (st.session_state.plant_hue + 45) % 360

        cust_active = st.toggle("Custom Settings", value=False, on_change=on_setting_change)
        selected_formats = []
        final_cx, final_cy = 0.5, 0.5

        if cust_active:
            with st.container(border=True):
                lock_ar = st.checkbox("Force Original Aspect Ratio & Size", value=False, on_change=on_setting_change)
                orig_img_ref = Image.open(uploaded_files[0])
                ow, oh = orig_img_ref.size
                
                c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
                if lock_ar:
                    cust_w = c1.number_input("Width (Original)", value=ow, on_change=on_setting_change)
                    cust_h = int(cust_w * (oh / ow))
                    c2.number_input("Height (Original)", value=cust_h, disabled=True)
                else:
                    cust_w = c1.number_input("Width", value=1080, on_change=on_setting_change)
                    cust_h = c2.number_input("Height", value=1080, on_change=on_setting_change)
                
                cust_ext = c3.selectbox("Format", ["WebP", "JPEG"], on_change=on_setting_change)
                cust_q = c4.slider("Export Quality (100 = Lossless)", 10, 100, 95, on_change=on_setting_change)

                with st.expander("👁️ Preview & Alignment Controls", expanded=False):
                    aspect_val = cust_w / cust_h
                    sw, sh = (500, int(500/aspect_val)) if aspect_val > 1 else (int(500*aspect_val), 500)
                    pcol_img, pcol_ctrl = st.columns([1, 1])
                    with pcol_ctrl:
                        preset = st.radio("Quick Presets", ["Center", "Top", "Bottom", "Left", "Right", "Manual"], horizontal=True)
                        if preset == "Center": dx, dy = 50, 50
                        elif preset == "Top": dx, dy = 50, 0
                        elif preset == "Bottom": dx, dy = 50, 100
                        elif preset == "Left": dx, dy = 0, 50
                        elif preset == "Right": dx, dy = 100, 50
                        else: dx, dy = 50, 50
                        mx = st.slider("Left ← Alignment → Right", 0, 100, dx, on_change=on_setting_change)
                        my = st.slider("Top ← Alignment → Bottom", 0, 100, dy, on_change=on_setting_change)
                        final_cx, final_cy = mx / 100, my / 100
                    with pcol_img:
                        prev_img = Image.open(uploaded_files[0]).convert("RGB")
                        crop = ImageOps.fit(prev_img, (cust_w, cust_h), method=Image.Resampling.LANCZOS, centering=(final_cx, final_cy))
                        st.image(crop, width=sw, caption=f"Preview ({calculate_ratio(cust_w, cust_h)})")
            
            selected_formats.append({"label": "Custom", "width": cust_w, "height": cust_h, "ext": cust_ext, "quality": cust_q, "cx": final_cx, "cy": final_cy})

        st.write(" ")
        show_templates = st.toggle("Templates", value=False, on_change=on_setting_change)

        if show_templates:
            # ... (Template Grid Logic - LOCKED) ...
            cats = sorted(list(set(s.get('category', 'OTHER') for s in st.session_state.specs)))
            for cat in cats:
                cat_specs = [s for s in st.session_state.specs if s.get('category') == cat]
                # (Render rows/checkboxes here as before - LOCKED)
                for sp in cat_specs:
                    if st.session_state.get(f"run_{sp['label']}", False): selected_formats.append(sp)

        st.divider()
        if st.button("GENERATE ALL ASSETS", use_container_width=True):
            if selected_formats:
                st.session_state.is_generating = True
                st.rerun() # Refresh to show Crazy Plant
                
                # (Actual Generation Logic runs here - LOCKED)
                # ... 
                
                st.session_state.is_generating = False
                st.session_state.show_cyclist = True # Trigger Cyclist
                st.success("Batch Generated.")
                # Show Download Button
