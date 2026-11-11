"""devtools/perf_metrics.py: the optimization test's maths (frame pacing, thermals, memory, the runtime's [perf] lines) and its budget check,
on synthetic device output, so a regression in the analyzer shows without a device. The budget file of each device must load and be sane."""
import json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'devtools'))
import perf_metrics as pm   # noqa: E402

MS = 1_000_000
BUDGETS = ROOT / 'devtools/perf_budgets'


def presents(frame_ms, start=10_000 * MS):
    t, out = start, [start]
    for f in frame_ms: t += int(f * MS); out.append(t)
    return out


def sf_dump(ts, period=8_333_333):
    rows = [str(period)] + [f'{t - 5 * MS}\t{t}\t{t - 2 * MS}' for t in ts]
    rows += [f'0\t{pm.PENDING}\t0', '']   # a frame queued but not presented yet
    return '\n'.join(rows)


class SurfaceFlinger(unittest.TestCase):
    def test_parse(self):
        ts = presents([33.3] * 10)
        period, got = pm.parse_sf_latency(sf_dump(ts))
        self.assertEqual(period, 8_333_333)
        self.assertEqual(got, ts)   # the pending row is dropped

    def test_merge_overlapping_polls(self):
        ts = presents([33.3] * 200)
        seen = set()
        self.assertEqual(pm.merge_timestamps(seen, ts[:128]), 128)
        self.assertEqual(pm.merge_timestamps(seen, ts[100:]), len(ts) - 128)   # 28 repeated frames are not counted twice

    def test_pick_layer(self):
        pkg = 'org.nx2a.t010050f00bc1a000'
        a15 = f'''RequestedLayerState{{{pkg}/android.app.NativeActivity#1055 parentId=1054}}
RequestedLayerState{{e09fa56 {pkg}/android.app.NativeActivity#1054 parentId=1041}}
RequestedLayerState{{a1fe8d4 ActivityRecordInputSink {pkg}/android.app.NativeActivity#1047 parentId=1041 z=-2147483648}}
RequestedLayerState{{ActivityRecord{{efd1e27 u0 {pkg}/android.app.NativeActivity t21, isEmbedded=false}}#1041 parentId=1040}}
RequestedLayerState{{StatusBar#80 parentId=79}}'''   # Android 15 (Legion Y700 2023): the window's buffer layer, not its token, record or input sink
        self.assertEqual(pm.pick_layer(a15, pkg), f'{pkg}/android.app.NativeActivity#1055')
        old = f'SurfaceView[{pkg}/x.Main](BLAST)#12\nBackground for SurfaceView[{pkg}/x.Main]#13\n{pkg}/x.Main#11'
        self.assertEqual(pm.pick_layer(old, pkg), f'SurfaceView[{pkg}/x.Main](BLAST)#12')
        self.assertIsNone(pm.pick_layer('StatusBar#80', pkg))

    def test_garbage(self):
        self.assertEqual(pm.parse_sf_latency(''), (0, []))
        self.assertEqual(pm.parse_sf_latency('no such layer'), (0, []))


class Pacing(unittest.TestCase):
    V = 8_333_333   # 120 Hz

    def rows(self, shown_vsyncs, ready_before_ms=12.0):
        """Frames that each ask for the vsync 4 after the last one's target (30 fps on 120 Hz) and are shown shown_vsyncs[i] vsyncs after the previous one"""
        out, tgt, shown = {}, 1_000 * MS, 1_000 * MS
        for i, v in enumerate([4] + list(shown_vsyncs)):
            if i: tgt += 4 * self.V; shown += v * self.V
            out[shown - self.V // 2] = (tgt - self.V // 2, tgt - int(ready_before_ms * MS))
        return out

    def test_steady(self):
        m = pm.pace_metrics(self.rows([4] * 100), self.V)
        self.assertEqual((m['off_cadence'], m['cadence_changes']), (0, 0))
        self.assertAlmostEqual(m['ready_margin_p50_ms'], 12.0 - 4.17, delta=0.01)   # ready to shown: the rows' frames are shown half a vsync before their target

    def test_latch_missed(self):
        m = pm.pace_metrics(self.rows([4] * 20 + [5, 3] + [4] * 20 + [3, 5] + [4] * 20), self.V)   # one frame shown a vsync late, one a vsync early: each makes two odd intervals
        self.assertEqual(m['off_cadence'], 4); self.assertEqual(m['cadence_changes'], 0)

    def test_resync(self):
        r = self.rows([4] * 30)
        later = {a + self.V: (d + self.V, rd + self.V) for a, (d, rd) in list(r.items())[10:]}   # the pacer moved its cadence a vsync out at frame 10
        r = dict(list(r.items())[:10]); r.update(later)
        m = pm.pace_metrics(r, self.V)
        self.assertEqual(m['off_cadence'], 0); self.assertEqual(m['cadence_changes'], 2)   # the pacer's own 5-vsync step, then back to 4: shown as asked

    def test_rows_parse(self):
        period, rows = pm.parse_sf_rows(f'{self.V}\n100\t200\t150\n0\t{pm.PENDING}\t0\n')
        self.assertEqual((period, rows), (self.V, {200: (100, 150)}))


class FrameMetrics(unittest.TestCase):
    def test_steady_30(self):
        m = pm.frame_metrics(presents([1000 / 30] * 1800), 30)
        self.assertAlmostEqual(m['avg_fps'], 30.0, delta=0.05)
        self.assertAlmostEqual(m['low1_fps'], 30.0, delta=0.05)
        self.assertEqual(m['stutters'], 0)
        self.assertLess(m['jitter_ms'], 0.01)
        self.assertAlmostEqual(m['drift_pct'], 0.0, delta=0.1)

    def test_stutters_and_low(self):
        f = [1000 / 30] * 600
        for i in range(0, 600, 100): f[i] = 100.0   # 6 hitches of 100 ms (> 2 × 33.3)
        m = pm.frame_metrics(presents(f), 30)
        self.assertEqual(m['stutters'], 6)
        self.assertAlmostEqual(m['low1_fps'], 10.0, delta=0.01)   # the worst 1% (6 frames) are all the hitches
        self.assertAlmostEqual(m['max_ms'], 100.0, delta=0.01)
        self.assertGreater(m['p99_ms'], 33.4)
        self.assertLess(m['avg_fps'], 30.0)

    def test_thermal_drift(self):
        m = pm.frame_metrics(presents([1000 / 30] * 1000 + [1000 / 24] * 1000), 30)   # throttled to 24 fps in the second half
        self.assertAlmostEqual(m['drift_pct'], -20.0, delta=0.5)

    def test_load_screen_gap(self):
        m = pm.frame_metrics(presents([1000 / 30] * 300 + [4000] + [1000 / 30] * 300), 30)
        self.assertEqual(m['long_gaps'], 1)   # a 4 s load is not a frame, so it does not count as a stutter
        self.assertEqual(m['stutters'], 0)
        self.assertAlmostEqual(m['avg_fps'], 30.0, delta=0.05)

    def test_percentiles(self):
        m = pm.frame_metrics(presents(list(range(1, 101))), 30, max_gap_s=10)
        self.assertAlmostEqual(m['p50_ms'], 50.5, delta=0.01)
        self.assertAlmostEqual(m['p99_ms'], 99.01, delta=0.01)

    def test_empty(self):
        self.assertEqual(pm.frame_metrics([], 30)['frames'], 0)


THERMAL = '''IsStatusOverride: false
Thermal Status: 2
Cached temperatures:
	Temperature{mValue=41.2, mType=3, mName=skin-therm, mStatus=0}
Current temperatures from HAL:
	Temperature{mValue=58.0, mType=0, mName=cpu-1-1, mStatus=0}
	Temperature{mValue=43.5, mType=3, mName=skin-therm, mStatus=2}
	Temperature{mValue=36.1, mType=2, mName=battery, mStatus=0}
'''
MEMINFO_13 = '''Applications Memory Usage (in Kilobytes):
 App Summary
           Java Heap:    12000
               TOTAL PSS:  3456789            TOTAL RSS:  3600000      TOTAL SWAP PSS:     12
'''
MEMINFO_OLD = '''                   Pss  Private
                 Total    Dirty
        TOTAL  2345678  2000000
'''
LOG = '''[perf] ADPF session open (target 33.33 ms, thread 1234; GPU time on, load increases on)
[perf] adaptive frame rate: 30 fps, frame work p50 14.2 / p90 21.0 / p95 24.8 ms (last 15.0 ms); late on screen 1 of 64, step-downs held back 0
[RED] nvnCommandBufferSetConservativeRasterDilate is not implemented
[perf] adaptive frame rate: 30 fps, frame work p50 15.0 / p90 26.5 / p95 31.2 ms (last 16.0 ms); late on screen 5 of 64, step-downs held back 2
[perf] adaptive frame rate: 20 fps (frames p90 36.1 ms, late on screen 12 of 64)
'''


class DeviceDumps(unittest.TestCase):
    def test_thermal(self):
        self.assertEqual(pm.parse_thermal_status(THERMAL), 2)
        self.assertEqual(pm.parse_skin_temp(THERMAL), 43.5)   # the hottest skin sensor, not the CPU's 58
        self.assertEqual(pm.parse_thermal_status('nothing'), -1)
        self.assertIsNone(pm.parse_skin_temp('nothing'))

    def test_meminfo(self):
        self.assertEqual(pm.parse_meminfo_pss_kb(MEMINFO_13), 3456789)
        self.assertEqual(pm.parse_meminfo_pss_kb(MEMINFO_OLD), 2345678)
        self.assertEqual(pm.parse_meminfo_pss_kb('No process found'), 0)

    def test_battery_power(self):
        self.assertEqual(pm.parse_battery_temp_c('  temperature: 345\n'), 34.5)
        self.assertAlmostEqual(pm.power_watts('-1500000', '4200000'), 6.3)
        self.assertIsNone(pm.power_watts('', '4200000'))

    def test_perf_log(self):
        p = pm.parse_perf_log(LOG)
        self.assertEqual(p['work_samples'], 2)
        self.assertEqual(p['work_p95_ms_max'], 31.2)
        self.assertEqual(p['late_of_64_max'], 5)
        self.assertEqual((p['fps_step_downs'], p['fps_lowest_step']), (1, 20))
        boot = '[perf] adaptive frame rate: 40 fps (frames p90 30.1 ms, late on screen 9 of 64)\n[perf] adaptive frame rate: 30 fps (frames p90 33.8 ms, late on screen 11 of 64)\n'
        self.assertEqual(pm.parse_perf_log(boot, 30)['fps_step_downs'], 0)   # 60 → 40 → 30 at boot is the game's own 30, no slowdown
        self.assertEqual(pm.parse_perf_log(boot, 60)['fps_step_downs'], 2)
        self.assertEqual(p['adpf'], 'open')
        self.assertEqual(p['red_lines'], 1)


def report(fps=30.0, low=29.0, p99=35.0, spm=0.0, drift=0.0, pss=3000.0, thermal=1, skin=40.0, first=8.0, steps=0):
    return {'variant': 'soak', 'frames': {'avg_fps': fps, 'low1_fps': low, 'p99_ms': p99, 'stutters_per_min': spm, 'drift_pct': drift, 'frames': 1000},
            'system': {'peak_pss_mb': pss, 'max_thermal': thermal, 'max_skin_c': skin, 'first_frame_s': first}, 'perf_log': {'fps_step_downs': steps}}


class Budget(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.b = pm.load_budget(BUDGETS / 'y700_2023.json')

    def test_pass(self):
        self.assertEqual(pm.evaluate(report(), self.b, 'soak'), [])

    def test_each_miss(self):
        cases = {'frames.avg_fps': report(fps=28), 'frames.low1_fps': report(low=20), 'frames.p99_ms': report(p99=60), 'frames.stutters_per_min': report(spm=9),
                 'frames.drift_pct': report(drift=-12), 'system.peak_pss_mb': report(pss=7000), 'system.max_thermal': report(thermal=3),
                 'system.max_skin_c': report(skin=47), 'perf_log.fps_step_downs': report(steps=3)}
        for key, r in cases.items():
            with self.subTest(key):
                fails = pm.evaluate(r, self.b, 'soak')
                self.assertEqual(len(fails), 1, fails); self.assertTrue(fails[0].startswith(key))

    def test_unmeasured_fails(self):
        r = report(); del r['system']['max_skin_c']
        self.assertEqual(pm.evaluate(r, self.b, 'soak'), ['system.max_skin_c: not measured'])

    def test_compare(self):
        rows = {p: v for p, _, _, _, v in pm.compare(report(fps=29, p99=45), report(fps=30, p99=38))}
        self.assertEqual(rows['frames.avg_fps'], 'better'); self.assertEqual(rows['frames.p99_ms'], 'better')
        rows = {p: v for p, _, _, _, v in pm.compare(report(pss=3000), report(pss=3500))}
        self.assertEqual(rows['system.peak_pss_mb'], 'worse')

    def test_markdown(self):
        md = pm.markdown(dict(report(), app='org.nx2a.t010050f00bc1a000'), [])
        self.assertIn('**PASS**', md); self.assertIn('MODERATE', pm.markdown(dict(report(thermal=2)), ['x']))


class BudgetFiles(unittest.TestCase):
    def test_every_budget_is_sane(self):
        files = sorted(BUDGETS.glob('*.json'))
        self.assertTrue(files)
        for f in files:
            with self.subTest(f.name):
                b = pm.load_budget(f)
                t = b['target_fps']; self.assertIn(t, (30, 60))
                for v, rules in b['variants'].items():
                    fps = rules.get('frames.avg_fps', {}).get('min')
                    if fps: self.assertLessEqual(fps, t)                                                     # a floor above the cap could never pass
                    p99 = rules.get('frames.p99_ms', {}).get('max')
                    if p99: self.assertGreaterEqual(p99, 1000 / t)                                           # nor a p99 below one frame
                    th = rules.get('system.max_thermal', {}).get('max')
                    if th is not None: self.assertLess(th, 3)                                                # SEVERE throttles hard: never a pass
                self.assertIn('smoke', b['variants']); self.assertIn('soak', b['variants'])

    def test_y700_2023_fits_12gb(self):
        b = json.loads((BUDGETS / 'y700_2023.json').read_text(encoding='utf-8'))
        for v in ('smoke', 'soak'): self.assertLessEqual(b['variants'][v]['system.peak_pss_mb']['max'], 6144)   # half the 12 GB model's memory


if __name__ == '__main__':
    unittest.main()
