# On-device benchmark of a port: frame pacing, thermals, memory and power against a device's budget file.
#   perf_bench.py run [--variant smoke|soak|cold_cache] [--minutes N] [--budget devtools/perf_budgets/y700_2023.json]
#                     [--route devtools/perf_routes/<title id>.json] [--no-launch] [--out DIR] [--label TEXT]
#   perf_bench.py compare <a.json> <b.json>          A/B of a setting: the deltas, better / worse per metric
#   perf_bench.py check <report.json> [--budget ...] the budget check of a saved report again (exit 1 on a miss)
# The device and app come from devtools/device.json (devtools/device.py). Input routes write DM_CTL lines to files/ctl.txt,
# which only a --debug port reads; without one the run measures what the player (or an idle scene) does.
# Reports go to .gamedump/<App>/perf/ by default (CLAUDE.md: debug output stays beside the game). Exit 0 pass, 1 budget miss, 2 no data.
import argparse, datetime, json, os, re, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import perf_metrics as pm   # noqa: E402

ENV = dict(os.environ, MSYS_NO_PATHCONV='1')


class Dev:
    def __init__(self):
        from device import ADB, PKG, FILES   # devtools/device.json (stops when no app is set)
        self.adb, self.pkg, self.files = ADB, PKG, FILES

    def sh(self, cmd, timeout=30):
        try: return subprocess.run(self.adb + ['shell', cmd], env=ENV, capture_output=True, text=True, timeout=timeout, errors='replace').stdout
        except subprocess.TimeoutExpired: return ''

    def layer(self):
        """The app's game surface in SurfaceFlinger (perf_metrics.pick_layer): its SurfaceView, else its window's buffer layer."""
        return pm.pick_layer(self.sh('dumpsys SurfaceFlinger --list'), self.pkg)

    def pid(self): return self.sh(f'pidof {self.pkg}').strip()


def sample_system(d):
    """One second's system sample: thermal status, skin and battery temperature, cluster clocks, GPU clock, power."""
    th = d.sh('dumpsys thermalservice')
    cpu = d.sh('for c in 0 4 7; do cat /sys/devices/system/cpu/cpu$c/cpufreq/scaling_cur_freq 2>/dev/null || echo 0; done').split()
    gpu = d.sh('cat /sys/class/kgsl/kgsl-3d0/gpuclk 2>/dev/null').strip()
    cur = d.sh('cat /sys/class/power_supply/battery/current_now /sys/class/power_supply/battery/voltage_now 2>/dev/null').split()
    return {
        't': time.time(),
        'thermal': pm.parse_thermal_status(th),
        'skin_c': pm.parse_skin_temp(th),
        'battery_c': pm.parse_battery_temp_c(d.sh('dumpsys battery')),
        'cpu_khz': [int(x) for x in cpu if x.isdigit()],            # A510 / A710 / X2 clusters on the Snapdragon 8+ Gen 1
        'gpu_hz': int(gpu) if gpu.isdigit() else None,
        'watts': pm.power_watts(*cur) if len(cur) == 2 else None,
    }


def load_route(path):
    if not path: return []
    r = json.loads(Path(path).read_text(encoding='utf-8'))
    return [(s['ctl'], float(s.get('hold', 3))) for s in r['steps']]   # {"steps": [{"ctl": "LUp~0.8", "hold": 3}, ...], "loop": true}


def run(a):
    d = Dev()
    budget = pm.load_budget(a.budget)
    target = budget.get('target_fps', 30)
    if not d.sh('echo ok').strip(): sys.exit('perf_bench: no device (adb devices)')
    build = d.sh(f'dumpsys package {d.pkg} | grep -m1 versionName').strip().replace('versionName=', '') or '?'
    model = d.sh('getprop ro.product.model').strip()
    t0 = time.time()
    first_frame_s = None
    old_layer = d.layer()   # the running instance's surface: a launch makes a new one (a new number), and only its frames count
    if not a.no_launch:
        d.sh(f'am force-stop {d.pkg}')
        if a.variant == 'cold_cache': d.sh(f'rm -f {d.files}/vk_pipeline_cache.bin')   # the first-launch experience: every pipeline compiled anew
        d.sh('logcat -c')
        t0 = time.time()
        d.sh(f'monkey -p {d.pkg} -c android.intent.category.LAUNCHER 1', timeout=60)
    lay = None
    for _ in range(120):                                  # the surface appears once the activity is up
        lay = d.layer()
        if lay and (a.no_launch or lay != old_layer): break
        lay = None; time.sleep(0.5)
    if not lay: sys.exit('perf_bench: the app shows no surface (did it start? see log.txt)')
    print(f'perf_bench: {model} · {d.pkg} {build} · layer {lay} · {a.variant} {a.minutes} min', flush=True)

    route = load_route(a.route)
    ri, next_ctl = 0, 0.0
    seen, samples, pss, allrows, period_ns = set(), [], [], {}, 0
    end = time.time() + a.minutes * 60
    next_sys = next_mem = 0.0
    quoted = "'" + lay.replace("'", "'\\''") + "'"
    last_new = time.time()
    while time.time() < end:
        now = time.time()
        period_ns, rows = pm.parse_sf_rows(d.sh(f'dumpsys SurfaceFlinger --latency {quoted}')); allrows.update(rows); ts = list(rows)
        if pm.merge_timestamps(seen, ts):
            last_new = now
            if first_frame_s is None and not a.no_launch: first_frame_s = round(now - t0, 2)   # the new surface's first frames (within one poll, 0.5 s)
        elif now - last_new > 5:   # a new surface (the activity recreated, a mode switch): its layer has a new number
            nl = d.layer()
            if nl and nl != lay: print(f'perf_bench: layer now {nl}', flush=True); lay = nl; quoted = "'" + lay.replace("'", "'\\''") + "'"
            last_new = now
        if route and now >= next_ctl:
            ctl, hold = route[ri % len(route)]; ri += 1; next_ctl = now + hold
            d.sh(f"echo '{ctl}' >> {d.files}/ctl.txt")
        if now >= next_sys: samples.append(sample_system(d)); next_sys = now + 1.0
        if now >= next_mem: pss.append(pm.parse_meminfo_pss_kb(d.sh(f'dumpsys meminfo {d.pkg}', 60))); next_mem = now + 10.0
        if not d.pid(): print('perf_bench: the app is gone (crash?)', flush=True); break
        time.sleep(0.5)   # SurfaceFlinger keeps 128 frames: two polls a second leave room up to 120 fps

    log = d.sh(f'cat {d.files}/log.txt', timeout=120)
    watts = [s['watts'] for s in samples if s['watts']]
    report = {
        'app': d.pkg, 'device': model, 'build': build, 'variant': a.variant, 'label': a.label,
        'started': datetime.datetime.fromtimestamp(t0).isoformat(timespec='seconds'),
        'duration_s': round(time.time() - t0, 1), 'cache': 'cold' if a.variant == 'cold_cache' else 'warm', 'target_fps': target,
        'frames': pm.frame_metrics(seen, target),
        'pace': pm.pace_metrics(allrows, period_ns),
        'system': {
            'first_frame_s': first_frame_s,
            'peak_pss_mb': round(max(pss, default=0) / 1024, 1),
            'max_thermal': max((s['thermal'] for s in samples), default=-1),
            'max_skin_c': max((s['skin_c'] for s in samples if s['skin_c'] is not None), default=None),
            'max_battery_c': max((s['battery_c'] for s in samples if s['battery_c'] is not None), default=None),
            'avg_watts': round(sum(watts) / len(watts), 2) if watts else None,
        },
        'perf_log': pm.parse_perf_log(log, target),
        'samples': samples,
    }
    if a.no_launch: report['system'].pop('first_frame_s')
    return finish(report, budget, a.out or default_out(d.pkg), log)


def default_out(pkg):
    root = HERE.parent / '.gamedump'
    apps = [p for p in root.iterdir() if p.is_dir()] if root.is_dir() else []
    return str((apps[0] if len(apps) == 1 else root / pkg) / 'perf')


def finish(report, budget, out, log=None):
    fails = pm.evaluate(report, budget, report['variant'])
    report['budget'] = {'file': budget.get('device'), 'fails': fails, 'pass': not fails}
    o = Path(out); o.mkdir(parents=True, exist_ok=True)
    stem = f"{report['started'].replace(':', '')}-{report['variant']}" + (f"-{re.sub(r'[^\w.-]', '_', report['label'])}" if report.get('label') else '')
    (o / f'{stem}.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
    md = pm.markdown(report, fails); (o / f'{stem}.md').write_text(md, encoding='utf-8')
    if log: (o / f'{stem}.log.txt').write_text(log, encoding='utf-8')   # the app's log of the run, for the lines behind the numbers
    print(md); print(f'report: {o / stem}.json')
    if report['frames']['frames'] < 2: return 2
    return 0 if not fails else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    r.add_argument('--variant', default='smoke', choices=['smoke', 'soak', 'cold_cache'])
    r.add_argument('--minutes', type=float)
    r.add_argument('--budget', default=str(HERE / 'perf_budgets/y700_2023.json'))
    r.add_argument('--route'); r.add_argument('--no-launch', action='store_true'); r.add_argument('--out'); r.add_argument('--label', default='')
    c = sub.add_parser('compare'); c.add_argument('a'); c.add_argument('b')
    k = sub.add_parser('check'); k.add_argument('report'); k.add_argument('--budget', default=str(HERE / 'perf_budgets/y700_2023.json'))
    a = ap.parse_args()
    if a.cmd == 'run':
        if a.minutes is None: a.minutes = {'smoke': 3, 'soak': 20, 'cold_cache': 3}[a.variant]
        sys.exit(run(a))
    if a.cmd == 'compare':
        A, B = (json.loads(Path(p).read_text(encoding='utf-8')) for p in (a.a, a.b))
        A.pop('samples', None); B.pop('samples', None)
        print(f"{'metric':32} {'A':>10} {'B':>10} {'delta':>10}  verdict   (A {A.get('label') or a.a}, B {B.get('label') or a.b})")
        for p, x, y, dl, v in pm.compare(A, B): print(f'{p:32} {x:>10} {y:>10} {dl:>+10}  {v}')
        return
    rep = json.loads(Path(a.report).read_text(encoding='utf-8'))
    fails = pm.evaluate(rep, pm.load_budget(a.budget), rep['variant'])
    print('PASS' if not fails else 'FAIL\n' + '\n'.join(fails)); sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
