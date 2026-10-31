"""Run rejection controls in temporary directories; preserve filed evidence."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import run
import verify


class MetricAcceptance(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="eidos-metric-controls-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.corpus = self.root / "pairs.json"
        shutil.copyfile(run.HERE / "pairs.json", self.corpus)
        self.evidence = self.root / "evidence.json"
        self.record = run.produce([self.corpus], self.evidence)

    def changed_record(self, change):
        record = copy.deepcopy(self.record)
        change(record)
        self.evidence.write_text(json.dumps(record), encoding="utf-8")

    def test_all_short_graph_pairs_and_unicode_examples(self):
        self.evidence.unlink()
        paths = [run.HERE / "pairs.json", run.HERE / "short-graph.json"]
        run.produce(paths, self.evidence)
        result = verify.validate(self.evidence, paths)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["records"], 235)
        self.assertEqual(result["qualification"]["ordered_pairs"], 225)
        self.assertGreater(result["qualification"]["legacy_control_mismatches"], 0)
        self.assertGreater(result["qualification"]["zero_control_mismatches"], 0)

    def test_legacy_implementation_is_rejected(self):
        self.changed_record(lambda r: [row.update(distance=row["legacy_cost"], repaired_rate=row["legacy_rate"])
                                      for row in r["records"]])
        with self.assertRaisesRegex(ValueError, "metric mismatch"):
            verify.validate(self.evidence, [self.corpus])

    def test_wrong_normalization_is_rejected(self):
        self.changed_record(lambda r: r["records"][0].update(repaired_rate=1.0))
        with self.assertRaisesRegex(ValueError, "metric mismatch"):
            verify.validate(self.evidence, [self.corpus])

    def test_missing_record_is_rejected(self):
        self.changed_record(lambda r: r["records"].pop())
        with self.assertRaisesRegex(ValueError, "inventory"):
            verify.validate(self.evidence, [self.corpus])

    def test_boolean_distance_is_rejected(self):
        self.changed_record(lambda r: r["records"][0].update(distance=True))
        with self.assertRaisesRegex(ValueError, "metric mismatch"):
            verify.validate(self.evidence, [self.corpus])

    def test_changed_data_is_rejected(self):
        self.corpus.write_text('[{"goal":"a","perturbation":"b"}]', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "corpus hash"):
            verify.validate(self.evidence, [self.corpus])

    def test_changed_source_is_rejected(self):
        sources = self.root / "source"
        sources.mkdir()
        for name in run.SOURCES:
            shutil.copyfile(run.HERE / name, sources / name)
        with (sources / "run.py").open("a", encoding="utf-8") as stream:
            stream.write("\n# changed source\n")
        with patch.object(verify, "HERE", sources), self.assertRaisesRegex(ValueError, "source/config/lock"):
            verify.validate(self.evidence, [self.corpus])

    def test_missing_evidence_is_rejected(self):
        self.evidence.unlink()
        with self.assertRaises(FileNotFoundError):
            verify.validate(self.evidence, [self.corpus])

    def test_malformed_or_unpaired_data_is_rejected(self):
        self.evidence.unlink()
        for payload in ("not json", "[]", '[{"goal":"a"}]', '[{"goal":false,"perturbation":"a"}]'):
            self.corpus.write_text(payload, encoding="utf-8")
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                run.produce([self.corpus], self.evidence)

    def test_production_cannot_overwrite_corpus_or_existing_result(self):
        for output in (self.corpus, self.evidence):
            before = output.read_bytes()
            with self.subTest(output=output), self.assertRaises(FileExistsError):
                run.produce([self.corpus], output)
            self.assertEqual(output.read_bytes(), before)

    def test_verifier_cannot_overwrite_corpus_or_evidence(self):
        for output in (self.corpus, self.evidence):
            before = output.read_bytes()
            result = subprocess.run([sys.executable, str(run.HERE / "verify.py"), "--corpus", str(self.corpus),
                                     "--evidence", str(self.evidence), "--output", str(output)],
                                    capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.assertEqual(result.returncode, 1)
            self.assertIn(b"refusing existing output", result.stderr)
            self.assertEqual(output.read_bytes(), before)

    def test_production_refuses_hardlink_input_alias(self):
        alias = self.root / "alias.json"
        try:
            alias.hardlink_to(self.corpus)
        except OSError as exc:
            self.skipTest("filesystem does not support hard links: " + str(exc))
        before = self.corpus.read_bytes()
        with self.assertRaises(FileExistsError):
            run.produce([self.corpus], alias)
        self.assertEqual(self.corpus.read_bytes(), before)

    def test_source_change_during_production_is_rejected(self):
        sources = self.root / "source"
        sources.mkdir()
        for name in run.SOURCES:
            shutil.copyfile(run.HERE / name, sources / name)
        self.evidence.unlink()
        original = run.distance
        def changed(source, target):
            with (sources / "protocol.json").open("a", encoding="utf-8") as stream:
                stream.write("\n")
            return original(source, target)
        with patch.object(run, "HERE", sources), patch.object(run, "distance", changed):
            with self.assertRaisesRegex(ValueError, "source/config/lock changed"):
                run.produce([self.corpus], self.evidence)
        self.assertFalse(self.evidence.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
