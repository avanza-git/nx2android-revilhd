// Resident Evil 1.0.0: optional manual door skip. No guest code changes at runtime.
// The build-checked observation gates in the profile retain the original instructions.
#include "hle.h"
#include "dm_input.h"
#ifdef DM_ANDROID
#include "android_profile.h"
#include <stdatomic.h>
int dm_android_skip_doors(void);
static _Atomic int g_door_active, g_door_skip, g_door_busy;   // g_door_busy: a door's controller runs (start to cleanup), whatever the skip toggle (hle_re_save.c)
static _Atomic int g_start_down, g_start_consumed;   // observe presses outside doors too
int dm_re_door_active(void) { return atomic_load(&g_door_busy); }
uint64_t dm_door_skip_buttons(uint64_t buttons) {
    int down = (buttons & DM_BTN_PLUS) != 0;
    int active = DM_ANDROID_SKIP_DOORS && dm_android_skip_doors() && atomic_load(&g_door_active);
    int was = atomic_exchange(&g_start_down, down);
    if (!down) atomic_store(&g_start_consumed, 0);
    if (active && down && !was) { atomic_store(&g_door_skip, 1); atomic_store(&g_start_consumed, 1); }
    if (!active) atomic_store(&g_door_skip, 0);
    return active || atomic_load(&g_start_consumed) ? buttons & ~(uint64_t)DM_BTN_PLUS : buttons;
}
static int door_build(void) {
    static int checked, valid;
    if (!checked) {
        checked = 1;
        for (int i = 0; i < g_nmod; i++) if (!strcmp(g_mod[i].name, "main") &&
            !strcmp(g_mod[i].build_id, "6bec9b23b09df46c315aa6f4bfacf91c")) valid = 1;
    }
    return valid;
}
static void door_execute(const uint64_t *regs) {
    if (!(DM_ANDROID_SKIP_DOORS || DM_ANDROID_SAVE_ANYWHERE) || !door_build()) return;
    // cDoorDemoControl::execute dispatches +0xb8: 0 start, 1 animation, 2 cleanup, 3 done.
    // Set only 1 -> 2; execute still runs its resource, sound and filter cleanup normally.
    uint32_t *state = (uint32_t *)(uintptr_t)(regs[0] + 0xb8), s;
    memcpy(&s, state, sizeof s);
    atomic_store(&g_door_busy, s <= 2);
    if (s == 0) LOG("[door] animation starting (Start skip %s)", dm_android_skip_doors() ? "on" : "off");
    int active = dm_android_skip_doors() && (s == 0 || s == 1);
    atomic_store(&g_door_active, active);
    if (!active) { atomic_store(&g_door_skip, 0); return; }
    if (s == 1 && atomic_exchange(&g_door_skip, 0)) {
        dm_guest_write_prepare(state, sizeof *state);
        __atomic_store_n(state, 2, __ATOMIC_RELAXED);
        atomic_store(&g_door_active, 0);
        LOG("[door] Start (+): door animation skipped through normal cleanup");
    }
}
static void door_final(const uint64_t *regs) {
    (void)regs; atomic_store(&g_door_busy, 0); atomic_store(&g_door_active, 0); atomic_store(&g_door_skip, 0);
}
__attribute__((constructor)) static void door_gates(void) {
    if (!DM_ANDROID_SKIP_DOORS && !DM_ANDROID_SAVE_ANYWHERE) return;
    gate_obs_set(OBS_RE_DOOR_EXEC, door_execute); gate_obs_set(OBS_RE_DOOR_FINAL, door_final);
}
#endif
