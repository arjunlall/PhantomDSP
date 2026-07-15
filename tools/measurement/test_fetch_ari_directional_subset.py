import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from fetch_ari_directional_subset import (
    load_expected_hashes,
    parse_subjects,
    selection_description,
)


class FetchAriDirectionalSubsetTests(unittest.TestCase):
    def test_parse_subjects(self):
        self.assertEqual(parse_subjects("965, 1124,948"), (965, 1124, 948))

    def test_explicit_selection_is_recorded_exactly(self):
        arguments = Namespace(all=False, subjects=(965, 1124, 948))
        self.assertEqual(
            selection_description(arguments, arguments.subjects),
            "explicit subjects: nh965, nh1124, nh948",
        )

    def test_selected_source_manifest_hashes_are_loaded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.json"
            path.write_text(
                json.dumps(
                    {
                        "selected_subjects": [
                            {"filename": "subject.sofa", "sha256": "abc"}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(load_expected_hashes(path), {"subject.sofa": "abc"})


if __name__ == "__main__":
    unittest.main()
