"""C code templates for Raspberry Pi 4 pthreads firmware."""

from eda_platform.agents.firmware_engineer.models import SchedulingPlan
from eda_platform.agents.firmware_engineer.pin_map import (
    I2C_BUS_NUMBER,
    I2C_DEVICE_PATH,
    bcm_for_logical_pin,
)

_FALLBACK_SDA_BCM = 2
_FALLBACK_SCL_BCM = 3


def board_config_h(
    plan: SchedulingPlan,
    sda_pin_id: str | None = None,
    scl_pin_id: str | None = None,
) -> str:
    # Resolve the schematic's actual wired I2C pins through the platform pin
    # map; fall back to the Pi I2C1 default (BCM 2/3) only when the
    # schematic's pin_id isn't in the map (e.g. an unmapped MCU family).
    sda_bcm = (bcm_for_logical_pin(sda_pin_id) if sda_pin_id else None) or _FALLBACK_SDA_BCM
    scl_bcm = (bcm_for_logical_pin(scl_pin_id) if scl_pin_id else None) or _FALLBACK_SCL_BCM

    return f"""/* Auto-generated board configuration for {plan.platform} */
#ifndef BOARD_CONFIG_H
#define BOARD_CONFIG_H

#define I2C_DEV_PATH "{I2C_DEVICE_PATH}"
#define I2C_BUS_NUMBER {I2C_BUS_NUMBER}
#define SENSOR_POLL_PERIOD_MS 20

/* Schematic I2C pins ({sda_pin_id or "default"}/{scl_pin_id or "default"}) mapped to Pi header */
#define PIN_I2C_SDA_BCM {sda_bcm}
#define PIN_I2C_SCL_BCM {scl_bcm}

#endif /* BOARD_CONFIG_H */
"""


def hal_i2c_bus_0_h() -> str:
    return """/* Auto-generated I2C bus HAL */
#ifndef HAL_I2C_BUS_0_H
#define HAL_I2C_BUS_0_H

#include <pthread.h>
#include <stdint.h>

int hal_i2c_bus_0_init(void);
void hal_i2c_bus_0_lock(void);
void hal_i2c_bus_0_unlock(void);
int hal_i2c_bus_0_read_reg(uint8_t addr, uint8_t reg, uint8_t *buf, size_t len);
int hal_i2c_bus_0_write_reg(uint8_t addr, uint8_t reg, const uint8_t *buf, size_t len);

#endif /* HAL_I2C_BUS_0_H */
"""


def hal_i2c_bus_0_c() -> str:
    return f"""/* Auto-generated I2C bus HAL — {I2C_DEVICE_PATH} with pthread mutex */
#include "hal_i2c_bus_0.h"

#include <fcntl.h>
#include <linux/i2c-dev.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#include "../platform/board_config.h"

static int i2c_fd = -1;
static pthread_mutex_t bus_mutex = PTHREAD_MUTEX_INITIALIZER;

int hal_i2c_bus_0_init(void) {{
    i2c_fd = open(I2C_DEV_PATH, O_RDWR);
    if (i2c_fd < 0) {{
        perror("hal_i2c_bus_0_init: open");
        return -1;
    }}
    /* Target address is set per-transaction in set_slave(); no fixed slave here. */
    return 0;
}}

void hal_i2c_bus_0_lock(void) {{ pthread_mutex_lock(&bus_mutex); }}
void hal_i2c_bus_0_unlock(void) {{ pthread_mutex_unlock(&bus_mutex); }}

static int set_slave(uint8_t addr) {{
    if (ioctl(i2c_fd, I2C_SLAVE, addr) < 0) {{
        perror("hal_i2c_bus_0: set_slave");
        return -1;
    }}
    return 0;
}}

int hal_i2c_bus_0_write_reg(uint8_t addr, uint8_t reg, const uint8_t *buf, size_t len) {{
    uint8_t tmp[1 + len];
    tmp[0] = reg;
    memcpy(tmp + 1, buf, len);
    if (set_slave(addr) < 0) return -1;
    if (write(i2c_fd, tmp, 1 + len) != (ssize_t)(1 + len)) {{
        perror("hal_i2c_bus_0_write_reg");
        return -1;
    }}
    return 0;
}}

int hal_i2c_bus_0_read_reg(uint8_t addr, uint8_t reg, uint8_t *buf, size_t len) {{
    if (set_slave(addr) < 0) return -1;
    if (write(i2c_fd, &reg, 1) != 1) {{
        perror("hal_i2c_bus_0_read_reg: write reg");
        return -1;
    }}
    if (read(i2c_fd, buf, len) != (ssize_t)len) {{
        perror("hal_i2c_bus_0_read_reg: read");
        return -1;
    }}
    return 0;
}}
"""


def hal_ina219_h(sensor: dict) -> str:
    hal = sensor["hal_module"]
    return f"""/* Auto-generated INA219 HAL for node {sensor["node_id"]} */
#ifndef {hal.upper()}_H
#define {hal.upper()}_H

#include <stdint.h>

int {hal}_init(void);
int {hal}_read_current_ma(float *current_ma);

#endif /* {hal.upper()}_H */
"""


def hal_ina219_c(sensor: dict) -> str:
    hal = sensor["hal_module"]
    addr = sensor["i2c_address"]
    return f"""/* Auto-generated INA219 driver — I2C address 0x{addr:02X} */
#include "{hal}.h"

#include <stdint.h>
#include <stdio.h>

#include "hal_i2c_bus_0.h"

#define INA219_ADDR 0x{addr:02X}
#define INA219_REG_CONFIG   0x00
#define INA219_REG_SHUNT_MV 0x01
#define INA219_REG_BUS_MV   0x02
#define INA219_REG_CALIB    0x05

static int configured = 0;

int {hal}_init(void) {{
    uint8_t cfg[2] = {{0x19, 0x9F}}; /* 32V, 2A range, 12-bit */
    hal_i2c_bus_0_lock();
    int rc = hal_i2c_bus_0_write_reg(INA219_ADDR, INA219_REG_CONFIG, cfg, 2);
    hal_i2c_bus_0_unlock();
    configured = (rc == 0);
    return rc;
}}

int {hal}_read_current_ma(float *current_ma) {{
    if (!configured) return -1;
    uint8_t raw[2];
    hal_i2c_bus_0_lock();
    int rc = hal_i2c_bus_0_read_reg(INA219_ADDR, INA219_REG_SHUNT_MV, raw, 2);
    hal_i2c_bus_0_unlock();
    if (rc < 0) return rc;
    int16_t shunt_raw = (int16_t)((raw[0] << 8) | raw[1]);
    *current_ma = shunt_raw * 0.1f; /* simplified: 0.1 mA per LSB at default cal */
    return 0;
}}
"""


def task_sensor_poll_c(sensors: list[dict]) -> str:
    inits = "\n    ".join(f"{s['hal_module']}_init();" for s in sensors)
    reads = "\n        ".join(
        f'float {s["node_id"]}_ma = 0.0f;\n        '
        f'if ({s["hal_module"]}_read_current_ma(&{s["node_id"]}_ma) == 0) {{\n            '
        f'printf("[T1] {s["node_id"]} current: %.2f mA\\n", {s["node_id"]}_ma);\n        }}'
        for s in sensors
    )
    return f"""/* Auto-generated T1 sensor poll task (timerfd + pthread) */
#include <pthread.h>
#include <stdio.h>
#include <sys/timerfd.h>
#include <time.h>
#include <unistd.h>

#include "../platform/board_config.h"
#include "../hal/hal_i2c_bus_0.h"
{chr(10).join(f'#include "../hal/{s["hal_module"]}.h"' for s in sensors)}

void *task_sensor_poll(void *arg) {{
    (void)arg;
    {inits}

    int tfd = timerfd_create(CLOCK_MONOTONIC, 0);
    struct itimerspec spec = {{
        .it_interval = {{SENSOR_POLL_PERIOD_MS / 1000, (SENSOR_POLL_PERIOD_MS % 1000) * 1000000L}},
        .it_value = {{SENSOR_POLL_PERIOD_MS / 1000, (SENSOR_POLL_PERIOD_MS % 1000) * 1000000L}},
    }};
    timerfd_settime(tfd, 0, &spec, NULL);

    uint64_t expirations;
    for (;;) {{
        if (read(tfd, &expirations, sizeof(expirations)) < 0) {{
            continue; /* interrupted or spurious wakeup — try again next period */
        }}
        {reads}
    }}
    return NULL;
}}
"""


def task_background_c() -> str:
    return """/* Auto-generated T3 background worker */
#include <pthread.h>
#include <stdio.h>
#include <unistd.h>

void *task_background(void *arg) {
    (void)arg;
    for (;;) {
        printf("[T3] background heartbeat\\n");
        sleep(5);
    }
    return NULL;
}
"""


def main_c(plan: SchedulingPlan, sensors: list[dict]) -> str:
    has_sensor_poll = any(t.task_id == "task_sensor_poll" for t in plan.tasks)
    has_background = any(t.task_id == "task_background" for t in plan.tasks)

    # Precomputed outside the f-string: Python 3.11 (our declared minimum,
    # see pyproject.toml `requires-python`) disallows backslash escapes
    # inside f-string `{...}` expressions, so the embedded C string literals
    # below can't be built inline within the template's f-string braces.
    sensor_poll_extern = "    extern void *task_sensor_poll(void *);" if has_sensor_poll else ""
    sensor_poll_spawn = (
        '    spawn_thread(task_sensor_poll, "task_sensor_poll");' if has_sensor_poll else ""
    )
    background_extern = "    extern void *task_background(void *);" if has_background else ""
    background_spawn = (
        '    spawn_thread(task_background, "task_background");' if has_background else ""
    )

    return f"""/* Auto-generated firmware entry point — {plan.project_id} */
#include <pthread.h>
#include <stdio.h>
#include <unistd.h>

#include "platform/board_config.h"
#include "hal/hal_i2c_bus_0.h"

static void spawn_thread(void *(*fn)(void *), const char *name) {{
    pthread_t tid;
    pthread_attr_t attr;
    pthread_attr_init(&attr);
    if (pthread_create(&tid, &attr, fn, NULL) != 0) {{
        perror(name);
    }} else {{
        pthread_detach(tid);
    }}
    pthread_attr_destroy(&attr);
}}

int main(void) {{
    /* stdout is fully buffered when not attached to a TTY (e.g. under
     * systemd) — force line buffering so status output interleaves with
     * stderr in the correct order when tailing logs on real hardware. */
    setvbuf(stdout, NULL, _IOLBF, 0);

    printf("EDA Platform firmware — project: {plan.project_id} (platform: {plan.platform})\\n");

    if (hal_i2c_bus_0_init() != 0) {{
        fprintf(stderr, "I2C bus init failed — enable I2C on Pi (raspi-config)\\n");
        return 1;
    }}

{sensor_poll_extern}
{sensor_poll_spawn}
{background_extern}
{background_spawn}

    /* Thin supervisor — no hardware logic in main */
    for (;;) {{
        sleep(10);
        printf("[main] supervisor alive\\n");
    }}
    return 0;
}}
"""


def makefile(project_id: str, sensors: list[dict]) -> str:
    hal_objs = " ".join(f"hal/{s['hal_module']}.o" for s in sensors)
    return f"""# Auto-generated Makefile for {project_id} on Raspberry Pi 4
CC = gcc
CFLAGS = -Wall -Wextra -O2 -pthread -I.
LDFLAGS = -pthread

OBJS = main.o hal/hal_i2c_bus_0.o tasks/task_sensor_poll.o tasks/task_background.o {hal_objs}

TARGET = {project_id}_firmware

all: $(TARGET)

$(TARGET): $(OBJS)
\t$(CC) $(LDFLAGS) -o $@ $^

main.o: main.c platform/board_config.h
hal/hal_i2c_bus_0.o: hal/hal_i2c_bus_0.c hal/hal_i2c_bus_0.h
tasks/task_sensor_poll.o: tasks/task_sensor_poll.c
tasks/task_background.o: tasks/task_background.c
{chr(10).join(f"hal/{s['hal_module']}.o: hal/{s['hal_module']}.c hal/{s['hal_module']}.h" for s in sensors)}

clean:
\trm -f $(OBJS) $(TARGET)

.PHONY: all clean
"""
