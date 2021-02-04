import matplotlib
matplotlib.use('TkAgg')

import time
import threading
import queue
import numpy as np
import datetime
import tkinter as tk
import numbers
import pandas as pd

import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable

class Plotter:
    """
    Handler for plotting data based on the runcard plotting settings and data context
    """

    def __init__(self, data, settings=None):
        """
        PLot data based on settings

        :param data: (pandas.Dataframe) data to be plotted.
        :param settings: (dict) dictionary of plot settings
        """

        self.data = data

        if settings:
            self.settings = settings
        else:
            self.settings = {'Plot': {x:'time', y: data.columns}}

        self.plots = {}
        for plot_name in settings:
            self.plots[plot_name] = plt.subplots()

    def save(self, plot_name=None, save_as=None):

        if plot_name:
            fig, ax = self.plots[plot_name]
            if save_as:
                fig.savefig(save_as + '-' + '.png')
            else:
                fig.savefig(plot_name + '-' + '.png')
        else:
            for name, plot in self.plots.items():
                fig, ax = plot
                fig.savefig(name + '-' + '.png')

    def close(self, plot_name=None):

        self.save()

        if plot_name:
            fig, _ = self.plots[plot_name]
            plt.close(fig)
        else:
            plt.close('all')

    def plot(self):

        # Make the plots, by name and style
        new_plots = {}

        for name, settings in self.settings.items():

            style = settings.get('style', 'basic')

            if style == 'basic':
                new_plots[name] = self._plot_basic(name)
            elif style == 'averaged':
                new_plots[name] = self._plot_averaged(name)
            elif style == 'errorbars':
                new_plots[name] = self._plot_errorbars(name)
            elif style == 'parametric':
                new_plots[name] = self._plot_parametric(name)
            elif style == 'order':
                new_plots[name] = self._plot_order(name)
            else:
                raise AttributeError(f"Plotting style '{style}' not recognized!")

        plt.pause(0.01)
        return new_plots

    def _plot_basic(self, name):

        fig, ax = self.plots[name]
        ax.clear()

        x = self.settings[name]['x']
        ys = np.array([self.settings[name]['y']]).flatten()

        for y in ys:

            if y not in self.data.columns:
                raise AttributeError(f'Specified variable {var} is not in data set. Check variable names in plot specification.')

            # If data points to a file, then generate a parametric plot
            y_is_path = bool( sum([ 'csv' in y_value for y_value in self.data[y] if isinstance(y_value, str)]))
            if y_is_path:
                return self._plot_parametric(name)
            else:
                plt_kwargs = self.settings[name].get('options', {})

                if x.lower() ==  'time':
                    self.data.plot(y=y,ax=ax, kind='line', **plt_kwargs)  # use index as time axis
                else:
                    self.data.plot(y=y, x=x, ax=ax, kind='line', **plt_kwargs)

        ax.set_title(name)
        ax.grid()
        ax.ticklabel_format(axis='y', style='sci', scilimits=(-2, 4))
        ax.set_xlabel(self.settings[name].get('xlabel', x))
        ax.set_ylabel(self.settings[name].get('ylabel', ys[0]))

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

        colormap = 'viridis'
        plt.rcParams['image.cmap'] = colormap
        cmap = plt.get_cmap('viridis')

        x = self.settings[name]['x']
        y = np.array([self.settings[name]['y']]).flatten()[0]
        c = self.settings[name].get('parameter', 'time')

        if c not in self.data.columns:
            raise PlotError(f'Parameter {c} not in data!')

        # Handle simple numeric data
        y_is_numeric = bool( sum([isinstance(y_value, numbers.Number) for y_value in self.data[y]]) )

        if y_is_numeric:

            x_data = np.array(self.data[x].values, dtype=float)
            y_data = np.array(self.data[y].values, dtype=float)
            c_data = np.array(self.data[c].values, dtype=float)

            # Rescale time if needed
            if c == 'time':
                units = 'seconds'
                if np.max(c_data) > 60:
                    units = 'minutes'
                    c_data = c_data / 60
                    if np.max(c_data) > 60:
                        units = 'hours'
                        c_data = c_data / 60

        # Handle data stored in a file
        y_is_path = bool( sum([ 'csv' in y_value for y_value in self.data[y] if isinstance(y_value, str)]))

        if y_is_path:

            x_data = []
            y_data = []
            c_data = []

            for i, x_path, y_path in zip(range(len(self.data)), self.data[x].values, self.data[y].values):

                x_file_data = pd.read_csv(x_path, index_col=0)
                y_file_data = pd.read_csv(y_path, index_col=0)

                if c == 'time':
                    y_file_data.index = pd.to_datetime(y_file_data.index, infer_datetime_format=True)
                    first_datetime = pd.date_range(start=self.data.index[0], end=self.data.index[0], periods=len(y_file_data))
                    y_file_data[c] = (y_file_data.index - first_datetime).total_seconds()

                    # Rescale time if values are large
                    units = 'seconds'
                    if np.max(y_file_data[c].values) > 60:
                        units = 'minutes'
                        y_file_data[c] = y_file_data[c] / 60
                        if np.max(y_file_data[c].values) > 60:
                            units = 'hours'
                            y_file_data[c] = y_file_data[c] / 60
                else:
                    y_file_data[c] = [self.data[c].values[i]] * len(y_file_data)

                x_data.append(x_file_data[x].values)
                y_data.append(y_file_data[y].values)
                c_data.append(y_file_data[c].values)

            x_data = np.concatenate(x_data)
            y_data = np.concatenate(y_data)
            c_data = np.concatenate(c_data)

        c_min, c_max = np.min(c_data), np.max(c_data)
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

        if c == 'time':
            fig.cbar.ax.set_ylabel('Time ' + f" ({units})")
        else:
            fig.cbar.ax.set_ylabel(self.settings[name].get('clabel', c))

        # Draw the plot
        if marker:
            for i in range(x_data.shape[0]):
                ax.plot([x_data[i]], [y_data[i]], marker=marker, markersize=3, color=cmap(norm(np.mean(c_data[i]))))
        else:
            for i in range(x_data.shape[0] - 1):
                ax.plot(x_data[i: i + 2], y_data[i: i + 2], color=cmap(norm(np.mean(c_data[i: i + 2]))))

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


class ExperimentGUI:
    """
    GUI showing experimental progress, values of all experiment variables, any alarms.
    Also, manages plotting data via the Plotter class

    This GUI allows the user to pause or stop the experiment.
    When paused, the user can also directly interact with instruments through the Dashboard button.
    """

    def __init__(self, experiment, alarms=None, instruments=None, title=None, plots=None, save_interval=None):

        self.experiment = experiment

        self.quitted = False  # has the GUI been closed?

        self.variables = experiment.variables

        if alarms is None:
            self.alarms = {}
        else:
            self.alarms = alarms

        if instruments:
            self.instruments = instruments
        else:
            # If instruments are not specified, get them from the experiment variables
            self.instruments = {}
            for variable in self.experiment.variables.values():
                if variable.type in ['meter', 'knob']:
                    instrument = variable.instrument
                    if instrument.name not in self.instruments:
                        self.instruments[instrument.name] = instrument

        if plots:
            self.plotter = Plotter(experiment.data, plots)

            self.plot_interval = 0  # grows if plotting takes longer
            self.last_plot = float('-inf')

            # Set interval for saving plots
            if save_interval:
                self.save_interval = save_interval
            else:
                self.save_interval = 0
            self.last_save = time.time()

        self.root = tk.Tk()
        self.root.lift()
        self.root.wm_attributes('-topmost', True)  # bring window to front
        self.root.protocol("WM_DELETE_WINDOW", self.end)

        if title:
            self.root.title(f'Experiment: {title}')
        else:
            self.root.title('Experiment')

        # Status field shows current experiment status
        tk.Label(self.root, text='Status', width=len('Status'), anchor=tk.E).grid(row=0, column=0, sticky=tk.E)

        self.status_label = tk.Label(self.root, text='', width=40, relief=tk.SUNKEN)
        self.status_label.grid(row=0, column=1, sticky=tk.W)

        # Table of variables shows most recently measured/set variable values
        self.variable_status_labels = {}

        i = 2
        tk.Label(self.root, text='Run Time', width=len('Run Time'), anchor=tk.E).grid(row=i, column=0, sticky=tk.E)

        self.variable_status_labels['time'] = tk.Label(self.root, text='', relief=tk.SUNKEN, width=40)
        self.variable_status_labels['time'].grid(row=i, column=1, sticky=tk.W)

        i += 1
        tk.Label(self.root, text='', font=("Arial", 14, 'bold')).grid(row=i, column=0, sticky=tk.E)

        i += 1
        tk.Label(self.root, text='Variables', font=("Arial", 14, 'bold')).grid(row=i, column=1)

        i += 1
        for variable in self.variables:
            tk.Label(self.root, text=variable, width=len(variable), anchor=tk.E).grid(row=i, column=0, sticky=tk.E)

            self.variable_status_labels[variable] = tk.Label(self.root, text='', relief=tk.SUNKEN, width=40)
            self.variable_status_labels[variable].grid(row=i, column=1, sticky=tk.W)

            i += 1

        tk.Label(self.root, text='', font=("Arial", 14, 'bold')).grid(row=i, column=0, sticky=tk.E)

        # Table of alarm indicators shows the status of any alarms being monitored
        self.alarm_status_labels = {}

        if len(alarms) > 0:

            i += 1
            tk.Label(self.root, text='Alarms', font=("Arial", 14, 'bold')).grid(row=i, column=1)

            i += 1
            for alarm in self.alarms:
                tk.Label(self.root, text=alarm, width=len(alarm), anchor=tk.E).grid(row=i, column=0, sticky=tk.E)

                self.alarm_status_labels[alarm] = tk.Label(self.root, text='Clear', relief=tk.SUNKEN, width=40)
                self.alarm_status_labels[alarm].grid(row=i, column=1, sticky=tk.W)

                i += 1

            tk.Label(self.root, text='', font=("Arial", 14, 'bold')).grid(row=i, column=0, sticky=tk.E)


        self.dash_button = tk.Button(self.root, text='Dashboard', font=("Arial", 14, 'bold'),
                                     command=self.open_dashboard, state=tk.DISABLED)
        self.dash_button.grid(row=i + 1, column=0, sticky=tk.W)

        self.hold_button = tk.Button(self.root, text='Hold', font=("Arial", 14, 'bold'),
                                      command=self.toggle_hold)
        self.hold_button.grid(row=i + 2, column=0, sticky=tk.W)

        self.stop_button = tk.Button(self.root, text='Stop', font=("Arial", 14, 'bold'),
                                      command=self.toggle_stop)
        self.stop_button.grid(row=i + 3, column=0, sticky=tk.W)

        self.terminate_button = tk.Button(self.root, text='Terminate', font=("Arial", 14, 'bold'),
                                          command=self.end, height=5)
        self.terminate_button.grid(row=i + 1, column=1, sticky=tk.E, rowspan=3)

    def run(self):
        self.update()
        self.root.mainloop()

    def update(self):
        # Updates the GUI based on the state of the experiment

        if self.quitted:
            return  # don't update GUI if it no longer exists

        self.root.wm_attributes('-topmost', False)  # Allow window to fall back once things get started

        # Check the state of the experiment
        state = self.experiment.state
        for name, label in self.variable_status_labels.items():
            if state[name] == None:
                label.config(text='none')
            elif state[name] == np.nan:
                label.config(text='nan')
            else:
                if name.lower() == 'time':
                    label.config(text=str(datetime.timedelta(seconds=state['time'])))
                else:
                    label.config(text=str(state[name]))

        self.status_label.config(text=self.experiment.status)

        # Check alarms
        for name, label in self.alarm_status_labels.items():
            if self.alarms[name].triggered:
                label.config(text="TRIGGERED", bg='red')
            else:
                label.config(text="CLEAR", bg='green')

        # Update hold, stop and dashboard buttons
        if self.experiment.status == 'Holding':
            self.dash_button.config(state=tk.NORMAL)
            self.hold_button.config(text='Resume')
            self.stop_button.config(text='Stop')
        elif self.experiment.status == 'Stopped':
            self.dash_button.config(state=tk.NORMAL)
            self.hold_button.config(text='Hold')
            self.stop_button.config(text='Resume')
        else:
            self.dash_button.config(state=tk.DISABLED)
            self.hold_button.config(text='Hold')
            self.stop_button.config(text='Stop')

        # Quit if experiment has ended
        if self.experiment.status == self.experiment.TERMINATED:
            self.quit()

        # Plot data
        if hasattr(self, 'plotter') and len(self.experiment.data) > 0:
            if time.time() > self.last_plot + self.plot_interval:

                start_plot = time.perf_counter()
                self.plotter.plot()
                end_plot = time.perf_counter()

                self.plot_interval = int(5*(end_plot - start_plot))  # increase plot interval, if plotting slows down
                self.last_plot = time.time()

            # Save plots
            if time.time() > self.last_save + self.save_interval and self.experiment.timestamp:

                start_save = time.perf_counter()
                self.plotter.save()
                end_save = time.perf_counter()

                self.save_interval = int(5*(end_save - start_save))
                self.last_save = time.time()

        if not self.quitted:
            self.root.after(50, self.update)

    def open_dashboard(self):
        # Opens a window which allows the user to change variable values while the experiment is stopped
        prior_status = self.experiment.status

        self.experiment.stop()  # stop routines and measurements to avoid communication conflicts while dashboard is open

        Dashboard(self.root, self.instruments)

        # Return experiment to prior state
        if prior_status == self.experiment.HOLDING:
            print('returning to hold')
            self.experiment.hold()
        elif prior_status in [self.experiment.READY, self.experiment.RUNNING]:
            self.experiment.start()
            print('returning to running')

    def toggle_hold(self):
        # User pauses/resumes the experiment

        if self.experiment.status == 'Holding':
            self.experiment.start()
        else:
            self.experiment.hold()

    def toggle_stop(self):
        # User pauses/resumes the experiment

        if self.experiment.status == 'Stopped':
            self.experiment.start()
        else:
            self.experiment.stop()

    def end(self):
        # User ends the experiment

        self.experiment.terminate()
        self.quit()
        self.terminated = True

    def quit(self):
        # Closes the GUI and plots

        if hasattr(self, 'plotter'):
            self.plotter.close()

        self.status_label.config(text=self.experiment.TERMINATED)

        self.quitted = True
        plt.pause(0.1)  # give GUI and plotter enough time to wrap up
        self.root.update()

        self.root.destroy()
        self.root.quit()


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


class Dashboard(BasicDialog):
    """
    Once the instruments are selected, this window allows the user to configure and test instruments before setting up an experiment
    """

    def __init__(self, parent, instruments):

        self.instruments = instruments

        BasicDialog.__init__(self, parent, title='Dashboard')

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

        dialog = ConfigTestDialog(self, instrument)


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
        knob_values = {knob: getattr(self.instrument, knob.replace(' ','_')) for knob in knobs}
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