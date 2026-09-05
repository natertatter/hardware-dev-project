"use client";

import { memo } from "react";
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";

import type { HardwareNodeData, Pin, PinType } from "@/types/schemas";

/** POWER pins that source voltage onto a net (rendered on the right). */
const OUTPUT_POWER_PIN_IDS = new Set(["3V3_OUT", "3V3", "5V_OUT", "5V"]);

const LEFT_PIN_TYPES: ReadonlySet<PinType> = new Set([
  "GND",
  "GPIO_IN",
  "I2C_SDA",
  "I2C_SCL",
  "SPI_MISO",
  "UART_RX",
  "ANALOG_IN",
]);

const RIGHT_PIN_TYPES: ReadonlySet<PinType> = new Set([
  "GPIO_OUT",
  "SPI_MOSI",
  "SPI_SCK",
  "SPI_CS",
  "UART_TX",
]);

function isLeftSidePin(pin: Pin): boolean {
  if (pin.pin_type === "POWER") {
    return !OUTPUT_POWER_PIN_IDS.has(pin.pin_id);
  }
  if (LEFT_PIN_TYPES.has(pin.pin_type)) return true;
  if (RIGHT_PIN_TYPES.has(pin.pin_type)) return false;
  return true;
}

function pinHandleType(pin: Pin): "source" | "target" {
  return isLeftSidePin(pin) ? "target" : "source";
}

function PinRow({
  pin,
  side,
  index,
  total,
}: {
  pin: Pin;
  side: "left" | "right";
  index: number;
  total: number;
}) {
  const topPct = ((index + 1) / (total + 1)) * 100;

  return (
    <div
      className={`hardware-node__pin hardware-node__pin--${side}`}
      style={{ top: `${topPct}%` }}
    >
      {side === "left" && (
        <Handle
          type={pinHandleType(pin)}
          position={Position.Left}
          id={pin.pin_id}
          className="hardware-node__handle"
        />
      )}
      <span className="hardware-node__pin-label">
        <span className="hardware-node__pin-id">{pin.pin_id}</span>
        <span className="hardware-node__pin-type">{pin.pin_type}</span>
      </span>
      {side === "right" && (
        <Handle
          type={pinHandleType(pin)}
          position={Position.Right}
          id={pin.pin_id}
          className="hardware-node__handle"
        />
      )}
    </div>
  );
}

function HardwareNodeComponent({
  data,
}: NodeProps<Node<HardwareNodeData>>) {
  const { manifest } = data;
  const leftPins = manifest.pins.filter(isLeftSidePin);
  const rightPins = manifest.pins.filter((p) => !isLeftSidePin(p));

  return (
    <div className="hardware-node">
      <header className="hardware-node__header">
        <span className="hardware-node__type">{manifest.type}</span>
        <strong className="hardware-node__name">{manifest.name}</strong>
        <span className="hardware-node__id">{manifest.component_id}</span>
      </header>

      <div className="hardware-node__body">
        <div className="hardware-node__column hardware-node__column--left">
          {leftPins.map((pin, i) => (
            <PinRow
              key={pin.pin_id}
              pin={pin}
              side="left"
              index={i}
              total={leftPins.length}
            />
          ))}
        </div>
        <div className="hardware-node__column hardware-node__column--right">
          {rightPins.map((pin, i) => (
            <PinRow
              key={pin.pin_id}
              pin={pin}
              side="right"
              index={i}
              total={rightPins.length}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export const HardwareNode = memo(HardwareNodeComponent);
