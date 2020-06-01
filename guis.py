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
from matplotlib.cm import ScalarMappable
from tkinter.filedialog import askopenfilename, askopenfile

from mercury.elements import Experiment
from mercury.utilities import *

plt.ion()


# Guis for controlling and monitoring ongoing experiments
class ExperimentController:

    def __init__(self, runcard_path=None):

        # Start tkinter master frame
        self.root = tk.Tk()
        self.root.withdraw()

        # Pull in the runcard
        if runcard_path is None:
            runcard_path = askopenfilename(title='Select Experiment Runcard')

        self.runcard_path = runcard_path

        working_dir = os.path.dirname(runcard_path)
        if working_dir != '':
            os.chdir(working_dir)

        with open(runcard_path, 'rb') as runcard:
            self.runcard = yaml.load(runcard)

        # Set up the experiment
        self.settings = self.runcard['Settings']
        self.experiment = Experiment(self.runcard)

        # Create a new directory for each runcard execution and store a copy of executed runcard and all data there
        name = self.experiment.description.get('name', 'experiment')
        timestamp = get_timestamp()
        working_dir = os.path.join(working_dir, name + '-' + timestamp)
        os.mkdir(working_dir)
        os.chdir(working_dir)

        with open(timestamp_path(name + '_runcard.yaml', timestamp=timestamp), 'w') as runcard_file:
            yaml.dump(self.runcard, runcard_file)  # save executed runcard for record keeping

        # Set up the main user interface
        self.status_gui = StatusGUI(parent=self.root, experiment=self.experiment)

        # Set up the data plotter
        self.plot_interval = convert_time(self.settings['plot interval'])
        self.plotter = Plotter(data=self.experiment.data,
                               settings=self.experiment.plotting)

        self.last_plot = -np.inf

        # Run the main loop
        self.interval = int(float(self.experiment.settings['step interval'])*1000)
        self.root.after(self.interval, self.step)
        self.root.mainloop()

        # Experiment prescribed by runcard has ended, do any follow-up experiments or shut things down
        self.plotter.close()

        os.chdir('..')
        followup = self.experiment.followup

        if len(followup) == 0:
            return
        elif followup[0].lower() == 'repeat':
            self.__init__(self.runcard_path)
        else:
            for task in followup:
                self.__init__(task)

    def step(self):

        try:
            step = next(self.experiment)
        except StopIteration:
            self.root.quit()
            self.root.destroy()
            return None

        self.status_gui.update(step, status=self.experiment.status)

        # Plot data if sufficient time has passed since the last plot generation
        now = time.time()
        if now >= self.last_plot + self.plot_interval:
            self.plotter.plot()
            self.plotter.save()
            self.last_plot = now

        # Stop the schedule clock and stop iterating if the user pauses the experiment
        if self.status_gui.paused:
            self.experiment.schedule.stop()
            while self.status_gui.paused:
                self.status_gui.update(step)
                plt.pause(0.01)
            self.experiment.schedule.clock.resume()

        plt.pause(0.01)

        self.root.after(self.interval, self.step)


class StatusGUI:
    """
    GUI showing experimental progress and values of all experiment variables.
    This GUI allows the user to stop or pause the experiment.
    When paused, the user can also directly interact with instruments through the "Check" button.
    """

    def __init__(self, parent, experiment):

        self.parent = parent
        self.experiment = experiment

        self.paused = False

        self.variables = experiment.instruments.mapped_variables

        self.root = tk.Toplevel(self.parent)
        self.root.attributes("-topmost", True)
        self.root.title('Experiment: ' + self.experiment.description['name'])

        tk.Label(self.root, text='Status:').grid(row=0, column=0, sticky=tk.E)

        self.status_label = tk.Label(self.root, text='Getting started.', width=40, relief=tk.SUNKEN)
        self.status_label.grid(row=0, column=1, columnspan=2, sticky=tk.W)

        tk.Label(self.root, text='', font=("Arial", 14, 'bold')).grid(row=1, column=0, sticky=tk.E)

        self.variable_status_labels = {}

        i = 1
        for variable in self.variables:
            tk.Label(self.root, text=variable, width=len(variable), anchor=tk.E).grid(row=i, column=0, sticky=tk.E)
            self.variable_status_labels[variable] = tk.Label(self.root, text='', relief=tk.SUNKEN, width=40)
            self.variable_status_labels[variable].grid(row=i, column=1, columnspan=2, sticky=tk.W)

            i += 1

        tk.Label(self.root, text='', font=("Arial", 14, 'bold')).grid(row=i, column=0, sticky=tk.E)

        self.config_button = tk.Button(self.root, text='Instruments...', font=("Arial", 14, 'bold'), command=self.check_instr,
                                       width=22, state=tk.DISABLED)
        self.config_button.grid(row=i + 1, column=2)

        self.pause_button = tk.Button(self.root, text='Pause', font=("Arial", 14, 'bold'), command=self.toggle_pause,
                                      width=10)
        self.pause_button.grid(row=i + 1, column=1)

        self.stop_button = tk.Button(self.root, text='Stop', font=("Arial", 14, 'bold'), command=self.user_stop,
                                     width=10)
        self.stop_button.grid(row=i + 1, column=0)

    def update(self, step=None, status=None):

        if step is not None:
            for name, label in self.variable_status_labels.items():
                label.config(text=str(step[name]))

        if status:
            self.status_label.config(text=status)
        else:
            if self.paused:
                self.status_label.config(text='Paused by user')
            else:
                self.status_label.config(text=self.experiment.status)

        self.root.lift()

    def check_instr(self):

        instrument_gui = InstrumentConfigGUI(self.root, self.experiment.instruments, runcard_warning=True)

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

        if self.paused:
            self.paused = False

        self.experiment.status = 'Finished: Stopped by user'  # tells the experiment to stop iterating
        self.update(status=self.experiment.status)
        self.experiment.followup = []  # cancel any follow-ups


class PlotError(BaseException):
    pass


class Plotter:
    """
    Handler for plotting data based on the runcard plotting settings and data context
    """

    def __init__(self, data, settings=None):
        """
        PLot data based on settings

        :param data: (DataFrame) Dataframe containing the data to be plotted.
        :param settings: (dict) dictionary of plot settings
        """

        self.data = data

        if settings:
            self.settings = settings
        else:
            self.settings = {}

        self.plots = {}
        for plot_name in settings:
            self.plots[plot_name] = plt.subplots()

        self.timestamp = get_timestamp()

    def configure(self, settings=None, interval=None):

        if settings:
            self.settings = settings
        if interval:
            self.interval = interval

    def plot(self):

        # Make the plots, by name and style
        new_plots = {}

        for name, settings in self.settings.items():

            style = settings.get('style', 'none')

            if style == 'none' or style == 'all':
                new_plots[name] = self._plot_all(name)
            elif style == 'averaged':
                new_plots[name] = self._plot_averaged(name)
            elif style == 'errorbars':
                new_plots[name] = self._plot_errorbars(name)
            elif style == 'parametric':
                new_plots[name] = self._plot_parametric(name)
            elif style == 'order':
                new_plots[name] = self._plot_order(name)
            else:
                raise PlotError(f"Plotting style '{style}' not recognized!")

        return new_plots

    def save(self, plot_name=None, save_as=None):

        if plot_name:
            fig, ax = self.plots[plot_name]
            if save_as:
                fig.savefig(timestamp_path(save_as + '.png', timestamp=self.timestamp))
            else:
                fig.savefig(timestamp_path(plot_name + '.png', timestamp=self.timestamp))
        else:
            for name, plot in self.plots.items():
                fig, ax = plot
                fig.savefig(timestamp_path(name+'.png', timestamp=self.timestamp))

    def _plot_all(self, name):

        fig, ax = self.plots[name]
        ax.clear()

        x = self.settings[name]['x']
        y = np.array([self.settings[name]['y']]).flatten()

        # If data points to a file, then generate a parametric plot
        y_is_path = isinstance(self.data[y].to_numpy().flatten()[0], str)
        if y_is_path:
            return self._plot_parametric(name)

        plt_kwargs = self.settings[name].get('options', {})

        if x.lower() ==  'time':
            self.data.plot(y=y,ax=ax, kind='line', **plt_kwargs)
        else:
            self.data.plot(y=y, x=x, ax=ax, kind='line', **plt_kwargs)

        ax.set_title(name)
        ax.grid()
        ax.ticklabel_format(axis='y', style='sci', scilimits=(-2, 4))
        ax.set_xlabel(self.settings[name].get('xlabel', x))
        ax.set_ylabel(self.settings[name].get('ylabel', y[0]))

        return fig, ax

    def _plot_averaged(self, name):

        fig, ax = self.plots[name]
        ax.clear()

        x = self.settings[name]['x']
        y = np.array([self.settings[name]['y']]).flatten()

        plt_kwargs = self.settings[name].get('options',{})

        averaged_data = self.data.groupby(x).mean()

        averaged_data.plot(y=y, ax=ax, kind='line', **plt_kwargs)

        ax.set_title(name)
        ax.grid(True)
        ax.ticklabel_format(axis='y', style='sci', scilimits=(-2, 4))
        ax.set_xlabel(self.settings[name].get('xlabel', x))
        ax.set_ylabel(self.settings[name].get('ylabel', y[0]))

        return fig, ax

    def _plot_errorbars(self, name):

        fig, ax = self.plots[name]
        ax.clear()

        x = self.settings[name]['x']
        y = np.array([self.settings[name]['y']]).flatten()

        plt_kwargs = self.settings[name].get('options',{})

        self.data.boxplot(column=y[0], by=x, ax=ax, **plt_kwargs)

        ax.set_title(name)
        ax.grid(True)
        ax.ticklabel_format(axis='y', style='sci', scilimits=(-2, 4))
        ax.set_xlabel(self.settings[name].get('xlabel', x))
        ax.set_ylabel(self.settings[name].get('ylabel', y[0]))

        return fig, ax

    def _plot_parametric(self, name):

        fig, ax = self.plots[name]
        ax.clear()

        marker = self.settings[name].get('marker', 'None')
        if marker.lower() == 'none':
            marker = None

        # Color plot according to elapsed time
        colormap = 'viridis'  # Determines colormap to use for plotting timeseries data
        plt.rcParams['image.cmap'] = colormap
        cmap = plt.get_cmap('viridis')

        x = self.settings[name]['x']
        y = np.array([self.settings[name]['y']]).flatten()[0]
        c = self.settings[name].get('parameter', 'Time')

        if c not in self.data.columns and c != 'Time':
            raise PlotError(f'Parameter {c} not in data!')

        # Handle simple numeric data
        y_is_numeric = isinstance(self.data[y].values[0], numbers.Number) or self.data[y].values[0] in [None, np.nan]

        if y_is_numeric:

            if c == 'Time':
                indices = self.data.index
                first_datetime = pd.date_range(start=indices[0], end=indices[0],
                                               periods=len(indices))
                self.data[c] = (self.data.index - first_datetime).total_seconds()

            x_data = self.data[x].values
            y_data = self.data[y].values
            c_data = self.data[c].values

            # Rescale time if needed
            if c == 'Time':
                units = 'seconds'
                if np.max(self.data[c].values) > 60:
                    units = 'minutes'
                    self.data[c] = self.data[c] / 60
                    if np.max(self.data[c].values) > 60:
                        units = 'hour'
                        self.data[c] = self.data[c] / 60

        # Handle data stored in a file
        y_is_path = isinstance(self.data[y].values[0], str)

        if y_is_path:

            data_file = self.data[y].values[-1]
            file_data = pd.read_csv(data_file, index_col=0)
            file_data.index = pd.to_datetime(file_data.index, infer_datetime_format=True)  # convert to pandas DateTime index

            if c == 'Time':
                first_datetime = pd.date_range(start=file_data.index[0], end=file_data.index[0], periods=len(file_data.index))
                file_data[c] = (file_data.index - first_datetime).total_seconds()

                # Rescale time if needed
                units = 'seconds'
                if np.max(file_data[c].values) > 60:
                    units = 'minutes'
                    file_data[c] = file_data[c] / 60
                    if np.max(file_data.values) > 60:
                        units = 'hour'
                        file_data[c] = file_data[c] / 60

            else:
                file_indices = file_data.index  # timestamps for the referenced data file
                data_indices = self.data.index  # timestamps for the main data set, can be slightly different from the file timestamps
                unique_file_indices = np.unique(file_indices).sort()
                index_map = {file_index: data_index for file_index, data_index in zip(unique_file_indices, data_indices)}
                for index in file_indices:
                    file_data[c][index] = data[c][index_map[index]]

            x_data = file_data[x].values
            y_data = file_data[y].values
            c_data = file_data[c].values

        c_min, c_max = [np.min(c_data), np.max(c_data)]
        norm = plt.Normalize(vmin=c_min, vmax=c_max)

        # Add the colorbar, if the figure doesn't already have one
        try:
            fig.has_colorbar
            fig.scalarmappable.set_clim(vmin=c_min, vmax=c_max)
            fig.cbar.update_normal(fig.scalarmappable)

        except AttributeError:

            fig.scalarmappable = ScalarMappable(cmap=cmap, norm=norm)
            fig.scalarmappable.set_array(np.linspace(c_min, c_max, 1000))

            fig.cbar = plt.colorbar(fig.scalarmappable, ax=ax)
            fig.has_colorbar = True

        if c == 'Time':
            fig.cbar.ax.set_ylabel('Time ' + f" ({units})")
        else:
            fig.cbar.ax.set_ylabel(self.settings[name].get('clabel', c))


        # Draw the plot
        if marker:
            for i in range(x_data.shape[0]):
                ax.plot([x_data[i]], [y_data[i]], marker=marker, markersize=3,
                                   color=cmap(norm(np.mean(c_data[i]))))
        else:
            for i in range(x_data.shape[0] - 1):
                ax.plot(x_data[i: i + 2], y_data[i: i + 2],
                                   color=cmap(norm(np.mean(c_data[i: i + 2]))))
        ax.set_title(name)
        ax.grid(True)
        ax.ticklabel_format(axis='y', style='sci', scilimits=(-2, 4))
        ax.set_xlabel(self.settings[name].get('xlabel', x))
        ax.set_ylabel(self.settings[name].get('ylabel', y))

        return fig, ax

    def _plot_order(self, name):

        fig, ax = self._plot_all(name)

        colors = [line.get_color() for line in ax.get_lines()]

        x = self.settings[name]['x']
        y = np.array([self.settings[name]['y']]).flatten()

        # Show arrows pointing in the direction of the scan
        num_points = len(self.data[x])
        for yy, color in zip(y, colors):
            for i in range(num_points - 1):
                x1, x2 = self.data[x].iloc[i], self.data[x].iloc[i + 1]
                y1, y2 = self.data[yy].iloc[i], self.data[yy].iloc[i + 1]
                ax.annotate('', xytext=(x1, y1),
                              xy=(0.5 * (x1 + x2), 0.5 * (y1+ y2)),
                              arrowprops=dict(arrowstyle='->', color=color))

        ax.set_title(name)
        ax.grid(True)
        ax.ticklabel_format(axis='y', style='sci', scilimits=(-2, 4))
        ax.set_xlabel(self.settings[name].get('xlabel', x))
        ax.set_ylabel(self.settings[name].get('ylabel', y[0]))

        return fig, ax

    def close(self, plot_name=None):

        if plot_name:
            fig, _ = self.plots[plot_name]
            plt.close(fig)
        else:
            for plot in self.plots.values():
                fig, _ = plot
                plt.close(fig)


# GUIs for instrument acess
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

        self.protocol("WM_DELETE_WINDOW", self.ok)

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

        self.parent.focus_set()
        self.destroy()

    def validate(self):

        return 1  # override


class InstrumentConfigGUI(BasicDialog):
    """
    Once the instruments are selected, this window allows the user to configure and test instruments before setting up an experiment
    """

    def __init__(self, parent, instruments_set, runcard_warning=False):

        self.instruments = instruments_set.instruments
        self.runcard_warning = runcard_warning

        BasicDialog.__init__(self, parent, title='Instrument Config/Test')

    def body(self, master):

        tk.Label(master, text='Instruments:', font=('Arial', 14), justify=tk.LEFT).grid(row=0, column=0, sticky=tk.W)

        i = 1

        self.instrument_labels = {}
        self.config_buttons = {}

        for name, instrument in self.instruments.items():

            instrument_label = tk.Label(master, text=name)
            instrument_label.grid(row=i, column=0)

            self.instrument_labels[name] = instrument_label

            config_button = tk.Button(master, text = 'Config/Test', command = lambda instr = instrument: self.config(instr))
            config_button.grid(row=i,column=1)

            self.config_buttons[name] = config_button

            i+=1

    def config(self, instrument):

        if self.runcard_warning:
            RuncardDepartureDialog(self)

        dialog = ConfigTestDialog(self, instrument)


class RuncardDepartureDialog(BasicDialog):

    def body(self, master):
        self.title('WARNING')
        tk.Label(master, text='If you make any changes, you will deviate from the runcard!').pack()


class ConfigTestDialog(BasicDialog):
    """
    Dialog box for setting knobs and checking meters.
    Allows the user to quickly access basic instrument functionality as well as configure instrument for an experiment

    """

    def __init__(self, parent, instrument):

        self.instrument = instrument
        BasicDialog.__init__(self, parent, title='Config/Test: '+instrument.name)

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


# Runcard Wizard GUI

