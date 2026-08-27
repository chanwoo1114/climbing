"""영상 분석 파이프라인 — 다운로드 → 프레임 샘플링 → MediaPipe Pose → 지표 계산.

Celery 워커에서만 실행되는 무거운 단계(cv2, mediapipe)는 함수 안에서 import 한다.
web 이미지에는 그 패키지가 없고, 테스트는 extract_keypoints 를 mock 한다.

    extract_keypoints(video_path) -> keypoints dict   (cv2 + mediapipe 필요)
    compute_metrics(keypoints)    -> metrics dict     (numpy 만 필요, 순수 함수)
    run_pipeline(video_url)       -> (keypoints, metrics)

keypoints 형식 (JSONB 에 그대로 저장):
    {"fps": 샘플링 fps, "source_fps": 원본 fps, "duration": 초, "width": w, "height": h,
     "frames": [{"t": 초, "lm": [[x, y, z, visibility] × 33] | null}, ...]}
x, y 는 프레임 크기로 정규화된 0~1 값(y 는 아래로 증가), lm 이 null 이면 그 프레임에서
자세를 못 찾은 것이다.
"""

import logging
import socket
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import numpy as np
from django.conf import settings

logger = logging.getLogger(__name__)

MB = 1024 * 1024
MAX_VIDEO_BYTES = 200 * MB
MAX_FRAME_WIDTH = 640
DOWNLOAD_TIMEOUT = 30
DOWNLOAD_CHUNK = MB

# 무게중심(COM) 속도가 이 값(정규화 좌표/초)을 넘는 프레임을 "동적 무브"로 본다.
# 프레임 높이의 5%/초 — 홀드를 잡고 버티는 구간의 미세한 흔들림은 걸러진다.
DYNAMIC_SPEED_THRESHOLD = 0.05
# metrics 에 넣는 궤적 요약 점 수 상한 (전체 궤적은 keypoints 에 있다).
MAX_TRAJECTORY_POINTS = 120

# MediaPipe Pose 33 랜드마크 인덱스
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24
L_KNEE, R_KNEE = 25, 26
L_ANKLE, R_ANKLE = 27, 28
LANDMARK_COUNT = 33

COM_LANDMARKS = (L_SHOULDER, R_SHOULDER, L_HIP, R_HIP)
# 관절 각도: (시작점, 꼭짓점, 끝점) — 꼭짓점에서의 각도(도)
JOINT_TRIPLES = {
    "left_elbow": (L_SHOULDER, L_ELBOW, L_WRIST),
    "right_elbow": (R_SHOULDER, R_ELBOW, R_WRIST),
    "left_knee": (L_HIP, L_KNEE, L_ANKLE),
    "right_knee": (R_HIP, R_KNEE, R_ANKLE),
    "left_hip": (L_SHOULDER, L_HIP, L_KNEE),
    "right_hip": (R_SHOULDER, R_HIP, R_KNEE),
}

ERROR_MESSAGES = {
    "video_required": "분석할 영상이 없습니다.",
    "invalid_video_url": "영상 주소가 올바르지 않습니다.",
    "download_failed": "영상을 내려받지 못했습니다. 잠시 후 다시 시도해 주세요.",
    "video_too_large": "영상 파일이 너무 큽니다 (최대 200MB).",
    "video_too_long": "영상은 최대 {max_seconds}초까지 분석할 수 있습니다.",
    "video_unreadable": "영상을 읽을 수 없습니다. 파일 형식을 확인해 주세요.",
    "no_pose_detected": "영상에서 사람의 자세를 찾지 못했습니다.",
    "pipeline_unavailable": "분석 엔진이 설치되지 않았습니다.",
    "timeout": "분석 시간이 초과되었습니다. 더 짧은 영상으로 시도해 주세요.",
    "unknown": "분석 중 오류가 발생했습니다.",
}


class AnalysisError(Exception):
    """파이프라인 실패. message 는 그대로 사용자에게 보여줄 수 있는 문장.

    retryable=True 인 오류(네트워크성)만 태스크가 1회 재시도한다.
    """

    def __init__(self, code: str, message: str | None = None, *, retryable=False):
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, ERROR_MESSAGES["unknown"])
        self.retryable = retryable
        super().__init__(f"{code}: {self.message}")


def max_video_seconds() -> int:
    return settings.ANALYSIS_MAX_VIDEO_SECONDS


def sample_fps_setting() -> int:
    return settings.ANALYSIS_SAMPLE_FPS


def _too_long_error() -> AnalysisError:
    return AnalysisError(
        "video_too_long",
        ERROR_MESSAGES["video_too_long"].format(max_seconds=max_video_seconds()),
    )


# --- 1. 다운로드 -----------------------------------------------------------


def download_video(
    url: str,
    dest_dir,
    *,
    max_bytes: int = MAX_VIDEO_BYTES,
    timeout: int = DOWNLOAD_TIMEOUT,
) -> Path:
    """video_url 을 임시 파일로 스트리밍 다운로드. max_bytes 를 넘으면 중단한다."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise AnalysisError("invalid_video_url")

    suffix = Path(parsed.path).suffix.lower()
    if not suffix or len(suffix) > 8:
        suffix = ".mp4"
    dest = Path(dest_dir) / f"video{suffix}"

    request = Request(url, headers={"User-Agent": "climbing-analysis/1.0"})
    total = 0
    try:
        with urlopen(request, timeout=timeout) as response, open(dest, "wb") as out:
            length = response.headers.get("Content-Length")
            if length and length.isdigit() and int(length) > max_bytes:
                raise AnalysisError("video_too_large")
            while chunk := response.read(DOWNLOAD_CHUNK):
                total += len(chunk)
                if total > max_bytes:
                    raise AnalysisError("video_too_large")
                out.write(chunk)
    except AnalysisError:
        raise
    except HTTPError as exc:
        # 4xx 는 다시 받아도 같다(주소 만료/삭제). 5xx 만 재시도 대상.
        raise AnalysisError("download_failed", retryable=exc.code >= 500) from exc
    except (URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as exc:
        raise AnalysisError("download_failed", retryable=True) from exc

    if total == 0:
        raise AnalysisError("video_unreadable")
    return dest


# --- 2. 프레임 샘플링 + MediaPipe Pose --------------------------------------


def _load_engine():
    """cv2 / mediapipe 는 워커에만 설치된다. 없으면 pipeline_unavailable."""
    try:
        import cv2
        import mediapipe as mp
    except ImportError as exc:  # pragma: no cover - 워커 이미지에서는 항상 있음
        raise AnalysisError("pipeline_unavailable") from exc
    if not hasattr(mp, "solutions"):  # pragma: no cover
        raise AnalysisError("pipeline_unavailable")
    return cv2, mp


def extract_keypoints(
    video_path,
    *,
    sample_fps: int | None = None,
    max_seconds: int | None = None,
    max_width: int = MAX_FRAME_WIDTH,
) -> dict:
    """영상을 sample_fps 로 샘플링해 프레임마다 33개 랜드마크를 뽑는다.

    - 긴 변이 max_width 를 넘으면 다운스케일 (정규화 좌표라 결과에는 영향 없음)
    - 길이가 max_seconds 를 넘으면 video_too_long (메타데이터가 틀린 파일도 실제
      프레임 시각으로 다시 검사)
    """
    sample_fps = sample_fps or sample_fps_setting()
    max_seconds = max_seconds or max_video_seconds()
    cv2, mp = _load_engine()

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise AnalysisError("video_unreadable")

    frames: list[dict] = []
    index = 0
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        if fps <= 0 or fps != fps:  # 0 또는 NaN
            fps = 30.0
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if frame_count > 0 and frame_count / fps > max_seconds:
            raise _too_long_error()

        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        scale = min(1.0, max_width / width) if width > max_width else 1.0
        out_width = int(round(width * scale)) if width else 0
        out_height = int(round(height * scale)) if height else 0

        step = max(1, int(round(fps / sample_fps)))

        pose_cls = mp.solutions.pose.Pose
        with pose_cls(
            static_image_mode=False,
            model_complexity=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        ) as pose:
            while capture.grab():
                if index % step == 0:
                    t = index / fps
                    if t > max_seconds:
                        raise _too_long_error()
                    ok, frame = capture.retrieve()
                    if ok and frame is not None:
                        if scale < 1.0:
                            frame = cv2.resize(
                                frame,
                                (out_width, out_height),
                                interpolation=cv2.INTER_AREA,
                            )
                        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        result = pose.process(rgb)
                        frames.append({"t": round(t, 3), "lm": _landmarks(result)})
                index += 1
    finally:
        capture.release()

    if index == 0:
        raise AnalysisError("video_unreadable")

    return {
        "fps": round(fps / step, 3),
        "source_fps": round(fps, 3),
        "duration": round(index / fps, 3),
        "width": out_width,
        "height": out_height,
        "frames": frames,
    }


def _landmarks(result) -> list[list[float]] | None:
    landmarks = getattr(result, "pose_landmarks", None)
    if not landmarks:
        return None
    return [
        [round(p.x, 4), round(p.y, 4), round(p.z, 4), round(p.visibility, 3)]
        for p in landmarks.landmark
    ]


# --- 3. 지표 계산 (numpy, 순수 함수) ----------------------------------------


def _angle_deg(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """꼭짓점 b 에서 a-b-c 가 이루는 각(도). a, b, c: (n, 2)."""
    ba = a - b
    bc = c - b
    norm = np.linalg.norm(ba, axis=1) * np.linalg.norm(bc, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        cosine = np.sum(ba * bc, axis=1) / norm
    cosine = np.clip(np.nan_to_num(cosine, nan=1.0), -1.0, 1.0)
    return np.degrees(np.arccos(cosine))


def _stats(values: np.ndarray, digits: int = 1) -> dict:
    return {
        "mean": round(float(values.mean()), digits),
        "min": round(float(values.min()), digits),
        "max": round(float(values.max()), digits),
    }


def _downsample(times: np.ndarray, points: np.ndarray, limit: int) -> list:
    n = len(times)
    if n > limit:
        idx = np.unique(np.linspace(0, n - 1, limit).round().astype(int))
        times, points = times[idx], points[idx]
    return [
        [round(float(t), 3), round(float(x), 4), round(float(y), 4)]
        for t, (x, y) in zip(times, points)
    ]


def compute_metrics(
    keypoints: dict, *, speed_threshold: float = DYNAMIC_SPEED_THRESHOLD
) -> dict:
    """keypoints → 지표 요약. 자세를 못 찾은 프레임(lm=null)은 건너뛴다.

    - com: 어깨·엉덩이 4점 평균을 무게중심으로 본 궤적 요약, 총 이동 거리(path_length),
      시작 대비 최고 상승량(vertical_gain, y 는 아래로 증가하므로 시작 y − 최소 y),
      상하 이동 폭(vertical_range)
    - joint_angles: 팔꿈치/무릎/엉덩이 좌우 각도의 mean/min/max (도)
    - move_ratio: COM 속도가 speed_threshold 를 넘는 구간 비율(dynamic) / 나머지(static)
    - duration, sample_fps, frame_count, detected_frames, detection_rate
    """
    frames = keypoints.get("frames") or []
    detected = [
        (float(f["t"]), np.asarray(f["lm"], dtype=float))
        for f in frames
        if f.get("lm") and len(f["lm"]) == LANDMARK_COUNT
    ]
    duration = keypoints.get("duration")
    if duration is None:
        duration = frames[-1]["t"] if frames else 0.0

    metrics = {
        "duration": round(float(duration), 3),
        "sample_fps": keypoints.get("fps"),
        "frame_count": len(frames),
        "detected_frames": len(detected),
        "detection_rate": round(len(detected) / len(frames), 3) if frames else 0.0,
        "com": None,
        "joint_angles": {},
        "move_ratio": None,
    }
    if not detected:
        return metrics

    times = np.array([t for t, _ in detected])
    xy = np.stack([lm for _, lm in detected])[:, :, :2]  # (n, 33, 2)

    # 무게중심
    com = xy[:, COM_LANDMARKS, :].mean(axis=1)  # (n, 2)
    steps = np.linalg.norm(np.diff(com, axis=0), axis=1)
    y = com[:, 1]
    metrics["com"] = {
        "trajectory": _downsample(times, com, MAX_TRAJECTORY_POINTS),
        "path_length": round(float(steps.sum()), 4),
        "vertical_gain": round(float(y[0] - y.min()), 4),
        "vertical_range": round(float(y.max() - y.min()), 4),
        "start": [round(float(v), 4) for v in com[0]],
        "end": [round(float(v), 4) for v in com[-1]],
    }

    # 관절 각도
    metrics["joint_angles"] = {
        name: _stats(_angle_deg(xy[:, a], xy[:, b], xy[:, c]))
        for name, (a, b, c) in JOINT_TRIPLES.items()
    }

    # 무브 비율 — 구간별 COM 속도
    if len(steps):
        dt = np.diff(times)
        dt = np.where(dt > 0, dt, np.nan)
        speed = np.nan_to_num(steps / dt, nan=0.0)
        dynamic = float((speed > speed_threshold).mean())
    else:
        dynamic = 0.0
    metrics["move_ratio"] = {
        "dynamic": round(dynamic, 3),
        "static": round(1.0 - dynamic, 3),
        "speed_threshold": speed_threshold,
    }
    return metrics


# --- 전체 실행 ---------------------------------------------------------------


def run_pipeline(video_url: str) -> tuple[dict, dict]:
    """다운로드 → 랜드마크 추출 → 지표. 임시 파일은 끝나면 지운다."""
    if not video_url:
        raise AnalysisError("video_required")
    with tempfile.TemporaryDirectory(prefix="climb-analysis-") as tmp:
        path = download_video(video_url, tmp)
        keypoints = extract_keypoints(path)
    metrics = compute_metrics(keypoints)
    if metrics["detected_frames"] == 0:
        raise AnalysisError("no_pose_detected")
    return keypoints, metrics
