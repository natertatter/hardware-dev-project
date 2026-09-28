"""Firmware pin-map aliases for canvas MCU pins → Pi 4 BCM."""

from eda_platform.agents.firmware_engineer.pin_map import bcm_for_logical_pin


def test_rp2040_spi_logical_pins_map_to_pi_spi0():
    assert bcm_for_logical_pin("GPIO18") == 10
    assert bcm_for_logical_pin("GPIO19") == 9
    assert bcm_for_logical_pin("GPIO20") == 11
    assert bcm_for_logical_pin("GPIO17") == 8


def test_rpi4_spi_header_names_map_to_same_bcm():
    assert bcm_for_logical_pin("GPIO10_SPI_MOSI") == 10
    assert bcm_for_logical_pin("GPIO9_SPI_MISO") == 9
    assert bcm_for_logical_pin("GPIO11_SPI_SCK") == 11
    assert bcm_for_logical_pin("GPIO8_SPI_CE0") == 8
    assert bcm_for_logical_pin("GPIO7_SPI_CE1") == 7
