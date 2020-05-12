import matplotlib
matplotlib.use('TkAgg')

from tkinter.filedialog import askdirectory, askopenfilename
import os
import re
import time
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable

class ProcessingError(BaseException):
    pass

class PlottingError(BaseException):
    pass

class DataHandler():

    def __init__(self, data, timestamp = None):

        self.data = data
        self.timestamp = timestamp
        self.plot_names = []
        self.figures = {}
        self.axes = {}

    def plot(self, y, x=None, **kwargs):

        colors = ['k', 'r', 'b', 'm', 'g', 'c', 'y', '0.5']
        linestyles = ['-', '--', ':']

        if len(args) < 2:
            raise PlottingError('Data to be plotted is not specified!')

        if len(args) % 2:
            raise PlottingError('The numbers of x_labels and y_labels are different!')

        plot_name = kwargs.pop('plot_name', 'Plot ' + get_timestamp())

        style = kwargs.pop('style', None)
        save = kwargs.pop('save', False)
        clear = kwargs.pop('clear', False)

        param_label = kwargs.pop('param_label', None)
        param_values = kwargs.pop('param_values', None)
        param_bounds = kwargs.pop('param_bounds', None)

        if 'figure' in kwargs and 'axes' in kwargs:
            figure = kwargs.pop('figure')
            axes = kwargs.pop('axes')
        else:
            figure, axes = plt.subplots()

        if clear:
            axes.clear()

        data_to_plot = [self.data[label] for label in labels]
        y_data_set = [self.data[ylabel] for ylabel in y]
        x_data_set = [self.data[x]]*len(y_data_set)
        data_length = len(x_data_set)

        plot_dict = {
            'averaged':self._plot_averaged,
            'errorbarr':self._plot_errorbars,
            'showparam': self._plot_showparam,
            'showorder':self._plot_showorder,
            'fastIV':self._plot_fastIV,
            None: lambda x_data, y_data, figure=None, axes=None, **kwargs: axes.plot(x_data,y_data,**kwargs)
                     }

        if style not in plot_dict:
            raise PlottingError('Given plottng style is not supported!')

        for x_data, y_data, i in zip(x_data_set, y_data_set, range(data_length)):

            subkwargs = {}  # these keywords will be passed to matplotlib
            for key, value in kwargs.items():
                if type(value) in [list, tuple]:
                    subkwargs[key] = value[i]
                else:
                    subkwargs[key] = value

            if style in ['fastIV', 'showparam']:
                subkwargs['param_label'] = param_label
                subkwargs['param_values'] = param_values
                subkwargs['param_bounds'] = param_bounds
            else:
                if 'colors' not in kwargs:
                    subkwargs['color'] = colors[i % len(colors)]
                if 'linestyles' not in kwargs:
                    subkwargs['linestyle'] = linestyles[i // len(colors)]
                if 'labels' not in kwargs and len(labels) > 2:
                    subkwargs['label'] = stylize(labels[2*i+1])+ ' vs. ' + stylize(labels[2*i])

            plot_dict[style](x_data, y_data, figure=figure, axes=axes, **subkwargs)

        axes.ticklabel_format(axis='both',style='sci', scilimits=(-3,3))
        axes.set_title(plot_name)
        axes.set_xlabel(stylize(labels[0]))
        axes.set_ylabel(stylize(labels[1]))
        axes.grid(True)

        figure.tight_layout()

        if style not in ['showparam', 'fastIV'] and len(labels)>2:
            axes.legend()

        if save:
            figure.savefig(plot_name+'.png')

        plt.pause(0.1)

        return figure, axes

    def unplot(self,*args):

        if len(args) == 0:
            plt.close('all')
        else:
            plt.close(args)

    def _plot_averaged(self, x_data, y_data, **kwargs):

        figure, axes = kwargs.pop('figure'), kwargs.pop('axes')
        x_data_averaged, y_data_averaged, _ = average_by(x_data, y_data)
        axes.plot(x_data_averaged, y_data_averaged, **kwargs)

    def _plot_errorbars(self, x_data, y_data, **kwargs):

        figure, axes = kwargs.pop('figure'), kwargs.pop('axes')
        x_data_averaged, y_data_averaged, y_data_std_err = average_by(x_data, y_data)
        axes.errorbar(x_data_averaged, y_data_averaged, yerr = y_data_std_err, **kwargs)

    def _plot_showparam(self, x_data, y_data, **kwargs):

        if 'param_values' not in kwargs:
            raise PlottingError('Parameter Values not specified with "showparam" style!')

        figure, axes = kwargs.pop('figure'), kwargs.pop('axes')

        # Color plot according to elapsed time
        colormap = 'viridis'  # Determines colormap to use for plotting timeseries data
        plt.rcParams['image.cmap'] = colormap
        cmap = plt.get_cmap('viridis')

        # Get parameter values
        s_data = kwargs.pop('param_values')

        param_label = kwargs.pop('param_label', None)
        if param_label is None:
            param_label = 'Parameter'

        # Prepare colormap
        s_bounds = kwargs.pop('param_bounds', None)
        try:
            if s_bounds == None:  # this will throw an error if s_bounds is an array
                s_bounds = [np.floor(np.amin(s_data)), np.ceil(np.amax(s_data))]
        except ValueError:
            pass

        s_min, s_max = s_bounds
        norm = plt.Normalize(vmin=s_min, vmax=s_max)

        # Add the colorbar, if the figure doesn't already have one
        try:
            figure.has_colorbar
            self.scalarmappable.set_clim(vmin=s_min, vmax=s_max)
            self.cbar.update_normal(self.scalarmappable)
            self.cbar.ax.set_ylabel(param_label)

        except AttributeError:

            self.scalarmappable = ScalarMappable(cmap=cmap, norm=norm)
            self.scalarmappable.set_array(np.linspace(s_min, s_max, 1000))

            self.cbar = plt.colorbar(self.scalarmappable, ax=axes)
            self.cbar.ax.set_ylabel(param_label)
            figure.has_colorbar = True

        # Draw the plot
        kwargs.pop('color', None)  # remove from kwargs, because it's not used here
        kwargs.pop('label', None)
        for i in range(x_data.shape[0] - 1):
            axes.plot(x_data[i: i + 2], y_data[i: i + 2], **kwargs,
                               color=cmap(norm(np.mean(s_data[i: i + 2]))))


    def _plot_showorder(self, x_data, y_data, **kwargs):

        figure, axes = kwargs.pop('figure'), kwargs.pop('axes')
        color = kwargs.pop('color','k')

        # Show arrows pointing in the direction of the scan
        axes.plot(x_data, y_data, color = color, **kwargs)
        num_points = len(x_data)
        for i in range(num_points - 1):
            axes.annotate('', xytext=(x_data[i], y_data[i]),
                               xy=(0.5 * (x_data[i] + x_data[i + 1]), 0.5 * (y_data[i] + y_data[i + 1])),
                               arrowprops=dict(arrowstyle='->', color=color))

    def _plot_fastIV(self, *args, **kwargs):

        path = args[0][0]

        fast_iv_data = pd.read_csv(path)

        voltages_swept = fast_iv_data['VOLTAGE']
        current_columns = [label for label in fast_iv_data.columns if 'CURRENT' in label]

        voltages = np.tile(voltages_swept, len(current_columns))
        currents = np.concatenate([ fast_iv_data[label] for label in current_columns ])

        if 'color' in kwargs:  # If a specific color is given, then just plot it in that color

            self._plot_showorder(voltages, currents, **kwargs)

        elif 'param_values' in kwargs:  # Often we want to indicate time (or some other parameter) associated with the IV curve

            param_values = np.array(kwargs.pop('param_values'))
            param_bounds = np.array(kwargs.pop('param_bounds', None))
            param_label = kwargs.pop('param_label', None)

            if param_label == 'Time (seconds)':
                if param_bounds[1] > 1000:
                    param_values = param_values / 60
                    param_bounds = param_bounds / 60
                    param_label = 'Time (minutes)'

                    if param_bounds[1] > 1000:
                        param_values = param_values / 60
                        param_bounds = param_bounds / 60
                        param_label = 'Time (hours)'

            self._plot_showparam(voltages, currents,
                                 param_values=np.repeat(param_values, len(voltages_swept)),
                                 param_bounds=param_bounds,
                                 param_label=param_label, **kwargs)

        else:  # Otherwise, just colorize by sweep number

            self._plot_showparam(voltages, currents,
                                 param_values=np.repeat(range(1, len(current_columns)+1), len(voltages_swept)),
                                 param_bounds=[1, len(current_columns)],
                                 param_label = 'Sweep #', **kwargs)


def average_by(x_vals, y_vals, x_tolerance=0.0):

    x_vals_unique = np.array([])
    y_vals_average = np.array([])
    y_vals_std_dev = np.array([])

    for x_val in x_vals:

        if x_val in x_vals_unique:
            continue

        x_vals_unique = np.append(x_vals_unique, x_val)

        where_same_x = np.argwhere(np.abs(np.array(x_vals) - x_val) <= x_tolerance).flatten()

        y_vals_average = np.append(y_vals_average, np.mean(np.array(y_vals)[where_same_x]))
        y_vals_std_dev = np.append(y_vals_std_dev, np.std(np.array(y_vals)[where_same_x]))

    sorting = np.argsort(x_vals_unique)

    return [x_vals_unique[sorting], y_vals_average[sorting], y_vals_std_dev[sorting]]


def stylize(label):

    common_labels = {
        'TIME': 'Time (s)',
        'V_ANODE':'$V_{anode}$ (V)',
        'V_CATHODE':'$V_{cathode}$ (V)',
        'I_ANODE':'$I_{anode}$ (A)',
        'I_CATHODE':'$I_{cathode}$ (A)',
        'anode_PHI_BAR':'$\phi_a$ (eV)',
        'cathode_PHI_BAR': '$\phi_c$ (eV)',
        'gap_D':'$d_{ca}$ (cm)',
        'cathode_T':'$T_c$ (K)',
        'anode_T':'$T_a$ (K)',
        'FAST_VOLTAGE': 'Voltage (V)',
        'FAST_CURRENT': 'Current (A)',
        'FAST_VOLTAGES':'Voltage (V)',
        'FAST_CURRENTS':'Current (A)'
    }

    common_prefixes = (
        'I','J','V','T','P'
    )

    if label in common_labels:
        return common_labels[label]

    prefix = label.split('_')[0]
    if prefix in common_prefixes:
        suffix = ('\/'.join(label.split('_')[1:])).lower()

        return '$%s_{%s}$' % (prefix, suffix)

    return label

def set_scale(axes, x_data = None, y_data = None, log_threshold = 1):

    if not x_data and not y_data:
        return None

    if x_data:

        mean_log = np.mean(np.log10(np.abs(x_data)))
        std_log = np.std(np.log10(np.abs(x_data)))

        is_multiscale_x = np.std(np.log10(x_data)) > log_threshold

        try:
            axes.is_multiscale_x = np.logical_or(axes.is_multiscale_x, is_multiscale_x)
        except AttributeError:
            axes.is_multiscale_x = is_multiscale_x

        if axes.is_multiscale_x:
            if np.sum(np.abs(x_data) - x_data) > 0:
                axes.set_xscale('symlog', linthreshx=np.power(10, mean_log - 2*std_log))
            else:
                axes.set_xscale('log')

    if y_data:

        mean_log = np.mean(np.log10(np.abs(y_data)))
        std_log = np.std(np.log10(np.abs(y_data)))

        is_multiscale_y = np.std(np.log10(y_data)) > log_threshold

        try:
            axes.is_multiscale_y = np.logical_or(axes.is_multiscale_y, is_multiscale_y)
        except AttributeError:
            axes.is_multiscale_y = is_multiscale_y

        if axes.is_multiscale_y:
            if np.sum(np.abs(y_data) - y_data) > 0:
                axes.set_yscale('symlog', linthreshy=np.power(10, mean_log - 2 * std_log))
            else:
                axes.set_yscale('log')
