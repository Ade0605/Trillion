"""
Face enrollment / verification via the local webcam (face_recognition + dlib).

Scope: this identifies who's in front of the camera on request — it does
NOT replace or touch the web UI's bearer-token login (trillion/security/
http_guard.py). Wiring biometric match into that auth path is a separate,
more consequential decision left for later; this module is standalone.

Data: face encodings (128-float vectors, not images) are stored locally in
data/faces/encodings.json. No image frames are persisted.
"""
from __future__ import annotations

import json
from pathlib import Path

_DATA = Path(__file__).parent.parent.parent / "data" / "faces" / "encodings.json"
_DEFAULT_TOLERANCE = 0.5  # face_recognition's own default; lower = stricter


def _load() -> dict[str, list[float]]:
    if not _DATA.exists():
        return {}
    return json.loads(_DATA.read_text(encoding="utf-8"))


def _save(encodings: dict[str, list[float]]) -> None:
    _DATA.parent.mkdir(parents=True, exist_ok=True)
    _DATA.write_text(json.dumps(encodings, indent=2), encoding="utf-8")


def _capture_encoding():
    """Open the webcam, grab a frame, return its face encoding (or None)."""
    try:
        import cv2
        import face_recognition
    except ImportError as e:
        return None, f"Face recognition requires 'opencv-python' and 'face_recognition' (missing: {e})"

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        cap.release()
        return None, "No webcam found."
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return None, "Couldn't read a frame from the webcam."

    rgb = frame[:, :, ::-1]  # BGR (OpenCV) → RGB (face_recognition)
    encodings = face_recognition.face_encodings(rgb)
    if not encodings:
        return None, "No face detected — face the camera and try again."
    return encodings[0], None


def enroll_face(name: str, samples: int = 5) -> str:
    """Enroll a face by name, averaging several webcam samples for robustness."""
    if not name.strip():
        return "Need a name to enroll under."
    try:
        import numpy as np
    except ImportError:
        return "Face enrollment requires 'numpy' (pip install numpy)."

    captured = []
    for _ in range(max(1, samples)):
        encoding, err = _capture_encoding()
        if encoding is None:
            return err
        captured.append(encoding)

    averaged = np.mean(captured, axis=0)
    data = _load()
    data[name.strip()] = averaged.tolist()
    _save(data)
    return f"Enrolled '{name}' from {len(captured)} sample(s)."


def verify_identity(tolerance: float = _DEFAULT_TOLERANCE) -> str:
    """Capture one frame and report who it matches, if anyone enrolled."""
    try:
        import face_recognition
        import numpy as np
    except ImportError as e:
        return f"Face recognition requires 'face_recognition' and 'numpy' (missing: {e})"

    data = _load()
    if not data:
        return "No one is enrolled yet."

    encoding, err = _capture_encoding()
    if encoding is None:
        return err

    names = list(data.keys())
    known = [np.array(v) for v in data.values()]
    distances = face_recognition.face_distance(known, encoding)
    best_idx = int(np.argmin(distances))
    if distances[best_idx] <= tolerance:
        return f"Identity match: {names[best_idx]} (distance {distances[best_idx]:.3f})"
    return f"No match (closest was '{names[best_idx]}' at distance {distances[best_idx]:.3f}, above tolerance {tolerance})."


def list_enrolled() -> str:
    data = _load()
    if not data:
        return "No one is enrolled."
    return "Enrolled: " + ", ".join(sorted(data.keys()))


def forget_face(name: str) -> str:
    data = _load()
    if name not in data:
        return f"'{name}' isn't enrolled."
    del data[name]
    _save(data)
    return f"Removed '{name}' from face enrollment."


def register_face_auth(registry) -> None:
    registry.register(
        name="enroll_face",
        description="Enroll a person's face via the webcam for later identification. Takes a few samples for robustness.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name to enroll the face under"},
            },
            "required": ["name"],
        },
        fn=enroll_face,
    )
    registry.register(
        name="verify_identity",
        description="Capture a webcam frame and report which enrolled person (if any) it matches.",
        input_schema={"type": "object", "properties": {}},
        fn=verify_identity,
    )
    registry.register(
        name="list_enrolled_faces",
        description="List everyone currently enrolled for face recognition.",
        input_schema={"type": "object", "properties": {}},
        fn=list_enrolled,
    )
    registry.register(
        name="forget_face",
        description="Remove a person's enrolled face data.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name to remove"},
            },
            "required": ["name"],
        },
        fn=forget_face,
        requires_confirmation=True,
    )
