import numbers
import os.path
import time
import sys
import numpy as np
import datetime
import tkinter as tk
import pandas as pd

from empyric.tools import recast
from empyric.routines import Server

if sys.platform == 'darwin':
    import matplotlib

    matplotlib.use('TkAgg')  # works better on MacOS

import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
import matplotlib.dates as mdates

from pandas.plotting import register_matplotlib_converters

register_matplotlib_converters()


# needed for converting Pandas datetimes for matplotlib


class Plotter:
    """
    Handler for plotting data based on the runcard plotting settings and data
    context.

    Argument must be a pandas DataFrame with a 'time' column and datetime
    indices.

    The optional settings keyword argument is given in the form,
    {...,
    plot_name:
    {'x': x_name, 'y': [y_name1, y_name2,...], 'style': plot_style, ...} ,
    ...}

    where plot_name is the user designated title for the plot, x_name, y_name_1,
    y_name2, etc. are columns in the DataFrame, and plot_style is either 'basic'
    (default), 'log', 'symlog', 'averaged', 'errorbars' or 'parametric'.
    """

    # For using datetimes on x-axis
    date_locator = mdates.AutoDateLocator()
    date_formatter = mdates.ConciseDateFormatter(date_locator)

    def __init__(self, data, settings=None):
        """
        Plot data based on settings

        :param data: (pandas.Dataframe) data to be plotted.
        :param settings: (dict) dictionary of plot settings
        """

        self.data = data
        self.full_data = self.numericize(data)

        self.plotted = []

        if settings:
            self.settings = settings
        else:
            self.settings = {'Plot': {'x': 'Time', 'y': data.columns}}

        self.plots = {}
        for plot_name in settings:
            self.plots[plot_name] = plt.subplots(
                constrained_layout=True, figsize=(5, 4)
            )

    def save(self, plot_name=None, save_as=None):
        """Save the plots to PNG files in the working directory"""

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
        """
        If the plot_name keyword argument is specified, close the corresponding
        plot. Otherwise, close all plots.
        """

        self.save()

        if plot_name:
            fig, _ = self.plots[plot_name]
            plt.close(fig)
        else:
            plt.close('all')

    def plot(self):
        """Plot all plots"""

        # Update full data
        new_indices = np.setdiff1d(self.data.index, self.full_data.index)
        self.full_data = pd.concat(
            [self.full_data, self.numericize(self.data.loc[new_indices])]
        )

        # Make the plots, by name and style

        for name, settings in self.settings.items():

            style = settings.get('style', 'basic')

            if style == 'basic':
                self._plot_basic(name)
            elif style == 'averaged':
                self._plot_basic(name, averaged=True)
            elif style == 'errorbars':
                self._plot_basis(name, errorbars=True)
            elif style == 'parametric':
                self._plot_parametric(name)
            else:
                raise AttributeError(
                    f"Plotting style '{style}' not recognized!"
                )

    def _plot_basic(self, name, averaged=False, errorbars=False):
        """Make a simple plot, (possibly multiple) y vs. x"""

        fig, ax = self.plots[name]

        x = self.settings[name].get('x', 'Time')
        ys = np.array([self.settings[name]['y']]).flatten()

        not_in_data = np.setdiff1d(np.concatenate([[x], ys]), self.data.columns)
        if not_in_data.size > 0:
            raise AttributeError(
                f'{", ".join(not_in_data)} specified for plotting, '
                'but not in variables!'
            )

        if averaged or errorbars:

            grouped_data = self.full_data.groupby(x)
            averaged_data = grouped_data.mean()
            xdata = averaged_data[x]
            ydata = averaged_data[ys]

            if errorbars:
                ystddata = grouped_data.std()[ys]

        else:

            if x == 'Time':
                xdata = self.full_data.index
            else:
                xdata = self.full_data[x].astype(float)

            ydata = self.full_data[ys].astype(float)

        if ax.lines and not errorbars:
            # For simple plots (i.e. not error bar plots), if already plotted,
            # simply update the plot data and axes

            for line, y in zip(ax.lines, ys):
                line.set_data(xdata, ydata[y])
                ax.draw_artist(line)

            ax.relim()  # reset plot limits based on data
            ax.autoscale_view()

            fig.canvas.draw_idle()
            fig.canvas.start_event_loop(0.01)

        else:  # draw a new plot

            plot_kwargs = self.settings[name].get('configure', {})
            # kwargs for matplotlib

            plot_kwargs = {
                key: np.array([value]).flatten()
                for key, value in plot_kwargs.items()
            }

            if len(ys) > 1:  # a legend will be made
                plot_kwargs['label'] = ys

            xscale = self.settings[name].get('x scale', 'linear')
            yscale = self.settings[name].get('y scale', 'linear')

            if x == 'Time':
                ax.xaxis.set_major_locator(self.date_locator)
                ax.xaxis.set_major_formatter(self.date_formatter)

            for i, y in enumerate(ys):

                plot_kwargs_i = {
                    key: value[i] for key, value in plot_kwargs.items()
                }

                if errorbars:
                    ax.errorbar(
                        xdata, ydata[y], yerr=ystddata[y], **plot_kwargs_i
                    )
                else:
                    ax.plot(xdata, ydata[y], **plot_kwargs_i)

            if x == 'Time':
                pass
                # axis is automatically configured for datetimes; do not modify
            elif xscale == 'linear':
                try:
                    ax.ticklabel_format(
                        axis='x', style='sci', scilimits=(-2, 4)
                    )
                except AttributeError:
                    pass
            elif type(xscale) == dict:
                for scale, options in xscale.items():
                    ax.set_xscale(scale, **options)
            else:
                ax.set_xscale(xscale)

            if yscale == 'linear':
                try:
                    ax.ticklabel_format(
                        axis='y', style='sci', scilimits=(-2, 4)
                    )
                except AttributeError:
                    pass
            elif type(yscale) == dict:
                for scale, options in yscale.items():
                    ax.set_yscale(scale, **options)
            else:
                ax.set_yscale(yscale)

            ax.set_title(name)
            ax.tick_params(labelsize='small')
            ax.grid()

            if len(ys) > 1:
                ax.legend()

            if x != 'Time':
                ax.set_xlabel(self.settings[name].get('xlabel', x))
            ax.set_ylabel(self.settings[name].get('ylabel', ys[0]))

            plt.pause(0.01)

    def _plot_parametric(self, name):
        """Make a parametric plot of x and y against a third parameter"""

        fig, ax = self.plots[name]

        x = self.settings[name]['x']
        y = np.array([self.settings[name]['y']]).flatten()[0]
        s = self.settings[name].get('s', 'Time')

        not_in_data = np.setdiff1d([x, y, s], self.data.columns)
        if not_in_data.size > 0:
            raise AttributeError(
                f'{", ".join(not_in_data)} specified for plotting, '
                'but not in variables!'
            )

        xdata = self.full_data[x]
        ydata = self.full_data[y]
        sdata = self.full_data[s]

        if s == 'Time':  # Rescale time if values are large
            units = 'seconds'
            if np.max(sdata) > 60:
                units = 'minutes'
                sdata = sdata / 60
                if np.max(sdata) > 60:
                    units = 'hours'
                    sdata = sdata / 60

        s_min, s_max = np.min(sdata), np.max(sdata)
        norm = plt.Normalize(vmin=s_min, vmax=s_max)

        colormap = 'viridis'
        plt.rcParams['image.cmap'] = colormap
        cmap = plt.get_cmap('viridis')

        plot_kwargs = self.settings[name].get('configure', {})
        # kwargs for matplotlib

        if not hasattr(fig, 'cbar'):  # draw a new plot

            for i in range(len(xdata) - 1):
                ax.plot(
                    xdata[i: i + 2], ydata[i: i + 2],
                    color=cmap(norm(sdata[i])),
                    **plot_kwargs
                )

            fig.scalarmappable = ScalarMappable(cmap=cmap, norm=norm)
            fig.scalarmappable.set_array(np.linspace(s_min, s_max, 1000))
            fig.cbar = plt.colorbar(fig.scalarmappable, ax=ax)

            xscale = self.settings[name].get('x scale', 'linear')
            yscale = self.settings[name].get('y scale', 'linear')

            if xscale == 'linear':
                ax.ticklabel_format(axis='x', style='sci', scilimits=(-2, 4))
            elif type(xscale) == dict:
                for scale, options in xscale.items():
                    ax.set_xscale(scale, **options)
            else:
                ax.set_xscale(xscale)

            if yscale == 'linear':
                ax.ticklabel_format(axis='y', style='sci', scilimits=(-2, 4))
            elif type(yscale) == dict:
                for scale, options in yscale.items():
                    ax.set_yscale(scale, **options)
            else:
                ax.set_yscale(yscale)

            ax.set_title(name)
            ax.grid(True)
            ax.tick_params(labelsize='small')
            ax.set_xlabel(self.settings[name].get('xlabel', x))
            ax.set_ylabel(self.settings[name].get('ylabel', y))
            if s == 'Time':
                fig.cbar.ax.set_ylabel('Time ' + f" ({units})")
            else:
                fig.cbar.ax.set_ylabel(s)

            fig.cbar.ax.tick_params(labelsize='small')

            fig.get_layout_engine().execute(fig)

            plt.pause(0.01)

        else:  # if already plotted, update the plot data and axes

            # update color bar
            fig.scalarmappable.set_clim(vmin=s_min, vmax=s_max)
            fig.cbar.update_normal(fig.scalarmappable)

            # update_normal method above removes the colorbar's ylabel;
            # redraw it
            if s == 'Time':
                fig.cbar.ax.set_ylabel('Time ' + f" ({units})")
            else:
                fig.cbar.ax.set_ylabel(s)

            # update colors of existing line segments
            for i, line in enumerate(ax.lines):
                line.set_color(cmap(norm(sdata[i])))
                ax.draw_artist(line)

            # plot new line segments
            for i in range(len(ax.lines) - 1, len(xdata) - 1):
                ax.plot(
                    xdata[i: i + 2], ydata[i: i + 2],
                    color=cmap(norm(sdata[i])),
                    **plot_kwargs
                )

            ax.relim()
            ax.autoscale_view()

            fig.canvas.draw_idle()
            fig.canvas.start_event_loop(0.01)

    @staticmethod
    def numericize(data):
        """
        Convert a DataFrame, possibly containing lists or paths,
        such that all elements are numeric
        """

        indices = data.index
        labels = data.columns

        data_array = data.values

        numerical_indices = []
        numerical_array = [[]] * len(labels)

        # Iterate through each row and expand any files or lists into columns
        for index, row in zip(indices, data_array):

            columns = []
            max_len = 0  # maximum length of columns
            for i, element in enumerate(row):

                if type(element) == str and os.path.isfile(element):
                    expanded_element = list(
                        pd.read_csv(element)[labels[i]].values
                    )

                elif np.ndim(element) == 1:

                    expanded_element = list(element)

                    expanded_element = [
                        value if value is not None else np.nan
                        for value in expanded_element
                    ]

                else:
                    if element is None:
                        element = np.nan

                    expanded_element = [element]

                max_len = np.max([len(expanded_element), max_len])

                columns.append(expanded_element)

            numerical_indices = numerical_indices + [index] * max_len
            for i, column in enumerate(columns):
                new_elements = column + [np.nan] * (max_len - len(column))
                numerical_array[i] = numerical_array[i] + new_elements

        numerical_data = pd.DataFrame(
            data=np.array(numerical_array).T,
            columns=labels,
            index=numerical_indices
        )

        return numerical_data


class ExperimentGUI:
    """
    GUI showing experimental progress, values of all experiment variables and
    any alarms, and managing plotting data via the Plotter class.

    This GUI allows the user to hold, stop and terminate the experiment. When
    stopped, the user can change the values of knob and parameter variables,
    and also directly interact with instruments through the Dashboard.
    """

    def __init__(self, experiment, title=None, **kwargs):

        self.experiment = experiment

        if title:
            self.title = title
        else:
            self.title = 'Empyric'

        self.closed = False  # has the GUI been closed?

        self.variables = experiment.variables

        if 'alarms' in kwargs:
            self.alarms = {}
        else:
            self.alarms = kwargs['alarms']

        if 'instruments' in kwargs:
            self.instruments = kwargs['instruments']
        else:
            # If instruments are not specified,
            # get them from the experiment variables
            self.instruments = {}
            for variable in self.experiment.variables.values():
                if variable.type in ['meter', 'knob']:
                    instrument = variable.instrument
                    if instrument.name not in self.instruments:
                        self.instruments[instrument.name] = instrument

        if 'plots' in kwargs or 'plotter' in kwargs:
            if 'plotter' in kwargs:
                self.plotter = kwargs['plotter']
            else:
                self.plotter = Plotter(experiment.data, kwargs['plots'])

            self.plot_interval = kwargs.get('plot_interval', 0)
            # grows if plotting takes longer

            self.last_plot = float('-inf')

            # Set interval for saving plots
            self.save_interval = kwargs.get('save_interval', 0)

            self.last_save = time.time()

        self.root = tk.Tk()
        self.root.lift()
        self.root.wm_attributes('-topmost', True)  # bring window to front
        self.root.protocol("WM_DELETE_WINDOW", self.end)

        self.root.title(self.title)
        self.root.resizable(False, False)

        self.status_frame = tk.Frame(self.root)
        self.status_frame.grid(row=0, column=0, columnspan=2)

        i = 0
        title = kwargs.get('title', 'Experiment')

        tk.Label(
            self.status_frame, text=title, font=("Arial", 14, 'bold')
        ).grid(row=i, column=1)

        # Status field shows current experiment status
        i += 1
        tk.Label(
            self.status_frame, text='Status', width=len('Status'), anchor=tk.E
        ).grid(row=i, column=0, sticky=tk.E)

        self.status_label = tk.Label(
            self.status_frame, text='', width=30, relief=tk.SUNKEN
        )
        self.status_label.grid(row=i, column=1, sticky=tk.W, padx=10)

        # Table of variables shows most recently measured/set variable values
        self.variable_entries = {}
        self._entry_enter_funcs = {}  # container for enter press event handlers
        self._entry_esc_funcs = {}  # container for esc press event handlers

        i += 1
        tk.Label(
            self.status_frame, text='', font=("Arial", 14, 'bold')
        ).grid(row=i, column=0, sticky=tk.E)

        i += 1
        tk.Label(
            self.status_frame, text='Variables', font=("Arial", 14, 'bold')
        ).grid(row=i, column=1)

        i += 1
        tk.Label(
            self.status_frame, text='Run Time', width=len('Run Time'),
            anchor=tk.E
        ).grid(row=i, column=0, sticky=tk.E)

        self.variable_entries['Time'] = tk.Entry(
            self.status_frame, state='readonly', disabledforeground='black',
            width=30
        )
        self.variable_entries['Time'].grid(
            row=i, column=1, sticky=tk.W, padx=10
        )

        i += 1
        for name in self.variables:
            tk.Label(
                self.status_frame, text=name, width=len(name), anchor=tk.E
            ).grid(row=i, column=0, sticky=tk.E)

            self.variable_entries[name] = tk.Entry(
                self.status_frame, state='readonly', disabledforeground='black',
                width=30
            )
            self.variable_entries[name].grid(
                row=i, column=1, sticky=tk.W, padx=10
            )

            if self.variables[name].settable:
                entry = self.variable_entries[name]
                variable = self.variables[name]
                root = self.status_frame

                enter_func = \
                    lambda event, entry=entry, variable=variable, root=root: \
                        self._entry_enter(entry, variable, root)

                self._entry_enter_funcs[name] = enter_func
                self.variable_entries[name].bind(
                    '<Return>', self._entry_enter_funcs[name]
                )

                esc_func = \
                    lambda event, entry=entry, variable=variable, root=root: \
                        self._entry_esc(entry, variable, root)

                self._entry_esc_funcs[name] = esc_func
                self.variable_entries[name].bind(
                    '<Escape>', self._entry_esc_funcs[name]
                )

            i += 1

        tk.Label(
            self.status_frame, text='', font=("Arial", 14, 'bold')
        ).grid(row=i, column=0, sticky=tk.E)

        # Table of alarm indicators shows the status of any alarms monitored
        self.alarm_status_labels = {}

        if len(self.alarms) > 0:

            i += 1
            tk.Label(
                self.status_frame, text='Alarms', font=("Arial", 14, 'bold')
            ).grid(row=i, column=1)

            i += 1
            for alarm in self.alarms:
                tk.Label(
                    self.status_frame, text=alarm, width=len(alarm),
                    anchor=tk.E
                ).grid(row=i, column=0, sticky=tk.E)

                self.alarm_status_labels[alarm] = tk.Label(
                    self.status_frame, text='Clear', relief=tk.SUNKEN, width=30
                )
                self.alarm_status_labels[alarm].grid(
                    row=i, column=1, sticky=tk.W, padx=10
                )

                i += 1

            tk.Label(
                self.status_frame, text='', font=("Arial", 14, 'bold')
            ).grid(row=i, column=0, sticky=tk.E)

        # Servers
        self.servers = {
            name: routine for name, routine in self.experiment.routines.items()
            if isinstance(routine, Server)
        }

        if self.servers:

            self.server_status_labels = {}

            tk.Label(
                self.status_frame, text='Servers', font=("Arial", 14, 'bold')
            ).grid(row=i, column=1)

            i += 1
            for server in self.servers:

                tk.Label(
                    self.status_frame, text=server, width=len(server),
                    anchor=tk.E
                ).grid(row=i, column=0, sticky=tk.E)

                ip_address = self.servers[server].ip_address
                port = self.servers[server].port

                # Make entry so text is selectable
                self.server_status_labels[server] = tk.Entry(
                    self.status_frame, disabledforeground='black',
                )

                self.server_status_labels[server].insert(
                    0, f'{ip_address}::{port}'
                )
                self.server_status_labels[server].config(state='readonly')

                self.server_status_labels[server].grid(
                    row=i, column=1, sticky=tk.W, padx=10
                )

                i += 1

        # Buttons (root is not self.status_frame, so indexing starts at 1)
        i = 1
        self.dash_button = tk.Button(
            self.root, text='Dashboard', font=("Arial", 14, 'bold'), width=10,
            command=self.open_dashboard, state=tk.DISABLED
        )
        self.dash_button.grid(row=i, column=0, sticky=tk.W)

        self.hold_button = tk.Button(
            self.root, text='Hold', font=("Arial", 14, 'bold'), width=10,
            command=self.toggle_hold
        )
        self.hold_button.grid(row=i + 1, column=0, sticky=tk.W)

        self.stop_button = tk.Button(
            self.root, text='Stop', font=("Arial", 14, 'bold'), width=10,
            command=self.toggle_stop
        )
        self.stop_button.grid(row=i + 2, column=0, sticky=tk.W)

        self.terminate_button = tk.Button(
            self.root, text='Terminate', font=("Arial", 14, 'bold'), width=10,
            fg='red', bg='gray87', command=self.end, height=5
        )
        self.terminate_button.grid(row=i, column=1, sticky=tk.E, rowspan=3)

    def run(self):
        """Starts the Tkinter mainloop and the experiment update loop"""
        self.update()
        self.root.mainloop()

    def update(self):
        """Updates the GUI based on the state of the experiment"""

        if self.closed:
            return  # don't update GUI if it no longer exists

        # Allow window to fall back once things get started
        self.root.wm_attributes('-topmost', False)

        state = self.experiment.state

        # Update all variable entries based on experiment state
        for name, entry in self.variable_entries.items():

            # If stopped or holding allow user to edit knobs or parameters
            if self.experiment.stopped or self.experiment.holding:
                if name != 'Time' and self.variables[name].settable:
                    continue

            def write_entry(_entry, text):
                _entry.config(state=tk.NORMAL)
                _entry.delete(0, tk.END)
                _entry.insert(0, text)
                _entry.config(state=tk.DISABLED)

            if state[name] is None:
                write_entry(entry, 'None')
            elif state[name] == np.nan:
                write_entry(entry, 'NaN')
            else:
                if name == 'Time':
                    write_entry(
                        entry, str(datetime.timedelta(seconds=state['Time']))
                    )
                else:
                    if isinstance(state[name], numbers.Number):
                        # display numbers neatly
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
                protocol = self.alarms[name].protocol
                if protocol == 'none':
                    label.config(text='TRIGGERED: NO PROTOCOL', bg='red')
                else:
                    label.config(
                        text='TRIGGERED' + f': {protocol.upper()}', bg='red'
                    )
            else:
                label.config(text="CLEAR", bg='green')

        # Update hold, stop and dashboard buttons
        if self.experiment.holding or self.experiment.stopped:
            self.dash_button.config(state=tk.NORMAL)

            if self.experiment.holding:
                self.hold_button.config(text='Resume')
                self.stop_button.config(text='Stop')
            else:
                self.hold_button.config(text='Hold')
                self.stop_button.config(text='Resume')

            # Settable variable values can be edited
            for name, entry in self.variable_entries.items():
                if name != 'Time' and self.variables[name].settable:
                    entry.config(state=tk.NORMAL)

        else:  # otherwise, experiment is running
            self.dash_button.config(state=tk.DISABLED)
            self.hold_button.config(text='Hold')
            self.stop_button.config(text='Stop')

            for entry in self.variable_entries.values():
                entry.config(state=tk.DISABLED)

        # Quit if experiment has ended
        if self.experiment.terminated:
            self.quit()

        # Plot data
        has_plotter = hasattr(self, 'plotter')
        has_data = len(self.experiment.data) > 0
        not_stopped = not self.experiment.stopped
        if has_plotter and has_data and not_stopped:
            if time.time() > self.last_plot + self.plot_interval:
                start_plot = time.perf_counter()
                self.plotter.plot()
                end_plot = time.perf_counter()
                self.last_plot = time.time()

                self.plot_interval = np.max([
                    self.plot_interval,
                    5 * int(end_plot - start_plot)
                ])  # adjust interval if drawing plots takes significant time

            # Save plots
            saving_needed = time.time() > self.last_save + self.save_interval
            if saving_needed and self.experiment.timestamp:
                start_save = time.perf_counter()
                self.plotter.save()
                end_save = time.perf_counter()
                self.last_save = time.time()

                self.save_interval = np.max([
                    self.save_interval,
                    5 * int(end_save - start_save)
                ])  # adjust interval if saving plots takes significant time

        if not self.closed:
            self.root.after(50, self.update)

    def open_dashboard(self):
        """
        When the user hits the Dashboard button, open a window which allows
        the user to interact with instruments while the experiment is paused or
        stopped.
        """

        prior_status = self.experiment.status

        self.experiment.stop()
        # stop routines and measurements to avoid communication conflicts
        # while dashboard is open

        Dashboard(self.root, self.instruments)

        # Return experiment to prior state
        if 'Holding' in prior_status:
            self.experiment.hold()
        elif 'Ready' in prior_status or 'Running' in prior_status:
            self.experiment.start()

    def toggle_hold(self):
        """User pauses/resumes the experiment through the Hold/Resume button."""

        if self.experiment.holding:
            self.experiment.start()
        else:
            self.experiment.hold()

    def toggle_stop(self):
        """User stops the experiment through the Stop button."""

        if self.experiment.stopped:
            self.experiment.start()
        else:
            self.experiment.stop()

    def end(self):
        """
        User terminates the experiment and closes the GUI with the Terminate
        button; cancels any experiment follow-ups.
        """

        self.experiment.terminate(reason='user terminated')
        self.quit()

    def quit(self):

        if hasattr(self, 'plotter'):
            self.plotter.close()

        self.status_label.config(text=self.experiment.TERMINATED)

        self.closed = True
        plt.pause(0.1)  # give GUI and plotter enough time to wrap up
        self.root.update()

        self.root.destroy()
        self.root.quit()

    @staticmethod
    def _entry_enter(entry, variable, root):
        """Assigns the value to a variable if entered by the user"""

        variable.value = recast(entry.get())
        root.focus()

    @staticmethod
    def _entry_esc(entry, variable, root):
        """Restores the value of a variable to an entry if user escapes entry"""
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

        w = tk.Button(
            box, text="OK", width=10, command=self.ok, default=tk.ACTIVE
        )
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
        tk.Label(
            master, text='Instruments:', font=('Arial', 14), justify=tk.LEFT
        ).grid(row=0, column=0, sticky=tk.W)

        i = 1

        self.instrument_labels = {}
        self.config_buttons = {}

        for name, instrument in self.instruments.items():
            instrument_label = tk.Label(master, text=name)
            instrument_label.grid(row=i, column=0)

            self.instrument_labels[name] = instrument_label

            config_button = tk.Button(
                master, text='Config/Test',
                command=lambda instr=instrument: self.config(instr)
            )
            config_button.grid(row=i, column=1)

            self.config_buttons[name] = config_button

            i += 1

    def config(self, instrument):
        dialog = ConfigTestDialog(self, instrument)


class ConfigTestDialog(BasicDialog):
    """
    Dialog box for setting knobs and checking meters.
    Allows the user to quickly access basic instrument functionality as well as
    configure instrument for an experiment.
    """

    def __init__(self, parent, instrument):

        self.instrument = instrument
        BasicDialog.__init__(
            self, parent, title='Config/Test: ' + instrument.name
        )

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
        knob_values = {
            knob: getattr(self.instrument, knob.replace(' ', '_'))
            for knob in knobs
        }
        self.knob_entries = {}

        meters = self.instrument.meters
        self.meter_entries = {}

        label = tk.Label(master, text='Knobs', font=("Arial", 14, 'bold'))
        label.grid(row=0, column=0, sticky=tk.W)

        label = tk.Label(master, text='Meters', font=("Arial", 14, 'bold'))
        label.grid(row=0, column=3, sticky=tk.W)

        self.set_buttons = {}
        i = 1
        for knob in knobs:
            formatted_name = ' '.join(
                [word[0].upper() + word[1:] for word in knob.split(' ')]
            )

            label = tk.Label(master, text=formatted_name)
            label.grid(row=i, column=0, sticky=tk.W)

            self.knob_entries[knob] = tk.Entry(master)
            self.knob_entries[knob].grid(row=i, column=1)
            self.knob_entries[knob].insert(0, str(knob_values[knob]))

            self.set_buttons[knob] = tk.Button(
                master, text='Set',
                command=lambda knob=knob: self.apply_knob_entry(knob)
            )
            self.set_buttons[knob].grid(row=i, column=2)

            i += 1

        self.measure_buttons = {}
        i = 1
        for meter in meters:
            formatted_name = ' '.join(
                [word[0].upper() + word[1:] for word in meter.split(' ')]
            )

            label = tk.Label(master, text=formatted_name)
            label.grid(row=i, column=3, sticky=tk.W)

            self.meter_entries[meter] = tk.Entry(master)
            self.meter_entries[meter].grid(row=i, column=4)
            self.meter_entries[meter].insert(0, '???')
            self.meter_entries[meter].config(state='readonly')

            self.measure_buttons[meter] = tk.Button(
                master, text='Measure',
                command=lambda meter=meter: self.update_meter_entry(meter)
            )
            self.measure_buttons[meter].grid(row=i, column=5)

            i += 1
