#encoding: utf-8
"""Shared crop planning for analyzer and converter."""
from dataclasses import dataclass


MAX_CROP_LOSS_RATIO = 0.30
FACE_MARGIN_RATIO = 0.03


@dataclass(frozen=True)
class CropPlan:
    mode: str
    reason: str
    crop_box: tuple
    crop_loss: float
    faces: tuple
    face_detection: str


def center_crop_box(width, height, target_w, target_h):
    """Return the centered cover crop used by convert.py."""
    img_ar = width / height
    tgt_ar = target_w / target_h
    if img_ar >= tgt_ar:
        new_w = int(height * tgt_ar)
        x0 = (width - new_w) // 2
        return (x0, 0, x0 + new_w, height)
    new_h = int(width / tgt_ar)
    y0 = (height - new_h) // 2
    return (0, y0, width, y0 + new_h)


def crop_loss_ratio(width, height, crop_box):
    left, top, right, bottom = crop_box
    kept_area = max(0, right - left) * max(0, bottom - top)
    total_area = width * height
    if total_area <= 0:
        return 1.0
    return 1.0 - kept_area / total_area


def _crop_axis(width, height, crop_box):
    left, top, right, bottom = crop_box
    if right - left < width:
        return "x"
    if bottom - top < height:
        return "y"
    return None


def _face_margin(crop_box):
    left, top, right, bottom = crop_box
    return max(2, int(round(min(right - left, bottom - top) * FACE_MARGIN_RATIO)))


def _expand_face(face, margin):
    left, top, right, bottom = face
    return (left - margin, top - margin, right + margin, bottom + margin)


def faces_fit_crop(faces, crop_box, margin=None):
    if not faces:
        return True
    if margin is None:
        margin = _face_margin(crop_box)
    crop_left, crop_top, crop_right, crop_bottom = crop_box
    for face in faces:
        left, top, right, bottom = _expand_face(face, margin)
        if (left < crop_left or top < crop_top or
                right > crop_right or bottom > crop_bottom):
            return False
    return True


def shift_crop_to_include_faces(width, height, crop_box, faces):
    """Shift a center crop along the cropped axis to keep faces inside."""
    if not faces or faces_fit_crop(faces, crop_box):
        return crop_box

    axis = _crop_axis(width, height, crop_box)
    if axis is None:
        return crop_box

    left, top, right, bottom = crop_box
    crop_w = right - left
    crop_h = bottom - top
    margin = _face_margin(crop_box)
    expanded = [_expand_face(face, margin) for face in faces]

    if axis == "x":
        required_left = min(face[0] for face in expanded)
        required_right = max(face[2] for face in expanded)
        if required_right - required_left > crop_w:
            return crop_box
        min_x0 = max(0, required_right - crop_w)
        max_x0 = min(width - crop_w, required_left)
        if min_x0 > max_x0:
            return crop_box
        preferred = left
        x0 = int(round(min(max(preferred, min_x0), max_x0)))
        return (x0, top, x0 + crop_w, bottom)

    required_top = min(face[1] for face in expanded)
    required_bottom = max(face[3] for face in expanded)
    if required_bottom - required_top > crop_h:
        return crop_box
    min_y0 = max(0, required_bottom - crop_h)
    max_y0 = min(height - crop_h, required_top)
    if min_y0 > max_y0:
        return crop_box
    preferred = top
    y0 = int(round(min(max(preferred, min_y0), max_y0)))
    return (left, y0, right, y0 + crop_h)


def best_effort_shift_crop_to_faces(width, height, crop_box, faces):
    """Shift crop as close as possible to faces when full preservation is impossible."""
    if not faces or faces_fit_crop(faces, crop_box):
        return crop_box

    perfect_box = shift_crop_to_include_faces(width, height, crop_box, faces)
    if perfect_box != crop_box:
        return perfect_box

    axis = _crop_axis(width, height, crop_box)
    if axis is None:
        return crop_box

    left, top, right, bottom = crop_box
    crop_w = right - left
    crop_h = bottom - top
    margin = _face_margin(crop_box)
    expanded = [_expand_face(face, margin) for face in faces]

    if axis == "x":
        required_left = min(face[0] for face in expanded)
        required_right = max(face[2] for face in expanded)
        span = required_right - required_left
        if span <= crop_w:
            ideal = required_left
        else:
            ideal = required_left + (span - crop_w) / 2
        x0 = int(round(min(max(ideal, 0), width - crop_w)))
        return (x0, top, x0 + crop_w, bottom)

    required_top = min(face[1] for face in expanded)
    required_bottom = max(face[3] for face in expanded)
    span = required_bottom - required_top
    if span <= crop_h:
        ideal = required_top
    else:
        ideal = required_top + (span - crop_h) / 2
    y0 = int(round(min(max(ideal, 0), height - crop_h)))
    return (left, y0, right, y0 + crop_h)


def detect_faces(pil_img):
    """Detect faces with OpenCV when available.

    Returns (faces, status), where faces are (left, top, right, bottom).
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return (), "opencv unavailable"

    cascade_path = getattr(cv2.data, "haarcascades", "") + "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(cascade_path)
    if cascade.empty():
        return (), "opencv cascade unavailable"

    rgb = pil_img.convert("RGB")
    arr = np.array(rgb)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    detected = cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(30, 30),
    )
    faces = tuple(
        (int(x), int(y), int(x + w), int(y + h))
        for x, y, w, h in detected
    )
    return faces, f"detected {len(faces)} face(s)"


def plan_fill_crop(width, height, target_w, target_h, faces=(),
                   face_detection="not checked",
                   max_crop_loss=MAX_CROP_LOSS_RATIO):
    center_box = center_crop_box(width, height, target_w, target_h)
    loss = crop_loss_ratio(width, height, center_box)
    if loss > max_crop_loss:
        return CropPlan(
            "scale",
            f"scale: cut would remove {loss*100:.0f}% of the image, above the {max_crop_loss*100:.0f}% limit",
            center_box,
            loss,
            tuple(faces),
            face_detection,
        )

    faces = tuple(faces)
    if not faces:
        reason = f"safe crop removes {loss*100:.0f}% of the image; {face_detection}"
        return CropPlan("cut", reason, center_box, loss, faces, face_detection)

    if faces_fit_crop(faces, center_box):
        return CropPlan(
            "cut",
            f"center crop keeps {len(faces)} face(s) inside and removes {loss*100:.0f}% of the image",
            center_box,
            loss,
            faces,
            face_detection,
        )

    shifted_box = shift_crop_to_include_faces(width, height, center_box, faces)
    if shifted_box != center_box and faces_fit_crop(faces, shifted_box):
        return CropPlan(
            "cut",
            f"shifted crop keeps {len(faces)} face(s) inside and removes {loss*100:.0f}% of the image",
            shifted_box,
            loss,
            faces,
            face_detection,
        )

    return CropPlan(
        "scale",
        f"scale: face would be cropped by full-screen cut ({face_detection})",
        center_box,
        loss,
        faces,
        face_detection,
    )
