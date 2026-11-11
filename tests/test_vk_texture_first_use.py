"""Run the real first-use CPU texture policy against pre-registration content."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class TextureFirstUse(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'a host C compiler is required')
    def test_prefilled_storage_and_gpu_exclusions(self):
        src = (Path(__file__).resolve().parents[1] / 'nxnative/dm/android/gfx_vk_tex.c').read_text()
        start = src.index('static int mem_any(')
        functions = src[start:src.index('static int packaged_tex(', start)]
        harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#define NVN_TEXTURE_TARGET_2D 1
#define NVN_MEMORY_POOL_FLAGS_VIRTUAL 1
#define NVN_TEXTURE_FLAGS_IMAGE 1
#define NVN_TEXTURE_FLAGS_COMPRESSIBLE 2
#define NVN_TEXTURE_FLAGS_LINEAR 4
#define NVN_TEXTURE_FLAGS_LINEAR_RENDER_TARGET 8
#define NVN_TEXTURE_FLAGS_SPARSE 16
#define VKLOG(...) ((void)0)
typedef struct { int flags; } pool_t;
typedef struct {
    pool_t *pool;
    int has_layout;
    struct { int target, samples, flags; } d;
    uint8_t *mem;
    struct { uint64_t size; } L;
} tex_t;
typedef struct { int compressed; } vkfmt_t;
static int marks;
static void mtl_tex_cpu_written(const tex_t *t) { assert(t->mem); marks++; }
FUNCTIONS
static void check(tex_t t, vkfmt_t f, int expected) {
    const char *e = getenv("DM_NVN_STORAGE_FIRST_USE");
    if (e && !atoi(e)) expected = 0;
    int before = marks;
    assert(cpu_content_tex(&t, &f) == expected);
    assert(marks == before + expected);
}
int main(void) {
    uint8_t data[17] = {0};
    pool_t pool = {0};
    tex_t t = {.pool=&pool, .d={.target=1, .samples=1}, .mem=data, .L={sizeof data}};
    vkfmt_t f = {0};
    check(t, f, 0);  // empty GPU storage is not CPU content
    data[16] = 1;  // prefilled R32F depth, before tracking/registration
    check(t, f, DM_GAME_TEX_DIRTY_UPLOAD);
    t.d.target = 4; check(t, f, 0);  // opt-in does not broaden arrays
    t.d.target = 2; check(t, f, 1);  // existing uncompressed 3D policy
    t.d.target = 1; f.compressed = 1;
    check(t, f, 1);  // existing BC/ASTC policy
    for (int compressed=0; compressed<=1; compressed++) {
        f.compressed = compressed;
        t.d.target = 2;
        t.has_layout = 1; check(t, f, 0); t.has_layout = 0;
        t.pool = NULL; check(t, f, 0); t.pool = &pool;
        t.d.samples = 4; check(t, f, 0); t.d.samples = 1;
        pool.flags = NVN_MEMORY_POOL_FLAGS_VIRTUAL; check(t, f, 0); pool.flags = 0;
        for (int flag=1; flag<=16; flag<<=1) {
            t.d.flags = flag; check(t, f, 0);
        }
        t.d.flags = 0;
    }
    memset(data, 0, sizeof data);
    assert(!mem_any(data, sizeof data));
    for (unsigned i=0; i<sizeof data; i++) {
        data[i] = 1;
        assert(mem_any(data, sizeof data));
        assert(!mem_any(data, i));
        data[i] = 0;
    }
}
'''.replace('FUNCTIONS', functions)
        with tempfile.TemporaryDirectory(prefix='nx2a-first-use-') as tmp:
            c, exe = Path(tmp) / 'check.c', Path(tmp) / 'check'
            c.write_text(harness)
            for dirty in (0, 1):
                subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                                f'-DDM_GAME_TEX_DIRTY_UPLOAD={dirty}', str(c), '-o', str(exe)],
                               check=True, timeout=30)
                for enabled in ('0', '1'):
                    subprocess.run([str(exe)], check=True, timeout=15,
                                   env={**os.environ, 'DM_NVN_STORAGE_FIRST_USE': enabled})
