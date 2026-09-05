"use client";

import { memo } from "react";
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";

import type { HardwareNodeData, Pin, PinType } from "@/types/schemas";

/**
 * Left side: input pins and power pins (POWER, GND, GPIO_IN, I2C/SPI/UART/ANALOG
 * inputs). Right side: output and signal pins (GPIO_OUT, SPI_MOSI/SCK/CS, UART_TX).
 *
 * This intentionally does not distinguish a POWER pin that sources voltage (e.g.
 * a regulated 3V3_OUT rail) from one that consumes it (e.g. VBUS) — per the
 * spec, all "Power" pins render on the left regardless of pin_id naming.
 */
const LEFT_PIN_TYPES: ReadonlySet<PinType> = new Set([
  "POWER",
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
  if (RIGHT_PIN_TYPES.has(pin.pin_type)) return false;
  if (LEFT_PIN_TYPES.has(pin.pin_type)) return true;
  return true;
}

/**
 * All handles are declared type="source", regardless of visual side.
 *
 * The React Flow docs for `ConnectionMode.Loose` are explicit: loose mode
 * allows source-to-source connections but "does not support target-to-target
 * connections" (https://reactflow.dev/api-reference/react-flow#connectionmode;
 * confirmed by xyflow maintainers in github.com/xyflow/xyflow/issues/5758).
 * Since our left-side pins (GND, POWER, I2C_SDA, I2C_SCL, ...) are exactly
 * the pins that need to wire to the SAME pin type on another node — GND to
 * GND, SDA to SDA — typing them "target" would make those connections
 * silently undraggable. Visual placement is controlled independently via the
 * `position` prop (Position.Left / Position.Right) passed to <Handle>, so
 * this does not affect the Task 2 requirement to render inputs/power on the
 * left and outputs/signals on the right.
 */
const HANDLE_TYPE = "source" as const;

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
          type={HANDLE_TYPE}
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
          type={HANDLE_TYPE}
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
