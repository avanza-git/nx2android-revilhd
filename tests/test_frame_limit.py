"""Explicit frame limits, opt-in menu visibility, and saved settings compatibility."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from porter.upstream import android_profile

DM = Path(__file__).resolve().parents[1] / 'nxnative/dm'

class FrameLimit(unittest.TestCase):
    def test_policy_and_profile_menu(self):
        cc = shutil.which('cc')
        if not cc:
            self.skipTest('C compiler required')
        harness = r'''
#include <assert.h>
#include "frame_limit.h"
#include "overlay_layout.h"
int main(void) {
    assert(dm_frame_limit_valid(30) == 30);
    assert(dm_frame_limit_valid(60) == 60);
    assert(dm_frame_limit_valid(0) == 0);
    assert(dm_frame_limit_valid(-1) == 30);
    assert(dm_frame_limit_valid(144) == 30);
    int limits[] = {30, 60, 0};
    for (int i = 0; i < 3; i++) {
        assert(dm_frame_limit_next(limits[i], 1) == limits[(i + 1) % 3]);
        assert(dm_frame_limit_next(limits[i], -1) == limits[(i + 2) % 3]);
        for (int j = 0; j < 3; j++) {
            assert(dm_frame_limit_period(limits[j], 0, 33333333) ==
                   (j == 0 ? 33333333 : j == 1 ? 16666667 : 0));
            assert(dm_frame_limit_period(limits[j], 1, 16666667) == 33333333);
        }
    }
    assert(dm_frame_limit_period(-1, 0, 25000000) == 25000000);
#if DM_ANDROID_SAVE_ANYWHERE
    // Save game heads the Game tab; Picture follows Mode
    assert(ov_menu_item(1, 1) == OVM_SAVE && ov_menu_item(1, 3) == OVM_MODE && ov_menu_item(1, 4) == OVM_PICTURE);
    assert(ov_menu_item(1, 7) == (DM_ANDROID_FRAME_LIMIT ? OVM_LIMIT : -1));
    assert(ov_menu_item(1, 8) == (DM_ANDROID_SKIP_DOORS ? OVM_DOORS : -1));
    assert(ov_menu_item(0, 6) == -1 && ov_menu_item(0, 7) == -1 && ov_menu_item(0, 8) == -1);
    assert(ov_menu_item(1, 9) == OVM_RESUME);
#elif DM_ANDROID_SKIP_DOORS
    assert(ov_menu_item(1, 3) == OVM_PICTURE);
    assert(ov_menu_item(1, 6) == (DM_ANDROID_FRAME_LIMIT ? OVM_LIMIT : -1));
    assert(ov_menu_item(1, 7) == OVM_DOORS);
    assert(ov_menu_item(0, 6) == -1 && ov_menu_item(0, 7) == -1);
    assert(ov_menu_item(1, 8) == OVM_RESUME);
#else
    assert(ov_menu_item(1, 2) == OVM_MODE && ov_menu_item(1, 3) == OVM_PICTURE);
    assert(ov_menu_item(1, 6) == (DM_ANDROID_FRAME_LIMIT ? OVM_LIMIT : -1));
    assert(ov_menu_item(0, 6) == -1);
    assert(ov_menu_item(1, 7) == OVM_RESUME);
#endif
}
'''
        for tid, enabled in [('010050F00BC1A000', True), ('010015100B514000', False)]:
            profile = android_profile.AndroidProfile(android_profile.game.load(tid))
            with self.subTest(tid=tid), tempfile.TemporaryDirectory() as tmp:
                d = Path(tmp)
                (d / 'android_profile.h').write_text(android_profile.header(profile))
                self.assertIn(f'#define DM_ANDROID_FRAME_LIMIT {int(enabled)}', (d / 'android_profile.h').read_text())
                (d / 'check.c').write_text(harness)
                subprocess.run([cc, '-std=c11', '-Wall', '-Werror', '-I'+str(d), '-I'+str(DM/'android'), '-I'+str(DM/'host'), str(d/'check.c'), '-lm', '-o', str(d/'check')], check=True)
                subprocess.run([str(d/'check')], check=True)

    def test_settings_roundtrip(self):
        # Compile the actual settings reader/writer with a minimal layout and host state.
        cc = shutil.which('cc')
        if not cc:
            self.skipTest('C compiler required')
        src = (DM/'android/front_android.c').read_text()
        functions = src[src.index('static void settings_load(void)'):src.index('\n}', src.index('static void settings_save(void)'))+2]
        harness = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdatomic.h>
#include "frame_limit.h"
#define DM_ANDROID_SKIP_DOORS 1
#define DM_ANDROID_FRAME_LIMIT 1
#define OV_OPACITY_MIN 20
#define OV_OPACITY_MAX 80
#define OVE_SCALE_MIN 0.5f
#define OVE_SCALE_MAX 2.0f
#define OV_N 1
#define LOG(...) ((void)0)
static char g_root[512];
static _Atomic int g_set_overlay=1,g_set_rumble=1,g_set_fps=1,g_set_frame_limit=30,g_set_skip_doors,g_set_opacity=60,g_set_grid,g_set_labels=-1,g_set_picture;
enum { OV_PIC_FIT, OV_PIC_STRETCH, OV_PIC_ZOOM, OV_PIC_N };
static _Atomic int g_cust[2][2][1][3];
static const char *LAYOUT_NAMES[]={"tablet","phone"};
static struct { const char *name; } OV_LAYOUTS[2][1]={{{"menu"}},{{"menu"}}};
static int ctl_named(const char *name) { return !strcmp(name,"menu") ? 0 : -1; }
static int dm_opmode(void) { return 1; }
''' + functions + r'''
int main(int argc,char **argv) {
    assert(argc==2); snprintf(g_root,sizeof g_root,"%s",argv[1]);
    char path[600]; snprintf(path,sizeof path,"%s/settings.txt",g_root);
    FILE *f=fopen(path,"w"); assert(f); fprintf(f,"overlay=0\nfps=1\n"); fclose(f);
    settings_load(); assert(g_set_frame_limit==30 && !g_set_overlay && g_set_fps && !g_set_skip_doors);
    const int choices[]={30,60,0};
    for(int i=0;i<3;i++) { g_set_frame_limit=choices[i]; g_set_skip_doors=i%2; settings_save(); g_set_frame_limit=99; g_set_skip_doors=99; settings_load(); assert(g_set_frame_limit==choices[i] && g_set_skip_doors==i%2); assert(!g_set_overlay && g_set_fps); }
    f=fopen(path,"w"); assert(f); fprintf(f,"frame_limit=144\nskip_doors=2\n"); fclose(f);
    settings_load(); assert(g_set_frame_limit==30 && !g_set_skip_doors);
    // the pause menu's Picture: each choice kept; an unknown value is fit
    for(int m=0;m<OV_PIC_N;m++) { g_set_picture=m; settings_save(); g_set_picture=9; settings_load(); assert(g_set_picture==m); }
    f=fopen(path,"w"); assert(f); fprintf(f,"picture=7\n"); fclose(f); g_set_picture=OV_PIC_ZOOM; settings_load(); assert(g_set_picture==OV_PIC_FIT);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp); (d/'settings.c').write_text(harness)
            subprocess.run([cc, '-D_POSIX_C_SOURCE=200809L', '-std=c11', '-Wall', '-Werror', '-I'+str(DM/'android'), str(d/'settings.c'), '-o', str(d/'settings')], check=True)
            subprocess.run([str(d/'settings'), tmp], check=True)

    def test_engine_build_guard_and_movie_timing(self):
        cc = shutil.which('cc')
        if not cc:
            self.skipTest('C compiler required')
        src = (DM/'host/hle_fpslock.c').read_text()
        block = src[src.index('static _Atomic int g_re_movie'):src.index('\n#endif', src.index('static _Atomic int g_re_movie'))]
        harness = r'''#include <assert.h>
#include <stdint.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>
#define DM_ANDROID_SKIP_DOORS 1
#define DM_ANDROID_FRAME_LIMIT 1
#define OBS_RE_MOVIE_START 22
#define OBS_RE_MOVIE_END 23
#define LOG(...) ((void)0)
static struct { const char *name,*build_id; uint8_t *base; } g_mod[1];
static int g_nmod=1, limit=30, gates=1;
static int dm_android_frame_limit(void) { return limit; }
static void gate_obs_set(int id, void (*fn)(const uint64_t *)) { (void)id; (void)fn; }
static int gate_obs_present(int id) { (void)id; return gates; }
static int rd(uint64_t addr, void *out, size_t n) { memcpy(out,(void *)(uintptr_t)addr,n); return 1; }
static void dm_guest_write_prepare(void *p,size_t n) { (void)p; (void)n; }
''' + block + r'''
int main(int argc,char **argv) {
    g_mod[0].name="main";
    g_mod[0].build_id=argc>1 && !strcmp(argv[1],"wrong-build") ? "other" : "6bec9b23b09df46c315aa6f4bfacf91c";
    if(argc>1 && !strcmp(argv[1],"missing-gate")) gates=0;
    g_mod[0].base=calloc(1,0x1ec6cf8); assert(g_mod[0].base);
    uint8_t object[128]={0}; float *fps=(float *)(void *)(object+0x4c); *fps=30;
    uintptr_t obj=(uintptr_t)object; memcpy(g_mod[0].base+0x1ec6cf0,&obj,8);
    re_movie_gates();
    limit=60; assert(re_frame_limit_tick());
    if(argc>1) { assert(*fps==30); free(g_mod[0].base); return 0; }
    assert(*fps==62);
    re_movie_start(NULL); assert(dm_fps_cutscene()); re_frame_limit_tick(); assert(*fps==30);
    re_movie_end(NULL); re_frame_limit_tick(); assert(*fps==62);
    limit=30; re_frame_limit_tick(); assert(*fps==30);
    limit=0; re_frame_limit_tick(); assert(*fps==62);
    free(g_mod[0].base);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp); (d/'engine.c').write_text(harness)
            subprocess.run([cc, '-std=c11', '-Wall', '-Werror', str(d/'engine.c'), '-o', str(d/'engine')], check=True)
            for args in [[], ['wrong-build'], ['missing-gate']]:
                subprocess.run([str(d/'engine'), *args], check=True)
