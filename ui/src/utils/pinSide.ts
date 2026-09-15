import type { ComponentManifest, Pin, PinType } from "@/types/schemas";

const BUS_PIN_TYPES: ReadonlySet<PinType> = new Set([
  "I2C_SDA",
  "I2C_SCL",
  "SPI_MOSI",
  "SPI_MISO",
  "SPI_SCK",
  "SPI_CS",
  "UART_TX",
  "UART_RX",
]);

/**
 * MCU host pins sit on the right (React Flow source). Peripherals accept on the
 * left (target) so auto-wire nets (MCU → device) can render.
 */
export function pinSide(manifest: ComponentManifest, pin: Pin): "left" | "right" {
  const pt = pin.pin_type;
  if (manifest.type === "MCU") {
    if (pt === "POWER" && (pin.max_current_source_ma ?? 0) > 0) return "right";
    if (pt === "GND") return "right";
    if (BUS_PIN_TYPES.has(pt) || pt === "GPIO_OUT") return "right";
    return "left";
  }
  if (pt === "POWER" || pt === "GND") return "left";
  if (BUS_PIN_TYPES.has(pt)) return "left";
  if (pt === "GPIO_OUT") return "right";
  return "left";
}
