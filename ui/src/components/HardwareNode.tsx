"use client";

import { memo, useMemo } from "react";
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";

import { ProtocolSelector } from "@/components/ProtocolSelector";
import type { HardwareNodeData, Pin, PinType } from "@/types/schemas";
import {
  availableProtocols,
  defaultProtocol,
  pinsForProtocol,
} from "@/utils/protocolProfiles";

/**
 * Left side: input pins and power pins (POWER, GND, GPIO_IN, I2C/SPI/UART/ANALOG
 * inputs). Right side: output and signal pins (GPIO_OUT, SPI_MOSI/SCK/CS, UART_TX).
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

function HardwareNodeComponent({ id, data }: NodeProps<Node<HardwareNodeData>>) {
  const { manifest, selected_protocol } = data;
  const protocols = useMemo(() => availableProtocols(manifest), [manifest]);
  const activeProtocol =
    selected_protocol ?? defaultProtocol(manifest) ?? protocols[0] ?? null;
  const visiblePins = useMemo(
    () => pinsForProtocol(manifest, activeProtocol),
    [manifest, activeProtocol],
  );

  const leftPins = visiblePins.filter(isLeftSidePin);
  const rightPins = visiblePins.filter((p) => !isLeftSidePin(p));

  return (
    <div className="hardware-node">
      <header className="hardware-node__header">
        <span className="hardware-node__type">{manifest.type}</span>
        <strong className="hardware-node__name">{manifest.name}</strong>
        <span className="hardware-node__id">{manifest.component_id}</span>
      </header>

      <ProtocolSelector
        nodeId={id}
        selectedProtocol={activeProtocol}
        protocols={protocols}
      />

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
