# --- [Sections 1-2 remain LOCKED: Initialization and save_specs_to_disk()] ---

# --- 2. HELPERS (Locked + Restored calculate_ratio) ---
def calculate_ratio(w, h):
    # Safe check to prevent math errors during initialization
    if not w or not h: return "1:1"
    gcd = math.gcd(int(w), int(h))
    return f"{int(w)//gcd}:{int(h)//gcd}"

# ... [get_svg_rect, sanitize, toggle_section - LOCKED] ...

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
        
        if cust_active:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
                # Initialize variables to prevent NameError
                cust_w = c1.number_input("Width", value=1080, key="cust_w")
                cust_h = c2.number_input("Height", value=1080, key="cust_h")
                cust_ext = c3.selectbox("Format", ["WebP", "JPEG"], key="cust_ext")
                cust_q = c4.slider("Export Quality", 10, 100, 95, key="cust_q")

                # --- 3.1.1 NEW: CAPPED LIVE PREVIEW & ALIGNMENT ENGINE ---
                with st.expander("👁️ Preview & Alignment Controls (Vertical/Horizontal Safe)", expanded=False):
                    
                    # Target aspect ratio based on user input
                    target_ratio_str = calculate_ratio(cust_w, cust_h)
                    t_w, t_h = map(int, target_ratio_str.split(':'))
                    target_aspect_float = t_w / t_h
                    
                    # DYNAMIC PROPORTIONAL CONSTRAINT:
                    # Establish a safe bounding box (500x500 max) to prevent layout break
                    max_ui_dim = 500
                    if target_aspect_float > 1: # Horizontal/Square
                        safe_ui_w = max_ui_dim
                        safe_ui_h = int(max_ui_dim / target_aspect_float)
                    else: # Vertical
                        safe_ui_h = max_ui_dim
                        safe_ui_w = int(max_ui_dim * target_aspect_float)

                    # Wrap columns in a div so CSS can target them for padding/wrapping
                    st.markdown('<div class="flex-container">', unsafe_allow_html=True)
                    pcol_img, pcol_ctrl = st.columns([1, 1]) 
                    
                    with pcol_ctrl:
                        st.markdown('<div class="preview-controls-box">', unsafe_allow_html=True)
                        st.write("**Alignment Controls**")
                        
                        # Apply unique keys using the format label to prevent state collision
                        unique_k = f"cust_custom"
                        preset = st.radio("Quick Presets", ["Center", "Top", "Bottom", "Left", "Right", "Manual"], horizontal=True, key=f"pre_{unique_k}")
                        
                        # Logic for presets (0.5 is center, 0.0 is top/left, 1.0 is bottom/right)
                        if preset == "Center": def_x, def_y = 50, 50
                        elif preset == "Top": def_x, def_y = 50, 0
                        elif preset == "Bottom": def_x, def_y = 50, 100
                        elif preset == "Left": def_x, def_y = 0, 50
                        elif preset == "Right": def_x, def_y = 100, 50
                        else: def_x, def_y = 50, 50

                        # UPDATED: Surgical Precision Sliders with descriptive labels
                        sl_x = st.slider("Left ← Alignment → Right", 0, 100, def_x, key=f"slx_{unique_k}")
                        sl_y = st.slider("Top ← Alignment → Bottom", 0, 100, def_y, key=f"sly_{unique_k}")
                        
                        final_cx, final_cy = sl_x / 100, sl_y / 100
                        st.markdown('</div>', unsafe_allow_html=True)

                    with pcol_img:
                        st.markdown('<div class="preview-image-box">', unsafe_allow_html=True)
                        
                        # Preview the first image only for alignment setting
                        preview_img_obj = Image.open(uploaded_files[0]).convert("RGB")
                        
                        # Generate the live crop using Pil's dynamic positioning (centering)
                        live_crop = ImageOps.fit(preview_img_obj, (cust_w, cust_h), method=Image.Resampling.LANCZOS, centering=(final_cx, final_cy))
                        
                        # Display constrained image: uses calculate_ratio for correct bounding box
                        # We use explicit width/height to force the 500px safe constraint
                        st.image(live_crop, width=safe_ui_w, caption=f"Proportional Preview ({target_ratio_str})")
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                    st.markdown('</div>', unsafe_allow_html=True) # Closing flex-container
            
            # Add to export batch immediately if toggled on
            selected_formats.append({
                "label": "Custom", "width": cust_w, "height": cust_h, 
                "ext": cust_ext, "quality": cust_q, 
                "cx": final_cx, "cy": final_cy # CRITICAL: Passing manual alignment data
            })
        else:
            # Safe defaults if not touching custom settings
            final_cx, final_cy = 0.5, 0.5
            cust_w, cust_h, cust_ext, cust_q = 1080, 1080, "WebP", 95

        # 3.2 TEMPLATES TOGGLE (LOCKED)
        st.write(" ")
        show_templates = st.toggle("Templates", value=False)
        
        # ... [Rest of the loop: Templates, Divider, Generate button - LOCKED] ...
