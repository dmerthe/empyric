import time
import threading
from mercury.instruments import Henon
from mercury.experiment import Variable, Alarm, Experiment
from mercury.graphics import GUI, Plotter

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

plt.ion()

henon = Henon(address=1)

x = Variable('meter', instrument=henon, label='x')
y = Variable('meter', instrument=henon, label='y')

alarm = Alarm(y, '>0', None)

experiment = Experiment({'x':x,'y':y})

plots = {'Henon Plot': {'x': 'x', 'y':'y', 'style':'parametric', 'marker':'o'}}
gui = GUI(experiment, alarms={"Positive y Alarm": alarm}, title='Test', plots=plots)

def run_experiment():
    for state in experiment:
        print(state)

        if state['time'] >= 60:
            experiment.terminate()

        time.sleep(1)

experiment_thread = threading.Thread(target=run_experiment)
experiment_thread.start()

gui.run()
