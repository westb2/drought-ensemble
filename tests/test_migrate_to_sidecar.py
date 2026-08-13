"""Tests for migrate_to_sidecar delete gates (no full 8760 extract)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ensemble_running.hourly_year import (
    LEGACY_HOURLY,
    RAW_TRANSIENT,
    SIDECAR_NAME,
    write_sidecar_atomic,
)
from ensemble_running.migrate_to_sidecar import delete_legacy_year, migrate_year


def _nc_with_time(path: Path, nt: int, vars_2d: dict | None = None) -> None:
    data = {}
    if vars_2d:
        for name, arr in vars_2d.items():
            data[name] = (("time", "y", "x"), arr)
    else:
        data["x"] = (("time",), np.zeros(nt))
    xr.Dataset(data, coords={"time": np.arange(1, nt + 1)}).to_netcdf(path)


class TestMigrateGates(unittest.TestCase):
    def test_delete_blocked_without_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            year_dir = Path(tmp) / "hash"
            year_dir.mkdir()
            _nc_with_time(year_dir / RAW_TRANSIENT, 8760)
            _nc_with_time(year_dir / LEGACY_HOURLY, 8760)
            _nc_with_time(year_dir / "processed_output_219h.nc", 40)
            status, detail, nbytes = delete_legacy_year(
                year_dir,
                interval=219,
                commit=False,
                require_indexed=False,
                indexed_years=None,
            )
            self.assertEqual(status, "blocked")
            self.assertIn(SIDECAR_NAME, detail or "")
            self.assertEqual(nbytes, 0)
            self.assertTrue((year_dir / LEGACY_HOURLY).is_file())

    def test_delete_would_and_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            year_dir = Path(tmp) / "hash"
            year_dir.mkdir()
            nt = 8760
            _nc_with_time(year_dir / RAW_TRANSIENT, nt)
            derived = xr.Dataset(
                {
                    "overland_flow": (
                        ("time", "y", "x"),
                        np.zeros((nt, 2, 2)),
                    ),
                    "subsurface_storage": (
                        ("time", "z", "y", "x"),
                        np.zeros((nt, 1, 2, 2)),
                    ),
                },
                coords={"time": np.arange(1, nt + 1)},
            )
            write_sidecar_atomic(year_dir, derived)
            legacy = year_dir / LEGACY_HOURLY
            _nc_with_time(legacy, nt)
            _nc_with_time(year_dir / "processed_output_219h.nc", 40)

            status, detail, nbytes = delete_legacy_year(
                year_dir,
                interval=219,
                commit=False,
                require_indexed=False,
                indexed_years=None,
            )
            self.assertEqual(status, "would_delete")
            self.assertGreater(nbytes, 0)
            self.assertTrue(legacy.is_file())

            status, detail, nbytes = delete_legacy_year(
                year_dir,
                interval=219,
                commit=True,
                require_indexed=False,
                indexed_years=None,
            )
            self.assertEqual(status, "deleted")
            self.assertFalse(legacy.is_file())
            self.assertTrue((year_dir / SIDECAR_NAME).is_file())
            self.assertTrue((year_dir / RAW_TRANSIENT).is_file())

    def test_migrate_dry_run_would_extract(self):
        with tempfile.TemporaryDirectory() as tmp:
            year_dir = Path(tmp) / "hash"
            year_dir.mkdir()
            # Valid legacy only (no sidecar). Dry-run must not write.
            _nc_with_time(
                year_dir / LEGACY_HOURLY,
                8760,
                {
                    "overland_flow": np.zeros((8760, 1, 1)),
                    "subsurface_storage": np.zeros((8760, 1, 1)),
                },
            )
            # Fake 219h so migrate only reports extract
            _nc_with_time(year_dir / "processed_output_219h.nc", 40)
            status, detail = migrate_year(
                year_dir, interval=219, commit=False, ensure_219h=True
            )
            self.assertEqual(status, "would_extract")
            self.assertFalse((year_dir / SIDECAR_NAME).is_file())


if __name__ == "__main__":
    unittest.main()
