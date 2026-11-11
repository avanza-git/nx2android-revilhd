# Frame-time, thermal and memory metrics for a port running on a device, and the check against a device's budget file.
# Pure functions (no adb): devtools/perf_bench.py collects the samples, tests/test_perf_metrics.py checks the maths.
#   parse_*      turn one adb dump (SurfaceFlinger --latency, thermalservice, meminfo, battery, log.txt) into numbers
#   frame_metrics  avg fps, 1% low, p50/p95/p99 frame time, stutters, pacing jitter, drift between the run's start and end
#   evaluate     the budget's failures (an empty list passes); compare: the deltas between two reports (A/B of a setting)
import json, math, re
from pathlib import Path

PENDING = 9223372036854775807   # SurfaceFlinger's "not presented yet" timestamp (INT64_MAX)


def parse_sf_latency(text):
    """dumpsys SurfaceFlinger --latency <layer>: line 1 the refresh period (ns), then up to 128 rows of
    desired-present, actual-present, frame-ready (ns). Returns (period_ns, [actual-present ns, ascending])."""
    lines = [l.split() for l in text.strip().splitlines() if l.strip()]
    if not lines or not lines[0][0].isdigit(): return 0, []
    period = int(lines[0][0])
    out = []
    for row in lines[1:]:
        if len(row) < 3 or not all(c.isdigit() for c in row[:3]): continue
        t = int(row[1])
        if 0 < t < PENDING: out.append(t)
    return period, sorted(set(out))


def parse_sf_rows(text):
    """parse_sf_latency with all three columns: (period_ns, {actual-present: (desired-present, frame-ready)}) for the presented frames."""
    lines = [l.split() for l in text.strip().splitlines() if l.strip()]
    if not lines or not lines[0][0].isdigit(): return 0, {}
    out = {}
    for row in lines[1:]:
        if len(row) < 3 or not all(c.isdigit() for c in row[:3]): continue
        d, a, r = int(row[0]), int(row[1]), int(row[2])
        if 0 < a < PENDING: out[a] = (d, r)
    return int(lines[0][0]), out


def pace_metrics(rows, period_ns):
    """Where a frame's time on screen came from, for frames that asked for a present time (VK_GOOGLE_display_timing). rows: {actual: (desired, ready)}.
    off_cadence = intervals shown for another number of vsyncs than the pacer asked (a frame shown a vsync off its slot makes two: 5-3 or 3-5 at 30 fps on 120 Hz);
    which vsync the compositor counts a desired time against is its own (the Legion Y700 2023 showed frames half a vsync before or after it), so this compares lengths, not times.
    cadence_changes = the pacer moved its next vsync (a resync). ready margin = from frame-ready to the vsync it was shown on (the presentation deadline must fit in it)."""
    a = sorted(t for t in rows if rows[t][0] > 0)
    if len(a) < 2 or not period_ns: return {'timed_frames': len(a)}
    off = changes = 0; margins = []; step = None
    for p, q in zip(a, a[1:]):
        d, rd = rows[q]
        s = round((d - rows[p][0]) / period_ns)
        if q - p < 1_000_000_000 and round((q - p) / period_ns) != s: off += 1
        if step is not None and s != step: changes += 1
        step = s
        if rd > 0: margins.append((q - rd) / 1e6)
    margins.sort()
    return {'timed_frames': len(a), 'off_cadence': off, 'off_cadence_pct': round(100.0 * off / (len(a) - 1), 2), 'cadence_changes': changes,
            'ready_margin_p5_ms': round(_pct(margins, 5), 2) if margins else None, 'ready_margin_p50_ms': round(_pct(margins, 50), 2) if margins else None,
            'vsync_ms': round(period_ns / 1e6, 3)}


def pick_layer(listing, pkg):
    """The game's buffer layer in dumpsys SurfaceFlinger --list. Android 15 writes each as 'RequestedLayerState{<name> parentId=<n>...}'; older ones the bare name.
    Of the package's layers: a SurfaceView (not its background), else the window's own layer '<pkg>/<activity>#<n>', not the window token ('<hex> <pkg>/...'),
    its ActivityRecord or its input sink, which have no buffers. None when the app shows nothing."""
    names = []
    for line in listing.splitlines():
        line = line.strip()
        m = re.match(r'RequestedLayerState\{(.*?) parentId=', line)
        n = m.group(1) if m else line
        if pkg in n: names.append(n)
    sv = [n for n in names if 'SurfaceView' in n and 'Background' not in n]
    if sv: return sv[0]
    win = [n for n in names if n.startswith(pkg + '/') and 'ActivityRecord' not in n and 'InputSink' not in n]
    return (win or [None])[0]


def merge_timestamps(seen, new):
    """Add one poll's present times to the run's (each poll repeats up to 128 earlier frames). Returns the count added."""
    before = len(seen); seen.update(new); return len(seen) - before


def _pct(sorted_vals, p):
    if not sorted_vals: return 0.0
    k = (len(sorted_vals) - 1) * p / 100.0
    lo, hi = math.floor(k), math.ceil(k)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def frame_metrics(present_ns, target_fps=30, max_gap_s=1.0):
    """Metrics of a run's present timestamps (ns). Gaps over max_gap_s (a load screen, the app paused) split the run
    into segments and are not counted as frames; they are reported as `long_gaps`."""
    ts = sorted(set(present_ns))
    dts = []
    gaps = 0
    for a, b in zip(ts, ts[1:]):
        d = (b - a) / 1e6
        if d > max_gap_s * 1000: gaps += 1; continue
        dts.append(d)
    if not dts:
        return {'frames': 0, 'avg_fps': 0.0, 'low1_fps': 0.0, 'p50_ms': 0.0, 'p95_ms': 0.0, 'p99_ms': 0.0, 'max_ms': 0.0,
                'stutters': 0, 'stutters_per_min': 0.0, 'jitter_ms': 0.0, 'drift_pct': 0.0, 'long_gaps': gaps, 'seconds': 0.0}
    s = sorted(dts)
    total_ms = sum(dts)
    budget_ms = 1000.0 / target_fps
    worst = s[-max(1, len(s) // 100):]                      # the slowest 1% of frames
    mean = total_ms / len(dts)
    jitter = math.sqrt(sum((d - mean) ** 2 for d in dts) / len(dts))
    stutters = sum(1 for d in dts if d > 2 * budget_ms)
    # drift: fps of the last fifth against the first fifth (thermal throttling shows as a negative drift)
    n5 = max(1, len(dts) // 5)
    first, last = dts[:n5], dts[-n5:]
    drift = (1000.0 * len(last) / sum(last)) / (1000.0 * len(first) / sum(first)) - 1.0 if len(dts) >= 10 else 0.0
    return {
        'frames': len(dts) + 1,
        'seconds': round(total_ms / 1000.0, 2),
        'avg_fps': round(1000.0 * len(dts) / total_ms, 2),
        'low1_fps': round(1000.0 / (sum(worst) / len(worst)), 2),
        'p50_ms': round(_pct(s, 50), 2), 'p95_ms': round(_pct(s, 95), 2), 'p99_ms': round(_pct(s, 99), 2), 'max_ms': round(s[-1], 2),
        'stutters': stutters,
        'stutters_per_min': round(stutters / (total_ms / 60000.0), 2),
        'jitter_ms': round(jitter, 2),
        'drift_pct': round(100.0 * drift, 2),
        'long_gaps': gaps,
    }


THERMAL_NAMES = ['NONE', 'LIGHT', 'MODERATE', 'SEVERE', 'CRITICAL', 'EMERGENCY', 'SHUTDOWN']


def parse_thermal_status(text):
    """dumpsys thermalservice: 'Thermal Status: 2' (PowerManager.THERMAL_STATUS_*). -1 when absent."""
    m = re.search(r'Thermal Status:\s*(\d+)', text)
    return int(m.group(1)) if m else -1


def parse_skin_temp(text):
    """The hottest SKIN (else any) temperature in dumpsys thermalservice's HAL list, °C; None when absent."""
    rows = re.findall(r'Temperature\{mValue=([-\d.]+), mType=(\d+), mName=([^,]+)', text)
    skin = [float(v) for v, t, _ in rows if t == '3']   # TYPE_SKIN
    vals = skin or [float(v) for v, _, _ in rows]
    return max(vals) if vals else None


def parse_meminfo_pss_kb(text):
    """dumpsys meminfo <pkg>: 'TOTAL PSS:  123456' (Android 11+) or the 'TOTAL  123456 ...' row. kB; 0 when absent."""
    m = re.search(r'TOTAL PSS:\s*(\d+)', text) or re.search(r'^\s*TOTAL\s+(\d+)', text, re.M)
    return int(m.group(1)) if m else 0


def parse_battery_temp_c(text):
    """dumpsys battery: 'temperature: 345' in tenths of °C."""
    m = re.search(r'temperature:\s*(-?\d+)', text)
    return int(m.group(1)) / 10.0 if m else None


def power_watts(current_now, voltage_now):
    """/sys/class/power_supply/battery current_now (µA, either sign by vendor) and voltage_now (µV) → W drawn."""
    try: return abs(int(current_now)) * int(voltage_now) / 1e12
    except (TypeError, ValueError): return None


PERF_LINE = re.compile(r'adaptive frame rate: (\d+) fps, frame work p50 ([\d.]+) / p90 ([\d.]+) / p95 ([\d.]+) ms.*?late on screen (\d+) of 64')
STEP_LINE = re.compile(r'adaptive frame rate: (\d+) fps \(frames p90')


def parse_perf_log(text, target_fps=30):
    """The runtime's own [perf] lines in log.txt (nxnative/dm/android/perf_android.c): its work-time percentiles
    every 600 frames, its frame-rate step changes, ADPF and [RED] errors. Step changes count as step-downs only below
    target_fps: at boot the adaptive rate starts at 60 and steps to a 30 fps game's own rate, which is no slowdown."""
    work = [dict(fps=int(a), p50=float(b), p90=float(c), p95=float(d), late=int(e)) for a, b, c, d, e in PERF_LINE.findall(text)]
    steps = [int(x) for x in STEP_LINE.findall(text)]
    return {
        'work_samples': len(work),
        'work_p90_ms_max': max((w['p90'] for w in work), default=0.0),
        'work_p95_ms_max': max((w['p95'] for w in work), default=0.0),
        'late_of_64_max': max((w['late'] for w in work), default=0),
        'fps_step_downs': sum(1 for x in steps if x < target_fps),
        'fps_lowest_step': min(steps, default=0),
        'adpf': 'open' if 'ADPF session open' in text else ('refused' if 'ADPF session refused' in text else 'absent'),
        'red_lines': sum(1 for l in text.splitlines() if '[RED]' in l),
    }


# ---- budgets -------------------------------------------------------------------------------------------------------
# A budget file (devtools/perf_budgets/<device>.json): {"device": ..., "target_fps": 30, "variants": {"smoke": {...}, "soak": {...}}}.
# Each rule is "<metric path>": {"min": x} or {"max": x}; a metric path is "frames.avg_fps", "system.peak_pss_mb", ...

def load_budget(path):
    b = json.loads(Path(path).read_text(encoding='utf-8'))
    for v, rules in b['variants'].items():
        for k, r in rules.items():
            if not (set(r) <= {'min', 'max'} and r): raise ValueError(f'{path}: {v}.{k}: a rule is {{"min": x}} and/or {{"max": x}}')
    return b


def _get(report, path):
    cur = report
    for part in path.split('.'):
        if not isinstance(cur, dict) or part not in cur: return None
        cur = cur[part]
    return cur


def evaluate(report, budget, variant):
    """The rules the report misses, as readable lines; a metric the run could not measure fails too (no silent pass)."""
    fails = []
    for key, rule in budget['variants'][variant].items():
        v = _get(report, key)
        if v is None: fails.append(f'{key}: not measured'); continue
        if 'min' in rule and v < rule['min']: fails.append(f'{key}: {v} < min {rule["min"]}')
        if 'max' in rule and v > rule['max']: fails.append(f'{key}: {v} > max {rule["max"]}')
    return fails


HIGHER_BETTER = {'avg_fps', 'low1_fps', 'drift_pct', 'game_speed'}


def compare(a, b, keys=None):
    """Deltas from report a to report b for the numeric metrics both have: [(path, a, b, delta, 'better'|'worse'|'same')]."""
    out = []
    def walk(x, y, pre):
        for k in sorted(set(x) & set(y)):
            p = f'{pre}{k}'
            if isinstance(x[k], dict) and isinstance(y[k], dict): walk(x[k], y[k], p + '.'); continue
            if isinstance(x[k], bool) or not isinstance(x[k], (int, float)) or not isinstance(y[k], (int, float)): continue
            if keys and p not in keys: continue
            d = y[k] - x[k]
            verdict = 'same' if abs(d) < 1e-9 else (('better' if d > 0 else 'worse') if k in HIGHER_BETTER else ('better' if d < 0 else 'worse'))
            out.append((p, x[k], y[k], round(d, 3), verdict))
    walk(a, b, '')
    return out


def markdown(report, fails):
    f, s, p = report.get('frames', {}), report.get('system', {}), report.get('perf_log', {})
    rows = [
        f"# Perf: {report.get('app', '?')} · {report.get('variant', '?')} · {report.get('device', '?')}",
        '', f"{report.get('started', '')} · build `{report.get('build', '?')}` · {report.get('duration_s', 0)} s · cache {report.get('cache', '?')}", '',
        '| metric | value |', '|---|---|',
        f"| avg fps | {f.get('avg_fps')} |", f"| 1% low fps | {f.get('low1_fps')} |",
        f"| frame time p50 / p95 / p99 / max ms | {f.get('p50_ms')} / {f.get('p95_ms')} / {f.get('p99_ms')} / {f.get('max_ms')} |",
        f"| stutters (>2× target) | {f.get('stutters')} ({f.get('stutters_per_min')}/min) |",
        f"| pacing jitter ms | {f.get('jitter_ms')} |", f"| fps drift start→end | {f.get('drift_pct')} % |",
        f"| frames off the pacer's cadence | {report.get('pace', {}).get('off_cadence')} ({report.get('pace', {}).get('off_cadence_pct')} %) |",
        f"| pacer cadence changes | {report.get('pace', {}).get('cadence_changes')} |",
        f"| ready before vsync p5 / p50 ms | {report.get('pace', {}).get('ready_margin_p5_ms')} / {report.get('pace', {}).get('ready_margin_p50_ms')} |",
        f"| time to first frame s | {s.get('first_frame_s')} |", f"| peak PSS MB | {s.get('peak_pss_mb')} |",
        f"| max thermal status | {THERMAL_NAMES[s['max_thermal']] if 0 <= s.get('max_thermal', -1) < 7 else 'unknown'} |",
        f"| max skin / battery °C | {s.get('max_skin_c')} / {s.get('max_battery_c')} |", f"| avg power W | {s.get('avg_watts')} |",
        f"| runtime work p95 max ms | {p.get('work_p95_ms_max')} |", f"| adaptive fps step-downs | {p.get('fps_step_downs')} |",
        f"| [RED] log lines | {p.get('red_lines')} |", '',
        '**PASS**' if not fails else '**FAIL**\n\n' + '\n'.join(f'- {x}' for x in fails), '']
    return '\n'.join(rows)
