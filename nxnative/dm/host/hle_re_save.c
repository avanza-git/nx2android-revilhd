// Resident Evil 1.0.0: Save game from the pause menu (android.tsv save_anywhere): a typewriter wherever the player stands. On a request in free play the game's own
// typewriter trigger runs, as cAreaHit::aev_check (main+0xf928) runs it for a typewriter: with an ink ribbon (sGameManager::getItemHolderDataNo(0x44) != -1) the
// "use an ink ribbon?" question (sUIManager::MESSET_CORE(0x39)) and the typewriter event (cRoomEventControl::createEvent(0xf, 0x42, true, false) on sScenario + 0x30,
// under its lock: uEventSce3::Typewriter_message_exec), without one the "no ink ribbon" message (0x3a); then sGameManager::disableStatusFlag(5). The event does the rest:
// the question's answer, the save screen, its ink ribbon, and its cleanup (it shows the player again: calling the save screen without the event left Chris undrawn).
// A save outside a save room gets the location "Mansion Dining Room" instead of "No Data" (patches.py CUTS, cSaveData::storeGameDataHeader), as eleval's BhdTool does on PC.
// Driven from an observation gate at aGame::move (patches.py OBS 26), on the game's own thread; build-checked. DM_RE_SAVE_PROBE=1 logs what the free-play check reads.
#include "hle.h"
#ifdef DM_ANDROID
#include "android_profile.h"
#include <stdatomic.h>
#if DM_ANDROID_SAVE_ANYWHERE
int dm_re_door_active(void);   // hle_re_door.c: a door's controller runs
static _Atomic int g_req, g_safe, g_note;   // g_note: RE_SAVE_* (dm.h), what the menu shows
static void **g_ui_inst, **g_unit_inst, **g_gm_inst, **g_scen_inst; static const uint8_t *g_job_safe;   // the singletons' mpInstance; cSystem::mJobSafe
static int (*is_sub)(void *), (*is_msg)(void *), (*holder_no)(void *, uint32_t, int);
static void (*messet)(void *, uint32_t), (*create_event)(void *, uint32_t, uint32_t, int, int), (*status_off)(void *, uint32_t);
static void (*mutex_lock)(void *), (*mutex_unlock)(void *);
#define RE_AGAME_STATE 0x5fc        // aGame's scene state (aGame::move dispatches on it)
#define RE_FIELD_STATE 50            // aGame's state in a room (2026-11-11 probe on TB320FC: 1, 6, 10, 20 loading and the opening; 50 rooms, events and menus too,
                                     // which the pause bits tell apart: bit 3 the opening's event, 2 and 0 menus, 4 the typewriter). DM_RE_SAVE_FIELD=<n> overrides it
#define RE_PAUSE_WORDS 0xd0294      // sBhdUnit's pause types, one bit each (sBhdUnit::isPauseType); the game's types are all in word 0, the next words are masks made from it
#define RE_INK_RIBBON 0x44
static int resolve(void) {
    static int done, ok;
    if (done) return ok;
    done = 1;
    if (strcmp(dm_main_build(), "6bec9b23b09df46c315aa6f4bfacf91c")) { LOG("[save] Save game off: main build %s is not the one checked", dm_main_build()); return 0; }
    g_ui_inst = guest_sym("_ZN2K210sUIManager10mpInstanceE"); g_unit_inst = guest_sym("_ZN5sUnit10mpInstanceE");
    g_gm_inst = guest_sym("_ZN2K212sGameManager10mpInstanceE"); g_scen_inst = guest_sym("_ZN2K29sScenario10mpInstanceE"); g_job_safe = guest_sym("_ZN7cSystem8mJobSafeE");
    is_sub = guest_sym("_ZN2K210sUIManager18isExecuteSubScreenEv"); is_msg = guest_sym("_ZN2K210sUIManager22isExecuteActiveMsgUnitEv");
    holder_no = guest_sym("_ZN2K212sGameManager19getItemHolderDataNoEjb"); messet = guest_sym("_ZN2K210sUIManager11MESSET_COREEj");
    create_event = guest_sym("_ZN2K217cRoomEventControl11createEventEjjbb"); status_off = guest_sym("_ZN2K212sGameManager17disableStatusFlagENS_9nGameInfo10StatusFlagE");
    mutex_lock = guest_sym("_ZN2nn2os9LockMutexEPNS0_9MutexTypeE"); mutex_unlock = guest_sym("_ZN2nn2os11UnlockMutexEPNS0_9MutexTypeE");
    ok = g_ui_inst && g_unit_inst && g_gm_inst && g_scen_inst && g_job_safe && is_sub && is_msg && holder_no && messet && create_event && status_off && mutex_lock && mutex_unlock;
    LOG("[save] Save game %s", ok ? "ready" : "off: a symbol is missing");
    return ok;
}
// free play: the room's scene state, no unit pause (menus, events, doors, movies and the game's own pause each set one), no sub screen or message, no door
static int field(const uint8_t *game, void *ui, const uint8_t *unit) {
    int32_t st; uint32_t pw[3]; memcpy(&st, game + RE_AGAME_STATE, sizeof st); memcpy(pw, unit + RE_PAUSE_WORDS, sizeof pw);
    int sub = is_sub(ui), msg = is_msg(ui), door = dm_re_door_active();
    static int probe = -1; static uint64_t last[2];
    if (probe < 0) { const char *e = getenv("DM_RE_SAVE_PROBE"); probe = e && *e == '1'; }
    if (probe) {
        uint64_t k[2] = {(uint64_t)(uint32_t)st | (uint64_t)sub << 32 | (uint64_t)msg << 33 | (uint64_t)door << 34, (uint64_t)pw[0] | (uint64_t)pw[1] << 32};
        if (memcmp(k, last, sizeof k)) { memcpy(last, k, sizeof k); LOG("[save] probe: scene %d, pause %08x %08x %08x, sub screen %d, message %d, door %d", st, pw[0], pw[1], pw[2], sub, msg, door); }
    }
    static int want = -2; if (want == -2) { const char *e = getenv("DM_RE_SAVE_FIELD"); want = e && *e ? atoi(e) : RE_FIELD_STATE; }
    return st == want && !pw[0] && !sub && !msg && !door;
}
// the typewriter trigger (cAreaHit::aev_check, main+0xf928..0xfbf0), on the game's thread
static void typewriter(void *ui, void *gm, uint8_t *scen) {
    if (holder_no(gm, RE_INK_RIBBON, 1) == -1) { messet(ui, 0x3a); LOG("[save] no ink ribbon: the game says so"); }
    else {
        messet(ui, 0x39);
        int lock = scen[0x28] | *g_job_safe;   // as the game: sScenario's lock only while jobs run on other threads
        if (lock) mutex_lock(scen + 8);
        create_event(scen + 0x30, 0xf, 0x42, 1, 0);
        if (lock) mutex_unlock(scen + 8);
        LOG("[save] typewriter started: the game asks for an ink ribbon");
    }
    status_off(gm, 5);
}
static void tick(const uint64_t *regs) {
    if (!resolve()) return;
    void *ui = *g_ui_inst, *unit = *g_unit_inst, *gm = *g_gm_inst; uint8_t *scen = *g_scen_inst;
    if (!ui || !unit || !gm || !scen || !regs[0]) { atomic_store(&g_safe, 0); return; }
    int safe = field((const uint8_t *)(uintptr_t)regs[0], ui, unit); atomic_store(&g_safe, safe);
    if (!atomic_exchange(&g_req, 0)) return;
    if (!safe) { atomic_store(&g_note, RE_SAVE_REFUSED); LOG("[save] not here: the player is not in free play"); return; }
    atomic_store(&g_note, RE_SAVE_OPEN); atomic_store(&g_safe, 0);   // the event's pause keeps the next frames out of free play
    typewriter(ui, gm, scen);
}
int dm_re_save_safe(void) { return atomic_load(&g_safe); }
int dm_re_save_note(void) { return atomic_load(&g_note); }
void dm_re_save_note_clear(void) { atomic_store(&g_note, RE_SAVE_IDLE); }
int dm_re_save_request(void) {   // the menu: 1 the typewriter starts when the game goes on, 0 not here
    if (!atomic_load(&g_safe)) { atomic_store(&g_note, RE_SAVE_REFUSED); return 0; }
    atomic_store(&g_note, RE_SAVE_IDLE); atomic_store(&g_req, 1); return 1;
}
__attribute__((constructor)) static void save_gate(void) { gate_obs_set(OBS_RE_SAVE_TICK, tick); }
#endif
#endif
