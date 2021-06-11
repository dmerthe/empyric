import time
import sys
import threading
import queue
import numpy as np
import datetime
import tkinter as tk
import numbers
import pandas as pd

if sys.platform == 'darwin':
    import matplotlib
    matplotlib.use('TkAgg')  # works better on MacOS

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
                fig.savefig(save_as + '.png')
            else:
                fig.savefig(plot_name + '.png')
        else:
            for name, plot in self.plots.items():
                fig, ax = plot
                fig.savefig(name + '.png')

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
            elif style == 'log':
                new_plots[name] = self._plot_log(name, floor=settings.get('floor', None))
            elif style == 'symlog':
                new_plots[name] = self._plot_symlog(name, linear_scale=settings.get('linear scale', None))
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

    def _plot_basic(self, name, linear=True):

        fig, ax = self.plots[name]
        ax.clear()

        x = self.settings[name]['x']
        ys = np.array([self.settings[name]['y']]).flatten()

        for y in ys:

            if y not in self.data.columns:
                raise AttributeError(f'Specified variable {y} is not in data set. Check variable names in plot specification.')

            # If data points to a file, then generate a parametric plot
            y_is_path = bool( sum([ 'csv' in y_value for y_value in self.data[y] if isinstance(y_value, str)]))
            if y_is_path:
                return self._plot_parametric(name)
            else:
                plt_kwargs = self.settings[name].get('options', {})

                if x.lower() == 'time':
                    self.data.plot(y=y,ax=ax, kind='line', legend=len(ys)>1, **plt_kwargs)  # use index as time axis
                else:
                    self.data.plot(y=y, x=x, ax=ax, kind='line', legend=len(ys)>1, **plt_kwargs)

        ax.set_title(name)
        ax.grid()
        if linear:
            ax.ticklabel_format(axis='y', style='sci', scilimits=(-2, 4))
        ax.set_xlabel(self.settings[name].get('xlabel', x))
        ax.set_ylabel(self.settings[name].get('ylabel', ys[0]))

        return fig, ax

    def _plot_log(self, name, floor=None):

        fig, ax = self._plot_basic(name, linear=False)
        ax.set_yscale('log')

        if floor is not None:
            ylim = ax.get_ylim()
            ax.set_ylim([floor, ylim[-1]])

        return fig, ax

    def _plot_symlog(self, name, linear_scale=None):

        fig, ax = self._plot_basic(name, linear=False)
        ax.set_yscale('symlog', linthresh=linear_scale)

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
            set_nums = np.array([1]*len(self.data))  # all the same data set

        # Handle data stored in a file
        y_is_path = bool( sum([ 'csv' in y_value for y_value in self.data[y] if isinstance(y_value, str)]))
        if y_is_path:

            x_data = []
            y_data = []
            c_data = []
            set_nums = []  # used to distinguish between sets

            for i, x_path, y_path in zip(range(len(self.data)), self.data[x].values, self.data[y].values):

                x_file_data = pd.read_csv(x_path, index_col=0)
                y_file_data = pd.read_csv(y_path, index_col=0)

                if c == 'time':
                    y_file_data.index = pd.to_datetime(y_file_data.index, infer_datetime_format=True)
                    first_datetime = pd.date_range(start=self.data.index[0], end=self.data.index[0], periods=len(y_file_data))
                    y_file_data[c] = (y_file_data.index - first_datetime).total_seconds()

                else:
                    y_file_data[c] = [self.data[c].values[i]] * len(y_file_data)

                x_data.append(x_file_data[x].values)
                y_data.append(y_file_data[y].values)
                c_data.append(y_file_data[c].values)
                set_nums.append(np.array([i]*len(x_file_data)))

            x_data = np.concatenate(x_data)
            y_data = np.concatenate(y_data)
            c_data = np.concatenate(c_data)
            set_nums = np.concatenate(set_nums)

        if c == 'time': # Rescale time if values are large
            units = 'seconds'
            if np.max(c_data) > 60:
                units = 'minutes'
                c_data = c_data / 60
                if np.max(c_data) > 60:
                    units = 'hours'
                    c_data = c_data / 60

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
            fig.cbar.ax.set_ylabel(self.settings[name].get('clabel', c))
            fig.has_colorbar = True

        if c == 'time':
            fig.cbar.ax.set_ylabel('Time ' + f" ({units})")

        # Draw the plot
        if marker:
            for i in range(x_data.shape[0]):
                ax.plot([x_data[i]], [y_data[i]], marker=marker, markersize=3, color=cmap(norm(np.mean(c_data[i]))))
        else:
            for i in range(x_data.shape[0] - 1):
                if set_nums[i] == set_nums[i+1]:
                    ax.plot(x_data[i: i + 2], y_data[i: i + 2], color=cmap(norm(np.mean(c_data[i: i + 2]))))

        ax.set_title(name)
        ax.grid(True)
        ax.ticklabel_format(axis='y', style='sci', scilimits=(-2, 4))
        ax.set_xlabel(self.settings[name].get('xlabel', x))
        ax.set_ylabel(self.settings[name].get('ylabel', y))

        return fig, ax


class ExperimentGUI:
    """
    GUI showing experimental progress, values of all experiment variables, any alarms.
    Also, manages plotting data via the Plotter class

    This GUI allows the user to hold, stop and terminate the experiment.
    When paused, the user can also directly interact with instruments through the Dashboard.
    """

    def __init__(self, experiment, alarms=None, instruments=None, title=None, plots=None, save_interval=None, plot_interval=0):

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

            self.plot_interval = plot_interval  # grows if plotting takes longer
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

        self.root.title('Empyric')

        self.status_frame = tk.Frame(self.root)
        self.status_frame.grid(row=0, column=0, columnspan=2)

        i = 0
        if title:
            tk.Label(self.status_frame, text=f'{title}', font=("Arial", 14, 'bold')).grid(row=i, column=1)
        else:
            tk.Label(self.status_frame, text=f'Experiment', font=("Arial", 14, 'bold')).grid(row=i, column=1)

        # Status field shows current experiment status
        i += 1
        tk.Label(self.status_frame, text='Status', width=len('Status'), anchor=tk.E).grid(row=i, column=0, sticky=tk.E)

        self.status_label = tk.Label(self.status_frame, text='', width=30, relief=tk.SUNKEN)
        self.status_label.grid(row=i, column=1, sticky=tk.W, padx=10)

        # Table of variables shows most recently measured/set variable values
        self.variable_entries = {}
        self._entry_enter_funcs = {}  # container for enter press event handlers
        self._entry_esc_funcs = {}  # container for esc press event handlers

        i += 1
        tk.Label(self.status_frame, text='', font=("Arial", 14, 'bold')).grid(row=i, column=0, sticky=tk.E)

        i += 1
        tk.Label(self.status_frame, text='Variables', font=("Arial", 14, 'bold')).grid(row=i, column=1)

        i += 1
        tk.Label(self.status_frame, text='Run Time', width=len('Run Time'), anchor=tk.E).grid(row=i, column=0, sticky=tk.E)

        self.variable_entries['time'] = tk.Entry(self.status_frame, state='readonly', disabledforeground='black', width=30)
        self.variable_entries['time'].grid(row=i, column=1, sticky=tk.W, padx=10)

        i += 1
        for name in self.variables:
            tk.Label(self.status_frame, text=name, width=len(name), anchor=tk.E).grid(row=i, column=0, sticky=tk.E)

            self.variable_entries[name] = tk.Entry(self.status_frame, state='readonly', disabledforeground='black', width=30)
            self.variable_entries[name].grid(row=i, column=1, sticky=tk.W, padx=10)

            if self.variables[name].type in ['knob', 'parameter']:
                entry = self.variable_entries[name]
                variable = self.variables[name]
                root = self.status_frame

                enter_func = lambda event, entry=entry, variable=variable, root=root : self._entry_enter(entry, variable, root)
                self._entry_enter_funcs[name] = enter_func
                self.variable_entries[name].bind('<Return>', self._entry_enter_funcs[name])

                esc_func = lambda event, entry=entry, variable=variable, root=root : self._entry_esc(entry, variable, root)
                self._entry_esc_funcs[name] = esc_func
                self.variable_entries[name].bind('<Escape>', self._entry_esc_funcs[name])

            i += 1

        tk.Label(self.status_frame, text='', font=("Arial", 14, 'bold')).grid(row=i, column=0, sticky=tk.E)

        # Table of alarm indicators shows the status of any alarms being monitored
        self.alarm_status_labels = {}

        if len(alarms) > 0:

            i += 1
            tk.Label(self.status_frame, text='Alarms', font=("Arial", 14, 'bold')).grid(row=i, column=1)

            i += 1
            for alarm in self.alarms:
                tk.Label(self.status_frame, text=alarm, width=len(alarm), anchor=tk.E).grid(row=i, column=0, sticky=tk.E)

                self.alarm_status_labels[alarm] = tk.Label(self.status_frame, text='Clear', relief=tk.SUNKEN, width=30)
                self.alarm_status_labels[alarm].grid(row=i, column=1, sticky=tk.W, padx=10)

                i += 1

            tk.Label(self.status_frame, text='', font=("Arial", 14, 'bold')).grid(row=i, column=0, sticky=tk.E)


        i = 1
        self.dash_button = tk.Button(self.root, text='Dashboard', font=("Arial", 14, 'bold'), width=10,
                                     command=self.open_dashboard, state=tk.DISABLED)
        self.dash_button.grid(row=i, column=0, sticky=tk.W)

        self.hold_button = tk.Button(self.root, text='Hold', font=("Arial", 14, 'bold'), width=10,
                                      command=self.toggle_hold)
        self.hold_button.grid(row=i + 1, column=0, sticky=tk.W)

        self.stop_button = tk.Button(self.root, text='Stop', font=("Arial", 14, 'bold'), width=10,
                                      command=self.toggle_stop)
        self.stop_button.grid(row=i + 2, column=0, sticky=tk.W)

        self.terminate_button = tk.Button(self.root, text='Terminate', font=("Arial", 14, 'bold'), width=10, fg='red', bg='gray87',
                                          command=self.end, height=5)
        self.terminate_button.grid(row=i, column=1, sticky=tk.E, rowspan=3)

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
        for name, entry in self.variable_entries.items():

            # If experiment stopped allow user to edit knobs or constant expressions
            if 'Stopped' in self.experiment.status and name != 'time':
                if self.variables[name].type in ['knob', 'parameter']:
                    continue

            def write_entry(_entry, text):
                _entry.config(state=tk.NORMAL)
                _entry.delete(0, tk.END)
                _entry.insert(0, text)
                _entry.config(state=tk.DISABLED)

            if state[name] is None:
                write_entry(entry, 'none')
            elif state[name] == np.nan:
                write_entry(entry, 'nan')
            else:
                if name.lower() == 'time':
                    write_entry(entry, str(datetime.timedelta(seconds=state['time'])))
                else:
                    if type(state[name]) == float:
                        if state[name] == 0:
                            write_entry(entry, '0.0')
                        elif np.abs(np.log10(np.abs(state[name]))) > 3:
                            write_entry(entry, '%.3e' % state[name])
                        else:
                            write_entry(entry, '%.3f' % state[name])
                    else:
                        write_entry(entry, str(state[name]))

        self.status_label.config(text=self.experiment.status)

        # Check alarms
        for name, label in self.alarm_status_labels.items():
            if self.alarms[name].triggered:
                label.config(text="TRIGGERED" + f': {self.alarms[name].protocol.upper()}', bg='red')
            else:
                label.config(text="CLEAR", bg='green')

        # Update hold, stop and dashboard buttons
        if 'Holding' in self.experiment.status:
            self.dash_button.config(state=tk.NORMAL)
            self.hold_button.config(text='Resume')
            self.stop_button.config(text='Stop')

            self.status_frame.focus()

            for entry in self.variable_entries.values():
                entry.config(state=tk.DISABLED)

        elif 'Stopped' in self.experiment.status:
            self.dash_button.config(state=tk.NORMAL)
            self.hold_button.config(text='Hold')
            self.stop_button.config(text='Resume')

            for name, entry in self.variable_entries.items():
                if name == 'time':
                    continue
                if self.variables[name].type in ['knob', 'parameter']:
                    entry.config(state=tk.NORMAL)

        else:  # otherwise, experiment is running
            self.dash_button.config(state=tk.DISABLED)
            self.hold_button.config(text='Hold')
            self.stop_button.config(text='Stop')

            self.status_frame.focus()

            for entry in self.variable_entries.values():
                entry.config(state=tk.DISABLED)

        # Quit if experiment has ended
        if 'Terminated' in self.experiment.status:
            self.quit()

        # Plot data
        if hasattr(self, 'plotter') and len(self.experiment.data) > 0 and 'Stopped' not in self.experiment.status:
            if time.time() > self.last_plot + self.plot_interval:

                start_plot = time.perf_counter()
                self.plotter.plot()
                end_plot = time.perf_counter()
                self.last_plot = time.time()

                self.plot_interval = np.max([
                    self.plot_interval,
                    5*int(end_plot - start_plot)
                ])  # adjust interval if drawing plots takes significant time


            # Save plots
            if time.time() > self.last_save + self.save_interval and self.experiment.timestamp:

                start_save = time.perf_counter()
                self.plotter.save()
                end_save = time.perf_counter()
                self.last_save = time.time()

                self.save_interval = np.max([
                    self.save_interval,
                    5*int(end_save - start_save)
                ])  # adjust interval if saving plots takes significant time


        if not self.quitted:
            self.root.after(50, self.update)

    def open_dashboard(self):
        # Opens a window which allows the user to change variable values while the experiment is stopped
        prior_status = self.experiment.status

        self.experiment.stop()  # stop routines and measurements to avoid communication conflicts while dashboard is open

        Dashboard(self.root, self.instruments)

        # Return experiment to prior state
        if 'Holding' in prior_status:
            self.experiment.hold()
        elif 'Ready' in prior_status or 'Running' in prior_status:
            self.experiment.start()

    def toggle_hold(self):
        # User pauses/resumes the experiment

        if 'Holding' in  self.experiment.status:
            self.experiment.start()
        else:
            self.experiment.hold()

    def toggle_stop(self):
        # User stops the experiment

        if 'Stopped' in self.experiment.status:
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

    @staticmethod
    def _entry_enter(entry, variable, root):

        entry_value = entry.get()

        try:
            entry_value = float(entry_value)
        except ValueError:
            if entry_value == 'True':
                entry_value = True
            elif entry_value == 'False':
                entry_value = False

        variable.value = entry_value
        root.focus()

    @staticmethod
    def _entry_esc(entry, variable, root):
        entry.delete(0, tk.END)

        value = variable.value

        try:
            value = float(value)
        except ValueError:
            pass

        if type(value) == float:
            if value == 0:
                entry.insert(0, '0.0')
            elif np.abs(np.log10(np.abs(value))) > 3:
                entry.insert(0, '%.3e' % value)
            else:
                entry.insert(0, '%.3f' % value)
        else:
            entry.insert(0, str(value))

        root.focus()
        print(f'Escaped {entry}')


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
    Allows the user to configure instruments while running up an experiment
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
        BasicDialog.__init__(self, parent, title='Config/Test: ' + instrument.name)

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

        knobs = self.instrument.knobs
        knob_values = {knob: getattr(self.instrument, knob.replace(' ','_')) for knob in knobs}
        self.knob_entries = {}

        meters = self.instrument.meters
        self.meter_entries = {}

        label = tk.Label(master, text='Knobs', font = ("Arial", 14, 'bold'))
        label.grid(row=0, column=0, sticky=tk.W)

        label = tk.Label(master, text='Meters', font = ("Arial", 14, 'bold'))
        label.grid(row=0, column=3, sticky=tk.W)

        self.set_buttons = {}
        i = 1
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
        i = 1
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