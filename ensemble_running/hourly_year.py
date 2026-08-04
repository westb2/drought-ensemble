"""Hourly year products: raw ParFlow + thin derived sidecar (or legacy full file).

Layout under ``domains/<domain>/raw_runs/<hash>/``::

    run.out.00000.nc       # statics
    run.out.00001.nc       # ParFlow transient (untouched)
    derived_hourly.nc      # overland_flow + subsurface_storage only (new)
    processed_output.nc    # legacy full hourly (still readable)
    processed_output_219h.nc

``file_locations.json`` entries may point at ``derived_hourly.nc`` or legacy
``processed_output.nc``; both resolve to the same year directory.
"""

from __future__ import annotations

import os
import tempfile
import weakref
from pathlib import Path
from typing import Iterable

import xarray as xr

ONE_YEAR_HOURS = 8760

RAW_STATIC = "run.out.00000.nc"
RAW_TRANSIENT = "run.out.00001.nc"
SIDECAR_NAME = "derived_hourly.nc"
LEGACY_HOURLY = "processed_output.nc"

DERIVED_VARS = ("overland_flow", "subsurface_storage")
STATIC_VARS = (
    "mask",
    "mannings",
    "porosity",
    "specific_storage",
    "DZ_Multiplier",
    "slopex",
    "slopey",
    "perm_x",
    "perm_y",
    "perm_z",
)

# Datasets from open_hourly_year -> underlying open handles to close
_HOURLY_HANDLES: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def resolve_year_dir(hourly_ref: str | Path) -> Path:
    """Year directory from a ``file_locations.json`` entry or directory path."""
    path = Path(hourly_ref)
    if path.is_dir():
        return path
    return path.parent


def sidecar_path(year_dir: str | Path) -> Path:
    return Path(year_dir) / SIDECAR_NAME


def legacy_hourly_path(year_dir: str | Path) -> Path:
    return Path(year_dir) / LEGACY_HOURLY


def raw_transient_path(year_dir: str | Path) -> Path:
    return Path(year_dir) / RAW_TRANSIENT


def raw_static_path(year_dir: str | Path) -> Path:
    return Path(year_dir) / RAW_STATIC


def hourly_ref_path(
    year_dir: str | Path, *, expected_time: int = ONE_YEAR_HOURS
) -> Path:
    """Canonical path to store in ``file_locations.json`` for this year."""
    year_dir = Path(year_dir)
    if _sidecar_looks_valid(year_dir, expected_time):
        return sidecar_path(year_dir)
    if _legacy_looks_valid(year_dir, expected_time):
        return legacy_hourly_path(year_dir)
    if legacy_hourly_path(year_dir).is_file():
        return legacy_hourly_path(year_dir)
    return sidecar_path(year_dir)


def _time_size(path: Path) -> int | None:
    """Read ``time`` length from NetCDF metadata only (no full load)."""
    try:
        import netCDF4

        with netCDF4.Dataset(path, "r") as nc:
            if "time" not in nc.dimensions:
                return 0
            return len(nc.dimensions["time"])
    except Exception:  # noqa: BLE001
        try:
            with xr.open_dataset(path) as ds:
                return int(ds.sizes.get("time", 0))
        except Exception:  # noqa: BLE001
            return None


def _sidecar_looks_valid(year_dir: Path, expected_time: int = ONE_YEAR_HOURS) -> bool:
    path = sidecar_path(year_dir)
    if not path.is_file():
        return False
    n = _time_size(path)
    if n != expected_time:
        return False
    try:
        import netCDF4

        with netCDF4.Dataset(path, "r") as nc:
            return all(v in nc.variables for v in DERIVED_VARS)
    except Exception:  # noqa: BLE001
        try:
            with xr.open_dataset(path) as ds:
                return all(v in ds.data_vars for v in DERIVED_VARS)
        except Exception:  # noqa: BLE001
            return False


def _legacy_looks_valid(year_dir: Path, expected_time: int = ONE_YEAR_HOURS) -> bool:
    path = legacy_hourly_path(year_dir)
    if not path.is_file():
        return False
    n = _time_size(path)
    return n == expected_time


def _raw_looks_valid(year_dir: Path, expected_time: int = ONE_YEAR_HOURS) -> bool:
    path = raw_transient_path(year_dir)
    if not path.is_file():
        return False
    n = _time_size(path)
    return n == expected_time


def hourly_product_ready(
    year_dir: str | Path, *, expected_time: int = ONE_YEAR_HOURS
) -> bool:
    """True if a trustworthy hourly derived product exists (sidecar or legacy)."""
    year_dir = Path(year_dir)
    if _sidecar_looks_valid(year_dir, expected_time) and _raw_looks_valid(
        year_dir, expected_time
    ):
        return True
    return _legacy_looks_valid(year_dir, expected_time)


def remove_invalid_sidecar(
    year_dir: str | Path, *, expected_time: int = ONE_YEAR_HOURS
) -> bool:
    """Delete an invalid final sidecar (and any ``*.tmp``). Return True if removed."""
    year_dir = Path(year_dir)
    removed = False
    path = sidecar_path(year_dir)
    if path.is_file() and not _sidecar_looks_valid(year_dir, expected_time):
        path.unlink()
        removed = True
    for tmp in year_dir.glob(f"{SIDECAR_NAME}*.tmp"):
        try:
            tmp.unlink()
            removed = True
        except OSError:
            pass
    for tmp in year_dir.glob("derived_hourly.*.nc.tmp"):
        try:
            tmp.unlink()
            removed = True
        except OSError:
            pass
    return removed


def _attach_statics(ds: xr.Dataset, static_path: Path) -> xr.Dataset:
    if not static_path.is_file():
        return ds
    with xr.open_dataset(static_path) as static_ds:
        for name in STATIC_VARS:
            if name not in static_ds:
                continue
            da = static_ds[name]
            if "time" in da.dims:
                da = da.isel(time=0)
            ds[name] = da.load()
    return ds


def open_hourly_year(
    hourly_ref: str | Path,
    *,
    chunks: dict | None = None,
    expected_time: int = ONE_YEAR_HOURS,
) -> xr.Dataset:
    """Open one year as a merged hourly Dataset (raw+sidecar, or legacy).

    Prefer ``derived_hourly.nc`` + ``run.out.00001.nc`` when both are valid.
    Fall back to legacy ``processed_output.nc``.

    Caller should use :func:`close_hourly_year` when finished so sidecar
    backends are released.
    """
    year_dir = resolve_year_dir(hourly_ref)
    open_kw = {}
    if chunks is not None:
        open_kw["chunks"] = chunks

    if _sidecar_looks_valid(year_dir, expected_time) and raw_transient_path(
        year_dir
    ).is_file():
        raw_ds = xr.open_dataset(raw_transient_path(year_dir), **open_kw)
        side_ds = xr.open_dataset(sidecar_path(year_dir), **open_kw)
        try:
            missing = [v for v in DERIVED_VARS if v not in side_ds]
            if missing:
                raise KeyError(f"{sidecar_path(year_dir)} missing {missing}")
            merged = raw_ds.assign(**{v: side_ds[v] for v in DERIVED_VARS})
            merged.attrs["hourly_layout"] = "raw+sidecar"
            merged.attrs["source_year_dir"] = str(year_dir)
            merged = _attach_statics(merged, raw_static_path(year_dir))
            _register_hourly_handles(merged, [raw_ds, side_ds])
            return merged
        except Exception:
            raw_ds.close()
            side_ds.close()
            raise

    legacy = legacy_hourly_path(year_dir)
    if legacy.is_file() and _legacy_looks_valid(year_dir, expected_time):
        ds = xr.open_dataset(legacy, **open_kw)
        ds.attrs["hourly_layout"] = "legacy"
        ds.attrs["source_year_dir"] = str(year_dir)
        _register_hourly_handles(ds, [ds])
        return ds

    raise FileNotFoundError(
        f"No hourly product in {year_dir}: need valid {SIDECAR_NAME}+"
        f"{RAW_TRANSIENT} or {LEGACY_HOURLY}"
    )


def _register_hourly_handles(ds: xr.Dataset, handles: list) -> None:
    try:
        _HOURLY_HANDLES[ds] = handles
    except TypeError:
        # Dataset not weak-referenceable on some xarray builds
        _HOURLY_HANDLES_BY_ID[id(ds)] = (ds, handles)


_HOURLY_HANDLES_BY_ID: dict[int, tuple] = {}


def close_hourly_year(ds: xr.Dataset) -> None:
    """Close a dataset from :func:`open_hourly_year`, including sidecar handles."""
    handles = None
    try:
        handles = _HOURLY_HANDLES.pop(ds, None)
    except Exception:  # noqa: BLE001
        handles = None
    if handles is None:
        entry = _HOURLY_HANDLES_BY_ID.pop(id(ds), None)
        if entry is not None:
            handles = entry[1]

    if handles:
        seen: set[int] = set()
        for handle in handles:
            hid = id(handle)
            if hid in seen:
                continue
            seen.add(hid)
            try:
                handle.close()
            except Exception:  # noqa: BLE001
                pass
    else:
        ds.close()


def write_sidecar_atomic(
    year_dir: str | Path,
    derived: xr.Dataset | dict[str, xr.DataArray],
    *,
    expected_time: int = ONE_YEAR_HOURS,
    encoding: dict | None = None,
) -> Path:
    """Atomically write ``derived_hourly.nc`` with only derived variables.

    Writes to a temp file in the same directory, validates time length and
    required variables, then ``os.replace`` onto the final name.
    """
    year_dir = Path(year_dir)
    year_dir.mkdir(parents=True, exist_ok=True)
    out_path = sidecar_path(year_dir)

    if isinstance(derived, xr.Dataset):
        ds = derived
    else:
        ds = xr.Dataset(derived)

    missing = [v for v in DERIVED_VARS if v not in ds]
    if missing:
        raise KeyError(f"sidecar write missing variables: {missing}")

    to_write = ds[list(DERIVED_VARS)]
    n_time = int(to_write.sizes.get("time", 0))
    if n_time != expected_time:
        raise ValueError(
            f"sidecar time length {n_time} != expected {expected_time}"
        )

    to_write.attrs["source_raw"] = str(raw_transient_path(year_dir))
    to_write.attrs["derived_vars"] = ",".join(DERIVED_VARS)
    to_write.attrs["hours_per_year"] = expected_time

    if encoding is None:
        encoding = {}
        for name, da in to_write.data_vars.items():
            enc = {"zlib": True, "complevel": 4}
            chunks = []
            for dim in da.dims:
                if dim == "time":
                    chunks.append(min(219, da.sizes[dim]))
                elif dim == "z":
                    chunks.append(da.sizes[dim])
                else:
                    chunks.append(min(64, da.sizes[dim]))
            enc["chunksizes"] = tuple(chunks)
            encoding[name] = enc

    fd, tmp_name = tempfile.mkstemp(
        prefix="derived_hourly.",
        suffix=".nc.tmp",
        dir=year_dir,
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        to_write.to_netcdf(tmp_path, encoding=encoding)
        # Validate before publish
        with xr.open_dataset(tmp_path) as check:
            if int(check.sizes.get("time", 0)) != expected_time:
                raise ValueError("sidecar temp failed time validation")
            if any(v not in check.data_vars for v in DERIVED_VARS):
                raise ValueError("sidecar temp failed variable validation")
        os.replace(tmp_path, out_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise

    return out_path


def extract_sidecar_from_legacy(
    year_dir: str | Path,
    *,
    overwrite: bool = False,
) -> Path | None:
    """Create ``derived_hourly.nc`` from legacy ``processed_output.nc`` if needed."""
    year_dir = Path(year_dir)
    if _sidecar_looks_valid(year_dir) and not overwrite:
        return sidecar_path(year_dir)
    legacy = legacy_hourly_path(year_dir)
    if not legacy.is_file():
        return None
    with xr.open_dataset(legacy) as ds:
        missing = [v for v in DERIVED_VARS if v not in ds]
        if missing:
            raise KeyError(f"{legacy} missing {missing}")
        return write_sidecar_atomic(year_dir, ds[list(DERIVED_VARS)])


def open_hourly_paths(
    paths: Iterable[str | Path],
    *,
    chunks: dict | None = None,
) -> xr.Dataset:
    """Concat year refs along time (lazy when ``chunks`` is set)."""
    datasets = [open_hourly_year(p, chunks=chunks) for p in paths]
    if not datasets:
        raise ValueError("no hourly paths to open")
    if len(datasets) == 1:
        return datasets[0]
    return xr.concat(datasets, dim="time", combine_attrs="override")
