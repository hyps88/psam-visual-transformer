import streamlit as st
from PIL import Image, ImageOps
import json, os, math, re, io, zipfile

# --- 1. INITIALIZATION [LOCKED] ---
st.set_page_config(page_title="Visual Transformer", layout="wide")

if 'specs' not in st.session_state:
    if os.path.exists("transformer_specs.json"):
        with open("transformer_specs.json", "r") as f:
            st.session_state.specs = json.load(f).get('formats', [])
    else:
        st.session_state.specs = []

if 'proj_name' not in st.session_state:
    st.session_state.proj_name = "PSAM_Export"

# --- 2. HELPERS [LOCKED] ---
def calculate_ratio(w, h):
    # Safety check for ratio calculation
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

def get_svg_rect(ratio_str):
    try:
        r_w, r_h = map(int, ratio_str.split(":")); max_d = 35
        w, h = (max_d, int(max_d*(r_h/r_w))) if r_w > r_h else (int(max_d*(r_w/r_h)), max_d)
        return f'<svg width="45" height="45"><rect x="{(45-w)/2}" y="{(45-h)/2}" width="{w}" height="{h}" fill="none" stroke="#f36e2e" stroke-width="2.5"/></svg>'
    except: return ""

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
    uploaded_files = st.file_uploader("Drag & Drop Images Here", type=['jpg', 'png', 'webp'], accept_multiple_files=True, label_visibility="collapsed")

    if uploaded_files:
        st.write(" ")
        
        # 3.1 CUSTOM SETTINGS TOGGLE (Default OFF)
        cust_active = st.toggle("Custom Settings", value=False)
        selected_formats = []
        
        # Safe Defaults if not touching custom settings
        final_cx, final_cy = 0.5, 0.5
        cust_w, cust_h, cust_ext, cust_q = 1080, 1080, "WebP", 95

        if cust_active:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
                cust_w = c1.number_input("Width", value=1080, key="cust_w")
                cust_h = c2.number_input("Height", value=1080, key="cust_h")
                cust_ext = c3.selectbox("Format", ["WebP", "JPEG"], key="cust_ext")
                cust_q = c4.slider("Export Quality", 10, 100, 95, key="cust_q")

                # --- 3.1.1 NEW: VISUAL POSITIONING ENGINE ---
                # Default closed to save space. We preview the FIRST image in the batch.
                with st.expander("👁️ Preview & Alignment Controls", expanded=False):
                    
                    # Proportional Bounding Box logic: Constraints at 500x500 max
                    try: aspect_ratio = cust_w / cust_h
                    except ZeroDivisionError: aspect_ratio = 1.0 # Safe default
                    
                    max_dim = 500
                    if aspect_ratio > 1: # Horizontal
                        safe_w, safe_h = max_dim, int(max_dim / aspect_ratio)
                    else: # Vertical or Square
                        safe_h, safe_w = max_dim, int(max_dim * aspect_ratio)

                    # Wrap columns in a custom CSS class for flex layout
                    st.markdown('<div class="flex-container">', unsafe_allow_html=True)
                    pcol_img, pcol_ctrl = st.columns([1, 1]) 
                    
                    with pcol_ctrl:
                        # Add a unique box wrapper for CSS padding logic
                        st.markdown('<div class="preview-controls-box">', unsafe_allow_html=True)
                        st.write("**Alignment Controls**")
                        preset = st.radio("Quick Presets", ["Center", "Top", "Bottom", "Left", "Right", "Manual"], horizontal=True)
                        
                        # Set default values based on preset
                        if preset == "Center": def_x, def_y = 50, 50
                        elif preset == "Top": def_x, def_y = 50, 0
                        elif preset == "Bottom": def_x, def_y = 50, 100
                        elif preset == "Left": def_x, def_y = 0, 50
                        elif preset == "Right": def_x, def_y = 100, 50
                        else: def_x, def_y = 50, 50

                        # Normalized coordinates (0.5 is center, 0.0 is top/left, 1.0 is bottom/right)
                        sl_x = st.slider("Left ← Alignment → Right", 0, 100, def_x)
                        sl_y = st.slider("Top ← Alignment → Bottom", 0, 100, def_y)
                        
                        final_cx, final_cy = sl_x / 100, sl_y / 100
                        st.markdown('</div>', unsafe_allow_html=True)

                    with pcol_img:
                        st.markdown('<div class="preview-image-box">', unsafe_allow_html=True)
                        
                        # Open only the first image to minimize memory load
                        preview_img_obj = Image.open(uploaded_files[0]).convert("RGB")
                        
                        # Generate the crop using Pil's robust fit method
                        live_crop = ImageOps.fit(preview_img_obj, (cust_w, cust_h), method=Image.Resampling.LANCZOS, centering=(final_cx, final_cy))
                        
                        # Constraint logic: Image stays within safe bounding box and resizes with the container
                        st.image(live_crop, width=safe_w, caption=f"Proportional Preview ({calculate_ratio(cust_w, cust_h)})")
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                    st.markdown('</div>', unsafe_allow_html=True) # Closing flex-container
            
            # Add to export batch immediately if toggled on
            selected_formats.append({
                "label": "Custom", "width": cust_w, "height": cust_h, 
                "ext": cust_ext, "quality": cust_q, 
                "cx": final_cx, "cy": final_cy # Pass the visual data
            })

        # 3.2 TEMPLATES TOGGLE [LOCKED]
        st.write(" ")
        show_templates = st.toggle("Templates", value=False)

        if show_templates:
            categories = sorted(list(set(s.get('category', 'OTHER') for s in st.session_state.specs)))
            for category in categories:
                cat_specs = [s for s in st.session_state.specs if s.get('category') == category]
                h_cols = st.columns([0.1, 0.05, 0.85]) 
                with h_cols[0]: st.markdown(f'<p class="cat-header-text" style="padding-top: 5px;">{category}</p>', unsafe_allow_html=True)
                with h_cols[1]: st.checkbox("", value=False, key=f"master_{category}", on_change=toggle_section, args=(category,), label_visibility="collapsed")
                
                for i in range(0, len(cat_specs), 2):
                    row_specs = cat_specs[i:i+2]
                    grid_cols = st.columns(2)
                    for idx, spec in enumerate(row_specs):
                        with grid_cols[idx]:
                            with st.container(border=True):
                                c_icon, c_info, c_check = st.columns([1, 6, 1])
                                with c_icon: st.markdown(get_svg_rect(spec['ratio']), unsafe_allow_html=True)
                                with c_info:
                                    st.markdown(f'<div class="card-label">{spec["label"]}</div>', unsafe_allow_html=True)
                                    sub_text = f"{spec['width']}x{spec['height']} — {spec.get('ext', 'WebP').upper()} @ {spec.get('quality', 85)}%"
                                    st.markdown(f'<div class="card-subline">{sub_text}</div>', unsafe_allow_html=True)
                                with c_check:
                                    # Use the spec data for generation logic only
                                    if st.checkbox("", value=st.session_state.get(f"run_{spec['label']}", False), key=f"run_{spec['label']}", label_visibility="collapsed"):
                                        selected_formats.append(spec)

        st.divider()
        if st.button("GENERATE ALL ASSETS", use_container_width=True):
            if selected_formats:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                    for up_file in uploaded_files:
                        img = Image.open(up_file).convert("RGB")
                        base_n = sanitize(os.path.splitext(up_file.name)[0])
                        for spec in selected_formats:
                            # CRITICAL FIX: The export now correctly uses visual alignment or defaults to center (0.5)
                            cx = spec.get('cx', 0.5); cy = spec.get('cy', 0.5)
                            res = ImageOps.fit(img, (spec['width'], spec['height']), method=Image.Resampling.LANCZOS, centering=(cx, cy))
                            
                            f_ext = spec.get('ext', 'WebP').upper()
                            label_slug = sanitize(spec['label'])
                            f_name = f"PSAM_{label_slug}_{spec['width']}x{spec['height']}.{f_ext.lower()}"
                            
                            img_io = io.BytesIO()
                            if f_ext == "JPEG":
                                res.save(img_io, format="JPEG", quality=spec.get('quality', 95), subsampling=0, optimize=True)
                            else:
                                res.save(img_io, format="WEBP", quality=spec.get('quality', 95), lossless=(spec.get('quality')==100), method=6)
                            
                            zip_file.writestr(f"{base_n}/{f_name}", img_io.getvalue())
                st.success(f"Generated {len(uploaded_files)} image batches."); st.download_button("DOWNLOAD ZIP", data=zip_buffer.getvalue(), file_name=f"{sanitize(st.session_state.proj_name)}.zip", mime="application/zip")

# --- 4. FORMATS & SETTINGS [LOCKED] ---
# ... (Remains LOCKED) ...
