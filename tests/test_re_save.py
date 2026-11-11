"""Resident Evil's Save game: the game's own typewriter trigger, refused outside free play, build-checked."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from porter.upstream import android_profile

DM = Path(__file__).resolve().parents[1] / 'nxnative/dm'


class ReSave(unittest.TestCase):
    def test_typewriter_trigger(self):
        cc = shutil.which('cc')
        if not cc:
            self.skipTest('C compiler required')
        src = (DM / 'host/hle_re_save.c').read_text()
        block = src[src.index('int dm_re_door_active(void);'):src.rindex('#endif\n#endif')]
        harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <stdatomic.h>
#define OBS_RE_SAVE_TICK 26
enum { RE_SAVE_IDLE, RE_SAVE_REFUSED, RE_SAVE_OPEN, RE_SAVE_CLOSED };
#define LOG(...) ((void)0)
static const char *g_build = "6bec9b23b09df46c315aa6f4bfacf91c";
static const char *dm_main_build(void) { return g_build; }
static void gate_obs_set(int id, void (*fn)(const uint64_t *)) { (void)id; (void)fn; }
static int door, sub, msg, ribbon = 1; static char calls[256]; static int ncalls;
int dm_re_door_active(void) { return door; }
static uint8_t ui_obj[16], unit_obj[0xd0294 + 16], gm_obj[16], scen_obj[0x40], game[0x600], job_safe;
static void *ui_inst = ui_obj, *unit_inst = unit_obj, *gm_inst = gm_obj, *scen_inst = scen_obj;
static void rec(const char *s) { ncalls += snprintf(calls + ncalls, sizeof calls - ncalls, "%s;", s); }
static int is_sub_(void *u) { assert(u == ui_obj); return sub; }
static int is_msg_(void *u) { assert(u == ui_obj); return msg; }
static int holder_(void *g, uint32_t item, int b) { assert(g == gm_obj && item == 0x44 && b == 1); return ribbon ? 3 : -1; }
static void messet_(void *u, uint32_t id) { assert(u == ui_obj); rec(id == 0x39 ? "ask" : id == 0x3a ? "none" : "?"); }
static void event_(void *c, uint32_t a, uint32_t id, int x, int y) { assert(c == scen_obj + 0x30 && a == 0xf && id == 0x42 && x == 1 && y == 0); rec("event"); }
static void status_(void *g, uint32_t f) { assert(g == gm_obj && f == 5); rec("status5"); }
static void lock_(void *m) { assert(m == scen_obj + 8); rec("lock"); }
static void unlock_(void *m) { assert(m == scen_obj + 8); rec("unlock"); }
static void *guest_sym(const char *n) {
    static const struct { const char *n; void *p; } t[] = {
        {"_ZN2K210sUIManager10mpInstanceE", &ui_inst}, {"_ZN5sUnit10mpInstanceE", &unit_inst},
        {"_ZN2K212sGameManager10mpInstanceE", &gm_inst}, {"_ZN2K29sScenario10mpInstanceE", &scen_inst}, {"_ZN7cSystem8mJobSafeE", &job_safe},
        {"_ZN2K210sUIManager18isExecuteSubScreenEv", (void *)is_sub_}, {"_ZN2K210sUIManager22isExecuteActiveMsgUnitEv", (void *)is_msg_},
        {"_ZN2K212sGameManager19getItemHolderDataNoEjb", (void *)holder_}, {"_ZN2K210sUIManager11MESSET_COREEj", (void *)messet_},
        {"_ZN2K217cRoomEventControl11createEventEjjbb", (void *)event_},
        {"_ZN2K212sGameManager17disableStatusFlagENS_9nGameInfo10StatusFlagE", (void *)status_},
        {"_ZN2nn2os9LockMutexEPNS0_9MutexTypeE", (void *)lock_}, {"_ZN2nn2os11UnlockMutexEPNS0_9MutexTypeE", (void *)unlock_}};
    for (unsigned i = 0; i < sizeof t / sizeof *t; i++) if (!strcmp(t[i].n, n)) return t[i].p;
    return NULL;
}
static void reset(void) { ncalls = 0; calls[0] = 0; }
''' + block + r'''
int main(int argc, char **argv) {
    (void)argv;
    uint64_t regs[31] = {(uintptr_t)game}; int32_t field = 50, other = 20;
    if (argc > 1) g_build = "unsupported";
    memcpy(game + 0x5fc, &field, 4); tick(regs);
    if (argc > 1) { assert(!dm_re_save_safe() && !dm_re_save_request()); tick(regs); assert(!ncalls); return 0; }
    // free play, an ink ribbon: the trigger's question and the typewriter event, once, then the status flag
    assert(dm_re_save_safe() && dm_re_save_request());
    tick(regs); assert(!strcmp(calls, "ask;event;status5;") && dm_re_save_note() == RE_SAVE_OPEN);
    assert(!dm_re_save_request());   // the same frame is no longer free play
    tick(regs); assert(!strcmp(calls, "ask;event;status5;"));   // no request: nothing more
    // the event's lock only while jobs run elsewhere (cSystem::mJobSafe or sScenario + 0x28)
    reset(); job_safe = 1; tick(regs); assert(dm_re_save_request()); tick(regs); assert(!strcmp(calls, "ask;lock;event;unlock;status5;")); job_safe = 0;
    reset(); scen_obj[0x28] = 1; tick(regs); assert(dm_re_save_request()); tick(regs); assert(!strcmp(calls, "ask;lock;event;unlock;status5;")); scen_obj[0x28] = 0;
    // no ink ribbon: the game's own message, no event
    reset(); ribbon = 0; tick(regs); assert(dm_re_save_request()); tick(regs); assert(!strcmp(calls, "none;status5;")); ribbon = 1;
    // each way out of free play refuses, and a request the menu sent drops when the state changed before the next frame
    reset();
    sub = 1; tick(regs); assert(!dm_re_save_request() && dm_re_save_note() == RE_SAVE_REFUSED); sub = 0;
    msg = 1; tick(regs); assert(!dm_re_save_safe()); msg = 0;
    door = 1; tick(regs); assert(!dm_re_save_safe()); door = 0;
    unit_obj[0xd0294] = 0x10; tick(regs); assert(!dm_re_save_safe()); unit_obj[0xd0294] = 0;
    unit_obj[0xd0294 + 4] = 0x7f; tick(regs); assert(dm_re_save_safe()); unit_obj[0xd0294 + 4] = 0;   // word 1 is a mask, not a pause
    memcpy(game + 0x5fc, &other, 4); tick(regs); assert(!dm_re_save_safe());
    memcpy(game + 0x5fc, &field, 4); tick(regs); assert(dm_re_save_request());
    sub = 1; tick(regs); assert(!ncalls && dm_re_save_note() == RE_SAVE_REFUSED); sub = 0;
    dm_re_save_note_clear(); assert(dm_re_save_note() == RE_SAVE_IDLE);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp); (d / 'save.c').write_text(harness)
            subprocess.run([cc, '-std=c11', '-Wall', '-Werror', '-Wno-unused-function', str(d / 'save.c'), '-o', str(d / 'save')], check=True)
            for args in [[], ['unsupported-build']]:
                subprocess.run([str(d / 'save'), *args], check=True)

    def test_profile_menu(self):
        profile = android_profile.load('010050F00BC1A000')
        self.assertIn('#define DM_ANDROID_SAVE_ANYWHERE 1', android_profile.header(profile))
        self.assertIn('#define DM_ANDROID_SAVE_ANYWHERE 0', android_profile.header(None))

    def test_no_data_cut(self):
        # the "No Data" place of a save outside save rooms becomes "Mansion Dining Room" (BhdTool's fix), on the checked build only
        ns = {}
        exec((DM / 'games/010050F00BC1A000/patches.py').read_text(), ns)
        cuts = ns['CUTS']['6bec9b23b09df46c315aa6f4bfacf91c']
        self.assertEqual([c[:3] for c in cuts], [(0x45e28, 'a9018052', '29008052'), (0x45fd0, 'aa018052', '2a008052')])
        self.assertEqual(list(ns['CUTS']), ['6bec9b23b09df46c315aa6f4bfacf91c'])


if __name__ == '__main__':
    unittest.main()
