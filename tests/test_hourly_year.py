"""Tests for raw+sidecar hourly year helpers."""

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
    DERIVED_VARS,
    LEGACY_HOURLY,
    RAW_STATIC,
    RAW_TRANSIENT,
    SIDECAR_NAME,
    close_hourly_year,
    hourly_product_ready,
    hourly_ref_path,
    open_hourly_year,
    write_sidecar_atomic,
)
from ensemble_running.consolidate_to_interval import consolidated_path


def _tiny_year(
    year_dir: Path,
    *,
    nt: int = 8,
    with_legacy: bool = False,
    with_sidecar: bool = False,
) -> None:
    year_dir.mkdir(parents=True, exist_ok=True)
    nz, ny, nx = 2, 3, 4
    time = np.arange(1, nt + 1)

    static = xr.Dataset(
        {
            "mask": (("z", "y", "x"), np.ones((nz, ny, nx))),
            "mannings": (("y", "x"), np.ones((ny, nx))),
            "porosity": (("z", "y", "x"), np.full((nz, ny, nx), 0.3)),
            "specific_storage": (("z", "y", "x"), np.full((nz, ny, nx), 1e-4)),
            "DZ_Multiplier": (("z", "y", "x"), np.ones((nz, ny, nx))),
            "slopex": (("y", "x"), np.full((ny, nx), 0.01)),
            "slopey": (("y", "x"), np.full((ny, nx), 0.01)),
            "perm_x": (("z", "y", "x"), np.ones((nz, ny, nx))),
            "perm_y": (("z", "y", "x"), np.ones((nz, ny, nx))),
            "perm_z": (("z", "y", "x"), np.ones((nz, ny, nx))),
        }
    )
    # match ParFlow static file shape with a time dim on some fields
    static = static.expand_dims(time=[0])
    static.to_netcdf(year_dir / RAW_STATIC)

    raw = xr.Dataset(
        {
            "pressure": (("time", "z", "y", "x"), np.random.randn(nt, nz, ny, nx)),
            "saturation": (
                ("time", "z", "y", "x"),
                np.clip(np.random.rand(nt, nz, ny, nx), 0.1, 1.0),
            ),
            "evaptrans": (("time", "z", "y", "x"), np.zeros((nt, nz, ny, nx))),
            "overland_bc_flux": (("time", "y", "x"), np.zeros((nt, ny, nx))),
        },
        coords={"time": time},
    )
    raw.to_netcdf(year_dir / RAW_TRANSIENT)

    derived = xr.Dataset(
        {
            "overland_flow": (("time", "y", "x"), np.random.rand(nt, ny, nx)),
            "subsurface_storage": (
                ("time", "z", "y", "x"),
                np.random.rand(nt, nz, ny, nx),
            ),
        },
        coords={"time": time},
    )

    if with_sidecar:
        write_sidecar_atomic(year_dir, derived, expected_time=nt)

    if with_legacy:
        legacy = raw.merge(derived)
        for name in static.data_vars:
            da = static[name]
            if "time" in da.dims:
                da = da.isel(time=0)
            legacy[name] = da
        legacy.to_netcdf(year_dir / LEGACY_HOURLY)


class TestHourlyYear(unittest.TestCase):
    def test_write_and_open_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            year_dir = Path(tmp) / "hash"
            nt = 8
            _tiny_year(year_dir, nt=nt, with_sidecar=True)
            self.assertTrue((year_dir / SIDECAR_NAME).is_file())
            self.assertTrue(hourly_product_ready(year_dir, expected_time=nt))
            self.assertEqual(
                hourly_ref_path(year_dir, expected_time=nt).name, SIDECAR_NAME
            )

            ds = open_hourly_year(year_dir, chunks=None, expected_time=nt)
            try:
                for v in ("pressure", "saturation", *DERIVED_VARS, "mask", "porosity"):
                    self.assertIn(v, ds.data_vars)
                self.assertEqual(ds.attrs.get("hourly_layout"), "raw+sidecar")
            finally:
                close_hourly_year(ds)

    def test_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            year_dir = Path(tmp) / "hash"
            nt = 8
            _tiny_year(year_dir, nt=nt, with_legacy=True)
            self.assertTrue(hourly_product_ready(year_dir, expected_time=nt))
            self.assertEqual(
                hourly_ref_path(year_dir, expected_time=nt).name, LEGACY_HOURLY
            )
            ds = open_hourly_year(year_dir, expected_time=nt)
            try:
                self.assertEqual(ds.attrs.get("hourly_layout"), "legacy")
                self.assertIn("overland_flow", ds)
            finally:
                close_hourly_year(ds)

    def test_atomic_reject_bad_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            year_dir = Path(tmp) / "hash"
            year_dir.mkdir()
            bad = xr.Dataset(
                {
                    "overland_flow": (("time", "y", "x"), np.zeros((3, 2, 2))),
                    "subsurface_storage": (
                        ("time", "z", "y", "x"),
                        np.zeros((3, 1, 2, 2)),
                    ),
                }
            )
            with self.assertRaises(ValueError):
                write_sidecar_atomic(year_dir, bad, expected_time=8)
            self.assertFalse((year_dir / SIDECAR_NAME).is_file())

    def test_consolidated_path_uses_year_dir(self):
        ref = Path("/data/raw_runs/abc/derived_hourly.nc")
        self.assertEqual(
            consolidated_path(ref, 219),
            Path("/data/raw_runs/abc/processed_output_219h.nc"),
        )
        legacy = Path("/data/raw_runs/abc/processed_output.nc")
        self.assertEqual(
            consolidated_path(legacy, 219),
            Path("/data/raw_runs/abc/processed_output_219h.nc"),
        )


if __name__ == "__main__":
    unittest.main()
