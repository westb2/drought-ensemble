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


def _write_nc(path: Path, ntime: int) -> None:
    from netCDF4 import Dataset

    path.parent.mkdir(parents=True, exist_ok=True)
    with Dataset(str(path), "w") as ds:
        ds.createDimension("time", ntime)
        ds.createVariable("time", "f8", ("time",))


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

    def test_truncated_netcdf_is_tip_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seq_path = self._write_seq(root)
            domain = "wolf2"
            raw = root / "domains" / domain / "raw_runs"
            raw.mkdir(parents=True)
            years = json.loads(seq_path.read_text())["years"]
            h0 = rw.hash_years(years[:1])
            h1 = rw.hash_years(years[:2])
            _write_nc(raw / h0 / "run.out.00001.nc", ntime=24)
            _write_nc(raw / h1 / "run.out.00001.nc", ntime=100)

            st = rw.assess_sequence(root, domain, "ens", seq_path)
            self.assertIsNotNone(st.tip_incomplete)
            self.assertEqual(st.tip_incomplete.index, 1)
            self.assertFalse(st.tip_incomplete.complete)
            self.assertEqual(st.missing_years, [2])
            self.assertEqual(st.mid_incomplete, [])

    def test_unreadable_tip_netcdf_is_incomplete(self):
        """A tip NetCDF that cannot be read (mid-write/corrupt) is not complete."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seq_path = self._write_seq(root)
            domain = "wolf2"
            raw = root / "domains" / domain / "raw_runs"
            raw.mkdir(parents=True)
            years = json.loads(seq_path.read_text())["years"]
            h0 = rw.hash_years(years[:1])
            h1 = rw.hash_years(years[:2])
            _write_nc(raw / h0 / "run.out.00001.nc", ntime=24)
            (raw / h1).mkdir()
            (raw / h1 / "run.out.00001.nc").write_text("not a netcdf file")

            self.assertIsNone(rw.netcdf_time_len(raw / h1 / "run.out.00001.nc"))
            st = rw.assess_sequence(root, domain, "ens", seq_path)
            self.assertIsNotNone(st.tip_incomplete)
            self.assertEqual(st.tip_incomplete.index, 1)

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
            _write_nc(raw / h2 / "run.out.00001.nc", ntime=24)

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


class WakeStateTests(unittest.TestCase):
    def _status(
        self,
        *,
        needs_work: bool = False,
        active_id: str | None = None,
        mid: bool = False,
    ) -> rw.TargetStatus:
        tip = None
        mid_list = []
        years = [
            rw.YearStatus(0, "a" * 64, Path("/tmp/a"), True, True),
            rw.YearStatus(1, "b" * 64, Path("/tmp/b"), True, not needs_work),
        ]
        if needs_work and not mid:
            tip = years[1]
        if mid:
            mid_list = [years[0]]
        st = rw.TargetStatus(
            domain="wolf2",
            ensemble="ens",
            sequence_name="toy",
            sequence_path=Path("/tmp/toy.json"),
            years=years,
            tip_incomplete=tip,
            mid_incomplete=mid_list,
            missing_years=[],
            needs_work=needs_work or mid,
            blocked_reason=(
                f"active job {active_id} state=Q" if active_id else None
            ),
            active_job={"id": active_id, "name": "wolf2_ens_toy", "state": "Q"}
            if active_id
            else None,
        )
        return st

    def test_watching_active_job_is_not_dirty(self):
        st = self._status(needs_work=True, active_id="7217032.desched1")
        wake = rw.build_wake_state(
            statuses=[st],
            deleted=[],
            submitted=[],
            planned_delete_count=0,
            planned_submit_count=0,
            apply=True,
            quota_blocks=False,
            no_submit=False,
            max_idle_hours=24,
        )
        self.assertEqual(wake["dirty"], "0")
        self.assertEqual(wake["reason"], "watching_jobs")
        self.assertEqual(wake["job_ids"], "7217032.desched1")

    def test_successful_submit_watches_new_job(self):
        st = self._status(needs_work=True)
        wake = rw.build_wake_state(
            statuses=[st],
            deleted=[],
            submitted=["7217032.desched1"],
            planned_delete_count=0,
            planned_submit_count=1,
            apply=True,
            quota_blocks=False,
            no_submit=False,
            max_idle_hours=24,
        )
        self.assertEqual(wake["dirty"], "0")
        self.assertIn("7217032.desched1", wake["job_ids"])

    def test_quota_blocked_submit_stays_dirty(self):
        st = self._status(needs_work=True)
        wake = rw.build_wake_state(
            statuses=[st],
            deleted=[],
            submitted=[],
            planned_delete_count=0,
            planned_submit_count=1,
            apply=True,
            quota_blocks=True,
            no_submit=False,
            max_idle_hours=24,
        )
        self.assertEqual(wake["dirty"], "1")
        self.assertEqual(wake["reason"], "actionable_work")

    def test_decide_skips_while_job_present(self):
        wake = {
            "dirty": "0",
            "reason": "watching_jobs",
            "job_ids": "7217032.desched1",
            "epoch": str(rw._now_epoch()),
            "max_idle_hours": "24",
        }
        submit, reason = rw.decide_casper_submit(wake, ["7217032.desched1"])
        self.assertFalse(submit)
        self.assertIn("skip", reason)

    def test_decide_submits_when_job_leaves(self):
        wake = {
            "dirty": "0",
            "reason": "watching_jobs",
            "job_ids": "7217032.desched1",
            "epoch": str(rw._now_epoch()),
            "max_idle_hours": "24",
        }
        submit, reason = rw.decide_casper_submit(wake, ["999.desched1"])
        self.assertTrue(submit)
        self.assertIn("job_left_queue", reason)

    def test_decide_submits_on_max_idle(self):
        wake = {
            "dirty": "0",
            "reason": "clean",
            "job_ids": "",
            "epoch": str(rw._now_epoch() - 25 * 3600),
            "max_idle_hours": "24",
        }
        submit, reason = rw.decide_casper_submit(wake, [])
        self.assertTrue(submit)
        self.assertIn("max_idle", reason)

    def test_decide_submits_when_dirty(self):
        wake = {
            "dirty": "1",
            "reason": "actionable_work",
            "job_ids": "",
            "epoch": str(rw._now_epoch()),
            "max_idle_hours": "24",
        }
        submit, reason = rw.decide_casper_submit(wake, [])
        self.assertTrue(submit)
        self.assertIn("dirty", reason)

    def test_decide_cli_skip_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wake_state.txt"
            rw.write_wake_state(
                {
                    "dirty": "0",
                    "reason": "watching_jobs",
                    "job_ids": "7217032.desched1",
                    "epoch": str(rw._now_epoch()),
                    "utc": rw._utc_stamp(),
                    "max_idle_hours": "24",
                },
                path=path,
            )
            code, reason = rw.run_decide_submit(
                wake_path=path,
                current_job_ids=["7217032.desched1"],
                probe_qstat=False,
            )
            self.assertEqual(code, rw.DECIDE_SKIP)
            self.assertIn("skip", reason)

    def test_heartbeat_allows_idle_scan_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp)
            old_cron = rw.CRON_STATUS
            old_cycle = rw.CYCLE_HEARTBEAT
            old_wake = rw.WAKE_STATE
            try:
                rw.CRON_STATUS = logs / "last_status.txt"
                rw.CYCLE_HEARTBEAT = logs / "last_cycle.txt"
                rw.WAKE_STATE = logs / "wake_state.txt"
                now = rw._now_epoch()
                rw.CRON_STATUS.write_text(
                    f"epoch={now}\nutc=now\nresult=ok\ndetail=skipped\n"
                )
                # Cycle 18h ago: unhealthy at 12h cron ceiling, healthy at 24h idle max
                rw.CYCLE_HEARTBEAT.write_text(
                    f"epoch={now - 18 * 3600}\nutc=old\nmode=apply\n"
                    "deleted=0\nsubmitted=0\nstuck=0\n"
                )
                cfg = {"safety": {"max_heartbeat_age_hours": 12, "max_idle_scan_hours": 24}}
                hb = rw.check_heartbeat(cfg)
                self.assertTrue(hb["healthy"], hb["problems"])
                cfg_tight = {"safety": {"max_heartbeat_age_hours": 12, "max_idle_scan_hours": 12}}
                hb2 = rw.check_heartbeat(cfg_tight)
                self.assertFalse(hb2["healthy"])
            finally:
                rw.CRON_STATUS = old_cron
                rw.CYCLE_HEARTBEAT = old_cycle
                rw.WAKE_STATE = old_wake


if __name__ == "__main__":
    unittest.main()
