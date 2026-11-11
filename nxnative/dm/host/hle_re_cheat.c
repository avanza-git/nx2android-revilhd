// Resident Evil 1.0.0: the pause menu's Cheats tab (android.tsv cheats): infinite health, infinite ammo, one-hit kills, unlimited ink ribbons. Saved toggles, off by default.
// No guest code changes: observation gates at function entries (patches.py OBS 27..32, original instructions asserted offline) adjust the game's own data just before
// the game's code uses it, so the game's checks that follow (death, an empty weapon, a used-up item) see the value they would have seen without the hit, shot or save.
// Read on main build 6bec9b23b09df46c315aa6f4bfacf91c with dm/tools/sdis.py (2026-11-12):
//   life: uMassModel + 0x175c, its maximum + 0x1760 (uMassModel::addLife main+0x3362f0, subLife main+0x336310)
//   cAttack::giveDamage(ctx) (main+0x19b50): the target is sEntryList::getPointer(ctx + 0x50); a player actor gets uActor::set_damage (damage ctx + 0x6c, reaction ctx + 0x60;
//     ctx + 0xc bit 2 forces the dying branch, bit 3 poison, bit 4 the yawn's poison), ctx + 0x1c == 3 Life_down_set2(ctx + 0x60, 0, ctx + 0xc: bit 1 forces 0), anything else
//     uMassModel::storeDamage (enemies; their damage_check then calls Life_down_set with uEmBase::getReceiveDamage)
//   uCharacterBase::Life_down_set(this, damage, spread) (main+0x1a7330) and Life_down_set2(this, damage, spread, flags) (main+0x1a7390): life -= damage - spread + rand % (2 * spread)
//     (spread 0: just the damage); about 60 callers, the enemies' damage checks and the player's grabs, throws and poison among them
//   uWeapon::requestShot (main+0x374740) and useBullte (main+0x3748c0): unless + 0x1500 bit 1, rounds + 0x1334 -= + 0x133c; with bit 3 (the player's weapon: uWeapon::init
//     main+0x374548 sets it from the owner) also sGameManager + 0x5134 + 4 * type (+ 0x1330, 0 when above 14) -= 1, both floored at 0
//   sGameManager::useHolderItem(this, item) (main+0xed0f0): the inventory, 7 slots (9 with sGameManager + 0x5118) of {item + 0x44, count + 0x48}; count - 1, the slot cleared at 0.
//     cSaveData::save (main+0x45184) uses the ink ribbon, item 0x44, through it
//   the kind of an object: MtObject::getDTI is vtable slot 5 (uPlayer's: main+0x357360), MtDTI's parent at + 0x20 (MtDTI::MtDTI main+0x38c61c)
#include "hle.h"
#ifdef DM_ANDROID
#include "android_profile.h"
#include <stdatomic.h>
#if DM_ANDROID_CHEATS
int dm_android_cheat(int which);   // front_android.c: RE_CHEAT_* (dm.h) switched on in the pause menu
#define RE_LIFE 0x175c
#define RE_RIBBON 0x44
static void *(*get_pointer)(void *, uint64_t); static void **g_entry_inst, **g_gm_inst; static const void *g_dti_player, *g_dti_npc, *g_dti_enemy;
static _Atomic int g_told;   // the cheats that acted once (logged)
static int resolve(void) {
    static int done, ok;
    if (done) return ok;
    done = 1;
    if (strcmp(dm_main_build(), "6bec9b23b09df46c315aa6f4bfacf91c")) { LOG("[cheat] cheats off: main build %s is not the one checked", dm_main_build()); return 0; }
    get_pointer = guest_sym("_ZNK2K210sEntryList10getPointerENS0_8SearchIDE"); g_entry_inst = guest_sym("_ZN2K210sEntryList10mpInstanceE"); g_gm_inst = guest_sym("_ZN2K212sGameManager10mpInstanceE");
    g_dti_player = guest_sym("_ZN2K27uPlayer3DTIE"); g_dti_npc = guest_sym("_ZN2K28uNpcBase3DTIE"); g_dti_enemy = guest_sym("_ZN2K27uEmBase3DTIE");
    ok = get_pointer && g_entry_inst && g_gm_inst && g_dti_player && g_dti_npc && g_dti_enemy;
    LOG("[cheat] cheats %s", ok ? "ready" : "off: a symbol is missing");
    return ok;
}
static int on(int c) { return dm_android_cheat(c) && resolve(); }
static void told(int c, const char *what) { if (!(atomic_fetch_or(&g_told, 1 << c) & 1 << c)) LOG("[cheat] %s", what); }
static int32_t get32(const uint8_t *p) { int32_t v; memcpy(&v, p, sizeof v); return v; }
static void put32(uint8_t *p, int32_t v) { dm_guest_write_prepare(p, sizeof v); memcpy(p, &v, sizeof v); }
enum { K_OTHER, K_PLAYER, K_ENEMY };
static int kind(const void *obj) {   // the player (uPlayer), an enemy (uEmBase, but not a partner: uNpcBase), anything else
    if (!obj) return K_OTHER;
    const void *(*dti)(const void *) = (*(const void *(*const *const *)(const void *))obj)[5];
    const uint8_t *d = dti(obj);
    for (int i = 0; d && i < 32; i++, d = *(const uint8_t *const *)(d + 0x20)) {   // (the root DTI is its own parent: the count ends the walk)
        if (d == g_dti_player) return K_PLAYER;
        if (d == g_dti_npc) return K_OTHER;
        if (d == g_dti_enemy) return K_ENEMY;
    }
    return K_OTHER;
}
// cAttack::giveDamage(this, ctx), entry: a hit on the player does no damage, cannot force the dying branch and does not poison; the hit's reaction still plays
static void give_damage(const uint64_t *regs) {
    uint8_t *ctx = (uint8_t *)(uintptr_t)regs[1];
    if (!ctx || !on(RE_CHEAT_HEALTH) || !*g_entry_inst) return;
    uint64_t id; memcpy(&id, ctx + 0x50, sizeof id);
    if (kind(get_pointer(*g_entry_inst, id)) != K_PLAYER) return;
    uint32_t fl = (uint32_t)get32(ctx + 0xc) & ~(4u | 8u | 0x10u);
    if (get32(ctx + 0x6c)) put32(ctx + 0x6c, 0);
    if (get32(ctx + 0x1c) == 3) { put32(ctx + 0x60, 0); fl &= ~2u; }   // (only that route reads + 0x60 as damage: uActor::set_damage takes it as the reaction)
    if (fl != (uint32_t)get32(ctx + 0xc)) put32(ctx + 0xc, (int32_t)fl);
    told(RE_CHEAT_HEALTH, "infinite health: a hit on the player does no damage");
}
// uCharacterBase::Life_down_set / Life_down_set2(this, damage, spread[, flags]), entry: the player's life is raised by the most the call can take (it ends where it was,
// up to 2 * spread above); an enemy's is set so that the least the call can take kills it
static void life_down(const uint64_t *regs) {
    uint8_t *o = (uint8_t *)(uintptr_t)regs[0]; int32_t dmg = (int32_t)regs[1], spread = (int32_t)regs[2]; spread = spread < 0 ? -spread : spread;
    if (!o || dmg <= 0 || !(dm_android_cheat(RE_CHEAT_HEALTH) || dm_android_cheat(RE_CHEAT_OHK)) || !resolve()) return;
    int k = kind(o); int32_t life = get32(o + RE_LIFE);
    if (k == K_PLAYER && dm_android_cheat(RE_CHEAT_HEALTH)) { put32(o + RE_LIFE, life + dmg + spread); told(RE_CHEAT_HEALTH, "infinite health: the player's life kept"); }
    else if (k == K_ENEMY && dm_android_cheat(RE_CHEAT_OHK) && life > 0) {
        int32_t least = dmg - spread; put32(o + RE_LIFE, least < 0 ? least : 0);
        told(RE_CHEAT_OHK, "one-hit kills: an enemy's hit is lethal");
    }
}
// uWeapon::requestShot / useBullte(this), entry: the rounds the shot takes are put back first, on the player's weapon only
static void shot(const uint64_t *regs) {
    uint8_t *w = (uint8_t *)(uintptr_t)regs[0];
    if (!w || !on(RE_CHEAT_AMMO)) return;
    uint32_t fl = (uint32_t)get32(w + 0x1500);
    if (!(fl & 8) || (fl & 2)) return;   // not the player's weapon, or one that uses no rounds
    put32(w + 0x1334, get32(w + 0x1334) + get32(w + 0x133c));
    uint8_t *gm = *g_gm_inst; uint32_t t = (uint32_t)get32(w + 0x1330);
    if (gm) { uint8_t *c = gm + 0x5134 + 4 * (t > 0xe ? 0 : t); put32(c, get32(c) + 1); }
    told(RE_CHEAT_AMMO, "infinite ammo: the shot's rounds put back");
}
// sGameManager::useHolderItem(this, item), entry: an ink ribbon about to be used is counted once more first
static void use_item(const uint64_t *regs) {
    uint8_t *gm = (uint8_t *)(uintptr_t)regs[0];
    if (!gm || (uint32_t)regs[1] != RE_RIBBON || !on(RE_CHEAT_RIBBON)) return;
    int n = get32(gm + 0x5118) ? 9 : 7;
    for (int i = 0; i < n; i++) if (get32(gm + 0x44 + 8 * i) == RE_RIBBON) { put32(gm + 0x48 + 8 * i, get32(gm + 0x48 + 8 * i) + 1); told(RE_CHEAT_RIBBON, "unlimited ink ribbons: the ribbon kept"); return; }
}
__attribute__((constructor)) static void cheat_gates(void) {
    gate_obs_set(OBS_RE_GIVE_DAMAGE, give_damage); gate_obs_set(OBS_RE_LIFE_DOWN, life_down); gate_obs_set(OBS_RE_LIFE_DOWN2, life_down);
    gate_obs_set(OBS_RE_SHOT, shot); gate_obs_set(OBS_RE_USE_BULLET, shot); gate_obs_set(OBS_RE_USE_ITEM, use_item);
}
#endif
#endif
