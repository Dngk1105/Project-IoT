#include "time_core.h"
#include <time.h>
#include <sys/time.h>

void time_core_init(void) {
    // TODO: Khởi tạo sntp_setoperatingmode(SNTP_OPMODE_POLL);
}

uint32_t get_current_unix_timestamp(void) {
    time_t now;
    time(&now);
    return (uint32_t)now;
}