"""本地测男主脸在画面里的位置（mediapipe face_landmarker，几十毫秒一张），用来在末帧前后挑景别标准的一帧，不占视觉模型质检的时间。
face_box(jpg) → [左, 上, 右, 下]（0–1）或 None；多张脸时取最大的那张。"""
from pathlib import Path
import mediapipe as mp

MODEL = '/Users/vicky/Interactive storyline/.media-runtime/face_landmarker.task'
_lm = None


def _get():
    global _lm
    if _lm is None:
        o = mp.tasks.vision.FaceLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=MODEL, delegate=mp.tasks.BaseOptions.Delegate.CPU), num_faces=3, min_face_detection_confidence=0.4)
        _lm = mp.tasks.vision.FaceLandmarker.create_from_options(o)
    return _lm


def face_box(jpg):
    r = _get().detect(mp.Image.create_from_file(str(jpg)))
    best = None
    for f in r.face_landmarks or []:
        xs = [p.x for p in f]; ys = [p.y for p in f]
        b = [max(0, min(xs)), max(0, min(ys)), min(1, max(xs)), min(1, max(ys))]
        if best is None or (b[2] - b[0]) > (best[2] - best[0]): best = b
    return [round(v, 3) for v in best] if best else None
