#ifndef AUDIO_PSRAM_H
#define AUDIO_PSRAM_H

#include <stddef.h>
#include <stdint.h>

#define PSRAM_MAX_SIZE (4 * 1024 * 1024) // 4MB

extern uint8_t* psram_buffer;
extern size_t psram_write_pos;

void audio_psram_init(void);
void audio_psram_feed(const uint8_t* data, size_t len);

#endif