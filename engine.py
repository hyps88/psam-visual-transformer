import io
from PIL import Image, ImageOps, ImageCms
import rawpy

class MuseumEngine:
    @staticmethod
    def load(file):
        ext = file.name.split('.')[-1].lower()
        if ext in ['arw', 'cr2', 'nef', 'dng']:
            with rawpy.imread(file) as raw:
                return Image.fromarray(raw.postprocess(use_camera_wb=True))
        return Image.open(file).convert("RGBA") # Always RGBA for transparency

    @staticmethod
    def process(img, spec, align, watermark=None, upscale=False):
        # 1. DPI Upscale (Museum Signage)
        if upscale:
            img = img.resize((img.width * 2, img.height * 2), Image.Resampling.LANCZOS)
        
        # 2. Color Profile Check (Force sRGB for Web)
        if "icc_profile" in img.info:
            img = ImageOps.exif_transpose(img)

        # 3. Professional Crop
        target_size = (spec['w'], spec['h'])
        out = ImageOps.fit(img, target_size, centering=(align['x']/100, align['y']/100))

        # 4. Watermark Injection
        if watermark:
            wm = Image.open(watermark).convert("RGBA")
            wm.thumbnail((out.width // 4, out.height // 4))
            out.paste(wm, (out.width - wm.width - 20, out.height - wm.height - 20), wm)

        return out

    @staticmethod
    def get_size(img, fmt, quality):
        buf = io.BytesIO()
        img.save(buf, format=fmt, quality=quality)
        return len(buf.getvalue()) / 1024 # KB
