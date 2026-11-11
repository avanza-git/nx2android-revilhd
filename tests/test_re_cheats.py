"""Resident Evil's Cheats tab: each gate adjusts only the player's (or an enemy's) data, only when switched on, only on the checked build."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from porter.upstream import android_profile

DM = Path(__file__).resolve().parents[1] / 'nxnative/dm'


class ReCheats(unittest.TestCase):
    def test_gates(self):
        cc = shutil.which('cc')
        if not cc:
            self.skipTest('C compiler required')
        src = (DM / 'host/hle_re_cheat.c').read_text()
        block = src[src.index('int dm_android_cheat(int which);'):src.rindex('#endif\n#endif')]
        harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdatomic.h>
enum { RE_CHEAT_HEALTH, RE_CHEAT_AMMO, RE_CHEAT_OHK, RE_CHEAT_RIBBON, RE_CHEAT_N };
enum { OBS_RE_GIVE_DAMAGE = 27, OBS_RE_LIFE_DOWN = 28, OBS_RE_LIFE_DOWN2 = 29, OBS_RE_SHOT = 30, OBS_RE_USE_BULLET = 31, OBS_RE_USE_ITEM = 32 };
#define LOG(...) ((void)0)
static const char *g_build = "6bec9b23b09df46c315aa6f4bfacf91c";
static const char *dm_main_build(void) { return g_build; }
static void (*gates[40])(const uint64_t *);
static void gate_obs_set(int id, void (*fn)(const uint64_t *)) { gates[id] = fn; }
static int writes;
static void dm_guest_write_prepare(void *p, size_t n) { (void)p; (void)n; writes++; }
static int cheats;
int dm_android_cheat(int c) { return cheats >> c & 1; }
// MtDTI: + 0x20 the parent. root <- model <- player; model <- enemy <- zombie; enemy <- npc <- partner (a partner derived from uEmBase still is not an enemy)
typedef struct { uint8_t pad[0x20]; const void *parent; } dti;
static dti root, model, player_dti, enemy_dti, zombie_dti, npc_dti, partner_dti;
static const void *dti_player(const void *o) { (void)o; return &player_dti; }
static const void *dti_zombie(const void *o) { (void)o; return &zombie_dti; }
static const void *dti_partner(const void *o) { (void)o; return &partner_dti; }
static const void *dti_model(const void *o) { (void)o; return &model; }
static void *vt_player[6] = {0, 0, 0, 0, 0, (void *)dti_player}, *vt_zombie[6] = {0, 0, 0, 0, 0, (void *)dti_zombie};
static void *vt_partner[6] = {0, 0, 0, 0, 0, (void *)dti_partner}, *vt_model[6] = {0, 0, 0, 0, 0, (void *)dti_model};
static _Alignas(8) uint8_t pl[0x1800], zo[0x1800], pa[0x1800], mo[0x1800], entry_obj[16], gm_obj[0x5200], weapon[0x1600];
static void *entry_inst = entry_obj, *gm_inst = gm_obj;
static void *get_pointer_(void *list, uint64_t id) { assert(list == entry_obj); return id == 1 ? pl : id == 2 ? zo : id == 3 ? pa : id == 4 ? mo : NULL; }
static void *guest_sym(const char *n) {
    static const struct { const char *n; void *p; } t[] = {
        {"_ZNK2K210sEntryList10getPointerENS0_8SearchIDE", (void *)get_pointer_}, {"_ZN2K210sEntryList10mpInstanceE", &entry_inst},
        {"_ZN2K212sGameManager10mpInstanceE", &gm_inst}, {"_ZN2K27uPlayer3DTIE", &player_dti}, {"_ZN2K28uNpcBase3DTIE", &npc_dti}, {"_ZN2K27uEmBase3DTIE", &enemy_dti}};
    for (unsigned i = 0; i < sizeof t / sizeof *t; i++) if (!strcmp(t[i].n, n)) return t[i].p;
    return NULL;
}
static int32_t rd(const uint8_t *p) { int32_t v; memcpy(&v, p, 4); return v; }
static void wr(uint8_t *p, int32_t v) { memcpy(p, &v, 4); }
static void obj(uint8_t *o, void **vt, int32_t life) { memset(o, 0, 0x1800); memcpy(o, &vt, sizeof vt); wr(o + 0x175c, life); }
static void call(int id, uint64_t x0, uint64_t x1, uint64_t x2) { uint64_t r[31] = {x0, x1, x2}; gates[id](r); }
// the game's own Life_down_set after the gate: life -= damage - spread + rand % (2 * spread)
static int32_t life_after(uint8_t *o, int id, int32_t dmg, int32_t spread, int32_t rnd) {
    call(id, (uintptr_t)o, (uint32_t)dmg, (uint32_t)spread); return rd(o + 0x175c) - (spread ? dmg - spread + rnd % (2 * spread) : dmg);
}
static uint8_t ctx[0x70];
static void hit(uint64_t target, int32_t route, uint32_t flags) { memset(ctx, 0, sizeof ctx); memcpy(ctx + 0x50, &target, 8); wr(ctx + 0x1c, route); wr(ctx + 0xc, (int32_t)flags); wr(ctx + 0x60, 12); wr(ctx + 0x6c, 30); }
''' + block + r'''
int main(int argc, char **argv) {
    (void)argv;
    root.parent = &root; model.parent = &root; player_dti.parent = &model; enemy_dti.parent = &model; zombie_dti.parent = &enemy_dti; npc_dti.parent = &enemy_dti; partner_dti.parent = &npc_dti;
    cheat_gates();
    for (int id = 27; id <= 32; id++) assert(gates[id]);
    if (argc > 1) g_build = "unsupported";
    // Switched off (and, with the argument, every cheat on a build not checked): nothing is written
    cheats = argc > 1 ? 15 : 0; writes = 0;
    obj(pl, vt_player, 50); obj(zo, vt_zombie, 100);
    hit(1, 4, 0x1f); call(27, 0, (uintptr_t)ctx, 0); assert(rd(ctx + 0x6c) == 30 && rd(ctx + 0xc) == 0x1f);
    assert(life_after(pl, 28, 10, 0, 0) == 40 && life_after(zo, 29, 10, 0, 0) == 90);
    memset(weapon, 0, sizeof weapon); wr(weapon + 0x1500, 8); wr(weapon + 0x1334, 5); wr(weapon + 0x133c, 1); call(30, (uintptr_t)weapon, 0, 0); assert(rd(weapon + 0x1334) == 5);
    memset(gm_obj, 0, sizeof gm_obj); wr(gm_obj + 0x44 + 8 * 3, 0x44); wr(gm_obj + 0x48 + 8 * 3, 1); call(32, (uintptr_t)gm_obj, 0x44, 0); assert(rd(gm_obj + 0x48 + 8 * 3) == 1);
    assert(!writes);
    if (argc > 1) return 0;

    // Infinite health: a hit on the player does no damage, cannot force dying and does not poison (bit 0 stays); the reaction (+ 0x60) stays on set_damage's route
    cheats = 1 << RE_CHEAT_HEALTH;
    hit(1, 4, 0x1f); call(27, 0, (uintptr_t)ctx, 0); assert(rd(ctx + 0x6c) == 0 && rd(ctx + 0x60) == 12 && rd(ctx + 0xc) == 0x03);
    hit(1, 3, 0x1f); call(27, 0, (uintptr_t)ctx, 0); assert(rd(ctx + 0x6c) == 0 && rd(ctx + 0x60) == 0 && rd(ctx + 0xc) == 0x01);   // Life_down_set2's route: + 0x60 is the damage, bit 1 forces 0
    hit(2, 4, 0x1f); call(27, 0, (uintptr_t)ctx, 0); assert(rd(ctx + 0x6c) == 30 && rd(ctx + 0xc) == 0x1f);   // an enemy's hit is its own
    hit(9, 4, 0x1f); call(27, 0, (uintptr_t)ctx, 0); assert(rd(ctx + 0x6c) == 30);                            // no target
    // the player's life ends at least where it was, whatever the spread draws; an enemy's is untouched by this cheat
    for (int r = 0; r < 4; r++) { obj(pl, vt_player, 50); int32_t l = life_after(pl, 28, 10, 2, r); assert(l >= 50 && l <= 54); }
    obj(pl, vt_player, 50); assert(life_after(pl, 29, 10, 0, 0) == 50);
    obj(pl, vt_player, 50); assert(life_after(pl, 28, 0, 0, 0) == 50);
    obj(zo, vt_zombie, 100); assert(life_after(zo, 28, 10, 0, 0) == 90);

    // One-hit kills: any real hit on an enemy kills it, whatever the spread draws; partners, other objects and the player are left alone
    cheats = 1 << RE_CHEAT_OHK;
    obj(zo, vt_zombie, 100); assert(life_after(zo, 28, 10, 0, 0) <= 0);
    for (int r = 0; r < 10; r++) { obj(zo, vt_zombie, 100); assert(life_after(zo, 29, 1, 5, r) <= 0); }
    obj(zo, vt_zombie, 100); call(28, (uintptr_t)zo, 0, 0); assert(rd(zo + 0x175c) == 100);   // no damage: no kill
    obj(zo, vt_zombie, 0); call(28, (uintptr_t)zo, 10, 0); assert(rd(zo + 0x175c) == 0);      // already dead
    obj(pa, vt_partner, 100); assert(life_after(pa, 28, 10, 0, 0) == 90);
    obj(mo, vt_model, 100); assert(life_after(mo, 28, 10, 0, 0) == 90);
    obj(pl, vt_player, 50); assert(life_after(pl, 28, 10, 0, 0) == 40);
    hit(1, 4, 0x1f); call(27, 0, (uintptr_t)ctx, 0); assert(rd(ctx + 0x6c) == 30);   // (one-hit kills alone does not shield the player)

    // Infinite ammo: the player's weapon gets the shot's rounds (and the game manager's count of its type) back first; other weapons, and weapons that use none, do not
    cheats = 1 << RE_CHEAT_AMMO;
    memset(gm_obj, 0, sizeof gm_obj); memset(weapon, 0, sizeof weapon);
    wr(weapon + 0x1500, 8); wr(weapon + 0x1334, 5); wr(weapon + 0x133c, 2); wr(weapon + 0x1330, 2); wr(gm_obj + 0x5134 + 8, 7);
    call(30, (uintptr_t)weapon, 0, 0); assert(rd(weapon + 0x1334) == 7 && rd(gm_obj + 0x5134 + 8) == 8);
    call(31, (uintptr_t)weapon, 0, 0); assert(rd(weapon + 0x1334) == 9 && rd(gm_obj + 0x5134 + 8) == 9);
    wr(weapon + 0x1330, 20); call(30, (uintptr_t)weapon, 0, 0); assert(rd(gm_obj + 0x5134) == 1);   // a type above 14 counts as 0, as the game does
    wr(weapon + 0x1500, 0); wr(weapon + 0x1334, 5); call(30, (uintptr_t)weapon, 0, 0); assert(rd(weapon + 0x1334) == 5);
    wr(weapon + 0x1500, 8 | 2); call(30, (uintptr_t)weapon, 0, 0); assert(rd(weapon + 0x1334) == 5);

    // Unlimited ink ribbons: the ribbon's slot counts one more before the save uses one; other items, and slots the game does not search, are left alone
    cheats = 1 << RE_CHEAT_RIBBON;
    memset(gm_obj, 0, sizeof gm_obj); wr(gm_obj + 0x44 + 8 * 3, 0x44); wr(gm_obj + 0x48 + 8 * 3, 1);
    call(32, (uintptr_t)gm_obj, 0x44, 0); assert(rd(gm_obj + 0x48 + 8 * 3) == 2);
    call(32, (uintptr_t)gm_obj, 0x45, 0); assert(rd(gm_obj + 0x48 + 8 * 3) == 2);
    memset(gm_obj, 0, sizeof gm_obj); wr(gm_obj + 0x44 + 8 * 8, 0x44); wr(gm_obj + 0x48 + 8 * 8, 1);
    call(32, (uintptr_t)gm_obj, 0x44, 0); assert(rd(gm_obj + 0x48 + 8 * 8) == 1);   // 7 slots
    wr(gm_obj + 0x5118, 1); call(32, (uintptr_t)gm_obj, 0x44, 0); assert(rd(gm_obj + 0x48 + 8 * 8) == 2);   // 9 slots
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp); (d / 'cheat.c').write_text(harness)
            subprocess.run([cc, '-std=c11', '-Wall', '-Werror', str(d / 'cheat.c'), '-o', str(d / 'cheat')], check=True)
            for args in [[], ['unsupported-build']]:
                subprocess.run([str(d / 'cheat'), *args], check=True)

    def test_profile_menu(self):
        profile = android_profile.load('010050F00BC1A000')
        self.assertIn('#define DM_ANDROID_CHEATS 1', android_profile.header(profile))
        self.assertIn('#define DM_ANDROID_CHEATS 0', android_profile.header(None))

    def test_obs_sites(self):
        """The gates' numbers match dm.h and sit at the entries the host's comments name"""
        import importlib.util
        spec = importlib.util.spec_from_file_location('re_patches', DM / 'games/010050F00BC1A000/patches.py')
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        sites = {oid: off for off, oid, word, why in m.OBS['6bec9b23b09df46c315aa6f4bfacf91c']}
        self.assertEqual({27: 0x19b50, 28: 0x1a7330, 29: 0x1a7390, 30: 0x374740, 31: 0x3748c0, 32: 0xed0f0}, {k: v for k, v in sites.items() if k >= 27})
        dm_h = (DM / 'host/dm.h').read_text()
        for name, oid in [('OBS_RE_GIVE_DAMAGE', 27), ('OBS_RE_LIFE_DOWN', 28), ('OBS_RE_LIFE_DOWN2', 29), ('OBS_RE_SHOT', 30), ('OBS_RE_USE_BULLET', 31), ('OBS_RE_USE_ITEM', 32)]:
            self.assertIn(f'{name} = {oid}', dm_h)
        self.assertIn('OBS_MAX = 33', dm_h)
