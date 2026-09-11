"""Tests for Raspberry Pi ↔ Arduino serial auto-wiring."""

from pathlib import Path

from eda_platform.agents.architect.template_layout import template_auto_wire
from eda_platform.schemas import ComponentManifest, Net, NetConnection, NetType, Node, ProjectState


def _load_manifest(name: str) -> ComponentManifest:
    path = Path(__file__).resolve().parents[2] / "hardware_library" / "manifests" / name
    return ComponentManifest.model_validate_json(path.read_text())


def test_uart_cross_wire_between_rpi4_and_arduino():
    manifests = {
        "mcu_rpi4": _load_manifest("mcu_rpi4.example.json"),
        "mcu_arduino_mega": _load_manifest("mcu_arduino_mega.example.json"),
    }
    project = ProjectState(
        project_id="pi_arduino_uart",
        nodes=[
            Node(node_id="pi_1", component_id="mcu_rpi4"),
            Node(
                node_id="arduino_1",
                component_id="mcu_arduino_mega",
                selected_protocol="UART",
            ),
        ],
        nets=[
            Net(
                net_id="placeholder",
                net_type=NetType.GND,
                connections=[NetConnection(node_id="pi_1", pin_id="GND")],
            )
        ],
    )

    updated, wires_added = template_auto_wire(project, manifests)
    assert wires_added >= 3
    net_ids = {n.net_id for n in updated.nets}
    assert any("uart_tx_rx" in nid for nid in net_ids)
    assert any("uart_rx_tx" in nid for nid in net_ids)

    tx_rx = next(n for n in updated.nets if "uart_tx_rx" in n.net_id)
    pins = {(c.node_id, c.pin_id) for c in tx_rx.connections}
    assert ("pi_1", "GPIO14_UART_TX") in pins
    assert ("arduino_1", "D0_RX") in pins


def test_usb_serial_link_between_rpi4_and_arduino():
    manifests = {
        "mcu_rpi4": _load_manifest("mcu_rpi4.example.json"),
        "mcu_arduino_mega": _load_manifest("mcu_arduino_mega.example.json"),
    }
    project = ProjectState(
        project_id="pi_arduino_usb",
        nodes=[
            Node(node_id="pi_1", component_id="mcu_rpi4", selected_protocol="USB_SERIAL"),
            Node(
                node_id="arduino_1",
                component_id="mcu_arduino_mega",
                selected_protocol="USB_SERIAL",
            ),
        ],
        nets=[
            Net(
                net_id="placeholder",
                net_type=NetType.GND,
                connections=[NetConnection(node_id="pi_1", pin_id="GND")],
            )
        ],
    )

    updated, wires_added = template_auto_wire(project, manifests)
    usb_net = next((n for n in updated.nets if "usb_serial" in n.net_id), None)
    assert usb_net is not None
    pins = {(c.node_id, c.pin_id) for c in usb_net.connections}
    assert ("pi_1", "USB_HOST") in pins
    assert ("arduino_1", "USB_DEVICE") in pins
