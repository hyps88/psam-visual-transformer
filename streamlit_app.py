from __future__ import annotations

import io
import json
import math
import re
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

APP_TITLE = "Visual Transformer"
DEFAULT_PROJECT_NAME = "PSAM_Export"
SPECS_FILE = Path("transformer_specs.json")
CSS_FILE = Path("style.css")
ALLOWED_UPLOAD_TYPES = ["jpg", "jpeg", "png", "webp"]
EXPORT_TYPES = ["WebP", "JPEG"]


@dataclass
class FormatSpec:
    category: str
    label: str
    width: int
    height: int
    ext: str = "WebP"
    quality: int = 95

    def normalized(self) -> "FormatSpec":
        category = (self.category or "OTHER").strip().upper()
        label = (self.label or "Untitled").strip()
        width = max(1, int(self.width))
        height = max(1, int(self.height))
        ext = normalize_export_type(self.ext)
        quality = max(10, min(100, int(self.quality)))
        return FormatSpec(
            category=category,
            label=label,
            width=width,
            height=height,
            ext=ext,
            quality=quality,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "FormatSpec":
        return cls(
            category=str(raw.get("category", "OTHER")),
            label=str(raw.get("label", "Untitled")),
            width=int(raw.get("width", 1080)),
            height=int(raw.get("height", 1080)),
            ext=str(raw.get("ext", "WebP")),
            quality=int(raw.get("quality", 95)),
        ).normalized()


def normalize_export_type(value: str | None) -> str:
    if not value:
        return "WebP"
    value_upper = str(value).strip().upper()
    if value_upper in {"JPG", "JPEG"}:
        return "JPEG"
    return "WebP"


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("._")
    return cleaned or "file"


def aspect_ratio_text(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return "1:1"
    divisor = math.gcd(width, height)
    return f"{width // divisor}:{height // divisor}"


def fit_preview_width(width: int, height: int, max_side: int = 500) -> tuple[int, int]:
    if width <= 0 or height <= 0:
        return max_side, max_side
    ratio = width / height
    if ratio >= 1:
        return max_side, max(1, int(max_side / ratio))
    return max(1, int(max_side * ratio)), max_side


def svg_ratio_box(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return ""

    max_dim = 40
    if width >= height:
        box_w = max_dim
        box_h = max(8, int(max_dim * (height / width)))
    else:
        box_h = max_dim
        box_w = max(8, int(max_dim * (width / height)))

    return f"""
    <div style="display:flex;align-items:center;justify-content:center;height:42px;">
        <svg width="{box_w + 8}" height="{box_h + 8}" viewBox="0 0 {box_w + 8} {box_h + 8}">
            <rect x="4" y="4" width="{box_w}" height="{box_h}" rx="3" ry="3"
                  fill="none" stroke="currentColor" stroke-width="2"/>
        </svg>
    </div>
    """


def load_css() -> None:
    if CSS_FILE.exists():
        st.markdown(f"<style>{CSS_FILE.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def default_specs_payload() -> dict[str, list[dict[str, Any]]]:
    return {"formats": []}


def load_specs_from_disk() -> list[FormatSpec]:
    if not SPECS_FILE.exists():
        return []

    try:
        payload = json.loads(SPECS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        st.warning("Could not read transformer_specs.json. Starting with an empty library.")
        return []

    raw_formats = payload.get("formats", [])
    parsed: list[FormatSpec] = []

    if not isinstance(raw_formats, list):
        return []

    for item in raw_formats:
        if not isinstance(item, dict):
            continue
        try:
            parsed.append(FormatSpec.from_dict(item))
        except (TypeError, ValueError):
            continue

    return parsed


def save_specs_to_disk(specs: list[FormatSpec]) -> None:
    payload = {"formats": [spec.to_dict() for spec in specs]}
    SPECS_FILE.write_text(json.dumps(payload, indent=4), encoding="utf-8")


def ensure_session_state() -> None:
    if "specs" not in st.session_state:
        st.session_state.specs = load_specs_from_disk()

    if "project_name" not in st.session_state:
        st.session_state.project_name = DEFAULT_PROJECT_NAME

    if "image_index" not in st.session_state:
        st.session_state.image_index = 0

    if "align_map" not in st.session_state:
        st.session_state.align_map = {}

    if "template_selection" not in st.session_state:
        st.session_state.template_selection = {}

    if "custom_enabled" not in st.session_state:
        st.session_state.custom_enabled = False

    if "templates_enabled" not in st.session_state:
        st.session_state.templates_enabled = True


@st.cache_data(show_spinner=False)
def get_upload_bytes(file_name: str, file_bytes: bytes) -> bytes:
    return file_bytes


def open_uploaded_image(uploaded_file) -> Image.Image:
    raw_bytes = get_upload_bytes(uploaded_file.name, uploaded_file.getvalue())
    try:
        image = Image.open(io.BytesIO(raw_bytes))
        image.load()
        return image
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"Could not open image: {uploaded_file.name}") from exc


def get_alignment_for_name(file_name: str) -> dict[str, int]:
    existing = st.session_state.align_map.get(file_name, {"x": 50, "y": 50})
    x = int(existing.get("x", 50))
    y = int(existing.get("y", 50))
    x = min(100, max(0, x))
    y = min(100, max(0, y))
    value = {"x": x, "y": y}
    st.session_state.align_map[file_name] = value
    return value


def unique_format_key(label: str, width: int, height: int, ext: str, quality: int) -> str:
    return f"{label}|{width}|{height}|{ext}|{quality}"


def make_preview(
    image: Image.Image,
    width: int,
    height: int,
    center_x: float = 0.5,
    center_y: float = 0.5,
) -> Image.Image:
    return ImageOps.fit(
        image.convert("RGB"),
        (width, height),
        method=Image.Resampling.LANCZOS,
        centering=(center_x, center_y),
    )


def export_image_to_bytes(image: Image.Image, spec: FormatSpec) -> bytes:
    buf = io.BytesIO()
    if spec.ext == "JPEG":
        image.save(
            buf,
            format="JPEG",
            quality=spec.quality,
            optimize=True,
            subsampling=0 if spec.quality >= 95 else 2,
        )
    else:
        image.save(
            buf,
            format="WEBP",
            quality=spec.quality,
            lossless=(spec.quality == 100),
            method=6,
        )
    return buf.getvalue()


def render_template_selector() -> list[FormatSpec]:
    specs: list[FormatSpec] = st.session_state.specs
    if not specs:
        st.info("No saved formats yet. Add some in the Formats tab.")
        return []

    selected: list[FormatSpec] = []
    categories = sorted({spec.category for spec in specs})

    for category in categories:
        cat_specs = [spec for spec in specs if spec.category == category]
        master_key = f"master_toggle_{category}"

        header_cols = st.columns([0.85, 0.15])
        with header_cols[0]:
            st.markdown(f"### {category}")
        with header_cols[1]:
            if st.button("All", key=f"{master_key}_all", use_container_width=True):
                for spec in cat_specs:
                    st.session_state.template_selection[
                        unique_format_key(spec.label, spec.width, spec.height, spec.ext, spec.quality)
                    ] = True
            if st.button("None", key=f"{master_key}_none", use_container_width=True):
                for spec in cat_specs:
                    st.session_state.template_selection[
                        unique_format_key(spec.label, spec.width, spec.height, spec.ext, spec.quality)
                    ] = False

        for start in range(0, len(cat_specs), 2):
            row_items = cat_specs[start : start + 2]
            cols = st.columns(2)

            for idx, spec in enumerate(row_items):
                spec_key = unique_format_key(spec.label, spec.width, spec.height, spec.ext, spec.quality)
                current_value = bool(st.session_state.template_selection.get(spec_key, False))

                with cols[idx]:
                    with st.container(border=True):
                        icon_col, text_col, check_col = st.columns([1, 5, 1])
                        with icon_col:
                            st.markdown(svg_ratio_box(spec.width, spec.height), unsafe_allow_html=True)
                        with text_col:
                            st.markdown(f"**{spec.label}**")
                            st.caption(
                                f"{spec.width} x {spec.height}  |  "
                                f"{aspect_ratio_text(spec.width, spec.height)}  |  "
                                f"{spec.ext}  |  Q{spec.quality}"
                            )
                        with check_col:
                            new_value = st.checkbox(
                                "Use",
                                value=current_value,
                                key=f"tpl_{spec_key}",
                                label_visibility="collapsed",
                            )
                            st.session_state.template_selection[spec_key] = new_value

                        if st.session_state.template_selection.get(spec_key):
                            selected.append(spec)

    return selected


def build_export_zip(uploaded_files: list[Any], selected_formats: list[tuple[FormatSpec, bool]]) -> bytes:
    total_jobs = len(uploaded_files) * len(selected_formats)
    progress = st.progress(0)
    status = st.empty()

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        completed = 0

        for uploaded in uploaded_files:
            source_image = open_uploaded_image(uploaded).convert("RGB")
            file_stub = sanitize_filename(Path(uploaded.name).stem)
            align = get_alignment_for_name(uploaded.name)
            custom_center = (align["x"] / 100, align["y"] / 100)

            for spec, use_custom_alignment in selected_formats:
                completed += 1
                center = custom_center if use_custom_alignment else (0.5, 0.5)

                rendered = make_preview(
                    source_image,
                    spec.width,
                    spec.height,
                    center_x=center[0],
                    center_y=center[1],
                )

                out_ext = "jpg" if spec.ext == "JPEG" else "webp"
                out_name = sanitize_filename(f"PSAM_{file_stub}_{spec.label}.{out_ext}")

                archive.writestr(out_name, export_image_to_bytes(rendered, spec))

                percent = int((completed / total_jobs) * 100) if total_jobs else 100
                progress.progress(percent)
                status.text(f"Processing {completed} of {total_jobs}: {uploaded.name}")

    progress.progress(100)
    status.text("Export ready")
    return zip_buffer.getvalue()


def transformer_tab() -> None:
    st.subheader("Transformer")

    uploaded_files = st.file_uploader(
        "Drag and drop images",
        type=ALLOWED_UPLOAD_TYPES,
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if not uploaded_files:
        st.info("Upload one or more JPG, PNG, or WebP files to begin.")
        return

    if st.session_state.image_index >= len(uploaded_files):
        st.session_state.image_index = 0

    current_file = uploaded_files[st.session_state.image_index]

    try:
        source_image = open_uploaded_image(current_file)
    except ValueError as exc:
        st.error(str(exc))
        return

    source_width, source_height = source_image.size
    alignment = get_alignment_for_name(current_file.name)

    nav_cols = st.columns([1, 4, 1])
    with nav_cols[0]:
        if st.button("Previous", use_container_width=True):
            st.session_state.image_index = (st.session_state.image_index - 1) % len(uploaded_files)
            st.rerun()
    with nav_cols[1]:
        st.markdown(
            f"**Image {st.session_state.image_index + 1} of {len(uploaded_files)}**  \n"
            f"{current_file.name}  \n"
            f"{source_width} x {source_height}  |  {aspect_ratio_text(source_width, source_height)}"
        )
    with nav_cols[2]:
        if st.button("Next", use_container_width=True):
            st.session_state.image_index = (st.session_state.image_index + 1) % len(uploaded_files)
            st.rerun()

    st.divider()

    st.session_state.custom_enabled = st.toggle(
        "Custom Settings",
        value=st.session_state.custom_enabled,
    )
    st.session_state.templates_enabled = st.toggle(
        "Templates",
        value=st.session_state.templates_enabled,
    )

    selected_exports: list[tuple[FormatSpec, bool]] = []

    if st.session_state.custom_enabled:
        with st.container(border=True):
            st.markdown("### Custom Export")

            lock_cols = st.columns(2)
            lock_aspect = lock_cols[0].checkbox("Lock aspect ratio", value=False)
            use_original_size = lock_cols[1].checkbox("Use original size", value=False)

            input_cols = st.columns(4)

            default_width = source_width if use_original_size else 1080
            custom_width = input_cols[0].number_input(
                "Width",
                min_value=1,
                value=int(default_width),
                step=1,
                disabled=use_original_size,
            )

            if lock_aspect:
                custom_height = max(1, int(round(custom_width * source_height / source_width)))
                input_cols[1].number_input(
                    "Height",
                    min_value=1,
                    value=int(custom_height),
                    step=1,
                    disabled=True,
                )
            else:
                default_height = source_height if use_original_size else 1080
                custom_height = input_cols[1].number_input(
                    "Height",
                    min_value=1,
                    value=int(default_height),
                    step=1,
                    disabled=use_original_size,
                )

            custom_ext = input_cols[2].selectbox("Format", EXPORT_TYPES, index=0)
            custom_quality = input_cols[3].slider("Quality", 10, 100, 95)

            preview_cols = st.columns([1, 1])

            with preview_cols[0]:
                st.markdown("### Preview")
                preview_image = make_preview(
                    source_image,
                    int(custom_width),
                    int(custom_height),
                    center_x=alignment["x"] / 100,
                    center_y=alignment["y"] / 100,
                )
                display_w, _ = fit_preview_width(int(custom_width), int(custom_height))
                st.image(preview_image, width=display_w)

            with preview_cols[1]:
                st.markdown("### Alignment")
                new_x = st.slider("Horizontal crop", 0, 100, int(alignment["x"]))
                new_y = st.slider("Vertical crop", 0, 100, int(alignment["y"]))
                st.session_state.align_map[current_file.name] = {"x": new_x, "y": new_y}

            custom_spec = FormatSpec(
                category="CUSTOM",
                label="Custom",
                width=int(custom_width),
                height=int(custom_height),
                ext=custom_ext,
                quality=int(custom_quality),
            ).normalized()

            st.caption(
                f"{custom_spec.width} x {custom_spec.height}  |  "
                f"{aspect_ratio_text(custom_spec.width, custom_spec.height)}  |  "
                f"{custom_spec.ext}  |  Q{custom_spec.quality}"
            )

            selected_exports.append((custom_spec, True))

    if st.session_state.templates_enabled:
        st.divider()
        template_specs = render_template_selector()
        selected_exports.extend((spec, False) for spec in template_specs)

    st.divider()

    deduped: list[tuple[FormatSpec, bool]] = []
    seen = set()

    for spec, use_custom_alignment in selected_exports:
        key = unique_format_key(spec.label, spec.width, spec.height, spec.ext, spec.quality)
        if (key, use_custom_alignment) in seen:
            continue
        seen.add((key, use_custom_alignment))
        deduped.append((spec, use_custom_alignment))

    st.markdown(f"**Selected outputs:** {len(deduped)}")

    if st.button("Generate All Assets", type="primary", use_container_width=True):
        if not deduped:
            st.warning("Select at least one custom export or saved format.")
            return

        try:
            zip_bytes = build_export_zip(uploaded_files, deduped)
        except Exception as exc:
            st.error(f"Export failed: {exc}")
            return

        st.success("Batch generated successfully.")
        st.download_button(
            "Download ZIP",
            data=zip_bytes,
            file_name=f"{sanitize_filename(st.session_state.project_name)}.zip",
            mime="application/zip",
            use_container_width=True,
        )


def formats_tab() -> None:
    st.subheader("Museum Standards Library")

    specs: list[FormatSpec] = st.session_state.specs

    if not specs:
        st.info("No saved formats yet.")
    else:
        for idx, spec in enumerate(specs):
            with st.expander(f"{spec.category}: {spec.label}", expanded=False):
                label = st.text_input("Label", value=spec.label, key=f"label_{idx}")
                category = st.text_input("Category", value=spec.category, key=f"category_{idx}")

                size_cols = st.columns(2)
                width = size_cols[0].number_input(
                    "Width",
                    min_value=1,
                    value=int(spec.width),
                    step=1,
                    key=f"width_{idx}",
                )
                height = size_cols[1].number_input(
                    "Height",
                    min_value=1,
                    value=int(spec.height),
                    step=1,
                    key=f"height_{idx}",
                )

                type_cols = st.columns(2)
                ext = type_cols[0].selectbox(
                    "Type",
                    EXPORT_TYPES,
                    index=0 if spec.ext == "WebP" else 1,
                    key=f"ext_{idx}",
                )
                quality = type_cols[1].slider(
                    "Quality",
                    10,
                    100,
                    int(spec.quality),
                    key=f"quality_{idx}",
                )

                action_cols = st.columns(2)
                with action_cols[0]:
                    if st.button("Save Changes", key=f"save_{idx}", use_container_width=True):
                        updated = FormatSpec(
                            category=category,
                            label=label,
                            width=int(width),
                            height=int(height),
                            ext=ext,
                            quality=int(quality),
                        ).normalized()
                        st.session_state.specs[idx] = updated
                        save_specs_to_disk(st.session_state.specs)
                        st.success("Format updated.")
                        st.rerun()

                with action_cols[1]:
                    if st.button("Remove Format", key=f"remove_{idx}", use_container_width=True):
                        st.session_state.specs.pop(idx)
                        save_specs_to_disk(st.session_state.specs)
                        st.success("Format removed.")
                        st.rerun()

    st.divider()

    with st.form("add_new_format", clear_on_submit=False):
        st.markdown("### Add New Permanent Format")

        new_category = st.text_input("Category", value="SOCIAL")
        new_label = st.text_input("Name")
        new_cols = st.columns(2)
        new_width = new_cols[0].number_input("Width", min_value=1, value=1080, step=1)
        new_height = new_cols[1].number_input("Height", min_value=1, value=1080, step=1)

        new_type_cols = st.columns(2)
        new_ext = new_type_cols[0].selectbox("Type", EXPORT_TYPES, index=0)
        new_quality = new_type_cols[1].slider("Quality", 10, 100, 95)

        submitted = st.form_submit_button("Add To System", use_container_width=True)

        if submitted:
            if not new_label.strip():
                st.warning("Format name is required.")
            else:
                spec = FormatSpec(
                    category=new_category,
                    label=new_label,
                    width=int(new_width),
                    height=int(new_height),
                    ext=new_ext,
                    quality=int(new_quality),
                ).normalized()
                st.session_state.specs.append(spec)
                save_specs_to_disk(st.session_state.specs)
                st.success("Format added.")
                st.rerun()


def settings_tab() -> None:
    st.subheader("Workflow Settings")

    st.session_state.project_name = st.text_input(
        "Project Name",
        value=st.session_state.project_name,
    )

    st.divider()

    export_json = json.dumps(
        {"formats": [spec.to_dict() for spec in st.session_state.specs]},
        indent=4,
    )

    st.download_button(
        "Export Library JSON",
        data=export_json,
        file_name="psam_library.json",
        mime="application/json",
        use_container_width=True,
    )

    uploaded_json = st.file_uploader(
        "Import Library JSON",
        type=["json"],
        accept_multiple_files=False,
    )

    if uploaded_json is not None:
        try:
            payload = json.loads(uploaded_json.getvalue().decode("utf-8"))
            imported_specs = [
                FormatSpec.from_dict(item)
                for item in payload.get("formats", [])
                if isinstance(item, dict)
            ]
            st.session_state.specs = imported_specs
            save_specs_to_disk(st.session_state.specs)
            st.success("Library imported successfully.")
            st.rerun()
        except Exception:
            st.error("Invalid JSON library file.")


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    load_css()
    ensure_session_state()

    st.title(APP_TITLE)

    tab_transformer, tab_formats, tab_settings = st.tabs(
        ["Transformer", "Formats", "Settings"]
    )

    with tab_transformer:
        transformer_tab()

    with tab_formats:
        formats_tab()

    with tab_settings:
        settings_tab()


if __name__ == "__main__":
    main()
