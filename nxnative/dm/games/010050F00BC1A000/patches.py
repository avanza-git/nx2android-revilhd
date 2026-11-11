# Resident Evil 1.0.0: preserve prerendered movie timing when the engine runs at 60 FPS.
# Movie lifetime sites from masagrator's FPSLocker-Warehouse v4 config 6BEC9B23B09DF46C;
# gate at constructor entry and after the destructor's final call (before its tail call).
# Original instructions are asserted by patch_nso.py, and execute unchanged after each gate.
OBS = {'6bec9b23b09df46c315aa6f4bfacf91c': [
    (0xb1a810, 22, 'f81e0ff3', 'Resident Evil movie constructor: hold movies at 30 FPS'),
    (0xb1a9a8, 23, 'aa1303e0', 'Resident Evil movie destructor: restore selected frame limit'),
    # cDoorDemoControl::execute / final: original instructions and main build checked offline.
    # execute state 1 is animation playback; state 2 follows the game's ordinary cleanup path.
    (0x26890, 24, 'a9bd57f6', 'Resident Evil door animation: optional Start skip'),
    (0x26cc0, 25, '321f03e8', 'Resident Evil door final: clear pending Start skip'),
    # aGame::move entry (sub sp, sp, #0xa0): the game thread's per-frame step for the pause menu's Save game (hle_re_save.c).
    (0x42c0, 26, 'd10283ff', 'Resident Evil aGame::move: Save game driver'),
    # The pause menu's Cheats tab (hle_re_cheat.c, android.tsv cheats): function entries whose data the host adjusts before the game's code reads it.
    (0x19b50, 27, 'a9be4ff4', 'Resident Evil cAttack::giveDamage: infinite health (a hit on the player does no damage)'),
    (0x1a7330, 28, 'f81d0ff5', 'Resident Evil uCharacterBase::Life_down_set: infinite health, one-hit kills'),
    (0x1a7390, 29, 'a9bd57f6', 'Resident Evil uCharacterBase::Life_down_set2: infinite health, one-hit kills'),
    (0x374740, 30, 'f81e0ff3', 'Resident Evil uWeapon::requestShot: infinite ammo'),
    (0x3748c0, 31, 'b9550008', 'Resident Evil uWeapon::useBullte: infinite ammo'),
    (0xed0f0, 32, 'a9bc5ff8', 'Resident Evil sGameManager::useHolderItem: unlimited ink ribbons'),
]}

# The pause menu's Save game (hle_re_save.c) saves outside save rooms. A save's place is named from the stage and room (sGameManager + 0xe4760 / 0xe4764) for save
# rooms only, and any other room gets 0xd, which the save and load lists show as "No Data" (uBhdGUI_Save::listupSaveData): its default becomes 1, "Mansion Dining Room",
# as eleval's BhdTool does on PC (SaveTool.cpp, GAID_INVALID_SAVE_FIX). A save room's own name is unchanged. The code is cSaveData::storeGameDataHeader (main+0x45f80),
# which nothing calls: the copy that runs is inlined in cSaveData::storeGameData (main+0x45e28; on 2026-11-11 a save with only the first cut still listed as "No Data").
CUTS = {'6bec9b23b09df46c315aa6f4bfacf91c': [
    (0x45e28, 'a9018052', '29008052', 'Resident Evil storeGameData (inlined header): a place outside save rooms is "Mansion Dining Room", not "No Data" (mov w9, #0xd -> #1)'),
    (0x45fd0, 'aa018052', '2a008052', 'Resident Evil storeGameDataHeader: the same default in the outlined copy (mov w10, #0xd -> #1)'),
]}
