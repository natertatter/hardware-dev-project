/** TypeScript mirrors of the backend Pydantic JSON schemas. */

export type ComponentType =
  | "MCU"
  | "SENSOR"
  | "MOTOR_DRIVER"
  | "ACTUATOR"
  | "PASSIVE";

export type PinType =
  | "POWER"
  | "GND"
  | "GPIO_IN"
  | "GPIO_OUT"
  | "I2C_SDA"
  | "I2C_SCL"
  | "SPI_MOSI"
  | "SPI_MISO"
  | "SPI_SCK"
  | "SPI_CS"
  | "UART_TX"
  | "UART_RX"
  | "ANALOG_IN";

export type ActiveState = "HIGH" | "LOW" | "NONE";

export type NetType = "POWER" | "GND" | "SIGNAL" | "BUS";

export interface PowerRequirements {
  min_operating_voltage: number;
  max_operating_voltage: number;
  logic_level_voltage: number;
  max_current_draw_ma: number;
}

export interface Pin {
  pin_id: string;
  pin_type: PinType;
  supported_features?: string[];
  max_current_source_ma?: number | null;
  internal_pullup_enabled?: boolean;
  active_state?: ActiveState;
}

export interface ComponentManifest {
  component_id: string;
  name: string;
  type: ComponentType;
  power_requirements: PowerRequirements;
  default_i2c_address?: string | null;
  pins: Pin[];
}

export interface ProjectStateNode {
  node_id: string;
  component_id: string;
  assigned_i2c_address?: string | null;
}

export interface NetConnection {
  node_id: string;
  pin_id: string;
}

export interface Net {
  net_id: string;
  net_type: NetType;
  connections: NetConnection[];
}

export interface ProjectState {
  project_id: string;
  nodes: ProjectStateNode[];
  nets: Net[];
}

/** Payload stored on each React Flow hardware node. */
export interface HardwareNodeData {
  manifest: ComponentManifest;
  assigned_i2c_address?: string | null;
  label?: string;
  [key: string]: unknown;
}
