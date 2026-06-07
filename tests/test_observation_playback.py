from __future__ import annotations

import pathlib
import tempfile
import unittest

import json

from generation_fabric.worker_bee.observation import write_code_observation_document
from generation_fabric.worker_bee.observation_playback import build_execution_playback_tracks


class ObservationPlaybackTests(unittest.TestCase):
    def test_build_execution_playback_tracks_extracts_call_data_and_return_steps(self) -> None:
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        source_path = repo_root / "generation_fabric" / "worker_bee" / "planner.py"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            markdown_path = tmp_path / "planner-observation.md"
            paths = write_code_observation_document(str(source_path), output=str(markdown_path), overwrite=True)
            data = json.loads(paths.data_path.read_text(encoding="utf-8"))

        tracks = build_execution_playback_tracks(data)

        self.assertGreaterEqual(len(tracks), 1)
        track = tracks[0]
        self.assertEqual(track.diagram_index, 1)
        self.assertTrue(track.participants[0] == "Caller")
        self.assertTrue(track.title)
        step_types = [step.step_type for step in track.steps]
        self.assertIn("call", step_types)
        self.assertIn("return", step_types)
        self.assertEqual(track.steps[0].source, "Caller")
        self.assertEqual(track.steps[0].target, track.title)
        self.assertEqual(track.steps[-1].target, "Caller")


if __name__ == "__main__":
    unittest.main()
