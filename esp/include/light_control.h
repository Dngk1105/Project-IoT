#ifndef LIGHT_CONTROL_H
#define LIGHT_CONTROL_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>

void light_control_init(void);
void light_control_set_state(bool turn_on);
bool light_control_get_state(void);

#ifdef __cplusplus
}
#endif

#endif // LIGHT_CONTROL_H