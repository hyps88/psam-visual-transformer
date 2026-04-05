import streamlit as st
from PIL import Image, ImageOps
import json, os, math, re, io
from datetime import datetime

# --- CORE LOGIC (REUSED FROM V1.7) ---
def calculate_ratio(w, h):
    """ Simplifies dimensions to ratio """
    gcd = math.gcd(w, h)
    return f"{w//gcd}:{h//gcd}"

def load_specs():
    """ Loads your museum format standards """
    with open("transformer_specs.json", "r") as f:
        return json.load(f)

# --- WEB APP UI ---
st.set_page_config(page_title="PSAM Visual Transformer", page_icon="🖼️", layout="wide")

st.markdown("# 🖼️ PSAM Visual Transformer")
st.write("Upload a master image to generate all museum-standard formats instantly.")

# 1. Sidebar - Upload
st.sidebar.header("1. Source Image")
uploaded_file = st.sidebar.file_uploader("Choose a high-res photo...", type=['jpg', 'jpeg', 'png', 'webp', 'tiff'])

# 2. Main Area - Selection
specs = load_specs()
st.header("2. Select Formats")

# Categorize into Columns
col1, col2, col3 = st.columns(3)
selected_specs = []

with col1:
    st.subheader("📱 SOCIAL")
    for item in [s for s in specs['formats'] if s['category'] == "SOCIAL"]:
        if st.checkbox(f"{item['label']} ({item['ratio']})", value=True, key=item['label']):
            selected_specs.append(item)

with col2:
    st.subheader("🌐 WEB")
    for item in [s for s in specs['formats'] if s['category'] == "WEB"]:
        if st.checkbox(f"{item['label']} ({item['ratio']})", value=True, key=item['label']):
            selected_specs.append(item)

with col3:
    st.subheader("📧 EMAIL")
    for item in [s for s in specs['formats'] if s['category'] == "EMAIL"]:
        if st.checkbox(f"{item['label']} ({item['ratio']})", value=True, key=item['label']):
            selected_specs.append(item)

# 3. Execution
if uploaded_file and st.button("🚀 GENERATE ASSETS", use_container_width=True):
    st.divider()
    with st.spinner("Transforming assets..."):
        # Load image once
        img = Image.open(uploaded_file)
        if img.mode != 'RGB': img = img.convert('RGB')
        
        # We will zip the results for easy download
        import zipfile
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for spec in selected_specs:
                # Apply V1.7 Smart-Crop
                res = ImageOps.fit(img, (spec['width'], spec['height']), Image.Resampling.LANCZOS)
                
                # Sanitize filename
                safe_label = re.sub(r'[^a-zA-Z0-9]', '_', spec['label'])
                f_name = f"PSAM_{safe_label}.{spec['ext'].lower()}"
                
                # Save to memory buffer instead of disk
                img_buffer = io.BytesIO()
                if spec['ext'].upper() == "JPEG":
                    res.save(img_buffer, format="JPEG", quality=spec['quality'])
                else:
                    res.save(img_buffer, format="WEBP", quality=spec['quality'])
                
                zip_file.writestr(f_name, img_buffer.getvalue())
        
        st.success(f"✅ Successfully created {len(selected_specs)} assets!")
        st.download_button(
            label="📂 DOWNLOAD ZIP FOLDER",
            data=zip_buffer.getvalue(),
            file_name=f"PSAM_Assets_{datetime.now().strftime('%Y%m%d')}.zip",
            mime="application/zip"
        )