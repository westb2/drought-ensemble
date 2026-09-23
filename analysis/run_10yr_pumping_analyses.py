#!/usr/bin/env python3
"""Run the 3-yr pumping analysis suite against ``10_year_pumping_tests``.

Outputs use the ``ten_year_`` prefix. Stress length is 10 years; recovery
panels use 5 years so they fit ``short_baseline`` (55 yr) and match the
10-yr drought recovery window. Vs-drought comparisons use ``10_year_drought``.

Usage::

    PUMPING_STRESS_YEARS=10 python analysis/run_10yr_pumping_analyses.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Must be set before analysis modules are imported.
os.environ["PUMPING_STRESS_YEARS"] = "10"

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
sys.path.insert(0, str(ROOT))

from analysis import pumping_stress_settings as S  # noqa: E402


def _patch_module(mod, *, drought: bool = False):
    """Apply 10-yr constants and rename outputs on an already-imported module."""
    tag = S.fig_tag()
    if hasattr(mod, "PUMP_ENSEMBLE"):
        mod.PUMP_ENSEMBLE = S.pump_ensemble()
    if hasattr(mod, "PUMP_YEARS"):
        mod.PUMP_YEARS = S.pump_years()
    if hasattr(mod, "STRESS_YEARS"):
        mod.STRESS_YEARS = S.pump_years()
    if hasattr(mod, "RECOVERY_YEARS"):
        mod.RECOVERY_YEARS = S.recovery_years()
    if hasattr(mod, "PUMP_RECOVERY"):
        mod.PUMP_RECOVERY = S.recovery_years()
    if hasattr(mod, "COMPARE_RECOVERY"):
        mod.COMPARE_RECOVERY = S.recovery_years()
    if hasattr(mod, "DROUGHT_RECOVERY"):
        mod.DROUGHT_RECOVERY = S.drought_recovery_years()
    if hasattr(mod, "N_YEARS"):
        mod.N_YEARS = S.n_years()
    if drought and hasattr(mod, "DROUGHT_MEMBER"):
        mod.DROUGHT_MEMBER = S.drought_member()

    # Prefix figure / summary / json outputs.
    for attr in ("SUMMARY_MD", "OUT_JSON"):
        if hasattr(mod, attr):
            p = Path(getattr(mod, attr))
            name = S.out_name(p.name) if attr == "OUT_JSON" else None
            if attr == "SUMMARY_MD":
                name = p.name if p.name.startswith("ten_year_") else "ten_year_" + p.name
            setattr(mod, attr, p.with_name(name))

    # Wrap fig.savefig destinations by patching Path construction in known outs —
    # instead, monkeypatch FIG_DIR / "pumping_..." via a thin helper used below.
    return mod


def _retarget_png_saves(mod):
    """Prefix ``pumping_*.png`` / json with ``ten_year_`` then resolve category."""
    from analysis.figure_paths import fig_path as _fig_path

    class FigDirProxy:
        def __truediv__(self, other):
            name = str(other)
            if name.endswith((".png", ".json")):
                name = S.out_name(name)
            if "/" in name or name.startswith("_"):
                # cache / subdir — keep under figures/_cache via smart FIG_DIR
                from analysis.figure_paths import FIG_DIR as _FD

                return _FD / name
            return _fig_path(name)

        def __str__(self):
            from analysis.figure_paths import FIG_ROOT

            return str(FIG_ROOT)

        def __fspath__(self):
            return str(self)

        def mkdir(self, *a, **k):
            from analysis.figure_paths import ensure_category_dirs

            return ensure_category_dirs()

    mod.FIG_DIR = FigDirProxy()
    return mod


def run_recovery_timeseries():
    import analysis.pumping_recovery_timeseries as M

    _patch_module(M)
    _retarget_png_saves(M)
    # Rebuild N_YEARS-dependent path helper closure
    print(
        f"[timeseries] ensemble={M.PUMP_ENSEMBLE} pump={M.PUMP_YEARS} "
        f"rec={M.RECOVERY_YEARS} n={M.N_YEARS}",
        flush=True,
    )
    M.main()


def run_vs_drought():
    import analysis.pumping_vs_drought_deficits as M

    _patch_module(M, drought=True)
    _retarget_png_saves(M)
    print(
        f"[vs_drought] pump={M.STRESS_YEARS} drought={M.DROUGHT_MEMBER} "
        f"ensemble={M.PUMP_ENSEMBLE}",
        flush=True,
    )
    M.main()


def run_annualized_q():
    import analysis.pumping_annualized_q as M

    _patch_module(M)
    _retarget_png_saves(M)
    print(f"[annualized_q] pump={M.PUMP_YEARS} n={M.N_YEARS}", flush=True)
    M.main()


def _patch_redo_modules():
    """Patch both import identities of redo_pumping_recovery_analogues.

    ``pumping_streamflow_impact`` does ``sys.path.insert(..., ROOT/analysis)`` then
    ``from redo_pumping_recovery_analogues import ...``, which can load a second
    module object distinct from ``analysis.redo_pumping_recovery_analogues``.
    """
    import analysis.redo_pumping_recovery_analogues as R

    _patch_module(R)
    _retarget_png_saves(R)
    alt = sys.modules.get("redo_pumping_recovery_analogues")
    if alt is not None and alt is not R:
        _patch_module(alt)
        _retarget_png_saves(alt)
    return R


def run_streamflow():
    import analysis.pumping_streamflow_impact as M

    R = _patch_redo_modules()
    # Re-bind names streamflow imported as copies
    M.PUMP_YEARS = S.pump_years()
    if hasattr(M, "PUMP_ENSEMBLE"):
        M.PUMP_ENSEMBLE = S.pump_ensemble()
    # Prefer 219h products over slim-from-raw for pump years.
    R.ensure_pumping_cache = _ensure_pumping_cache_219h(R)
    alt = sys.modules.get("redo_pumping_recovery_analogues")
    if alt is not None and alt is not R:
        alt.ensure_pumping_cache = R.ensure_pumping_cache
    _retarget_png_saves(M)
    _patch_module(M)
    print(f"[streamflow] pump={M.PUMP_YEARS} ensemble={R.PUMP_ENSEMBLE}", flush=True)
    M.main()


def _ensure_pumping_cache_219h(R):
    """Use consolidated processed_output_219h when present (has storage + Q)."""
    from pathlib import Path as _Path

    from analysis.paper_figures import utils as _utils

    def ensure_pumping_cache(domain_name: str, rate: float):
        hourly = R.pumping_hourly_files(domain_name, rate)
        base = R.baseline_219h_files(domain_name)
        assert len(hourly) == R.SPINUP_YEARS + R.PUMP_YEARS
        member = R._resolve_member(rate)
        files_219 = _utils._file_locations(
            R.PUMP_ENSEMBLE, member, domain_name, 0, interval=R.INTERVAL
        )
        paths = []
        for i in range(R.SPINUP_YEARS):
            paths.append(_Path(base[i]))
        for i in range(R.SPINUP_YEARS, R.SPINUP_YEARS + R.PUMP_YEARS):
            p219 = _Path(files_219[i])
            if p219.exists() and p219.name.startswith("processed_output_219h"):
                paths.append(p219)
            else:
                paths.append(R.build_slim_219h(domain_name, hourly[i]))
        return paths

    return ensure_pumping_cache


def run_shallow_deep():
    R = _patch_redo_modules()
    import analysis.pumping_shallow_deep_proxies as M

    M.PUMP_YEARS = S.pump_years()
    M.PUMP_ENSEMBLE = S.pump_ensemble()
    _patch_module(M)
    _retarget_png_saves(M)
    print(f"[shallow_deep] pump={M.PUMP_YEARS} ensemble={R.PUMP_ENSEMBLE}", flush=True)
    M.main()


def run_overland():
    import analysis.pumping_vs_drought_deficits as V
    import analysis.pumping_overland_persist as M

    _patch_module(V, drought=True)
    # overland imports STRESS_YEARS, DROUGHT_MEMBER from vs_drought
    M.STRESS_YEARS = S.pump_years()
    M.DROUGHT_MEMBER = S.drought_member()
    M.PUMP_ENSEMBLE = S.pump_ensemble()
    _patch_module(M, drought=True)
    _retarget_png_saves(M)
    print(f"[overland] stress={M.STRESS_YEARS} drought={M.DROUGHT_MEMBER}", flush=True)
    M.main()


def run_analogues():
    """During-pumping / early-buildup analogues (end markers use PUMP_YEARS)."""
    M = _patch_redo_modules()
    M.ensure_pumping_cache = _ensure_pumping_cache_219h(M)
    print(f"[analogues] pump={M.PUMP_YEARS} ensemble={M.PUMP_ENSEMBLE}", flush=True)
    M.main()


def main():
    assert S.is_10yr()
    print(
        f"10-yr pumping analyses → tag={S.fig_tag()!r}, "
        f"n_years={S.n_years()}, recovery={S.recovery_years()} "
        f"(baseline-limited)",
        flush=True,
    )
    steps = [
        ("recovery_timeseries", run_recovery_timeseries),
        ("vs_drought", run_vs_drought),
        ("annualized_q", run_annualized_q),
        ("streamflow", run_streamflow),
        ("shallow_deep", run_shallow_deep),
        ("overland", run_overland),
        ("analogues", run_analogues),
    ]
    requested = sys.argv[1:]
    for name, fn in steps:
        if requested and name not in requested:
            continue
        print(f"\n======== {name} ========", flush=True)
        fn()
    print("\nAll requested 10-yr pumping analyses finished.", flush=True)


if __name__ == "__main__":
    main()
