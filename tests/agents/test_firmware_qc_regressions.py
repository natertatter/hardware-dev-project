"""Regression tests for the Phase 9 quality-control pass.

These exist to prove the fixes matter, not just that the code runs:
1. I2C bus membership must be detected by ``pin_type``, never by pin_id
   naming convention — a schematic using non-RP2040 pin names must still
   be scheduled correctly.
2. The public ``codegen`` package must actually expose what it advertises
   in ``__all__``.
3. Generated ``board_config.h`` must reflect the schematic's actual wired
   I2C pins via the platform pin map, not a hardcoded assumption.
"""

from eda_platform.agents.firmware_engineer import classify_nodes, plan_from_project
from eda_platform.agents.firmware_engineer.codegen.emitter import generate_source_files
from eda_platform.schemas import (
    ComponentManifest,
    ComponentType,
    Net,
    NetConnection,
    NetType,
    Node,
    Pin,
    PinType,
    PowerRequirements,
    ProjectState,
)


def _custom_mcu_manifest() -> ComponentManifest:
    """An MCU whose I2C pins are NOT named GPIO4/GPIO5/I2C_SDA/I2C_SCL.

    Regression target: the old scheduler detected I2C membership by
    matching literal pin_id strings, so this manifest would have produced
    an empty bus and no sensor-poll task despite being wired identically
    to the RP2040 mock.
    """
    return ComponentManifest(
        component_id="mcu_custom",
        name="Custom Board",
        type=ComponentType.MCU,
        power_requirements=PowerRequirements(
            min_operating_voltage=3.0,
            max_operating_voltage=3.6,
            logic_level_voltage=3.3,
            max_current_draw_ma=300.0,
        ),
        pins=[
            Pin(pin_id="PWR3V3", pin_type=PinType.POWER, max_current_source_ma=200.0),
            Pin(pin_id="GROUND", pin_type=PinType.GND),
            Pin(pin_id="BUS_DATA", pin_type=PinType.I2C_SDA, supported_features=["I2C"]),
            Pin(pin_id="BUS_CLOCK", pin_type=PinType.I2C_SCL, supported_features=["I2C"]),
        ],
    )


def _custom_sensor_manifest() -> ComponentManifest:
    return ComponentManifest(
        component_id="sens_custom",
        name="Custom Sensor",
        type=ComponentType.SENSOR,
        power_requirements=PowerRequirements(
            min_operating_voltage=3.0,
            max_operating_voltage=3.6,
            logic_level_voltage=3.3,
            max_current_draw_ma=2.0,
        ),
        default_i2c_address="0x44",
        pins=[
            Pin(pin_id="VDD", pin_type=PinType.POWER),
            Pin(pin_id="VSS", pin_type=PinType.GND),
            Pin(pin_id="SDA_LINE", pin_type=PinType.I2C_SDA),
            Pin(pin_id="SCL_LINE", pin_type=PinType.I2C_SCL),
        ],
    )


def _custom_project() -> ProjectState:
    return ProjectState(
        project_id="custom_pin_names",
        nodes=[
            Node(node_id="mcu_1", component_id="mcu_custom"),
            Node(node_id="sensor_1", component_id="sens_custom", assigned_i2c_address="0x44"),
        ],
        nets=[
            Net(
                net_id="net_vcc",
                net_type=NetType.POWER,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="PWR3V3"),
                    NetConnection(node_id="sensor_1", pin_id="VDD"),
                ],
            ),
            Net(
                net_id="net_gnd",
                net_type=NetType.GND,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="GROUND"),
                    NetConnection(node_id="sensor_1", pin_id="VSS"),
                ],
            ),
            Net(
                net_id="net_sda",
                net_type=NetType.BUS,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="BUS_DATA"),
                    NetConnection(node_id="sensor_1", pin_id="SDA_LINE"),
                ],
            ),
            Net(
                net_id="net_scl",
                net_type=NetType.BUS,
                connections=[
                    NetConnection(node_id="mcu_1", pin_id="BUS_CLOCK"),
                    NetConnection(node_id="sensor_1", pin_id="SCL_LINE"),
                ],
            ),
        ],
    )


def _custom_manifests() -> dict[str, ComponentManifest]:
    mcu = _custom_mcu_manifest()
    sensor = _custom_sensor_manifest()
    return {mcu.component_id: mcu, sensor.component_id: sensor}


class TestI2CDetectionIsPinTypeDriven:
    def test_non_conventional_pin_names_still_detected_as_i2c_bus(self):
        project = _custom_project()
        manifests = _custom_manifests()

        plan = plan_from_project(project, manifests)

        assert len(plan.bus_locks) == 1, (
            "bus should be detected via pin_type even though pin_ids don't "
            "match the RP2040 naming convention (BUS_DATA/BUS_CLOCK, not "
            "I2C_SDA/I2C_SCL/GPIO4/GPIO5)"
        )
        assert plan.bus_locks[0].nodes == ["sensor_1"]

        poll_task = next(t for t in plan.tasks if t.task_id == "task_sensor_poll")
        assert "sensor_1" in poll_task.nodes

    def test_mcu_excluded_by_type_not_by_component_id_prefix(self):
        """MCU exclusion must use ComponentType.MCU, not a 'mcu_' prefix guess."""
        project = _custom_project()
        # Rename the MCU's component_id so it no longer starts with "mcu_".
        renamed_mcu = _custom_mcu_manifest().model_copy(
            update={"component_id": "board_custom"}
        )
        manifests = {
            "board_custom": renamed_mcu,
            "sens_custom": _custom_sensor_manifest(),
        }
        project = ProjectState(
            project_id=project.project_id,
            nodes=[
                Node(node_id="mcu_1", component_id="board_custom"),
                *[n for n in project.nodes if n.node_id != "mcu_1"],
            ],
            nets=project.nets,
        )

        plan = plan_from_project(project, manifests)

        assert plan.bus_locks[0].nodes == ["sensor_1"], (
            "the renamed MCU (component_id no longer prefixed 'mcu_') must "
            "still be excluded from bus membership because its manifest "
            "type is MCU"
        )


class TestBoardConfigReflectsActualWiring:
    def test_board_config_uses_wired_pin_map_not_hardcoded_default(self):
        """GPIO12/GPIO13 aren't the I2C pins, but they ARE in the pin map —
        proves board_config_h resolves through pin_map for whatever pins
        are actually wired, rather than assuming GPIO4/GPIO5 unconditionally.
        """
        mcu = _custom_mcu_manifest().model_copy(
            update={
                "pins": [
                    Pin(pin_id="PWR3V3", pin_type=PinType.POWER, max_current_source_ma=200.0),
                    Pin(pin_id="GROUND", pin_type=PinType.GND),
                    Pin(pin_id="GPIO12", pin_type=PinType.I2C_SDA, supported_features=["I2C"]),
                    Pin(pin_id="GPIO13", pin_type=PinType.I2C_SCL, supported_features=["I2C"]),
                ]
            }
        )
        manifests = {"mcu_custom": mcu, "sens_custom": _custom_sensor_manifest()}
        project = ProjectState(
            project_id="alt_pins",
            nodes=[
                Node(node_id="mcu_1", component_id="mcu_custom"),
                Node(node_id="sensor_1", component_id="sens_custom"),
            ],
            nets=[
                Net(
                    net_id="net_sda",
                    net_type=NetType.BUS,
                    connections=[
                        NetConnection(node_id="mcu_1", pin_id="GPIO12"),
                        NetConnection(node_id="sensor_1", pin_id="SDA_LINE"),
                    ],
                ),
                Net(
                    net_id="net_scl",
                    net_type=NetType.BUS,
                    connections=[
                        NetConnection(node_id="mcu_1", pin_id="GPIO13"),
                        NetConnection(node_id="sensor_1", pin_id="SCL_LINE"),
                    ],
                ),
            ],
        )
        classify_nodes(project, manifests)  # sanity: classification doesn't blow up
        plan = plan_from_project(project, manifests)
        files = generate_source_files(project, manifests, plan)

        board_config = files["platform/board_config.h"]
        assert "PIN_I2C_SDA_BCM 12" in board_config
        assert "PIN_I2C_SCL_BCM 13" in board_config


class TestCodegenPackageExportsWork:
    def test_generate_source_files_importable_from_package(self):
        """__all__ in codegen/__init__.py must match what's actually importable."""
        from eda_platform.agents.firmware_engineer.codegen import generate_source_files as gsf

        assert callable(gsf)


class TestHalInitDoesNotSetSpuriousSlaveAddress:
    def test_init_only_opens_device(self):
        from eda_platform.agents.firmware_engineer.codegen.templates import hal_i2c_bus_0_c

        source = hal_i2c_bus_0_c()
        init_block = source.split("hal_i2c_bus_0_init(void)")[1].split("}")[0]
        assert "I2C_SLAVE" not in init_block, (
            "init() should not set a slave address — every real transaction "
            "already calls set_slave(addr) with the correct target address"
        )
