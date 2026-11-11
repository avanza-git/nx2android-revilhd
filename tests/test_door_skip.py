"""Manual door skip preserves the original state machine and normal Plus input."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from porter.upstream import android_profile

DM = Path(__file__).resolve().parents[1] / 'nxnative/dm'

class DoorSkip(unittest.TestCase):
    def test_button_and_door_states(self):
        cc = shutil.which('cc')
        if not cc:
            self.skipTest('C compiler required')
        src = (DM/'host/hle_re_door.c').read_text()
        block = src[src.index('int dm_android_skip_doors'):src.rindex('#endif')]
        harness = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <stdatomic.h>
#include "dm_input.h"
#define DM_ANDROID_SKIP_DOORS 1
#define DM_ANDROID_SAVE_ANYWHERE 0
#define OBS_RE_DOOR_EXEC 24
#define OBS_RE_DOOR_FINAL 25
#define LOG(...) ((void)0)
static int enabled;
static struct {const char *name,*build_id;} g_mod[]={{"main","6bec9b23b09df46c315aa6f4bfacf91c"}};
static int g_nmod=1;
int dm_android_skip_doors(void) { return enabled; }
static void dm_guest_write_prepare(void *p,size_t n) { (void)p; (void)n; }
static void gate_obs_set(int id,void (*fn)(const uint64_t *)) { (void)id; (void)fn; }
''' + block + r'''
int main(int argc,char **argv) {
    (void)argv; uint32_t object[64]={0}; uint32_t *state=&object[0xb8/4];
    uint64_t regs[31]={(uintptr_t)object}; door_gates();
    if(argc>1) g_mod[0].build_id="unsupported";
    // Disabled by default: neither door state nor Start input changes.
    *state=1; door_execute(regs); assert(*state==1);
    assert(dm_door_skip_buttons(DM_BTN_PLUS)==DM_BTN_PLUS); dm_door_skip_buttons(0);
    enabled=1; door_execute(regs);
    if(argc>1) { assert(dm_door_skip_buttons(DM_BTN_PLUS)==DM_BTN_PLUS); assert(*state==1); return 0; }
    // A fresh Start press while animation is active preserves other buttons and requests cleanup.
    assert(dm_door_skip_buttons(DM_BTN_PLUS|DM_BTN_A)==DM_BTN_A);
    door_execute(regs); assert(*state==2);
    // Holding Start through completion cannot pause the room that just loaded.
    door_final(regs); assert(dm_door_skip_buttons(DM_BTN_PLUS)==0);
    dm_door_skip_buttons(0); assert(dm_door_skip_buttons(DM_BTN_PLUS)==DM_BTN_PLUS);
    // A button already held before the next door does not skip that door.
    *state=1; door_execute(regs); dm_door_skip_buttons(DM_BTN_PLUS); door_execute(regs); assert(*state==1);
    dm_door_skip_buttons(0); dm_door_skip_buttons(DM_BTN_PLUS); door_execute(regs); assert(*state==2);
    dm_door_skip_buttons(0);
    // A request during startup waits for animation state 1; never jumps over startup/loading.
    *state=0; door_execute(regs); dm_door_skip_buttons(DM_BTN_PLUS); door_execute(regs); assert(*state==0);
    *state=1; door_execute(regs); assert(*state==2); dm_door_skip_buttons(0);
    // Completed/cleanup states and disabling mid-door leave the native state untouched.
    *state=3; door_execute(regs); assert(dm_door_skip_buttons(DM_BTN_PLUS)==DM_BTN_PLUS); assert(*state==3);
    dm_door_skip_buttons(0); *state=1; door_execute(regs); enabled=0;
    assert(dm_door_skip_buttons(DM_BTN_PLUS)==DM_BTN_PLUS); door_execute(regs); assert(*state==1);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp); (d/'door.c').write_text(harness)
            subprocess.run([cc,'-std=c11','-Wall','-Werror','-I'+str(DM/'host'),str(d/'door.c'),'-o',str(d/'door')],check=True)
            for args in [[], ['unsupported-build']]:
                subprocess.run([str(d/'door'),*args],check=True)

    def test_profile_menu(self):
        profile = android_profile.load('010050F00BC1A000')
        self.assertIn('#define DM_ANDROID_SKIP_DOORS 1', android_profile.header(profile))
        self.assertIn('#define DM_ANDROID_SKIP_DOORS 0', android_profile.header(None))
