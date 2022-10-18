# Tests for adapters

import sys
import importlib


def test_serial():

    Serial = importlib.import_module('empyric.adapters').Serial

    assert Serial.lib is not None
