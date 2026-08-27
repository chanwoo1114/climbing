"""파이프라인 순수 함수 — compute_metrics(합성 keypoints, 영상 없음) + download_video 검증."""

import io
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.test import SimpleTestCase

from analysis.pipeline import (
    DYNAMIC_SPEED_THRESHOLD,
    JOINT_TRIPLES,
    MAX_TRAJECTORY_POINTS,
    AnalysisError,
    compute_metrics,
    download_video,
)
from analysis.tests.helpers import VIDEO_URL, make_keypoints


class ComputeMetricsTests(SimpleTestCase):
    def test_synthetic_climb_metrics(self):
        metrics = compute_metrics(make_keypoints(seconds=6.0, fps=10, rise=0.3))

        self.assertEqual(metrics["duration"], 6.0)
        self.assertEqual(metrics["sample_fps"], 10)
        self.assertEqual(metrics["frame_count"], 60)
        self.assertEqual(metrics["detected_frames"], 60)
        self.assertEqual(metrics["detection_rate"], 1.0)

        com = metrics["com"]
        # 위로 0.3 올라갔다 (y 는 아래로 증가하므로 시작 y − 최소 y)
        self.assertAlmostEqual(com["vertical_gain"], 0.3, places=2)
        self.assertAlmostEqual(com["vertical_range"], 0.3, places=2)
        self.assertGreaterEqual(com["path_length"], 0.3)
        self.assertLess(com["path_length"], 0.35)
        self.assertEqual(com["trajectory"][0][0], 0.0)
        self.assertLessEqual(len(com["trajectory"]), MAX_TRAJECTORY_POINTS)
        self.assertEqual(len(com["start"]), 2)
        self.assertAlmostEqual(com["start"][1] - com["end"][1], 0.3, places=2)

        # 가운데 1/3 동안만 움직였다
        ratio = metrics["move_ratio"]
        self.assertGreater(ratio["dynamic"], 0.25)
        self.assertLess(ratio["dynamic"], 0.45)
        self.assertAlmostEqual(ratio["dynamic"] + ratio["static"], 1.0, places=3)
        self.assertEqual(ratio["speed_threshold"], DYNAMIC_SPEED_THRESHOLD)

        angles = metrics["joint_angles"]
        self.assertEqual(set(angles), set(JOINT_TRIPLES))
        for stats in angles.values():
            self.assertLessEqual(0.0, stats["min"])
            self.assertLessEqual(stats["min"], stats["mean"])
            self.assertLessEqual(stats["mean"], stats["max"])
            self.assertLessEqual(stats["max"], 180.0)

    def test_joint_angle_values(self):
        # 왼팔: 어깨(0.5,0.5) - 팔꿈치(0.5,0.6) - 손목(0.6,0.6) → 직각.
        # 오른팔: 어깨(0.5,0.5) - 팔꿈치(0.5,0.6) - 손목(0.5,0.7) → 일직선.
        pose = {
            11: (0.5, 0.5),
            13: (0.5, 0.6),
            15: (0.6, 0.6),
            12: (0.5, 0.5),
            14: (0.5, 0.6),
            16: (0.5, 0.7),
        }
        metrics = compute_metrics(make_keypoints(seconds=1.0, rise=0.0, pose=pose))
        self.assertAlmostEqual(metrics["joint_angles"]["left_elbow"]["mean"], 90.0)
        self.assertAlmostEqual(metrics["joint_angles"]["right_elbow"]["mean"], 180.0)

    def test_static_video_has_no_dynamic_moves(self):
        metrics = compute_metrics(make_keypoints(seconds=3.0, rise=0.0))
        self.assertEqual(metrics["move_ratio"]["dynamic"], 0.0)
        self.assertEqual(metrics["move_ratio"]["static"], 1.0)
        self.assertEqual(metrics["com"]["vertical_gain"], 0.0)
        self.assertEqual(metrics["com"]["path_length"], 0.0)

    def test_skips_undetected_frames(self):
        metrics = compute_metrics(make_keypoints(seconds=2.0, undetected={0, 1, 2, 3}))
        self.assertEqual(metrics["frame_count"], 20)
        self.assertEqual(metrics["detected_frames"], 16)
        self.assertEqual(metrics["detection_rate"], 0.8)
        self.assertIsNotNone(metrics["com"])
        # 첫 검출 프레임부터 궤적이 시작된다
        self.assertEqual(metrics["com"]["trajectory"][0][0], 0.4)

    def test_no_detection_returns_empty_summary(self):
        metrics = compute_metrics(
            make_keypoints(seconds=1.0, undetected=set(range(10)))
        )
        self.assertEqual(metrics["detected_frames"], 0)
        self.assertIsNone(metrics["com"])
        self.assertEqual(metrics["joint_angles"], {})
        self.assertIsNone(metrics["move_ratio"])

    def test_empty_keypoints(self):
        metrics = compute_metrics({"fps": 10, "frames": []})
        self.assertEqual(metrics["frame_count"], 0)
        self.assertEqual(metrics["duration"], 0.0)
        self.assertIsNone(metrics["com"])

    def test_single_frame(self):
        metrics = compute_metrics(make_keypoints(seconds=0.1))
        self.assertEqual(metrics["detected_frames"], 1)
        self.assertEqual(metrics["com"]["path_length"], 0.0)
        self.assertEqual(metrics["move_ratio"]["dynamic"], 0.0)

    def test_trajectory_is_downsampled(self):
        metrics = compute_metrics(make_keypoints(seconds=60.0, fps=10))
        self.assertEqual(metrics["frame_count"], 600)
        self.assertLessEqual(len(metrics["com"]["trajectory"]), MAX_TRAJECTORY_POINTS)
        self.assertEqual(metrics["com"]["trajectory"][-1][0], 59.9)


class _FakeResponse(io.BytesIO):
    """urlopen() 응답 흉내 — headers + 스트리밍 read()."""

    def __init__(self, body: bytes, content_length: str | None = None):
        super().__init__(body)
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = content_length


class DownloadVideoTests(SimpleTestCase):
    def setUp(self):
        patcher = patch("analysis.pipeline.urlopen")
        self.urlopen = patcher.start()
        self.addCleanup(patcher.stop)
        tmp = self.enterContext(tempfile.TemporaryDirectory())
        self.tmp = Path(tmp)

    def test_downloads_to_temp_file(self):
        self.urlopen.return_value = _FakeResponse(b"x" * 1000, "1000")
        path = download_video(VIDEO_URL, self.tmp)
        self.assertEqual(path.suffix, ".mp4")
        self.assertEqual(path.stat().st_size, 1000)
        self.urlopen.assert_called_once()

    def test_rejects_non_http_url(self):
        with self.assertRaises(AnalysisError) as ctx:
            download_video("file:///etc/passwd", self.tmp)
        self.assertEqual(ctx.exception.code, "invalid_video_url")
        self.urlopen.assert_not_called()

    def test_rejects_declared_size_over_cap(self):
        self.urlopen.return_value = _FakeResponse(b"x", str(300 * 1024 * 1024))
        with self.assertRaises(AnalysisError) as ctx:
            download_video(VIDEO_URL, self.tmp)
        self.assertEqual(ctx.exception.code, "video_too_large")
        self.assertFalse(ctx.exception.retryable)

    def test_stops_streaming_over_cap(self):
        self.urlopen.return_value = _FakeResponse(b"x" * 300)
        with self.assertRaises(AnalysisError) as ctx:
            download_video(VIDEO_URL, self.tmp, max_bytes=200)
        self.assertEqual(ctx.exception.code, "video_too_large")

    def test_empty_body_is_unreadable(self):
        self.urlopen.return_value = _FakeResponse(b"")
        with self.assertRaises(AnalysisError) as ctx:
            download_video(VIDEO_URL, self.tmp)
        self.assertEqual(ctx.exception.code, "video_unreadable")

    def test_network_error_is_retryable(self):
        self.urlopen.side_effect = URLError("connection refused")
        with self.assertRaises(AnalysisError) as ctx:
            download_video(VIDEO_URL, self.tmp)
        self.assertEqual(ctx.exception.code, "download_failed")
        self.assertTrue(ctx.exception.retryable)

    def test_http_4xx_is_not_retryable(self):
        self.urlopen.side_effect = HTTPError(VIDEO_URL, 404, "Not Found", {}, None)
        with self.assertRaises(AnalysisError) as ctx:
            download_video(VIDEO_URL, self.tmp)
        self.assertEqual(ctx.exception.code, "download_failed")
        self.assertFalse(ctx.exception.retryable)

    def test_http_5xx_is_retryable(self):
        self.urlopen.side_effect = HTTPError(VIDEO_URL, 503, "Unavailable", {}, None)
        with self.assertRaises(AnalysisError) as ctx:
            download_video(VIDEO_URL, self.tmp)
        self.assertTrue(ctx.exception.retryable)
