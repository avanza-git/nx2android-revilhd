// Explicit frame targets override adaptive pacing; movies keep their original 30 FPS cadence.
#pragma once
#include <stdint.h>
static inline uint64_t dm_frame_limit_period(int limit, int movie, uint64_t period) {
    if (limit < 0) return period;
    return movie || limit == 30 ? 33333333ull : limit == 60 ? 16666667ull : 0;
}
static inline int dm_frame_limit_valid(int value) { return value == 0 || value == 60 ? value : 30; }
static inline int dm_frame_limit_next(int value, int direction) {
    const int values[] = {30, 60, 0};
    int i = value == 30 ? 0 : value == 60 ? 1 : 2;
    return values[(i + direction + 3) % 3];
}
