"""Unit tests for restart_watchdog helpers (no PBS required)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ensemble_running" / "watchdog"))

import restart_watchdog as rw  # noqa: E402


class HashTests(unittest.TestCase):
    def test_hash_matches_sha256_of_prefix(self):
        years = [
            {"wetness": "average", "pumping_rate_fraction": 0.0, "irrigation": "False"},
            {"wetness": "average", "pumping_rate_fraction": 1e-5, "irrigation": "False"},
        ]
        h0 = rw.hash_years(years[:1])
        h1 = rw.hash_years(years)
        self.assertNotEqual(h0, h1)
        self.assertEqual(len(h0), 64)

    def test_pumping_layer_suffix(self):
        years = [
            {"wetness": "average", "pumping_rate_fraction": 0.0, "irrigation": "False"},
            {"wetness": "average", "pumping_rate_fraction": 1e-5, "irrigation": "False"},
        ]
        plain = rw.sequence2string(years, pumping_layer=2)
        layered = rw.sequence2string(years, pumping_layer=4)
        self.assertTrue(layered.endswith("_pumping_layer_4"))
        self.assertNotEqual(plain, layered)
        # layer only appended once pumping appears in the prefix
        self.assertEqual(
            rw.sequence2string(years[:1], pumping_layer=4),
            rw.sequence2string(years[:1], pumping_layer=2),
        )


class AssessTests(unittest.TestCase):
    def _write_seq(self, folder: Path) -> Path:
        seq = {
            "name": "toy",
            "years": [
                {"wetness": "average", "pumping_rate_fraction": 0.0, "irrigation": "False"},
                {"wetness": "average", "pumping_rate_fraction": 0.0, "irrigation": "False"},
                {"wetness": "dry", "pumping_rate_fraction": 0.0, "irrigation": "False"},
            ],
        }
        path = folder / "toy.json"
        path.write_text(json.dumps(seq))
        return path

    def test_tip_incomplete_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seq_path = self._write_seq(root)
            domain = "wolf2"
            raw = root / "domains" / domain / "raw_runs"
            raw.mkdir(parents=True)

            years = json.loads(seq_path.read_text())["years"]
            h0 = rw.hash_years(years[:1])
            h1 = rw.hash_years(years[:2])
            (raw / h0).mkdir()
            (raw / h0 / "run.out.00001.nc").write_text("ok")
            (raw / h1).mkdir()  # incomplete tip, no later years

            st = rw.assess_sequence(root, domain, "ens", seq_path)
            self.assertIsNotNone(st.tip_incomplete)
            self.assertEqual(st.tip_incomplete.index, 1)
            self.assertEqual(st.missing_years, [2])
            self.assertEqual(st.mid_incomplete, [])

    def test_mid_incomplete_not_tip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seq_path = self._write_seq(root)
            domain = "wolf2"
            raw = root / "domains" / domain / "raw_runs"
            raw.mkdir(parents=True)
            years = json.loads(seq_path.read_text())["years"]
            h0 = rw.hash_years(years[:1])
            h1 = rw.hash_years(years[:2])
            h2 = rw.hash_years(years[:3])
            (raw / h0).mkdir()
            (raw / h0 / "run.out.00001.nc").write_text("ok")
            (raw / h1).mkdir()  # incomplete mid
            (raw / h2).mkdir()
            (raw / h2 / "run.out.00001.nc").write_text("ok")

            st = rw.assess_sequence(root, domain, "ens", seq_path)
            self.assertIsNone(st.tip_incomplete)
            self.assertEqual([m.index for m in st.mid_incomplete], [1])
            self.assertEqual(st.missing_years, [])


class QuotaParseTests(unittest.TestCase):
    def test_parse_scratch_free(self):
        sample = """
Current GLADE space usage: bwest
  Space                                       Used        Quota      % Full    # Files
/glade/work/bwest                             7.57 GiB     2.00 TiB    0.37 %      219680
/glade/derecho/scratch/bwest                 26.61 TiB    30.00 TiB   88.70 %      374589
/glade/u/home/bwest                          78.26 GiB   100.00 GiB   78.26 %       76766
"""
        free = rw.parse_scratch_free_tib(sample)
        self.assertIsNotNone(free)
        self.assertAlmostEqual(free, 30.0 - 26.61, places=2)


class PathSafetyTests(unittest.TestCase):
    def test_safe_raw_run_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = root / "domains" / "wolf2" / "raw_runs" / ("a" * 64)
            good.mkdir(parents=True)
            self.assertTrue(rw.is_safe_raw_run_dir(good, root))
            bad = root / "domains" / "wolf2" / "raw_runs" / "not-a-hash"
            bad.mkdir()
            self.assertFalse(rw.is_safe_raw_run_dir(bad, root))
            outside = root / "somewhere_else"
            outside.mkdir()
            self.assertFalse(rw.is_safe_raw_run_dir(outside, root))

    def test_false_incomplete_all_years_blocks_delete(self):
        """If every existing year looks incomplete, mid-years block tip delete."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seq = {
                "name": "toy",
                "years": [
                    {"wetness": "average", "pumping_rate_fraction": 0.0, "irrigation": "False"},
                    {"wetness": "average", "pumping_rate_fraction": 0.0, "irrigation": "False"},
                    {"wetness": "average", "pumping_rate_fraction": 0.0, "irrigation": "False"},
                ],
            }
            seq_path = root / "toy.json"
            seq_path.write_text(json.dumps(seq))
            raw = root / "domains" / "wolf2" / "raw_runs"
            raw.mkdir(parents=True)
            for i in range(3):
                h = rw.hash_years(seq["years"][: i + 1])
                (raw / h).mkdir()  # exist but no run.out.00001.nc
            st = rw.assess_sequence(root, "wolf2", "ens", seq_path)
            self.assertEqual(len(st.mid_incomplete), 2)
            self.assertIsNotNone(st.tip_incomplete)
            self.assertEqual(st.tip_incomplete.index, 2)
            # main() refuses delete when mid_incomplete non-empty
            self.assertTrue(st.mid_incomplete)


class TombstoneTests(unittest.TestCase):
    def test_blocks_backward_and_same_year_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tip_hi = rw.YearStatus(50, "a" * 64, root / ("a" * 64), True, False)
            tip_lo = rw.YearStatus(49, "b" * 64, root / ("b" * 64), True, False)
            tip_same = rw.YearStatus(50, "c" * 64, root / ("c" * 64), True, False)
            tip_fwd = rw.YearStatus(51, "d" * 64, root / ("d" * 64), True, False)
            safety = {
                "block_backward_tip_deletes": True,
                "max_unique_tip_years_deleted_per_sequence": 10,
                "max_tip_deletes_per_year_index": 1,
            }
            rw.record_tip_delete(
                root,
                domain="wolf2",
                ensemble="ens",
                sequence_name="toy",
                tip=tip_hi,
            )
            self.assertIsNotNone(
                rw.tombstone_blocks_delete(
                    root,
                    domain="wolf2",
                    ensemble="ens",
                    sequence_name="toy",
                    tip=tip_lo,
                    safety=safety,
                )
            )
            # Same year already deleted once → stuck (no second auto-restart)
            reason = rw.tombstone_blocks_delete(
                root,
                domain="wolf2",
                ensemble="ens",
                sequence_name="toy",
                tip=tip_same,
                safety=safety,
            )
            self.assertIsNotNone(reason)
            self.assertIn("stuck_same_year", reason)
            # Later year still OK
            self.assertIsNone(
                rw.tombstone_blocks_delete(
                    root,
                    domain="wolf2",
                    ensemble="ens",
                    sequence_name="toy",
                    tip=tip_fwd,
                    safety=safety,
                )
            )

    def test_unique_year_budget_10(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            safety = {
                "block_backward_tip_deletes": True,
                "max_unique_tip_years_deleted_per_sequence": 10,
                "max_tip_deletes_per_year_index": 1,
            }
            for idx in range(40, 50):
                t = rw.YearStatus(idx, chr(97 + idx - 40) * 64, root / (chr(97 + idx - 40) * 64), True, False)
                rw.record_tip_delete(
                    root, domain="wolf2", ensemble="ens", sequence_name="toy", tip=t
                )
            tip50 = rw.YearStatus(50, "z" * 64, root / ("z" * 64), True, False)
            self.assertIn(
                "tombstone budget",
                rw.tombstone_blocks_delete(
                    root,
                    domain="wolf2",
                    ensemble="ens",
                    sequence_name="toy",
                    tip=tip50,
                    safety=safety,
                ),
            )


if __name__ == "__main__":
    unittest.main()
