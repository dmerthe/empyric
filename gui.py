import matplotlib
matplotlib.use('TkAgg')

import numbers
import os
import time
import warnings
import numpy as np
import pandas as pd
import tkinter as tk
import matplotlib.pyplot as plt
from tkinter.filedialog import askopenfilename, askopenfile
from ruamel.yaml import YAML

from mercury.elements import yaml, get_timestamp, timestamp_path, Experiment

class ExperimentController():

    def __init__(self, runcard_path=None):

        # Start tkinter master frame
        self.root = tk.Tk()
        self.root.withdraw()

        # Pull in the runcard
        if runcard_path is None:
            runcard_path = askopenfilename(title='Select Experiment Runcard')

        os.chdir(os.path.dirname(runcard_path))

        with open(self.runcard_path, 'rb') as runcard:
            self.runcard = yaml.load(runcard)

        self.settings = self.runcard['Settings']

        self.run(self.runcard)

    def run(self, runcard, repeat=False):

        self.experiment = Experiment(runcard)

        # Save executed runcard for record keeping
        if not repeat:
            name = self.experiment.description.get('name', 'experiment')
            with open(timestamp_path(name + '_runcard.yaml'), 'w') as runcard_file:
                yaml.dump(self.runcard, runcard_file)

        self.status_gui = StatusGUI(self.root, self.experiment)
        self.plotter = Plotter(self.experiment.plotting)

        for step in self.experiment:
            self.status_gui.update(step)
            self.plotter.plot(self.experiment.data)

        followup = self.experiment.followup

        if len(followup) == 0:
            self.status_gui.quit()
        elif followup[0].lower() == 'repeat':
            self.run(runcard_path, repeat=True)
        else:
            for task in followup:
                self.run(task)


class BasicDialog(tk.Toplevel):
    """
    General purpose dialog window

    """

    def __init__(self, parent, title = None):

        tk.Toplevel.__init__(self, parent)
        self.transient(parent)

        if title:
            self.title(title)

        self.parent = parent

        self.result = None

        body = tk.Frame(self)
        self.initial_focus = self.body(body)
        body.pack(padx=5, pady=5)

        self.buttonbox()

        self.grab_set()

        if not self.initial_focus:
            self.initial_focus = self

        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.geometry("+%d+%d" % (parent.winfo_rootx()+50,
                                  parent.winfo_rooty()+50))

        self.initial_focus.focus_set()

        self.wait_window(self)

    # construction hooks

    def body(self, master):
        # create dialog body.  return widget that should have
        # initial focus.  this method should be overridden

        pass

    def buttonbox(self):
        # add standard button box. override if you don't want the
        # standard buttons

        box = tk.Frame(self)

        w = tk.Button(box, text="Apply", width=10, command=self.apply)
        w.pack(side=tk.LEFT, padx=5, pady=5)
        w = tk.Button(box, text="OK", width=10, command=self.ok, default=tk.ACTIVE)
        w.pack(side=tk.LEFT, padx=5, pady=5)
        w = tk.Button(box, text="Cancel", width=10, command=self.cancel)
        w.pack(side=tk.LEFT, padx=5, pady=5)

        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)

        box.pack()

    # standard button semantics

    def ok(self, event=None):

        if not self.validate():
            self.initial_focus.focus_set() # put focus back
            return

        self.withdraw()
        self.update_idletasks()

        self.apply()

        self.cancel()

    def cancel(self, event=None):

        # put focus back to the parent window
        self.parent.focus_set()
        self.destroy()

    # command hooks

    def validate(self):

        return 1 # override

    def apply(self):

        pass # override


class StatusGUI():
    """
    GUI showing experimental progress and values of all experiment variables, allowing the user to stop or pause the experiment.
    """

    def __init__(self, parent, experiment):

        self.experiment_name = experiment.description['name']
        self.variables = experiment.instrument.mapped_variables

        self.root = tk.Toplevel(self.parent)
        self.root.title('Experiment: ' + experiment_name)

        tk.Label(self.root, text='Status:').grid(row=0, column=0, sticky=tk.E)

        self.status_label = tk.Label(self.root, text='Getting started...', width=40, relief=tk.SUNKEN)
        self.status_label.grid(row=0, column=1, columnspan=2, sticky=tk.W)

        tk.Label(self.root, text='', font=("Arial", 14, 'bold')).grid(row=1, column=0, sticky=tk.E)

        self.variable_status_labels = {}

        i = 1
        for variable in self.variables:
            tk.Label(self.root, text=variable, width=20, anchor=tk.E).grid(row=i, column=0, sticky=tk.E)
            self.variable_status_labels[variable] = tk.Label(self.root, text='', relief=tk.SUNKEN, width=40)
            self.variable_status_labels[variable].grid(row=i, column=1, columnspan=2, sticky=tk.W)

            i += 1

        tk.Label(self.root, text='', font=("Arial", 14, 'bold')).grid(row=i, column=0, sticky=tk.E)

        self.config_button = tk.Button(self.root, text='Check', font=("Arial", 14, 'bold'), command=self.check_instr,
                                       width=10, state=tk.DISABLED)
        self.config_button.grid(row=i + 1, column=0)

        self.pause_button = tk.Button(self.root, text='Pause', font=("Arial", 14, 'bold'), command=self.toggle_pause,
                                      width=10)
        self.pause_button.grid(row=i + 1, column=1)

        self.stop_button = tk.Button(self.root, text='Stop', font=("Arial", 14, 'bold'), command=self.user_stop,
                                     width=10)
        self.stop_button.grid(row=i + 1, column=2)

    def update(self, state=None, status=None):

        if state:
            for name, label in self.variable_status_labels.items():
                label.config(text=str(state[name]))

        if status:
            self.status_label.config(text=status)
        else:
            self.status_label.config(text='Running')

        self.root.update()

    def check_instr(self):
        pass

    def toggle_puase(self):
        pass

    def user_stop(self):
        pass

    def quit(self):

        self.update(status='Finished with no follow-up. Closing...')
        self.root.update()
        time.sleep(1)
        self.root.destroy()


class PlotError(BaseException):
    pass


class Plotter():
    """
    Handler for plotting data based on the runcard plotting settings and data context
    """

    def __init__(self, settings):

        n_cols = len(settings)

        self.settings = settings
        self.plots = {}

        for plot_name in settings:
            self.plots[plot_name] = plt.subplots()

    def plot(self, data):
        """
        Plot the specified data

        :param data: (DataFrame) data from which to make the plot, based on settings
        :return:
        """

        for name, plot in self.plots.items:

            fig, ax = plot
            settings = self.settings[name]
            x = settings['x']
            y = np.array([settings['y']]).flatten()
            s  = settings.get('parameter', 'Time')  # parameter
            xlabel = settings.get('xlabel', x)
            ylabel = settings.get('ylabel', y[0])
            plt_kwargs = settings['options']

            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            ax.set_title(name)

            y_data = data[y]

            y_is_numeric = np.prod([isinstance(value, numbers.Number) for value in y_data.iloc[-1]].values)
            y_is_file = os.path.exists(str(y_data[y[0]].values[-1]))

            if not y_is_numeric and not y_is_file:
                raise TypeError('Y data must either be all numeric OR all path names pointing to data files')

            if y_is_file:

                if len(y) > 1:
                    raise PlotError('Only one x-y pair can be plotted in each plot showing a dependence on a third parameter!')

                data_file = y_data[y[0]].values[-1]

                file_data = pd.read_csv(data_file)

                if s == 'Time':
                    file_data[s] = file_data.index
                else:

                    file_indices = file_data.index  # timestamps for the referenced data file
                    data_indices = data.index  # timestamps for the main data file, slightly different from the file indices

                    unique_file_indices = np.unique(file_indices).sort()

                    index_map = {file_index: data_index for file_index, data_index in zip(file_indices, data_indices)}

                    for index in file_indices:
                        file_data[s][index] = data[s][index_map[index]]

                file_data.plot(x=x, y=y[0], ax=ax, kind='scatter',
                               s=10, c=s, colormap='viridis')

            elif x == 'Time':  # Plot some regular numbers versus time
                y_data.plot(ax=ax,**plt_kwargs)
            else:  # Plot some regular numbers versus some other numbers
                y_data.plot(x=x, ax=ax, **plt_kwargs)

            plt.pause(0.1)


class InstrumentConfigGUI():
    """
    Once the instruments are selected, this window allows the user to configure and test instruments before setting up an experiment
    """

    def __init__(self, parent, instruments):

        self.finished = False

        self.parent = parent

        self.root = tk.Toplevel(self.parent)
        self.root.title('Instrument Config/Test')

        self.instruments = instruments

        tk.Label(self.root, text='Instruments:', font=('Arial', 14), justify=tk.LEFT).grid(row=0, column=0, sticky=tk.W)

        i = 1

        self.instrument_labels = {}
        self.config_buttons = {}

        for name, instrument in instruments.items():

            instrument_label = tk.Label(self.root, text=name)
            instrument_label.grid(row=i, column=0)

            self.instrument_labels[name] = instrument_label

            config_button = tk.Button(self.root, text = 'Config/Test', command = lambda instr = instrument: self.config(instr))
            config_button.grid(row=i,column=1)

            self.config_buttons[name] = config_button

            i+=1

        self.ok_button = tk.Button(self.root, text='OK', font=('Arial', 14), command=self.okay, width=20)
        self.ok_button.grid(row=i, column=0, columnspan=2)

        while not self.finished:
            self.update()
            time.sleep(0.05)

        self.root.destroy()
        self.parent.focus_set()

    def update(self):

        if not self.finished:
            self.root.update()

    def okay(self):

        self.finished = True

    def config(self, instrument):

        dialog = ConfigTestDialog(self.root, instrument, title='Config/Test: '+instrument.name)


class ConfigTestDialog(BasicDialog):
    """
    Dialog box for setting knobs and checking meters.
    Allows the user to quickly access basic instrument functionality as well as configure instrument for an experiment

    """

    def __init__(self, parent, instrument, title=None):

        self.instrument = instrument

        BasicDialog.__init__(self, parent, title=title)

    def apply_knob_entry(self, knob):
        value = self.knob_entries[knob].get()
        try:
            self.instrument.set(knob, float(value))
        except ValueError:
            self.instrument.set(knob, value)

    def update_meter_entry(self, meter):
        value = str(self.instrument.measure(meter))
        self.meter_entries[meter].config(state=tk.NORMAL)
        self.meter_entries[meter].delete(0, tk.END)
        self.meter_entries[meter].insert(0, value)
        self.meter_entries[meter].config(state='readonly')

    def body(self, master):

        tk.Label(master, text = 'Instrument Name:').grid(row=0, column=0, sticky=tk.E)

        self.name_entry = tk.Entry(master, state="readonly")
        self.name_entry.grid(row=0, column = 1,sticky=tk.W)
        self.name_entry.insert(0, self.instrument.name)

        knobs = self.instrument.knobs
        knob_values = self.instrument.knob_values
        self.knob_entries = {}

        meters = self.instrument.meters
        self.meter_entries = {}

        label = tk.Label(master, text='Knobs', font = ("Arial", 14, 'bold'))
        label.grid(row=1, column=0, sticky=tk.W)

        label = tk.Label(master, text='Meters', font = ("Arial", 14, 'bold'))
        label.grid(row=1, column=3, sticky=tk.W)

        self.set_buttons = {}
        i = 2
        for knob in knobs:

            formatted_name = ' '.join([word[0].upper()+word[1:] for word in knob.split(' ')])

            label = tk.Label(master, text = formatted_name)
            label.grid(row = i, column = 0, sticky=tk.W)

            self.knob_entries[knob] = tk.Entry(master)
            self.knob_entries[knob].grid(row = i, column = 1)
            self.knob_entries[knob].insert(0, str(knob_values[knob]))

            self.set_buttons[knob] = tk.Button(master, text='Set', command = lambda knob = knob : self.apply_knob_entry(knob))
            self.set_buttons[knob].grid(row=i, column=2)

            i += 1

        self.measure_buttons = {}
        i = 2
        for meter in meters:

            formatted_name = ' '.join([word[0].upper() + word[1:] for word in meter.split(' ')])

            label = tk.Label(master, text=formatted_name)
            label.grid(row=i, column=3, sticky=tk.W)

            self.meter_entries[meter] = tk.Entry(master)
            self.meter_entries[meter].grid(row=i, column=4)
            self.meter_entries[meter].insert(0, '???')
            self.meter_entries[meter].config(state='readonly')

            self.measure_buttons[meter] =  tk.Button(master, text='Measure', command = lambda meter = meter: self.update_meter_entry(meter))
            self.measure_buttons[meter].grid(row=i, column=5)

            i += 1

    def apply(self):

        for knob in self.instrument.knobs:
            self.apply_knob_entry(knob)
