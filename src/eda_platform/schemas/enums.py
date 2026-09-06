"""Shared enumerations for EDA platform JSON schemas."""

from enum import Enum


class ComponentType(str, Enum):
    MCU = "MCU"
    SENSOR = "SENSOR"
    MOTOR_DRIVER = "MOTOR_DRIVER"
    ACTUATOR = "ACTUATOR"
    PASSIVE = "PASSIVE"


class PinType(str, Enum):
    POWER = "POWER"
    GND = "GND"
    GPIO_IN = "GPIO_IN"
    GPIO_OUT = "GPIO_OUT"
    I2C_SDA = "I2C_SDA"
    I2C_SCL = "I2C_SCL"
    SPI_MOSI = "SPI_MOSI"
    SPI_MISO = "SPI_MISO"
    SPI_SCK = "SPI_SCK"
    SPI_CS = "SPI_CS"
    UART_TX = "UART_TX"
    UART_RX = "UART_RX"
    ANALOG_IN = "ANALOG_IN"


class ActiveState(str, Enum):
    HIGH = "HIGH"
    LOW = "LOW"
    NONE = "NONE"


class NetType(str, Enum):
    POWER = "POWER"
    GND = "GND"
    SIGNAL = "SIGNAL"
    BUS = "BUS"
