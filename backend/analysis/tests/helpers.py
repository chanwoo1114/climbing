"""analysis 테스트 공용 헬퍼 — 합성 keypoints 픽스처와 기록/분석 생성.

make_keypoints() 는 영상 없이 파이프라인 출력 형식(33 랜드마크 × 프레임)을 만든다.
클라이머는 앞 1/3 은 정지, 가운데 1/3 동안 rise 만큼 위로(y 감소), 마지막 1/3 은 정지.
"""

from analysis.models import VideoAnalysis
from analysis.pipeline import LANDMARK_COUNT
from climbs.models import ClimbLog

VIDEO_URL = "https://media.example.com/climb_video/1/abc.mp4"

# 정규화 좌표 (x, y), y 는 아래로 증가. 두 팔을 위로 뻗어 홀드를 잡은 자세.
BASE_POSE = {
    11: (0.45, 0.40),  # left shoulder
    12: (0.55, 0.40),  # right shoulder
    13: (0.40, 0.30),  # left elbow
    14: (0.60, 0.30),  # right elbow
    15: (0.42, 0.20),  # left wrist
    16: (0.58, 0.20),  # right wrist
    23: (0.46, 0.60),  # left hip
    24: (0.54, 0.60),  # right hip
    25: (0.42, 0.72),  # left knee
    26: (0.58, 0.72),  # right knee
    27: (0.44, 0.85),  # left ankle
    28: (0.56, 0.85),  # right ankle
}


def _progress(i: int, n: int) -> float:
    """0 → 1 로 가는 상승 진행도. 앞/뒤 1/3 은 정지."""
    third = n / 3
    if i < third:
        return 0.0
    if i >= 2 * third:
        return 1.0
    return (i - third) / third


def make_frame(t: float, dy: float = 0.0, pose: dict | None = None) -> dict:
    pose = {**BASE_POSE, **(pose or {})}
    landmarks = []
    for idx in range(LANDMARK_COUNT):
        x, y = pose.get(idx, (0.5, 0.5))
        landmarks.append([round(x, 4), round(y + dy, 4), 0.0, 0.99])
    return {"t": round(t, 3), "lm": landmarks}


def make_keypoints(
    seconds: float = 6.0,
    fps: int = 10,
    rise: float = 0.3,
    undetected: set[int] | None = None,
    pose: dict | None = None,
) -> dict:
    n = int(seconds * fps)
    frames = []
    for i in range(n):
        t = i / fps
        if undetected and i in undetected:
            frames.append({"t": round(t, 3), "lm": None})
            continue
        frames.append(make_frame(t, dy=-rise * _progress(i, n), pose=pose))
    return {
        "fps": fps,
        "source_fps": 30.0,
        "duration": seconds,
        "width": 360,
        "height": 640,
        "frames": frames,
    }


def create_analysis(log: ClimbLog, **kwargs) -> VideoAnalysis:
    return VideoAnalysis.objects.create(climb_log=log, **kwargs)
