"""
Screen & UI reader — đọc cây UI Windows và trang web qua Accessibility API
để lấy tọa độ click chính xác hơn so với ước lượng VLM.

Chạy trên Desktop Agent (Windows). Backend chỉ gọi qua WebSocket tools.
"""
from __future__ import annotations

import logging
import platform
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Control types thường có thể click / tương tác
_INTERACTIVE_TYPES = frozenset({
    "Button", "Hyperlink", "MenuItem", "TabItem", "CheckBox",
    "RadioButton", "ComboBox", "Edit", "ListItem", "TreeItem",
    "SplitButton", "Document", "Image", "Text", "Group",
    "Custom", "DataItem", "MenuBar", "ToolBar",
})

# Lazy-loaded modules
_uia = None
_ocr_engine = None
_dpi_enabled = False


def _ensure_dpi_awareness() -> None:
    global _dpi_enabled
    if _dpi_enabled or platform.system() != "Windows":
        return
    try:
        import ctypes
        # PROCESS_PER_MONITOR_DPI_AWARE = 2
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    _dpi_enabled = True


def _get_uia():
    global _uia
    if _uia is None:
        import uiautomation as uia
        _uia = uia
    return _uia


def is_available() -> bool:
    return platform.system() == "Windows"


def _rect_to_dict(rect) -> Dict[str, int]:
    return {
        "left": int(rect.left),
        "top": int(rect.top),
        "width": int(rect.width()),
        "height": int(rect.height()),
    }


def _center_of(rect) -> Dict[str, int]:
    return {
        "x": int(rect.left + rect.width() / 2),
        "y": int(rect.top + rect.height() / 2),
    }


def _element_info(control, uia) -> Optional[Dict[str, Any]]:
    """Chuyển UIA control thành dict — bỏ qua element ẩn hoặc quá nhỏ."""
    try:
        rect = control.BoundingRectangle
        if rect.width() <= 0 or rect.height() <= 0:
            return None

        ctype = control.ControlTypeName or "Unknown"
        name = (control.Name or "").strip()
        aid = (control.AutomationId or "").strip()

        # Bỏ qua container rỗng không có tên
        if not name and not aid and ctype in ("Pane", "Window", "Group"):
            return None

        return {
            "name": name,
            "control_type": ctype,
            "automation_id": aid,
            "bounds": _rect_to_dict(rect),
            "center": _center_of(rect),
            "is_enabled": control.IsEnabled,
            "is_offscreen": control.IsOffscreen,
        }
    except Exception:
        return None


def get_foreground_window() -> Dict[str, Any]:
    """Thông tin cửa sổ đang focus."""
    if not is_available():
        return {"available": False}

    _ensure_dpi_awareness()
    uia = _get_uia()

    try:
        win = uia.GetForegroundControl()
        if not win:
            return {"available": True, "title": "", "process": ""}

        rect = win.BoundingRectangle
        proc = ""
        try:
            proc = win.ProcessName or ""
        except Exception:
            pass

        return {
            "available": True,
            "title": (win.Name or "").strip(),
            "process": proc,
            "control_type": win.ControlTypeName or "",
            "bounds": _rect_to_dict(rect),
            "is_browser": _is_browser(proc, win.Name or ""),
        }
    except Exception as e:
        logger.warning("get_foreground_window failed: %s", e)
        return {"available": True, "error": str(e)}


def _is_browser(process: str, title: str) -> bool:
    proc = process.lower()
    return any(b in proc for b in ("chrome", "msedge", "firefox", "brave", "opera"))


def scan_ui_elements(
    max_elements: int = 100,
    max_depth: int = 12,
    foreground_only: bool = True,
) -> List[Dict[str, Any]]:
    """Quét cây UI Automation, trả về danh sách element có thể tương tác."""
    if not is_available():
        return []

    _ensure_dpi_awareness()
    uia = _get_uia()
    elements: List[Dict[str, Any]] = []
    seen: set = set()

    try:
        root = uia.GetForegroundControl() if foreground_only else uia.GetRootControl()
        if not root:
            return []

        queue: List[Tuple[Any, int]] = [(root, 0)]

        while queue and len(elements) < max_elements:
            control, depth = queue.pop(0)
            if depth > max_depth:
                continue

            info = _element_info(control, uia)
            if info and not info.get("is_offscreen"):
                key = (
                    info["name"],
                    info["control_type"],
                    info["bounds"]["left"],
                    info["bounds"]["top"],
                )
                if key not in seen:
                    seen.add(key)
                    if info["control_type"] in _INTERACTIVE_TYPES or info["name"]:
                        elements.append(info)

            try:
                children = control.GetChildren()
                for child in children:
                    queue.append((child, depth + 1))
            except Exception:
                pass

    except Exception as e:
        logger.warning("scan_ui_elements failed: %s", e)

    return elements


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _match_score(query: str, candidate: str, partial: bool) -> float:
    q = _normalize(query)
    c = _normalize(candidate)
    if not q or not c:
        return 0.0
    if q == c:
        return 1.0
    if partial and q in c:
        return 0.85 + 0.1 * (len(q) / len(c))
    if partial and c in q:
        return 0.75
    # Fuzzy: tỷ lệ từ khớp
    q_words = set(q.split())
    c_words = set(c.split())
    if q_words and c_words:
        overlap = len(q_words & c_words) / len(q_words)
        if overlap >= 0.5:
            return 0.5 + overlap * 0.3
    return 0.0


def find_elements(
    query: str,
    partial: bool = True,
    control_type: Optional[str] = None,
    max_results: int = 10,
) -> List[Dict[str, Any]]:
    """Tìm element theo tên/automation_id trong cây UI hiện tại."""
    elements = scan_ui_elements(max_elements=200)
    results: List[Dict[str, Any]] = []

    for el in elements:
        if control_type and el["control_type"].lower() != control_type.lower():
            continue

        scores = []
        if el["name"]:
            scores.append(_match_score(query, el["name"], partial))
        if el["automation_id"]:
            scores.append(_match_score(query, el["automation_id"], partial) * 0.95)

        score = max(scores) if scores else 0.0
        if score >= 0.5:
            results.append({**el, "match_score": round(score, 3)})

    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results[:max_results]


def _get_ocr_engine():
    """Windows OCR (WinRT) — optional, cài qua winrt-Windows.Media.Ocr."""
    global _ocr_engine
    if _ocr_engine is not False and _ocr_engine is None:
        try:
            from winrt.windows.media.ocr import OcrEngine
            from winrt.windows.globalization import Language

            langs = OcrEngine.available_recognizer_languages
            lang = langs[0] if langs else Language("en-US")
            _ocr_engine = OcrEngine.try_create_from_language(lang)
        except Exception:
            _ocr_engine = False
    return _ocr_engine if _ocr_engine is not False else None


def ocr_scan(region: Optional[Dict[str, int]] = None) -> List[Dict[str, Any]]:
    """OCR vùng màn hình — fallback khi UIA không có text (ảnh, canvas)."""
    if not is_available():
        return []

    engine = _get_ocr_engine()
    if not engine:
        return []

    try:
        import asyncio
        import io
        import pyautogui
        from PIL import Image
        from winrt.windows.graphics.imaging import (
            BitmapPixelFormat,
            SoftwareBitmap,
        )
        from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

        if region:
            img = pyautogui.screenshot(region=(
                region["left"], region["top"],
                region["width"], region["height"],
            ))
            offset_x, offset_y = region["left"], region["top"]
        else:
            img = pyautogui.screenshot()
            offset_x, offset_y = 0, 0

        img = img.convert("RGBA")
        width, height = img.size
        raw = img.tobytes()

        bitmap = SoftwareBitmap.create_copy_from_buffer(
            raw, width, height, BitmapPixelFormat.RGBA8,
        )

        async def _run():
            return await engine.recognize_async(bitmap)

        result = asyncio.run(_run())
        items: List[Dict[str, Any]] = []

        for line in result.lines:
            text = (line.text or "").strip()
            if not text:
                continue
            rect = line.bounding_rect
            bounds = {
                "left": int(rect.x + offset_x),
                "top": int(rect.y + offset_y),
                "width": int(rect.width),
                "height": int(rect.height),
            }
            cx = bounds["left"] + bounds["width"] // 2
            cy = bounds["top"] + bounds["height"] // 2
            items.append({
                "name": text,
                "control_type": "OCRText",
                "automation_id": "",
                "bounds": bounds,
                "center": {"x": cx, "y": cy},
                "match_score": 1.0,
                "source": "ocr",
            })

        return items
    except Exception as e:
        logger.warning("ocr_scan failed: %s", e)
        return []


def find_text_ocr(query: str, partial: bool = True) -> List[Dict[str, Any]]:
    """Tìm text qua OCR trên toàn màn hình."""
    items = ocr_scan()
    results = []
    for item in items:
        score = _match_score(query, item["name"], partial)
        if score >= 0.5:
            results.append({**item, "match_score": round(score, 3), "source": "ocr"})
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results


def resolve_click_target(
    target: str,
    match_type: str = "auto",
    control_type: Optional[str] = None,
    index: int = 0,
    use_ocr_fallback: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Tìm tọa độ click chính xác cho một target.

    match_type: auto | text | name | automation_id | role
    Trả về: {x, y, bounds, name, control_type, confidence, source}
    """
    if not target or not target.strip():
        return None

    target = target.strip()
    matches: List[Dict[str, Any]] = []

    if match_type in ("auto", "text", "name"):
        matches = find_elements(target, partial=True, control_type=control_type)

    if match_type == "automation_id":
        elements = scan_ui_elements(max_elements=200)
        for el in elements:
            if _normalize(el["automation_id"]) == _normalize(target):
                matches.append({**el, "match_score": 1.0})

    if match_type == "role" and control_type:
        elements = scan_ui_elements(max_elements=200)
        for el in elements:
            if el["control_type"].lower() == control_type.lower():
                if not target or _match_score(target, el["name"], True) >= 0.5:
                    matches.append({**el, "match_score": 0.8})

    # OCR fallback
    if not matches and use_ocr_fallback and match_type in ("auto", "text"):
        matches = find_text_ocr(target)

    if not matches:
        return None

    if index >= len(matches):
        index = 0

    best = matches[index]
    center = best["center"]
    return {
        "x": center["x"],
        "y": center["y"],
        "bounds": best["bounds"],
        "name": best["name"],
        "control_type": best["control_type"],
        "automation_id": best.get("automation_id", ""),
        "confidence": best.get("match_score", 0.8),
        "source": best.get("source", "uia"),
        "alternatives": len(matches) - 1,
    }


def get_screen_context(max_elements: int = 80) -> Dict[str, Any]:
    """
    Context đầy đủ cho AI: cửa sổ focus + danh sách element.
    Gọi trước khi plan để AI chọn click_element thay vì đoán tọa độ.
    """
    window = get_foreground_window()
    elements = scan_ui_elements(max_elements=max_elements)

    # Rút gọn danh sách gửi lên server (chỉ field cần thiết)
    compact = []
    for el in elements:
        if not el.get("is_enabled", True):
            continue
        compact.append({
            "name": el["name"][:80] if el["name"] else "",
            "type": el["control_type"],
            "id": el["automation_id"][:40] if el["automation_id"] else "",
            "x": el["center"]["x"],
            "y": el["center"]["y"],
        })

    return {
        "window": {
            "title": window.get("title", ""),
            "process": window.get("process", ""),
            "is_browser": window.get("is_browser", False),
        },
        "element_count": len(compact),
        "elements": compact,
        "reader": "uia",
    }
