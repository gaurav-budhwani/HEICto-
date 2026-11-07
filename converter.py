#!/usr/bin/env python3
"""
converter.py - Universal High-Fidelity Apple Image & HEIC Conversion Engine.

Supports:
1. macOS Native Mode: Uses Apple `sips` + ColorSync ICC profiles for hardware-accelerated
   conversion and native Display P3 to sRGB transformation.
2. Cloud / Linux / Docker Mode: Uses `pillow-heif` and Pillow `ImageCms` to read Apple HEIC
   and accurately transform Display P3 color profiles to standard sRGB.
"""

import io
import os
import shutil
import subprocess
import tempfile
from typing import Dict, Any, Optional

# ColorSync system ICC profile paths on macOS
SRGB_PROFILE = "/System/Library/ColorSync/Profiles/sRGB Profile.icc"
DISPLAY_P3_PROFILE = "/System/Library/ColorSync/Profiles/Display P3.icc"
SIPS_BIN = "/usr/bin/sips"

# Check available backends
HAS_SIPS = os.path.exists(SIPS_BIN) and os.access(SIPS_BIN, os.X_OK)

try:
    from PIL import Image, ImageCms
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HAS_PILLOW_HEIF = True
except ImportError:
    HAS_PILLOW_HEIF = False


def check_system_support() -> Dict[str, Any]:
    """Verify available encoders and color engines."""
    return {
        "engine": "macOS sips (Native ColorSync)" if HAS_SIPS else ("Pillow-HEIF (Cloud / Linux)" if HAS_PILLOW_HEIF else "Basic Pillow"),
        "sips_available": HAS_SIPS,
        "srgb_profile_available": os.path.exists(SRGB_PROFILE),
        "display_p3_profile_available": os.path.exists(DISPLAY_P3_PROFILE),
        "pillow_available": HAS_PILLOW,
        "pillow_heif_available": HAS_PILLOW_HEIF,
    }


def get_image_info(filepath: str) -> Dict[str, Any]:
    """Extract format, dimensions, color space, and size from an image."""
    if not os.path.exists(filepath):
        return {"error": "File does not exist"}

    size_bytes = os.path.getsize(filepath)
    info = {
        "format": "",
        "width": 0,
        "height": 0,
        "space": "RGB",
        "profile": "sRGB IEC61966-2.1",
        "size_bytes": size_bytes,
        "size_formatted": format_file_size(size_bytes),
    }

    # 1. Try sips on macOS
    if HAS_SIPS:
        try:
            cmd = [
                SIPS_BIN,
                "-g", "format",
                "-g", "pixelWidth",
                "-g", "pixelHeight",
                "-g", "space",
                "-g", "profile",
                filepath,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    line = line.strip()
                    if ":" in line:
                        k, v = line.split(":", 1)
                        k, v = k.strip(), v.strip()
                        if k == "format":
                            info["format"] = v.upper()
                        elif k == "pixelWidth":
                            info["width"] = int(v)
                        elif k == "pixelHeight":
                            info["height"] = int(v)
                        elif k == "space":
                            info["space"] = v
                        elif k == "profile" and v:
                            info["profile"] = v
        except Exception:
            pass

    # 2. Try Pillow / pillow-heif fallback (Linux/Docker or if sips didn't capture)
    if (not info["format"] or info["width"] == 0) and HAS_PILLOW:
        try:
            with Image.open(filepath) as img:
                info["format"] = (img.format or "").upper()
                info["width"], info["height"] = img.size
                info["space"] = img.mode
                icc = img.info.get("icc_profile")
                if icc:
                    try:
                        p = ImageCms.getOpenProfile(io.BytesIO(icc))
                        name = ImageCms.getProfileName(p)
                        if name:
                            info["profile"] = name.strip()
                    except Exception:
                        info["profile"] = "Embedded ICC Profile"
        except Exception:
            pass

    # Fallback to extension
    if not info["format"]:
        ext = os.path.splitext(filepath)[1].lower().replace(".", "")
        info["format"] = ext.upper()

    return info


def convert_image(
    input_path: str,
    output_path: str,
    target_format: str,
    quality: int = 100,
    color_profile: str = "srgb",
    max_dimension: int = 0,
) -> Dict[str, Any]:
    """
    Convert an image using the best available engine (sips on macOS, Pillow on Linux/Cloud).
    """
    target_format = target_format.lower().strip()
    if target_format == "jpg":
        target_format = "jpeg"

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # If on macOS and sips is present, use sips for native ColorSync fidelity
    if HAS_SIPS and target_format != "webp":
        return _convert_with_sips(input_path, output_path, target_format, quality, color_profile, max_dimension)

    # For WebP, or when running on Linux / Docker / Cloud without sips
    return _convert_with_pillow(input_path, output_path, target_format, quality, color_profile, max_dimension)


def _convert_with_sips(
    input_path: str,
    output_path: str,
    target_format: str,
    quality: int,
    color_profile: str,
    max_dimension: int,
) -> Dict[str, Any]:
    """macOS native conversion using sips & ColorSync."""
    cmd = [SIPS_BIN, "-s", "format", target_format]

    if target_format == "jpeg":
        cmd.extend(["-s", "formatOptions", str(quality)])

    if color_profile == "srgb" and os.path.exists(SRGB_PROFILE):
        cmd.extend(["-m", SRGB_PROFILE])
    elif color_profile == "p3" and os.path.exists(DISPLAY_P3_PROFILE):
        cmd.extend(["-m", DISPLAY_P3_PROFILE])

    if max_dimension > 0:
        cmd.extend(["-Z", str(max_dimension)])

    cmd.extend([input_path, "--out", output_path])

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        # If sips fails, fall back to Pillow
        if HAS_PILLOW:
            return _convert_with_pillow(input_path, output_path, target_format, quality, color_profile, max_dimension)
        err = res.stderr.strip() or res.stdout.strip()
        raise RuntimeError(f"Conversion failed: {err}")

    return {
        "success": True,
        "output_path": output_path,
        "format": target_format.upper(),
        "info": get_image_info(output_path),
    }


def _convert_with_pillow(
    input_path: str,
    output_path: str,
    target_format: str,
    quality: int,
    color_profile: str,
    max_dimension: int,
) -> Dict[str, Any]:
    """Linux/Cloud/Docker cross-platform conversion using Pillow + LittleCMS."""
    if not HAS_PILLOW:
        raise RuntimeError("Pillow is required for cross-platform conversion.")

    # If sips is available and target is webp, convert to PNG first via sips for ColorSync
    if HAS_SIPS and target_format == "webp":
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            temp_png = tmp.name
        try:
            _convert_with_sips(input_path, temp_png, "png", 100, color_profile, max_dimension)
            with Image.open(temp_png) as img:
                is_lossless = quality >= 100
                img.save(output_path, "WEBP", quality=quality, lossless=is_lossless, method=6)
            return {
                "success": True,
                "output_path": output_path,
                "format": "WEBP",
                "info": get_image_info(output_path),
            }
        finally:
            if os.path.exists(temp_png):
                try:
                    os.remove(temp_png)
                except OSError:
                    pass

    # Pure Pillow + pillow_heif path
    with Image.open(input_path) as img:
        # Handle color profile transformation
        icc = img.info.get("icc_profile")
        if icc and color_profile == "srgb":
            try:
                in_prof = ImageCms.getOpenProfile(io.BytesIO(icc))
                srgb_prof = ImageCms.createProfile("sRGB")
                img = ImageCms.profileToProfile(img, in_prof, srgb_prof, outputMode="RGB")
                icc = None
            except Exception:
                pass

        # Resample if max_dimension is requested
        if max_dimension > 0:
            w, h = img.size
            if max(w, h) > max_dimension:
                scale = max_dimension / max(w, h)
                new_w, new_h = int(w * scale), int(h * scale)
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Output format mapping
        fmt_upper = target_format.upper()
        if fmt_upper == "JPG":
            fmt_upper = "JPEG"

        save_kwargs: Dict[str, Any] = {}
        if fmt_upper == "JPEG":
            save_kwargs["quality"] = quality
            save_kwargs["optimize"] = True
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
        elif fmt_upper == "WEBP":
            save_kwargs["quality"] = quality
            save_kwargs["lossless"] = (quality >= 100)
            save_kwargs["method"] = 6
        elif fmt_upper == "PNG":
            save_kwargs["optimize"] = True

        if icc and color_profile != "srgb":
            save_kwargs["icc_profile"] = icc

        img.save(output_path, fmt_upper, **save_kwargs)

    return {
        "success": True,
        "output_path": output_path,
        "format": target_format.upper(),
        "info": get_image_info(output_path),
    }


def generate_thumbnail(image_path: str, thumb_path: str, max_size: int = 300) -> bool:
    """Generate a quick thumbnail for the UI."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(thumb_path)), exist_ok=True)
        if HAS_SIPS:
            cmd = [
                SIPS_BIN,
                "-s", "format", "jpeg",
                "-s", "formatOptions", "85",
                "-Z", str(max_size),
                image_path,
                "--out", thumb_path,
            ]
            if os.path.exists(SRGB_PROFILE):
                cmd.extend(["-m", SRGB_PROFILE])
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and os.path.exists(thumb_path):
                return True

        if HAS_PILLOW:
            with Image.open(image_path) as img:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(thumb_path, "JPEG", quality=85)
                return True
    except Exception:
        pass
    return False


def format_file_size(bytes_num: int) -> str:
    """Format bytes into human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_num < 1024.0:
            return f"{bytes_num:.1f} {unit}" if unit != "B" else f"{bytes_num} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} TB"


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 converter.py <input_image> [output_image] [target_format]")
        print("Example: python3 converter.py photo.heic photo.png")
        sys.exit(1)

    in_file = sys.argv[1]
    if not os.path.exists(in_file):
        print(f"Error: Input file '{in_file}' not found.")
        sys.exit(1)

    if len(sys.argv) >= 3:
        out_file = sys.argv[2]
        fmt = os.path.splitext(out_file)[1].replace(".", "").lower() or "png"
    else:
        base = os.path.splitext(in_file)[0]
        fmt = "png"
        out_file = f"{base}.png"

    print(f"🍎 Converting: {in_file} -> {out_file} (ColorSync sRGB, Lossless)")
    res = convert_image(in_file, out_file, target_format=fmt, color_profile="srgb")
    print(f"✅ Converted successfully ({res['info'].get('size_formatted', '')})")
