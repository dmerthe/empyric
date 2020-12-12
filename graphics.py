import time
import threading
import queue
import numpy as np
import datetime
import tkinter as tk

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

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
                raise AttributeError(f"Plotting style '{style}' not recognized!")

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

        for var in y:
            if var not in self.data.columns:
                raise PlotError(f'Specified variable {var} is not in data set. Check variable names in plot specification.')

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
                        units = 'hours'
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
                    if np.max(file_data[c].values) > 60:
                        units = 'hours'
                        file_data[c] = file_data[c] / 60

            else:
                file_indices = file_data.index  # timestamps for the referenced data file
                data_indices = self.data.index  # timestamps for the main data set, can be slightly different from the file timestamps
                unique_file_indices = np.unique(file_indices).sort()
                index_map = {file_index: data_index for file_index, data_index in zip(unique_file_indices, data_indices)}
                for index in file_indices:
                    file_data[c][index] = self.data[c][index_map[index]]

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


class GUI:
    """
    GUI showing experimental progress and values of all experiment variables.
    This GUI allows the user to stop or pause the experiment.
    When paused, the user can also directly interact with instruments through the "Check" button.
    """

    def __init__(self, experiment, alarms=None, title=None):

        self.experiment = experiment

        self.paused = False

        self.variables = experiment.variables

        if alarms is None:
            self.alarms = {}
        else:
            self.alarms = alarms

        self.root = tk.Toplevel(self.parent)
        self.root.attributes("-topmost", True)

        if title:
            self.root.title(f'Experiment: {title}')
        else:
            self.root.title('Experiment')

        tk.Label(self.root, text='Status:').grid(row=0, column=0, sticky=tk.E)

        self.status_label = tk.Label(self.root, text='', width=40, relief=tk.SUNKEN)
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

        if len(alarms) > 0:
            self.alarm_status_labels = {}

            for alarm in self.alarms:
                tk.Label(self.root, text=alarm, width=len(alarm), anchor=tk.E).grid(row=i, column=0, sticky=tk.E)

                self.alarm_status_labels[alarm] = tk.Label(self.root, text='', relief=tk.SUNKEN, width=40)
                self.alarm_status_labels[alarm].grid(row=i, column=1, columnspan=2, sticky=tk.W)

                i += 1

            tk.Label(self.root, text='', font=("Arial", 14, 'bold')).grid(row=i, column=0, sticky=tk.E)


        self.dash_button = tk.Button(self.root, text='Dashboard...', font=("Arial", 14, 'bold'), command=self.open_dashboard, width=22, state=tk.DISABLED)
        self.dash_button.grid(row=i + 1, column=2)

        self.pause_button = tk.Button(self.root, text='Pause', font=("Arial", 14, 'bold'), command=self.toggle_pause, width=10)
        self.pause_button.grid(row=i + 1, column=1)

        self.stop_button = tk.Button(self.root, text='Stop', font=("Arial", 14, 'bold'), command=self.user_stop, width=10)
        self.stop_button.grid(row=i + 1, column=0)

    def update(self):

        # Check the state of the experiment
        state = self.experiment.state
        for name, label in self.variable_status_labels.items():

            if name.lower() == 'time':
                label.config(text=str(datetime.timedelta(seconds=state[name])))
            else:
                label.config(text=str(state[name]))

        self.status_label.config(text=self.experiment.status)

        if self.alarms:
            for name, label in self.alarm_status_labels.items():
                label.config(text=str(self.alarms[name]._signal))

        # Check if experiment is paused and update pause/resume button
        if self.experiment.status == self.experiment.PAUSED:
            self.paused = True
            self.pause_button.config(text='Resume')
            self.dash_button.config(state=tk.NORMAL)
        elif self.experiment.status == self.experiment.RUNNING:
            self.paused = False
            self.pause_button.config(text='Pause')
            self.dash_button.config(state=tk.DISABLED)

        #self.root.lift()
        self.root.after(100, self.update)

    def open_dashboard(self):
        # Opens a window which allows the user to change variable values when the experiment is paused
        pass

    def toggle_pause(self):

        if self.paused:
            self.experiment.start()
            self.pause_button.config(text='Pause')
            self.dash_button.config(state=tk.DISABLED)
        else:
            self.experiment.stop()
            self.pause_button.config(text='Resume')
            self.dash_button.config(state=tk.NORMAL)

        self.paused = not self.paused

    def user_stop(self):

        self.experiment.terminate()
        self.root.after(3000, self.root.destroy)

    def run(self):

        self.update()
        self.root.mainloop()
