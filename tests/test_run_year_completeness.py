"""Tests for Run's truncated-year detection and its rmtree path guard.

These cover the restart path that decides whether an existing raw_runs year
folder is reusable, deletable, or must be left alone. No ParFlow run required.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "classes"))

from Run import Run  # noqa: E402


class StubDomain:
    """Minimal stand-in for Domain: only what Run's completeness path touches."""

    TESTING = False
    p = 1
    q = 1

    def __init__(self, name="wolf2", stop_time=8760):
        self.name = name
        self.stop_time = stop_time
        self.dump_interval = 1
        self.num_output_files = stop_time // self.dump_interval


def _write_nc(path: Path, ntime: int) -> None:
    from netCDF4 import Dataset

    path.parent.mkdir(parents=True, exist_ok=True)
    with Dataset(str(path), "w") as ds:
        ds.createDimension("time", ntime)
        ds.createVariable("time", "f8", ("time",))


SEQUENCE = {
    "name": "toy",
    "years": [
        {"wetness": "average", "pumping_rate_fraction": 0.0, "irrigation": "False"},
        {"wetness": "average", "pumping_rate_fraction": 1e-5, "irrigation": "False"},
        {"wetness": "dry", "pumping_rate_fraction": 1e-5, "irrigation": "False"},
    ],
}


class YearCompletenessTests(unittest.TestCase):
    def _run(self, root: Path, years=None):
        sequence = dict(SEQUENCE)
        if years is not None:
            sequence = {"name": SEQUENCE["name"], "years": years}
        return Run(
            sequence=sequence,
            domain=StubDomain(),
            output_root=str(root),
            netcdf_output=True,
        )

    def test_full_year_is_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = self._run(root)
            _write_nc(Path(run.run_dir) / "run.out.00001.nc", ntime=8760)
            self.assertTrue(run.year_output_complete())

    def test_truncated_year_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = self._run(root)
            _write_nc(Path(run.run_dir) / "run.out.00001.nc", ntime=2335)
            self.assertTrue(run.run_exists())
            self.assertFalse(run.year_output_complete())

    def test_unreadable_year_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = self._run(root)
            d = Path(run.run_dir)
            d.mkdir(parents=True, exist_ok=True)
            (d / "run.out.00001.nc").write_text("not a netcdf file")
            self.assertFalse(run.year_output_complete())

    def test_legacy_processed_output_counts_as_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = self._run(root)
            d = Path(run.run_dir)
            d.mkdir(parents=True, exist_ok=True)
            (d / "processed_output.nc").write_text("legacy")
            self.assertTrue(run.year_output_complete())

    def test_later_year_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = self._run(root)
            folders = run.get_output_folders()
            self.assertFalse(run._later_year_exists(0))
            Path(folders[2]).mkdir(parents=True, exist_ok=True)
            self.assertTrue(run._later_year_exists(0))
            self.assertTrue(run._later_year_exists(1))
            self.assertFalse(run._later_year_exists(2))

    def test_rmtree_guard_accepts_only_hashed_raw_run_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = self._run(root)
            self.assertTrue(run._is_safe_year_dir(run.run_dir))
            self.assertFalse(run._is_safe_year_dir(str(root)))
            self.assertFalse(run._is_safe_year_dir(str(root / "raw_runs")))
            self.assertFalse(run._is_safe_year_dir(str(root / "raw_runs" / "not-a-hash")))
            self.assertFalse(
                run._is_safe_year_dir(str(root / "raw_runs" / ("a" * 64) / "forcing"))
            )
            self.assertFalse(run._is_safe_year_dir(str(root / "elsewhere" / ("a" * 64))))


if __name__ == "__main__":
    unittest.main()
