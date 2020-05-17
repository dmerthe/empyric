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

from mercury.elements import yaml, timestamp_path, Experiment
from mercury.util_funcs import convert_time

class ExperimentController():

    def __init__(self, runcard_path=None):

        # Start tkinter master frame
        self.root = tk.Tk()
        self.root.withdraw()

        # Pull in the runcard
        if runcard_path is None:
            runcard_path = askopenfilename(title='Select Experiment Runcard')

        os.chdir(os.path.dirname(runcard_path))

        with open(runcard_path, 'rb') as runcard:
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
        self.plotter = Plotter(self.experiment.data, self.experiment.plotting,
                               interval = convert_time(self.settings['plot interval']))
        for state in self.experiment:

            self.status_gui.update(state, status=f'Running: {state.name}')
            self.plotter.plot(save=True)

            # Stop the schedule clock and stop iterating if the user pauses the experiment
            if self.status_gui.paused:
                self.experiment.schedule.clock.stop()
                while self.status_gui.paused:
                    self.status_gui.update(state)
                    plt.pause(0.01)
                self.experiment.schedule.clock.resume()

        followup = self.experiment.followup

        if len(followup) == 0:
            self.status_gui.quit()
        elif followup[0].lower() == 'repeat':
            self.run(runcard_path, repeat=True)
        else:
            for task in followup:
                self.run(task)


class StatusGUI():
    """
    GUI showing experimental progress and values of all experiment variables, allowing the user to stop or pause the experiment.
    """

    def __init__(self, parent, experiment):

        self.parent = parent
        self.experiment = experiment

        self.paused = False

        self.variables = experiment.instruments.mapped_variables

        self.root = tk.Toplevel(self.parent)
        self.root.title('Experiment: ' + self.experiment.description['name'])

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

        if state is not None:
            for name, label in self.variable_status_labels.items():
                label.config(text=str(state[name]))

        if status:
            self.status_label.config(text=status)
        else:
            if self.paused:
                self.status_label.config(text='Paused by user')
            else:
                self.status_label.config(text='Running')

        self.root.update()

    def check_instr(self):
        instrument_gui = InstrumentConfigGUI(self.root, self.instruments, runcard_warning=True)

    def toggle_pause(self):

        self.paused = not self.paused

        if self.paused:
            self.update(status='Paused by user')
            self.pause_button.config(text='Resume')
            self.config_button.config(state=tk.NORMAL)
        else:
            self.update(status='Resumed by user')
            self.pause_button.config(text='Pause')
            self.config_button.config(state=tk.DISABLED)

    def user_stop(self):
        self.update(status='Stopped by User')
        self.experiment.status = 'Finished'  # tells the experiment to stop iterating

    def quit(self, message=None):
        self.update(status='Finished with no follow-up. Closing...')
        self.root.update()
        time.sleep(1)
        self.root.destroy()
        self.parent.focus_set()


class PlotError(BaseException):
    pass


class Plotter():
    """
    Handler for plotting data based on the runcard plotting settings and data context
    """

    def __init__(self, data, settings, interval=None):
        """
        PLot data based on settings

        :param data: (DataFrame) Dataframe containing the data to be plotted.
        :param settings: (dict) dictionary of plot settings
        """

        self.data = data
        self.settings = settings

        self.last_plot = -np.inf

        if interval is None:
            self.interval = 0
        else:
            self.interval = interval

        self.plots = {}
        for plot_name in settings:
            self.plots[plot_name] = plt.subplots()

    def plot(self, plot_now=False, save=False):

        # Only plot if sufficient time has passed since the last plot generation
        now = time.time()
        if now < self.last_plot + self.interval or plot_now:
            return

        self.last_plot = now

        # Make the plots, by name and style
        for name, settings in self.settings.items():

            style = settings['style'].lower()

            if style == 'none' or style == 'all':
                self._plot_all(name)
            elif style == 'averaged':
                self._plot_averaged(name)
            elif style == 'errorbars':
                self._plot_errorbars(name)
            elif style == 'parametric':
                self._plot_parametric(name)
            elif style == 'order':
                self._plot_order(name)
            else:
                raise PlotError(f"Plotting style '{style}' not recognized!")

        if save:
            self.save()

    def save(self):

        for name, plot in self.plots.items():
            fig, ax = plot
            fig.savefig('plot-'+name+'.png')

    def _plot_all(self, name):

        fig, ax = self.plots[name]
        ax.clear()

        x = self.settings[name]['x']
        y = self.settings[name]['y']

        plt_kwargs = self.settings[name]['options']

        self.data.plot(y=y,x=x, ax=ax, kind='line', **plt_kwargs)

        return fig, ax

    def _plot_averaged(self, name):

        fig, ax = self.plots[name]
        ax.clear()

        x = self.settings[name]['x']
        y = self.settings[name]['y']

        plt_kwargs = self.settings[name]['options']

        averaged_data = self.data.groupby(x).mean()

        averaged_data.plot(y=y, ax=ax, kind='line', **plt_kwargs)

        return fig, ax

    def _plot_errorbars(self, name):

        fig, ax = self.plots[name]
        ax.clear()

        x = self.settings[name]['x']
        y = self.settings[name]['y']

        plt_kwargs = self.settings[name]['options']

        self.data.boxplot(column=y, by=x, ax=ax, **plt_kwargs)

        return fig, ax

    def _plot_parametric(self, name):

        fig, ax = self.plots[name]
        ax.clear()

        x = self.settings[name]['x']
        y = np.array([self.settings[name]['y']]).flatten()[0]
        c = self.settings[name].get('parameter', 'Time')

        # Handle simple numeric data
        y_is_numeric = isinstance(self.data[y].values[0], numbers.Number)

        if y_is_numeric:

            if c not in self.data.columns:
                c = self.data.index
            else:
                c = self.data[c]

            self.data.plot(y=y, x=x, c=c, ax=ax, **plt_kwargs)

        # Handle data stored in a file
        y_is_path = isinstance(self.data[y].values[0], str)

        if y_is_path:

            data_file = self.data[y].values[-1]
            file_data = pd.read_csv(data_file)

            if c == 'Time':
                file_data[c] = file_data.index
            else:
                file_indices = file_data.index  # timestamps for the referenced data file
                data_indices = self.data.index  # timestamps for the main data set, can be slightly different from the file timestamps

                unique_file_indices = np.unique(file_indices).sort()

                index_map = {file_index: data_index for file_index, data_index in zip(unique_file_indices, data_indices)}

                for index in file_indices:
                    file_data[s][index] = data[s][index_map[index]]

            file_data.scatterplot(x=x, y=y, ax=ax, kind='scatter', s=10, c=c, colormap='viridis')

        return fig, ax

    def _plot_order(self, name):

        fig, ax = self._plot_all(name, colors=colors)

        colors = [line.get_color() for line in ax.get_lines()]

        x = self.settings[name]['x']
        y = self.settings[name]['y']

        # Show arrows pointing in the direction of the scan
        num_points = len(self.data[x])
        for yy, color in zip(y, colors):
            for i in range(num_points - 1):
                x1, x2 = self.data[x].iloc[i], self.data[x].iloc[i + 1]
                y1, y2 = self.data[yy].iloc[i], self.data[yy].iloc[i + 1]
                axes.annotate('', xytext=(x1, y1),
                              xy=(0.5 * (x1 + x2), 0.5 * (y1+ y1)),
                              arrowprops=dict(arrowstyle='->', color=color))

        return fig, ax

class InstrumentConfigGUI():
    """
    Once the instruments are selected, this window allows the user to configure and test instruments before setting up an experiment
    """

    def __init__(self, parent, instruments, runcard_warning=False):

        self.finished = False

        self.parent = parent

        self.root = tk.Toplevel(self.parent)
        self.root.title('Instrument Config/Test')

        self.instruments = instruments

        self.runcard_warning = runcard_warning

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

        if self.runcard_warning:
            RuncardDepartureDialog(self.root)

        dialog = ConfigTestDialog(self.root, instrument, title='Config/Test: '+instrument.name)


class BasicDialog(tk.Toplevel):
    """
    General purpose dialog window

    """

    def __init__(self, parent, title=None):

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

        self.geometry("+%d+%d" % (parent.winfo_rootx() + 50,
                                  parent.winfo_rooty() + 50))

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

        w = tk.Button(box, text="OK", width=10, command=self.ok, default=tk.ACTIVE)
        w.pack(side=tk.LEFT, padx=5, pady=5)

        self.bind("<Return>", self.ok)

        box.pack()

    # standard button semantics

    def ok(self, event=None):

        if not self.validate():
            self.initial_focus.focus_set()  # put focus back
            return

        self.withdraw()
        self.update_idletasks()

        self.apply()

        self.parent.focus_set()
        self.destroy()

    def validate(self):

        return 1  # override


class RuncardDepartureDialog(BasicDialog):

    def body(self, master):
        self.title('WARNING')
        tk.Label(master, text='If you make any changes, you will deviate from the runcard!').pack()


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
