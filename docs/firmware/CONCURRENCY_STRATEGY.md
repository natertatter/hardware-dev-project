# Firmware Agent Concurrency Strategy

This document defines how the **Firmware Engineer** agent classifies components from `ComponentManifest` data and maps them to execution contexts. The goal is to keep time-critical hardware control off the main loop while allowing background sensing, logging, and communication to proceed without blocking.

## Design Principles

1. **HAL isolation** — Application logic never touches raw pins or registers. Every component is accessed through a generated HAL module.
2. **Classify before scheduling** — Component `type`, `pin_type`, and `supported_features` drive scheduling decisions before any code is emitted.
3. **Fail loud on ambiguity** — If a component cannot be classified into exactly one scheduling tier, the agent emits a fatal error rather than guessing.
4. **Platform-agnostic tiers** — Tiers describe *intent*; the target runtime (FreeRTOS, pthreads, asyncio) is selected at codegen time.

## Execution Contexts (Task 2 Mapping)

The Firmware Agent maps every classified component into exactly one of three execution contexts:

| Execution Context | Description | Tier Mapping |
|-------------------|-------------|--------------|
| **Main loop** | Thin supervisor only — init, spawn workers, watchdog | MCU `main()`; no peripheral logic |
| **Async tasks** | Cooperative or event-driven work that must not block real-time control | T1 (periodic), T2 (bus/UART I/O), T3 (background) |
| **Separate processes / threads** | Isolated, preemptive contexts for deadline-critical control | T0 (dedicated high-priority thread or process) |

On bare-metal MCUs, T0/T1/T2/T3 map to FreeRTOS tasks (separate preemptive threads). On Linux SBCs, T0 may use a `SCHED_FIFO` thread or a child process for hard isolation; T2 async I/O uses coroutines or a thread pool. The agent never places hardware logic in the main loop.

## Execution Tiers

| Tier | Name | Description | Typical Runtime Mapping |
|------|------|-------------|-------------------------|
| **T0** | Hard Real-Time | Sub-millisecond control loops; missed deadlines cause hardware failure | Dedicated high-priority thread / FreeRTOS task |
| **T1** | Soft Real-Time | Periodic sampling or actuation; tens-of-ms tolerance | Medium-priority thread or timer-driven task |
| **T2** | Async I/O | Bus transactions, UART streams, network | Async coroutine or blocking I/O thread pool |
| **T3** | Background | Logging, telemetry aggregation, non-critical polling | Low-priority thread or deferred work queue |

## Component Classification Rules

Classification runs once per `ProjectState` node, using the node's `component_id` manifest.

### By `ComponentManifest.type`

| `type` | Default Tier | Rationale |
|--------|-------------|-----------|
| `MCU` | — (host) | MCU is the runtime host, not a schedulable peripheral |
| `MOTOR_DRIVER` | **T0** | PID, stepper pulse trains, and PWM duty updates are deadline-sensitive |
| `ACTUATOR` | **T0** or **T1** | Solenoids/relays → T1; servo PWM with tight timing → T0 |
| `SENSOR` | **T1** or **T2** | See sensor sub-rules below |
| `PASSIVE` | — (none) | No firmware interaction; wiring-only in schematic |

### Sensor Sub-Classification (`type == SENSOR`)

| Condition | Tier | Example |
|-----------|------|---------|
| Analog stream requiring continuous ADC sampling at >100 Hz | **T0** | Current shunt for motor protection |
| I2C/SPI periodic poll, ≤50 Hz | **T1** | INA219 power monitor, IMU at 50 Hz |
| One-shot or event-driven I2C read | **T2** | Temperature sensor polled on demand |
| UART sensor with streaming protocol | **T2** | GPS NMEA stream |

### Pin-Level Overrides

If a node connects pins with these `pin_type` values, the **highest** applicable tier wins:

| `pin_type` / `supported_features` | Minimum Tier |
|-------------------------------------|--------------|
| Motor PWM output on `GPIO_OUT` with `PWM` feature | **T0** |
| `SPI_*` bus (shared clock/data) | **T2** (bus mutex required) |
| `I2C_SDA` / `I2C_SCL` | **T2** (bus mutex required) |
| `UART_TX` / `UART_RX` | **T2** |
| `ANALOG_IN` with `ADC` at high sample rate | **T0** |
| `GPIO_IN` with interrupt-driven edge detect | **T1** |
| `GPIO_IN` simple polling | **T3** |

## Thread / Task Allocation Model

After classification, the Firmware Agent builds a **Scheduling Plan** (internal JSON, not persisted) with these structures:

```json
{
  "project_id": "example_robot",
  "tasks": [
    {
      "task_id": "motor_control_loop",
      "tier": "T0",
      "priority": 10,
      "period_ms": 1,
      "nodes": ["motor_driver_1"],
      "hal_modules": ["hal_motor_driver_1"]
    },
    {
      "task_id": "sensor_poll",
      "tier": "T1",
      "priority": 5,
      "period_ms": 20,
      "nodes": ["sensor_ina219_1"],
      "hal_modules": ["hal_ina219_1", "hal_i2c_bus_0"]
    }
  ],
  "bus_locks": [
    { "bus_id": "i2c_bus_0", "nodes": ["sensor_ina219_1", "sensor_bme280_1"] }
  ]
}
```

### Allocation Rules

1. **One T0 task per T0-classified node** — Motor drivers and high-rate ADC never share a control loop.
2. **T1 sensors on the same bus may share a task** — A single periodic poll loop reads all I2C sensors on that bus, holding the bus mutex for the transaction burst.
3. **T2 bus access always acquires a bus mutex** — Prevents interleaved I2C/SPI transactions from different contexts.
4. **T3 work runs on a single background worker** — Logging and slow GPIO polls are coalesced to avoid thread explosion.
5. **Main entry point is thin** — `main()` initializes HAL, spawns tasks, and blocks on a supervisor; it contains no hardware logic.

## HAL Module Structure (per component node)

Each node receives a generated HAL module:

```
generated/firmware/<project_id>/
├── hal/
│   ├── hal_i2c_bus_0.h / .c        # Shared bus abstraction
│   ├── hal_motor_driver_1.h / .c   # Per-node driver
│   └── hal_ina219_1.h / .c
├── tasks/
│   ├── task_motor_control.c          # T0 loop
│   ├── task_sensor_poll.c          # T1 loop
│   └── task_background.c           # T3 worker
├── main.c
└── platform/                       # Board-specific pin mappings
    └── board_config.h
```

HAL modules expose only semantic operations (`motor_set_speed`, `ina219_read_current_ma`). Tasks call HAL; HAL calls platform pin macros.

## Target Runtime Selection

| Target | T0 | T1 | T2 | T3 |
|--------|----|----|----|----|
| **FreeRTOS** (MCU bare-metal) | `xTaskCreate` priority 3+ | `xTaskCreate` priority 2 | Timer callback + mutex | `xTaskCreate` priority 1 |
| **pthreads** (Linux SBC) | `SCHED_FIFO` thread | `timerfd` + thread | `asyncio` or blocking thread + `pthread_mutex` | Detached low-priority thread |
| **Python asyncio** (prototyping) | `asyncio` not suitable for T0 → emit warning, use `threading` with real-time hints | `asyncio.create_task` with `loop.call_later` | Native async I/O | `asyncio.create_task` low priority |

The agent selects the runtime based on the board manifest. **v1 codegen targets Raspberry Pi 4 → pthreads + Linux I2C/GPIO.** RP2040/STM32 → FreeRTOS; other Linux SBCs → pthreads; development host → Python asyncio with threading fallback for T0.

## Anti-Patterns (Never Generated)

- Blocking `sleep()` inside a T0 loop.
- I2C/SPI transactions without acquiring the bus mutex.
- Direct `GPIOx->ODR = ...` in application or task code.
- Polling a sensor in the main loop when it belongs in T1/T2.
- Spawning unbounded threads (one thread per passive or one per net).

## Classification Algorithm (Pseudocode)

```
for each node in ProjectState.nodes:
    manifest = lookup(manifests, node.component_id)
    tier = CLASSIFICATION_TABLE[manifest.type]

    for each pin in manifest.pins connected in ProjectState.nets:
        tier = max(tier, PIN_TIER_RULES[pin.pin_type, pin.supported_features])

    if tier is MOTOR_DRIVER and node has PWM net:
        tier = T0

    scheduling_plan.add(node, tier)

group T1 nodes by shared I2C/SPI bus → merge into single poll task per bus
spawn one T0 task per T0 node
spawn one T3 background worker for all T3 nodes
emit HAL + task source files
```

This strategy ensures the Firmware Agent produces modular, concurrent firmware where sensitive hardware control is isolated and background work cannot starve real-time loops.
