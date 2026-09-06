import type { ComponentManifest } from "@/types/schemas";

/** Mock component catalog — mirrors tests/data/mock_data.py fixtures. */
export const COMPONENT_CATALOG: ComponentManifest[] = [
  {
    component_id: "mcu_rp2040",
    name: "Raspberry Pi Pico (RP2040)",
    type: "MCU",
    power_requirements: {
      min_operating_voltage: 1.8,
      max_operating_voltage: 5.5,
      logic_level_voltage: 3.3,
      max_current_draw_ma: 500.0,
    },
    pins: [
      {
        pin_id: "VBUS",
        pin_type: "POWER",
        supported_features: [],
        internal_pullup_enabled: false,
        active_state: "NONE",
      },
      {
        pin_id: "3V3_OUT",
        pin_type: "POWER",
        supported_features: [],
        max_current_source_ma: 300.0,
        internal_pullup_enabled: false,
        active_state: "NONE",
      },
      { pin_id: "GND", pin_type: "GND" },
      {
        pin_id: "GPIO4",
        pin_type: "I2C_SDA",
        supported_features: ["I2C"],
        max_current_source_ma: 12.0,
        internal_pullup_enabled: false,
        active_state: "NONE",
      },
      {
        pin_id: "GPIO5",
        pin_type: "I2C_SCL",
        supported_features: ["I2C"],
        max_current_source_ma: 12.0,
        internal_pullup_enabled: false,
        active_state: "NONE",
      },
      {
        pin_id: "GPIO12",
        pin_type: "GPIO_OUT",
        supported_features: ["PWM"],
        max_current_source_ma: 12.0,
        internal_pullup_enabled: false,
        active_state: "NONE",
      },
      {
        pin_id: "GPIO13",
        pin_type: "GPIO_IN",
        supported_features: [],
        internal_pullup_enabled: true,
        active_state: "NONE",
      },
    ],
  },
  {
    component_id: "sens_ina219",
    name: "INA219 Current/Power Monitor",
    type: "SENSOR",
    power_requirements: {
      min_operating_voltage: 3.0,
      max_operating_voltage: 5.5,
      logic_level_voltage: 3.3,
      max_current_draw_ma: 1.0,
    },
    default_i2c_address: "0x40",
    pins: [
      { pin_id: "VCC", pin_type: "POWER" },
      { pin_id: "GND", pin_type: "GND" },
      {
        pin_id: "I2C_SDA",
        pin_type: "I2C_SDA",
        supported_features: ["I2C"],
      },
      {
        pin_id: "I2C_SCL",
        pin_type: "I2C_SCL",
        supported_features: ["I2C"],
      },
    ],
  },
];

export function catalogById(): Record<string, ComponentManifest> {
  return Object.fromEntries(
    COMPONENT_CATALOG.map((m) => [m.component_id, m])
  );
}
