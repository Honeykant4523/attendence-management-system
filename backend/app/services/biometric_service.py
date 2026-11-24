"""Optional biometric adapter.

Templates are encrypted at rest. This module deliberately refuses to record attendance
unless the server has a face match *and* a basic multi-frame liveness check. For a
production deployment, replace the basic liveness function with an independently
validated anti-spoofing provider and complete a DPIA/legal review.
"""
import base64
import os
from datetime import datetime

import numpy as np
from cryptography.fernet import Fernet
from flask import current_app

from ..models import FaceTemplate


class BiometricUnavailable(RuntimeError):
    pass


def _face_lib():
    if not current_app.config["FACE_RECOGNITION_ENABLED"]:
        raise BiometricUnavailable("Face recognition is disabled by configuration.")
    try:
        import face_recognition
        return face_recognition
    except ImportError as error:
        raise BiometricUnavailable("Face-recognition dependencies are not installed.") from error


def _fernet():
    key = current_app.config["BIOMETRIC_ENCRYPTION_KEY"]
    if not key:
        raise BiometricUnavailable("BIOMETRIC_ENCRYPTION_KEY must be configured before biometric use.")
    return Fernet(key.encode() if isinstance(key, str) else key)


def _decode_image(data_url: str):
    try:
        encoded = data_url.split(",", 1)[1] if "," in data_url else data_url
        raw = base64.b64decode(encoded)
        import cv2
        image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError
        return image[:, :, ::-1]  # BGR -> RGB
    except Exception as error:
        raise ValueError("A valid base64 webcam image is required.") from error


def embedding_from_image(data_url: str):
    face_recognition = _face_lib()
    image = _decode_image(data_url)
    locations = face_recognition.face_locations(image, model="hog")
    if len(locations) != 1:
        raise ValueError("Exactly one face must be visible in the frame.")
    encodings = face_recognition.face_encodings(image, known_face_locations=locations)
    if len(encodings) != 1:
        raise ValueError("No usable facial embedding could be generated.")
    return encodings[0]


def basic_liveness_verified(frame_data_urls: list[str]) -> bool:
    """Basic, challenge-ready multi-frame signal; not a substitute for certified anti-spoofing."""
    if not isinstance(frame_data_urls, list) or len(frame_data_urls) < 3:
        return False
    face_recognition = _face_lib()
    centers = []
    for frame in frame_data_urls[:5]:
        locations = face_recognition.face_locations(_decode_image(frame), model="hog")
        if len(locations) != 1:
            return False
        top, right, bottom, left = locations[0]
        centers.append(((left + right) / 2, (top + bottom) / 2))
    # Requires observable motion across a short capture; static replay is rejected.
    movement = max(abs(centers[i][0] - centers[0][0]) + abs(centers[i][1] - centers[0][1]) for i in range(1, len(centers)))
    return movement >= 4


def encrypt_embedding(embedding: np.ndarray) -> bytes:
    return _fernet().encrypt(embedding.astype(np.float64).tobytes())


def decrypt_embedding(template: FaceTemplate) -> np.ndarray:
    plain = _fernet().decrypt(template.encrypted_embedding)
    return np.frombuffer(plain, dtype=np.float64)


def match_employee(employee, embedding: np.ndarray) -> float | None:
    face_recognition = _face_lib()
    templates = [item for item in employee.face_templates if item.active]
    if not templates:
        return None
    distances = [float(face_recognition.face_distance([decrypt_embedding(item)], embedding)[0]) for item in templates]
    score = min(distances)
    # Conservative threshold. A low distance is more similar.
    return score if score <= 0.42 else None


def create_template(employee, image_data: str, consent_version="v1"):
    if not employee.biometric_consent_at:
        raise ValueError("Explicit biometric consent is required before enrolment.")
    embedding = embedding_from_image(image_data)
    for template in employee.face_templates:
        template.active = False
    template = FaceTemplate(employee_id=employee.id, encrypted_embedding=encrypt_embedding(embedding),
                            algorithm_version="face-recognition-1.3", consent_version=consent_version)
    return template
