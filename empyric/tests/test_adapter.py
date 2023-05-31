# Tests for adapters

import sys
import importlib


def test_serial():
    Serial = importlib.import_module("empyric.adapters").Serial

    assert Serial.lib is not None


def test_gpib():
    GPIB = importlib.import_module("empyric.adapters").GPIB

    assert GPIB.lib is not None


def test_usb():
    USB = importlib.import_module("empyric.adapters").USB

    assert USB.lib is not None


def test_modbus():
    Modbus = importlib.import_module("empyric.adapters").Modbus

    assert Modbus.lib is not None


def test_phidget():
    Phidget = importlib.import_module("empyric.adapters").Phidget

    assert Phidget.lib is not None
