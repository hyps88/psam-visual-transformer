import streamlit as st
import json, io, zipfile, os
from engine import MuseumEngine

# --- APP CONFIG & THEME ---
st.set_page_config(page_title="PSAM Visual Transformer Ultra", layout="wide")
st.markdown("""
    <style>
    .viewport { height: 500px; background: #050505; display: flex; align-items: center; justify-content: center; border-radius: 12px; border: 2px solid #222; position: relative; overflow: hidden; }
    .insta-overlay { position: absolute; border: 2px dashed rgba(243, 110, 46, 0.5); pointer-events: none; }
    .stButton>button { border-radius: 2px; text-transform: uppercase; letter-spacing: 1px; font-size: 11px; background: #1a1a1a; border: 1px solid #333; }
    </small></style>
""", unsafe_allow_html=True)

# --- STATE INITIALIZATION ---
if 'db' not in st.session_state:
    st.session_state.db = {"templates": [], "aligns": {}, "tags": {}}
if 'lib' not in st.session_state:
    st.session_state.lib = [] # Current batch images

# --- SIDEBAR: LIBRARY & JSON ---
with st.sidebar:
    st.title("PSAM ASSETS")
    json_file = st.file_uploader("Import JSON Configuration", type=['json'])
    if json_file:
        st.session_state.db = json.load(json_file)
    
    st.download_button("Export JSON Configuration", 
                       data=json.dumps(st.session_state.db), 
                       file_name="psam_config.json")
    
    st.divider()
    watermark = st.file_uploader("Brand Watermark (PNG)", type=['png'])
    upscale = st.checkbox("Museum Signage (2x AI Upscale)")
    safe_zone = st.checkbox("Insta Safe-Zone Overlay")

# --- MAIN INTERFACE ---
files = st.file_uploader("UPLOAD BATCH", type=['jpg','png','webp','arw','cr2','nef','dng'], accept_multiple_files=True)

if files:
    idx = st.select_slider("Select Image", options=range(len(files)), format_func=lambda i: files[i].name)
    cur = files[idx]
    
    # Load via Engine
    img_raw = MuseumEngine.load(cur)
    
    # 1. VIEWPORT & SAFE ZONE
    st.markdown('<div class="viewport">', unsafe_allow_html=True)
    
    # Preview with current settings
    w_prev = st.number_input("Target W", value=1080, key="tw")
    h_prev = st.number_input("Target H", value=1080, key="th")
    
    align = st.session_state.db['aligns'].get(cur.name, {'x':50, 'y':50})
    preview = MuseumEngine.process(img_raw, {'w':w_prev, 'h':h_prev}, align)
    
    st.image(preview, use_container_width=False)
    
    if safe_zone:
        # Visual representation of Insta UI "dead zones"
        st.markdown('<div class="insta-overlay" style="width:100%; height:20%; top:0;"></div>', unsafe_allow_html=True)
        st.markdown('<div class="insta-overlay" style="width:100%; height:25%; bottom:0;"></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 2. CONTROLS
    c1, c2 = st.columns([2, 1])
    with c1:
        st.session_state.db['aligns'][cur.name] = {
            'x': st.slider("X Alignment", 0, 100, align['x'], key=f"x{idx}"),
            'y': st.slider("Y Alignment", 0, 100, align['y'], key=f"y{idx}")
        }
        
        # TAGGING SYSTEM
        st.subheader("Metadata")
        tags = st.session_state.db['tags'].get(cur.name, "")
        st.session_state.db['tags'][cur.name] = st.text_area("Manual Tags / Alt Text", value=tags)
        
        if st.button("Auto-Tag with AI"):
            # Placeholder for Google Vision / OpenAI Satellite
            st.session_state.db['tags'][cur.name] = "Modernism, Palm Springs, Architecture, Desert, PSAM Collection"
            st.rerun()

    with c2:
        st.subheader("Export Specs")
        custom_name = st.text_input("Custom Filename Override", placeholder="Artist_Title_Year")
        ext = st.selectbox("Format", ["PNG", "WebP", "JPEG"])
        q = st.slider("Quality", 10, 100, 95)
        
        # FILE SIZE PREVIEW
        kb = MuseumEngine.get_size(preview, ext, q)
        st.metric("Estimated Size", f"{kb:.1f} KB")

    # 3. TEMPLATE MANAGER
    st.divider()
    st.subheader("Template Library")
    with st.expander("Manage Templates"):
        t_name = st.text_input("Template Name")
        t_w = st.number_input("W", 100)
        t_h = st.number_input("H", 100)
        if st.button("Add to Library"):
            st.session_state.db['templates'].append({'name': t_name, 'w': t_w, 'h': t_h})
            st.rerun()
        
        for i, t in enumerate(st.session_state.db['templates']):
            st.write(f"**{t['name']}** ({t['w']}x{t['h']})")
            if st.button(f"Delete {i}", key=f"del{i}"):
                st.session_state.db['templates'].pop(i)
                st.rerun()

    # 4. FINAL EXPORT
    if st.button("PROCESS ALL ASSETS", type="primary", use_container_width=True):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for f in files:
                f_img = MuseumEngine.load(f)
                f_align = st.session_state.db['aligns'].get(f.name, {'x':50, 'y':50})
                
                # Use custom name or original
                prefix = custom_name if custom_name else f.name.split('.')[0]
                
                # Process for current settings
                final = MuseumEngine.process(f_img, {'w':w_prev, 'h':h_prev}, f_align, watermark, upscale)
                
                buf = io.BytesIO()
                final.save(buf, format=ext, quality=q)
                zf.writestr(f"{prefix}_{ext}.{ext.lower()}", buf.getvalue())
        
        st.download_button("Download Zip", data=zip_buffer.getvalue(), file_name="PSAM_Export.zip")
