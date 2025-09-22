# Basic script that measures x and y values in a Henon Map, using the empyric library

import time
import os
import sys
import threading
from empyric.instruments import HenonMapper
from empyric.experiment import Alarm, Experiment
from empyric.variables import Meter
from empyric.graphics import TkGUI

import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt

plt.ion()

if sys.platform == "win32":
    directory = os.path.join(
        os.environ["USERPROFILE"], "Desktop"
    )  # put example data on desktop
else:
    directory = os.path.join(os.environ["HOME"], "Desktop")

os.chdir(directory)

henon_mapper = HenonMapper()

x = Meter(instrument=henon_mapper, meter="x")
y = Meter(instrument=henon_mapper, meter="y")

alarm = Alarm("y > 0", definitions={"y": y})

experiment = Experiment(
    {"x": x, "y": y}
)  # an experiment that simply measures the values of x and y over time

plots = {
    "Henon Plot": {
        "x": "x",
        "y": "y",
        "style": "parametric",
        "configure": {"marker": "o", "linestyle": "None", "markersize": 3},
    }
}
gui = TkGUI(
    experiment, alarms={"y>0": alarm}, title="Henon Map Example", plots=plots
)


def run_experiment():
    for state in experiment:
        print(state)

        if state["Time"] >= 60:
            experiment.terminate()

        time.sleep(1)


experiment_thread = threading.Thread(
    target=run_experiment
)  # run experiment loop in a separate thread
experiment_thread.start()

gui.run()
