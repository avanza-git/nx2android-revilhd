"""Resident Evil (010050F00BC1A000) profile for the Lenovo Legion Y700 (2023): the keys its port and its optimization test rely on, read through porter's own loader,
and the benchmark's input route and budget it names"""
import json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from porter import profiles   # noqa: E402

TID = '010050F00BC1A000'
DIR = ROOT / 'nxnative/dm/games' / TID


def tsv(name):
    rows = {}
    for line in (DIR / name).read_text(encoding='utf-8').splitlines():
        if line and not line.startswith('#') and '\t' in line:
            k, v = line.split('\t', 1); rows.setdefault(k, []).append(v)
    return rows


class ResidentEvilProfile(unittest.TestCase):
    def test_loads(self):
        g, a = profiles.by_title(int(TID, 16))   # the loader keys games by the numeric title ID
        self.assertIsNotNone(g); self.assertIsNotNone(a)
        self.assertEqual(profiles.load(TID).package, 'org.nx2a.t010050f00bc1a000')

    def test_game_keys(self):
        t = tsv('game.tsv')
        self.assertEqual(t['title_id'], [TID])
        self.assertEqual(t['modules'], ['main subsdk0 sdk'])
        self.assertTrue(any(b.startswith('v0\t1.0.0\tmain=6bec9b23b09df46c315aa6f4bfacf91c') for b in t['build']))   # the build the profile was made on
        self.assertEqual((t['tex_flush_upload'], t['tex_dirty_upload']), (['on'], ['on']))                          # MT Framework never flushes its texture uploads
        self.assertIn(t.get('fps_target', ['0'])[0], ('0', '30', '60'))
        self.assertIn(t.get('present_interval', ['game'])[0], ('game', 'display'))

    def test_android_keys(self):
        a = tsv('android.tsv')
        self.assertIn(a['status'][0], ('playable', 'wip', 'boots', 'experimental'))
        self.assertEqual(a['orientation'], ['landscape'])
        self.assertIn('bcn', a['requires'])   # the Adreno 730 reads BC textures; a GPU that cannot must be refused

    def test_shader_tables(self):
        rows = [l for l in (DIR / 'shader_map.tsv').read_text(encoding='utf-8').splitlines() if l and not l.startswith('#')]
        self.assertGreater(len(rows), 19000)   # 19,060 shaders from the three shader packages
        for name in ('shader_pairs.tsv', 'shader_facts.tsv', 'pso_manifest.tsv'): self.assertTrue((DIR / name).is_file(), name)

    def test_pso_manifest_rows(self):
        for line in (DIR / 'pso_manifest.tsv').read_text(encoding='utf-8').splitlines():
            if line and not line.startswith('#'): self.assertIn(line.split('\t')[0], ('S', 'R', 'C'), line)

    def test_benchmark_files(self):
        route = json.loads((ROOT / 'devtools/perf_routes' / f'{TID}.json').read_text(encoding='utf-8'))
        self.assertTrue(route['steps'])
        for s in route['steps']:
            self.assertRegex(s['ctl'], r'^[LR](Up|Down|Left|Right)~[\d.]+$')   # stick moves only: the route never presses A, so a save's story does not move on
            self.assertGreater(s['hold'], 0)
        b = json.loads((ROOT / 'devtools/perf_budgets/y700_2023.json').read_text(encoding='utf-8'))
        self.assertEqual(b['target_fps'], 30)   # the game's own frame rate on the Switch


if __name__ == '__main__':
    unittest.main()
