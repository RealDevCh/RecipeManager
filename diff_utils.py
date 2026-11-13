import os
import hashlib
import difflib
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageChops

KST = timezone(timedelta(hours=9))
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
TEXT_EXTS = {".xml", ".txt", ".ini", ".cfg", ".json", ".csv", ".dat", ".log", ".rcp"}


def scan_recipe_folder(folder_path: str) -> dict:
    """지정된 폴더를 재귀 스캔하여 상대 경로, 크기, SHA256 해시, 수정시각(KST) 딕셔너리 반환"""
    file_map = {}
    if not folder_path or not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return file_map

    for root, _, files in os.walk(folder_path):
        for fname in files:
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, start=folder_path).replace("\\", "/")
            try:
                stat = os.stat(full_path)
                sha256 = hashlib.sha256()
                with open(full_path, "rb") as bf:
                    for chunk in iter(lambda: bf.read(65536), b""):
                        sha256.update(chunk)
                mtime_kst = datetime.fromtimestamp(stat.st_mtime, tz=KST).strftime("%Y-%m-%d %H:%M:%S")
                file_map[rel_path] = {
                    "full_path": full_path,
                    "rel_path": rel_path,
                    "ext": os.path.splitext(fname)[1].lower(),
                    "size": stat.st_size,
                    "hash": sha256.hexdigest(),
                    "mtime": mtime_kst,
                }
            except Exception:
                pass
    return file_map


def compare_folders(source_dir: str, target_dir: str) -> list[dict]:
    """기준 폴더(Source)와 대상 설비 폴더(Target) 간 전체 파일 트리 대조"""
    src_map = scan_recipe_folder(source_dir)
    tgt_map = scan_recipe_folder(target_dir)
    all_keys = sorted(set(src_map.keys()) | set(tgt_map.keys()))

    results = []
    for k in all_keys:
        in_src = k in src_map
        in_tgt = k in tgt_map
        if in_src and in_tgt:
            if src_map[k]["hash"] == tgt_map[k]["hash"]:
                status = "🟢 일치"
            else:
                status = "🟡 내용 변경"
            results.append({
                "파일경로": k,
                "상태": status,
                "기준크기(B)": src_map[k]["size"],
                "설비크기(B)": tgt_map[k]["size"],
                "기준해시": src_map[k]["hash"][:12],
                "설비해시": tgt_map[k]["hash"][:12],
                "src_path": src_map[k]["full_path"],
                "tgt_path": tgt_map[k]["full_path"],
                "ext": src_map[k]["ext"],
            })
        elif in_src and not in_tgt:
            results.append({
                "파일경로": k,
                "상태": "🔴 누락 (설비에 없음)",
                "기준크기(B)": src_map[k]["size"],
                "설비크기(B)": 0,
                "기준해시": src_map[k]["hash"][:12],
                "설비해시": "-",
                "src_path": src_map[k]["full_path"],
                "tgt_path": None,
                "ext": src_map[k]["ext"],
            })
        else:
            results.append({
                "파일경로": k,
                "상태": "🔵 추가 (신규 파일)",
                "기준크기(B)": 0,
                "설비크기(B)": tgt_map[k]["size"],
                "기준해시": "-",
                "설비해시": tgt_map[k]["hash"][:12],
                "src_path": None,
                "tgt_path": tgt_map[k]["full_path"],
                "ext": tgt_map[k]["ext"],
            })
    return results


def compute_text_diff_html(text_a: str, text_b: str) -> tuple[bool, str]:
    """두 텍스트 간 Line-by-Line Unified Diff HTML 생성"""
    lines_a = (text_a or "").splitlines(keepends=True)
    lines_b = (text_b or "").splitlines(keepends=True)
    diff_lines = list(difflib.unified_diff(lines_a, lines_b, fromfile="Source_A", tofile="Target_B"))
    if not diff_lines:
        return True, ""

    html_parts = []
    for line in diff_lines:
        esc = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if esc.startswith("+") and not esc.startswith("+++"):
            html_parts.append(f"<span style='color:#4ec9b0;font-weight:bold;'>{esc}</span>")
        elif esc.startswith("-") and not esc.startswith("---"):
            html_parts.append(f"<span style='color:#f14c4c;font-weight:bold;'>{esc}</span>")
        else:
            html_parts.append(esc)
    return False, "".join(html_parts)


def compute_image_pixel_diff(img1: Image.Image, img2: Image.Image, threshold: int = 15) -> dict:
    """[FV-03] 두 이미지 간 픽셀 단위 정밀 오차 계산 및 붉은색 오버레이 마스크 생성"""
    im1 = img1.convert("RGB")
    im2 = img2.convert("RGB")
    size_mismatch = False
    if im1.size != im2.size:
        size_mismatch = True
        im2_comp = im2.resize(im1.size, Image.Resampling.BILINEAR)
    else:
        im2_comp = im2

    diff_gray = ImageChops.difference(im1, im2_comp).convert("L")
    mask_l = diff_gray.point(lambda p: 255 if p >= threshold else 0, mode="L")
    hist = mask_l.histogram()
    diff_pixels = hist[255] if len(hist) > 255 else 0
    total_pixels = im1.size[0] * im1.size[1]
    diff_ratio = (diff_pixels / total_pixels) * 100.0 if total_pixels > 0 else 0.0

    base_gray = im1.convert("L").convert("RGBA")
    red_layer = Image.new("RGBA", im1.size, (255, 0, 0, 210))
    diff_visual = Image.composite(red_layer, base_gray, mask_l)

    return {
        "size1": im1.size,
        "size2": im2.size,
        "size_mismatch": size_mismatch,
        "total_pixels": total_pixels,
        "diff_pixels": diff_pixels,
        "match_pixels": total_pixels - diff_pixels,
        "diff_ratio": round(diff_ratio, 2),
        "match_ratio": round(100.0 - diff_ratio, 2),
        "diff_visual": diff_visual,
    }
