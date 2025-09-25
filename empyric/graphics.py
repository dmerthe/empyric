import asyncio
import numbers
import os.path
import time
import sys
import numpy as np
import datetime
import tkinter as tk
import pandas as pd
import pandas.errors
from nicegui import ui, app, binding

from empyric.types import recast, Type, Float, String, Toggle
from empyric.routines import SocketServer, ModbusServer, supported as supported_routines

import matplotlib
if sys.platform == "darwin":
    matplotlib.use("TkAgg")  # works better on macOS

import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
import matplotlib.dates as mdates

from pandas.plotting import register_matplotlib_converters

register_matplotlib_converters()
# needed for converting Pandas datetimes for matplotlib

# OLD
# class Plotter:
#     """
#     Handler for plotting data based on the runcard plotting settings and data
#     context.
#
#     Argument must be a pandas DataFrame with a 'time' column and datetime
#     indices.
#
#     The optional settings keyword argument is given in the form,
#     {...,
#     plot_name:
#     {'x': x_name, 'y': [y_name1, y_name2,...], 'style': plot_style, ...} ,
#     ...}
#
#     where plot_name is the user designated title for the plot, x_name, y_name_1,
#     y_name2, etc. are columns in the DataFrame, and plot_style is either 'basic'
#     (default), 'log', 'symlog', 'averaged', 'errorbars' or 'parametric'.
#     """
#
#     # For using datetimes on x-axis
#     date_locator = mdates.AutoDateLocator()
#     date_formatter = mdates.ConciseDateFormatter(date_locator)
#
#     def __init__(self, data, settings=None):
#         """
#         Plot data based on settings
#
#         :param data: (pandas.Dataframe) data to be plotted.
#         :param settings: (dict) dictionary of plot settings
#         """
#
#         self.data = data
#         self.full_data = self.numericize(data)
#
#         self.plotted = []
#
#         if settings:
#             self.settings = settings
#         else:
#             self.settings = {"Plot": {"x": "Time", "y": data.columns}}
#
#         self.plots = {}
#         for plot_name in settings:
#             self.plots[plot_name] = plt.subplots(
#                 constrained_layout=True, figsize=(5, 4)
#             )
#
#     def save(self, plot_name=None, save_as=None):
#         """Save the plots to PNG files in the working directory"""
#
#         if plot_name:
#             fig, ax = self.plots[plot_name]
#             if save_as:
#                 fig.savefig(save_as + ".png")
#             else:
#                 fig.savefig(plot_name + ".png")
#         else:
#             for name, plot in self.plots.items():
#                 fig, ax = plot
#                 fig.savefig(name + ".png")
#
#     def close(self, plot_name=None):
#         """
#         If the plot_name keyword argument is specified, close the corresponding
#         plot. Otherwise, close all plots.
#         """
#
#         self.save()
#
#         if plot_name:
#             fig, _ = self.plots[plot_name]
#             plt.close(fig)
#         else:
#             plt.close("all")
#
#     def plot(self):
#         """Plot all plots"""
#
#         # Update full data
#         new_indices = np.setdiff1d(self.data.index, self.full_data.index)
#         self.full_data = pd.concat(
#             [self.full_data, self.numericize(self.data.loc[new_indices])]
#         )
#
#         # Make the plots, by name and style
#
#         for name, settings in self.settings.items():
#             style = settings.get("style", "basic")
#
#             if style == "basic":
#                 self._plot_basic(name)
#             elif style == "averaged":
#                 self._plot_basic(name, averaged=True)
#             elif style == "errorbars":
#                 self._plot_basic(name, errorbars=True)
#             elif style == "parametric":
#                 self._plot_parametric(name)
#             else:
#                 raise AttributeError(f"Plotting style '{style}' not recognized!")
#
#     def _plot_basic(self, name, averaged=False, errorbars=False):
#         """Make a simple plot, (possibly multiple) y vs. x"""
#
#         fig, ax = self.plots[name]
#
#         x = self.settings[name].get("x", "Time")
#         ys = np.array([self.settings[name]["y"]]).flatten()
#
#         not_in_data = np.setdiff1d(np.concatenate([[x], ys]), self.data.columns)
#         if not_in_data.size > 0:
#             raise AttributeError(
#                 f'{", ".join(not_in_data)} specified for plotting, '
#                 "but not in variables!"
#             )
#
#         if averaged or errorbars:
#             grouped_data = self.full_data.groupby(x)
#             averaged_data = grouped_data.mean()
#             xdata = averaged_data[x]
#             ydata = averaged_data[ys]
#
#             if errorbars:
#                 ystddata = grouped_data.std()[ys]
#
#         else:
#             if x == "Time":
#                 xdata = self.full_data.index
#             else:
#                 xdata = self.full_data[x].astype(float)
#
#             ydata = self.full_data[ys].astype(float)
#
#         if ax.lines and not errorbars:
#             # For simple plots (i.e. not error bar plots), if already plotted,
#             # simply update the plot data and axes
#
#             for line, y in zip(ax.lines, ys):
#                 line.set_data(xdata, ydata[y])
#                 ax.draw_artist(line)
#
#             ax.relim()  # reset plot limits based on data
#             ax.autoscale_view()
#
#             fig.canvas.draw_idle()
#             fig.canvas.start_event_loop(0.01)
#
#         else:  # draw a new plot
#             plot_kwargs = self.settings[name].get("configure", {})
#             # kwargs for matplotlib
#
#             plot_kwargs = {
#                 key: np.array([value]).flatten() for key, value in plot_kwargs.items()
#             }
#
#             if len(ys) > 1:  # a legend will be made
#                 plot_kwargs["label"] = ys
#
#             xscale = self.settings[name].get("xscale", "linear")
#             yscale = self.settings[name].get("yscale", "linear")
#
#             if x == "Time":
#                 ax.xaxis.set_major_locator(self.date_locator)
#                 ax.xaxis.set_major_formatter(self.date_formatter)
#
#             for i, y in enumerate(ys):
#                 plot_kwargs_i = {key: value[i] for key, value in plot_kwargs.items()}
#
#                 if errorbars:
#                     ax.errorbar(xdata, ydata[y], yerr=ystddata[y], **plot_kwargs_i)
#                 else:
#                     ax.plot(xdata, ydata[y], **plot_kwargs_i)
#
#             if x == "Time":
#                 pass
#                 # axis is automatically configured for datetimes; do not modify
#             elif xscale == "linear":
#                 try:
#                     ax.ticklabel_format(axis="x", style="sci", scilimits=(-2, 4))
#                 except AttributeError:
#                     pass
#             elif type(xscale) == dict:
#                 for scale, options in xscale.items():
#                     ax.set_xscale(scale, **options)
#             else:
#                 ax.set_xscale(xscale)
#
#             if yscale == "linear":
#                 try:
#                     ax.ticklabel_format(axis="y", style="sci", scilimits=(-2, 4))
#                 except AttributeError:
#                     pass
#             elif type(yscale) == dict:
#                 for scale, options in yscale.items():
#                     ax.set_yscale(scale, **options)
#             else:
#                 ax.set_yscale(yscale)
#
#             ax.set_title(name)
#             ax.tick_params(labelsize="small")
#             ax.grid()
#
#             if len(ys) > 1:
#                 ax.legend()
#
#             if x != "Time":
#                 ax.set_xlabel(self.settings[name].get("xlabel", x))
#             ax.set_ylabel(self.settings[name].get("ylabel", ys[0]))
#
#             plt.pause(0.01)
#
#     def _plot_parametric(self, name):
#         """Make a parametric plot of x and y against a third parameter"""
#
#         fig, ax = self.plots[name]
#
#         x = self.settings[name]["x"]
#         y = np.array([self.settings[name]["y"]]).flatten()[0]
#         s = self.settings[name].get("s", "Time")
#
#         not_in_data = np.setdiff1d([x, y, s], self.data.columns)
#         if not_in_data.size > 0:
#             raise AttributeError(
#                 f'{", ".join(not_in_data)} specified for plotting, '
#                 "but not in variables!"
#             )
#
#         xdata = self.full_data[x].values
#         ydata = self.full_data[y].values
#         sdata = self.full_data[s].values
#
#         if s == "Time":  # Rescale time if values are large
#             units = "seconds"
#             if np.max(sdata) > 60:
#                 units = "minutes"
#                 sdata = sdata / 60
#                 if np.max(sdata) > 60:
#                     units = "hours"
#                     sdata = sdata / 60
#
#         s_min, s_max = np.min(sdata), np.max(sdata)
#         norm = plt.Normalize(vmin=s_min, vmax=s_max)
#
#         colormap = "viridis"
#         plt.rcParams["image.cmap"] = colormap
#         cmap = plt.get_cmap("viridis")
#
#         plot_kwargs = self.settings[name].get("configure", {})
#         # kwargs for matplotlib
#
#         if not hasattr(fig, "cbar"):  # draw a new plot
#             for i in range(len(xdata) - 1):
#                 ax.plot(
#                     xdata[i : i + 2],
#                     ydata[i : i + 2],
#                     color=cmap(norm(sdata[i])),
#                     **plot_kwargs,
#                 )
#
#             fig.scalarmappable = ScalarMappable(cmap=cmap, norm=norm)
#             fig.scalarmappable.set_array(np.linspace(s_min, s_max, 1000))
#             fig.cbar = plt.colorbar(fig.scalarmappable, ax=ax)
#
#             xscale = self.settings[name].get("xscale", "linear")
#             yscale = self.settings[name].get("yscale", "linear")
#
#             if xscale == "linear":
#                 ax.ticklabel_format(axis="x", style="sci", scilimits=(-2, 4))
#             elif type(xscale) == dict:
#                 for scale, options in xscale.items():
#                     ax.set_xscale(scale, **options)
#             else:
#                 ax.set_xscale(xscale)
#
#             if yscale == "linear":
#                 ax.ticklabel_format(axis="y", style="sci", scilimits=(-2, 4))
#             elif type(yscale) == dict:
#                 for scale, options in yscale.items():
#                     ax.set_yscale(scale, **options)
#             else:
#                 ax.set_yscale(yscale)
#
#             ax.set_title(name)
#             ax.grid(True)
#             ax.tick_params(labelsize="small")
#             ax.set_xlabel(self.settings[name].get("xlabel", x))
#             ax.set_ylabel(self.settings[name].get("ylabel", y))
#
#             if s == "Time":
#                 fig.cbar.ax.set_ylabel("Time " + f" ({units})")
#             else:
#                 fig.cbar.ax.set_ylabel(s)
#
#             fig.cbar.ax.tick_params(labelsize="small")
#
#             try:
#                 # Optimize plot layout using the figure's layout engine
#                 fig.get_layout_engine().execute(fig)
#             except AttributeError:  # sometimes happens for reasons
#                 pass
#             except ZeroDivisionError:  # sometimes happens for reasons
#                 pass
#
#             plt.pause(0.01)
#
#         else:  # if already plotted, update the plot data and axes
#             # update color bar
#             fig.scalarmappable.set_clim(vmin=s_min, vmax=s_max)
#             fig.cbar.update_normal(fig.scalarmappable)
#
#             # update_normal method above removes the colorbar's ylabel;
#             # redraw it
#             if s == "Time":
#                 fig.cbar.ax.set_ylabel("Time " + f" ({units})")
#             else:
#                 fig.cbar.ax.set_ylabel(s)
#
#             # update colors of existing line segments
#             for i, line in enumerate(ax.lines):
#                 line.set_color(cmap(norm(sdata[i])))
#                 ax.draw_artist(line)
#
#             # plot new line segments
#             for i in range(len(ax.lines) - 1, len(xdata) - 1):
#                 ax.plot(
#                     xdata[i : i + 2],
#                     ydata[i : i + 2],
#                     color=cmap(norm(sdata[i])),
#                     **plot_kwargs,
#                 )
#
#             ax.relim()
#             ax.autoscale_view()
#
#             fig.canvas.draw_idle()
#             fig.canvas.start_event_loop(0.01)
#
#     @staticmethod
#     def numericize(data):
#         """
#         Convert a DataFrame, possibly containing lists or paths,
#         such that all elements are numeric
#         """
#
#         indices = data.index
#         labels = data.columns
#
#         data_array = data.values
#
#         numerical_indices = []
#         numerical_array = [[]] * len(labels)
#
#         # Iterate through each row and expand any files or lists into columns
#         for index, row in zip(indices, data_array):
#             columns = []
#             max_len = 0  # maximum length of columns
#             for i, element in enumerate(row):
#                 if isinstance(element, str) and os.path.isfile(element):
#                     file_read = False
#                     attempt = 0
#                     while not file_read:
#                         try:
#                             expanded_element = list(
#                                 pd.read_csv(element)[labels[i]].values
#                             )
#
#                             file_read = True
#                         except pandas.errors.EmptyDataError:
#                             if attempt > 3:
#                                 expanded_element = [np.nan]
#                                 break
#
#                             attempt += 1
#                             plt.pause(1)
#
#                 elif np.ndim(element) == 1:
#                     expanded_element = list(element)
#
#                     expanded_element = [
#                         np.float64(value) if value is not None else np.nan
#                         for value in expanded_element
#                     ]
#
#                 else:
#                     if not isinstance(element, numbers.Number):
#                         element = np.nan
#
#                     expanded_element = [np.float64(element)]
#
#                 max_len = np.max([len(expanded_element), max_len])
#
#                 columns.append(expanded_element)
#
#             numerical_indices = numerical_indices + [index] * max_len
#             for i, column in enumerate(columns):
#                 # fill remainder of column with most recent value
#                 new_elements = column + [column[-1]] * (max_len - len(column))
#                 numerical_array[i] = numerical_array[i] + new_elements
#
#         numerical_data = pd.DataFrame(
#             data=np.array(numerical_array).T, columns=labels, index=numerical_indices
#         )
#
#         return numerical_data


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

    def __init__(self, data, fig=None, settings=None):
        """
        Plot data based on settings

        :param data: (pandas.Dataframe) data to be plotted.
        :param fig: (matplotlib.figure.Figure) option figure to plot data into;
        the number of axes must match the length of `settings`.
        :param settings: (dict) dictionary of plot settings
        """

        self.data = data
        self.full_data = self.numericize(data)

        if settings is not None:
            self.settings = settings
        else:
            self.settings = {"Plot": {"x": "Time", "y": data.columns}}

        self.plots = {}

        if fig is not None:

            axes = fig.get_axes()

            try:
                for i, plot_name in enumerate(settings):
                    self.plots[plot_name] = fig, axes[i]
            except IndexError:
                raise IndexError('number of axes in fig must match length of settings')

        else:
            for plot_name in settings:
                self.plots[plot_name] = plt.subplots(
                    constrained_layout=True, figsize=(5, 4)
                )

    def save(self, plot_name=None, save_as=None):
        """Save the plots to PNG files in the working directory"""

        if plot_name:
            fig, ax = self.plots[plot_name]
            if save_as:
                fig.savefig(save_as + ".png")
            else:
                fig.savefig(plot_name + ".png")
        else:
            for name, plot in self.plots.items():
                fig, ax = plot
                fig.savefig(name + ".png")

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
            plt.close("all")

    def plot(self):
        """Plot all plots"""

        # Update full data
        new_indices = np.setdiff1d(self.data.index, self.full_data.index)
        new_data = self.data.loc[new_indices]

        if np.any(pd.notna(new_data)):
            if self.full_data.empty:  # avoid empty concat warning
                self.full_data = self.numericize(new_data)
            else:
                self.full_data = pd.concat(
                    [self.full_data, self.numericize(new_data)]
                )
        else:  # no new data to plot
            return

        # Make the plots, by name and style

        for name, settings in self.settings.items():
            style = settings.get("style", "basic")

            if style == "basic":
                self._plot_basic(name)
            elif style == "averaged":
                self._plot_basic(name, averaged=True)
            elif style == "errorbars":
                self._plot_basic(name, errorbars=True)
            elif style == "parametric":
                self._plot_parametric(name)
            else:
                raise AttributeError(f"Plotting style '{style}' not recognized!")

    def _plot_basic(self, name, averaged=False, errorbars=False):
        """Make a simple plot, (possibly multiple) y vs. x"""

        fig, ax = self.plots[name]

        x = self.settings[name].get("x", "Time")
        ys = np.array([self.settings[name]["y"]]).flatten()

        not_in_data = np.setdiff1d(np.concatenate([[x], ys]), self.data.columns)
        if not_in_data.size > 0:
            raise AttributeError(
                f'{", ".join(not_in_data)} specified for plotting, '
                "but not in variables!"
            )

        last = self.settings[name].get('last', np.inf)

        plot_data = self.full_data.loc[
            self.full_data['Time'] > self.full_data['Time'].iloc[-1] - last
        ]

        if averaged or errorbars:
            grouped_data = plot_data.groupby(x)
            averaged_data = grouped_data.mean()
            xdata = averaged_data[x]
            ydata = averaged_data[ys]

            if errorbars:
                ystddata = grouped_data.std()[ys]

        else:
            if x == "Time":
                xdata = plot_data.index
            else:
                xdata = plot_data[x].astype(float)

            ydata = plot_data[ys].astype(float)

        if ax.lines and not errorbars:
            # For simple plots (i.e. not error bar plots), if already plotted,
            # simply update the plot data and axes

            for line, y in zip(ax.lines, ys):
                line.set_data(xdata, ydata[y])
                # ax.draw_artist(line)

            ax.relim()  # reset plot limits based on data
            ax.autoscale_view()

            fig.canvas.draw_idle()
            fig.canvas.start_event_loop(0.01)

        else:  # draw a new plot
            plot_kwargs = self.settings[name].get("configure", {})
            # kwargs for matplotlib

            plot_kwargs = {
                key: np.array([value]).flatten() for key, value in plot_kwargs.items()
            }

            if len(ys) > 1:  # a legend will be made
                plot_kwargs["label"] = ys

            xscale = self.settings[name].get("x scale", "linear")
            yscale = self.settings[name].get("y scale", "linear")

            if x == "Time":
                ax.xaxis.set_major_locator(self.date_locator)
                ax.xaxis.set_major_formatter(self.date_formatter)

            for i, y in enumerate(ys):
                plot_kwargs_i = {key: value[i] for key, value in plot_kwargs.items()}

                if errorbars:
                    ax.errorbar(xdata, ydata[y], yerr=ystddata[y], **plot_kwargs_i)
                else:
                    ax.plot(xdata, ydata[y], **plot_kwargs_i)

            if x == "Time":
                pass
                # axis is automatically configured for datetimes; do not modify
            elif xscale == "linear":
                try:
                    ax.ticklabel_format(axis="x", style="sci", scilimits=(-2, 4))
                except AttributeError:
                    pass
            elif type(xscale) == dict:
                for scale, options in xscale.items():
                    ax.set_xscale(scale, **options)
            else:
                ax.set_xscale(xscale)

            if yscale == "linear":
                try:
                    ax.ticklabel_format(axis="y", style="sci", scilimits=(-2, 4))
                except AttributeError:
                    pass
            elif type(yscale) == dict:
                for scale, options in yscale.items():
                    ax.set_yscale(scale, **options)
            else:
                ax.set_yscale(yscale)

            ax.set_title(name)
            ax.tick_params(labelsize="small")
            ax.grid()

            if len(ys) > 1:
                ax.legend()

            if x != "Time":
                ax.set_xlabel(self.settings[name].get("xlabel", x))
            ax.set_ylabel(self.settings[name].get("ylabel", ys[0]))

            if matplotlib.is_interactive():
                plt.pause(0.01)

    def _plot_parametric(self, name):
        """Make a parametric plot of x and y against a third parameter"""

        fig, ax = self.plots[name]

        x = self.settings[name]["x"]
        y = np.array([self.settings[name]["y"]]).flatten()[0]
        s = self.settings[name].get("s", "Time")

        not_in_data = np.setdiff1d([x, y, s], self.data.columns)
        if not_in_data.size > 0:
            raise AttributeError(
                f'{", ".join(not_in_data)} specified for plotting, '
                "but not in variables!"
            )

        last = self.settings[name].get("last", np.inf)

        plot_data = self.full_data.loc[
            self.full_data['Time'] > self.full_data['Time'].iloc[-1] - last
        ]

        index = plot_data.index
        xdata = plot_data[x].values
        ydata = plot_data[y].values
        sdata = plot_data[s].values

        if s == "Time":  # Rescale time if values are large
            units = "seconds"
            if np.max(sdata) > 60:
                units = "minutes"
                sdata = sdata / 60
                if np.max(sdata) > 60:
                    units = "hours"
                    sdata = sdata / 60

        s_min, s_max = np.min(sdata), np.max(sdata)
        norm = plt.Normalize(vmin=s_min, vmax=s_max)

        colormap = "viridis"
        plt.rcParams["image.cmap"] = colormap
        cmap = plt.get_cmap("viridis")

        plot_kwargs = self.settings[name].get("configure", {})
        # kwargs for matplotlib

        if not hasattr(fig, "cbar"):  # draw a new plot
            for i in range(len(xdata) - 1):
                line = ax.plot(
                    xdata[i : i + 2],
                    ydata[i : i + 2],
                    color=cmap(norm(sdata[i])),
                    **plot_kwargs,
                )

                line[0].timestamp = index[i]

            fig.scalarmappable = ScalarMappable(cmap=cmap, norm=norm)
            fig.scalarmappable.set_array(np.linspace(s_min, s_max, 1000))
            fig.cbar = plt.colorbar(fig.scalarmappable, ax=ax)

            xscale = self.settings[name].get("x scale", "linear")
            yscale = self.settings[name].get("y scale", "linear")

            if xscale == "linear":
                ax.ticklabel_format(axis="x", style="sci", scilimits=(-2, 4))
            elif type(xscale) == dict:
                for scale, options in xscale.items():
                    ax.set_xscale(scale, **options)
            else:
                ax.set_xscale(xscale)

            if yscale == "linear":
                ax.ticklabel_format(axis="y", style="sci", scilimits=(-2, 4))
            elif type(yscale) == dict:
                for scale, options in yscale.items():
                    ax.set_yscale(scale, **options)
            else:
                ax.set_yscale(yscale)

            ax.set_title(name)
            ax.grid(True)
            ax.tick_params(labelsize="small")
            ax.set_xlabel(self.settings[name].get("xlabel", x))
            ax.set_ylabel(self.settings[name].get("ylabel", y))

            if s == "Time":
                fig.cbar.ax.set_ylabel("Time " + f" ({units})")
            else:
                fig.cbar.ax.set_ylabel(s)

            fig.cbar.ax.tick_params(labelsize="small")

            try:
                # Optimize plot layout using the figure's layout engine
                fig.get_layout_engine().execute(fig)
            except AttributeError:  # sometimes happens for reasons
                pass
            except ZeroDivisionError:  # sometimes happens for reasons
                pass

        else:  # if already plotted, update the plot data and axes
            # update color bar
            fig.scalarmappable.set_clim(vmin=s_min, vmax=s_max)
            fig.cbar.update_normal(fig.scalarmappable)

            # update_normal method above removes the colorbar's ylabel;
            # redraw it
            if s == "Time":
                fig.cbar.ax.set_ylabel("Time " + f" ({units})")
            else:
                fig.cbar.ax.set_ylabel(s)

            # update colors of existing line segments
            for i, line in enumerate(ax.lines[:]):
                if line.timestamp not in index:
                    # line is too old; discard
                    ax.lines.pop(i)
                else:
                    # find s value corresponding to line timestamp
                    # and recolor line accordingly
                    idx = np.argwhere(index == line.timestamp)[0][0]
                    line.set_color(cmap(norm(sdata[idx])))

            # plot new line segments
            for i in range(len(ax.lines) - 1, len(xdata) - 1):
                line = ax.plot(
                    xdata[i: i + 2],
                    ydata[i: i + 2],
                    color=cmap(norm(sdata[i])),
                    **plot_kwargs,
                )

                line[0].timestamp = index[i]

            ax.relim()
            ax.autoscale_view()

            fig.canvas.draw_idle()
            fig.canvas.start_event_loop(0.01)

            if matplotlib.is_interactive():
                plt.pause(0.01)

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
                if isinstance(element, str) and os.path.isfile(element):
                    file_read = False
                    attempt = 0
                    while not file_read:
                        try:
                            expanded_element = list(
                                pd.read_csv(element, dtype=np.float64)[labels[i]].values
                            )

                            file_read = True
                        except pandas.errors.EmptyDataError:
                            if attempt > 3:
                                expanded_element = [np.nan]
                                break

                            attempt += 1
                            plt.pause(1)
                elif np.ndim(element) == 1:
                    expanded_element = list(element)

                    expanded_element = [
                        np.float64(value) if value is not None else np.nan
                        for value in expanded_element
                    ]

                else:

                    try:
                        expanded_element = [np.float64(element)]

                    except ValueError:
                        expanded_element = [np.nan]

                max_len = np.max([len(expanded_element), max_len])

                columns.append(expanded_element)

            numerical_indices = numerical_indices + [index] * max_len
            for i, column in enumerate(columns):
                # fill remainder of column with most recent value
                new_elements = column + [column[-1]] * (max_len - len(column))
                numerical_array[i] = numerical_array[i] + new_elements

        numerical_data = pd.DataFrame(
            data=np.array(numerical_array).T, columns=labels, index=numerical_indices
        )

        return numerical_data



class TkGUI:
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
            self.title = "Empyric"

        self.closed = False  # has the GUI been closed?

        self.variables = experiment.variables

        self.alarms = kwargs.get("alarms", {})

        if "instruments" in kwargs:
            self.instruments = kwargs["instruments"]
        else:
            # If instruments are not specified,
            # get them from the experiment variables
            self.instruments = {}
            for variable in self.experiment.variables.values():
                if variable._type in ["meter", "knob"]:
                    instrument = variable.instrument
                    if instrument.name not in self.instruments:
                        self.instruments[instrument.name] = instrument

        if (
            kwargs.get("plots", None) is not None
            or kwargs.get("plotter", None) is not None
        ):

            if "plotter" in kwargs:
                self.plotter = kwargs["plotter"]
            else:
                self.plotter = Plotter(experiment.data, kwargs["plots"])

            self.plot_interval = kwargs.get("plot_interval", 0)
            # grows if plotting takes longer

            self.last_plot = float("-inf")

            # Set interval for saving plots
            self.save_interval = kwargs.get("save_interval", 0)

            self.last_save = time.time()

        self.root = tk.Tk()
        self.root.lift()
        self.root.wm_attributes("-topmost", True)  # bring window to front
        self.root.protocol("WM_DELETE_WINDOW", self.end)

        self.root.title(self.title)
        self.root.resizable(False, False)

        self.status_frame = tk.Frame(self.root)
        self.status_frame.grid(row=0, column=0, columnspan=2)

        i = 0
        title = kwargs.get("title", "Experiment")

        tk.Label(self.status_frame, text=title, font=("Arial", 14, "bold")).grid(
            row=i, column=1
        )

        # Status field shows current experiment status
        i += 1
        tk.Label(
            self.status_frame, text="Status", width=len("Status"), anchor=tk.E
        ).grid(row=i, column=0, sticky=tk.E)

        self.status_label = tk.Label(
            self.status_frame, text="", width=30, relief=tk.SUNKEN
        )
        self.status_label.grid(row=i, column=1, sticky=tk.W, padx=10)

        # Table of variables shows most recently measured/set variable values
        self.variable_entries = {}
        self._entry_enter_funcs = {}  # container for enter press event handlers
        self._entry_esc_funcs = {}  # container for esc press event handlers

        i += 1
        tk.Label(self.status_frame, text="", font=("Arial", 14, "bold")).grid(
            row=i, column=0, sticky=tk.E
        )

        i += 1
        tk.Label(self.status_frame, text="Variables", font=("Arial", 14, "bold")).grid(
            row=i, column=1
        )

        i += 1
        tk.Label(
            self.status_frame, text="Run Time", width=len("Run Time"), anchor=tk.E
        ).grid(row=i, column=0, sticky=tk.E)

        self.variable_entries["Time"] = tk.Entry(
            self.status_frame, state="readonly", disabledforeground="black", width=30
        )
        self.variable_entries["Time"].grid(row=i, column=1, sticky=tk.W, padx=10)

        i += 1
        for name in self.variables:
            if self.variables[name]._hidden:
                continue

            tk.Label(self.status_frame, text=name, width=len(name), anchor=tk.E).grid(
                row=i, column=0, sticky=tk.E
            )

            self.variable_entries[name] = tk.Entry(
                self.status_frame,
                state="readonly",
                disabledforeground="black",
                width=30,
            )
            self.variable_entries[name].grid(row=i, column=1, sticky=tk.W, padx=10)

            if self.variables[name].settable:
                entry = self.variable_entries[name]
                variable = self.variables[name]
                root = self.status_frame

                enter_func = lambda event, entry=entry, variable=variable, root=root: self._entry_enter(
                    entry, variable, root
                )

                self._entry_enter_funcs[name] = enter_func
                self.variable_entries[name].bind(
                    "<Return>", self._entry_enter_funcs[name]
                )

                esc_func = lambda event, entry=entry, variable=variable, root=root: self._entry_esc(
                    entry, variable, root
                )

                self._entry_esc_funcs[name] = esc_func
                self.variable_entries[name].bind(
                    "<Escape>", self._entry_esc_funcs[name]
                )

            i += 1

        i += 1
        tk.Label(self.status_frame, text="", font=("Arial", 14, "bold")).grid(
            row=i, column=0, sticky=tk.E
        )

        # Table of alarm indicators shows the status of any alarms monitored
        self.alarm_status_labels = {}

        if len(self.alarms) > 0:
            i += 1
            tk.Label(self.status_frame, text="Alarms", font=("Arial", 14, "bold")).grid(
                row=i, column=1
            )

            i += 1
            for alarm in self.alarms:
                tk.Label(
                    self.status_frame, text=alarm, width=len(alarm), anchor=tk.E
                ).grid(row=i, column=0, sticky=tk.E)

                self.alarm_status_labels[alarm] = tk.Label(
                    self.status_frame, text="Clear", relief=tk.SUNKEN, width=30
                )
                self.alarm_status_labels[alarm].grid(
                    row=i, column=1, sticky=tk.W, padx=10
                )

                i += 1

            tk.Label(self.status_frame, text="", font=("Arial", 14, "bold")).grid(
                row=i, column=0, sticky=tk.E
            )

        # Servers
        self.servers = {
            name: routine
            for name, routine in self.experiment.routines.items()
            if isinstance(routine, SocketServer) or isinstance(routine, ModbusServer)
        }

        if self.servers:
            self.server_status_labels = {}

            i += 1
            tk.Label(
                self.status_frame, text="Servers", font=("Arial", 14, "bold")
            ).grid(row=i, column=1)

            i += 1
            for server in self.servers:
                tk.Label(
                    self.status_frame, text=server, width=len(server), anchor=tk.E
                ).grid(row=i, column=0, sticky=tk.E)

                ip_address = self.servers[server].ip_address
                port = self.servers[server].port

                # Make entry so text is selectable
                self.server_status_labels[server] = tk.Entry(
                    self.status_frame,
                    disabledforeground="black",
                )

                self.server_status_labels[server].insert(0, f"{ip_address}::{port}")
                self.server_status_labels[server].config(state="readonly")

                self.server_status_labels[server].grid(
                    row=i, column=1, sticky=tk.W, padx=10
                )

                i += 1

        # Buttons (root is not self.status_frame, so indexing starts at 1)
        i = 1
        self.dash_button = tk.Button(
            self.root,
            text="Dashboard",
            font=("Arial", 14, "bold"),
            width=10,
            command=self.open_dashboard,
            state=tk.DISABLED,
        )
        self.dash_button.grid(row=i, column=0, sticky=tk.W)

        self.hold_button = tk.Button(
            self.root,
            text="Hold",
            font=("Arial", 14, "bold"),
            width=10,
            command=self.toggle_hold,
        )
        self.hold_button.grid(row=i + 1, column=0, sticky=tk.W)

        self.stop_button = tk.Button(
            self.root,
            text="Stop",
            font=("Arial", 14, "bold"),
            width=10,
            command=self.toggle_stop,
        )
        self.stop_button.grid(row=i + 2, column=0, sticky=tk.W)

        self.terminate_button = tk.Button(
            self.root,
            text="Terminate",
            font=("Arial", 14, "bold"),
            width=10,
            fg="red",
            bg="gray87",
            command=self.end,
            height=5,
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
        self.root.wm_attributes("-topmost", False)

        state = self.experiment.state

        # Update all variable entries based on experiment state
        for name, entry in self.variable_entries.items():
            # If stopped or holding allow user to edit knobs or parameters
            if self.experiment.stopped or self.experiment.holding:
                if name != "Time" and self.variables[name].settable:
                    continue

            def write_entry(_entry, text):
                _entry.config(state=tk.NORMAL)
                _entry.delete(0, tk.END)
                _entry.insert(0, text)
                _entry.config(state=tk.DISABLED)

            if state[name] is None:
                write_entry(entry, "None")
            elif state[name] == np.nan:
                write_entry(entry, "NaN")
            else:
                if name == "Time":
                    write_entry(entry, str(datetime.timedelta(seconds=state["Time"])))
                elif isinstance(state[name], Float):
                    # display floating point numbers neatly
                    if state[name] == 0.0:
                        write_entry(entry, "0.0")
                    elif np.abs(np.log10(np.abs(state[name]))) > 3:
                        write_entry(entry, "%.3e" % state[name])
                    else:
                        write_entry(entry, "%.3f" % state[name])
                else:
                    write_entry(entry, str(state[name]))

        self.status_label.config(text=self.experiment.status)

        # Check alarms
        for name, label in self.alarm_status_labels.items():
            if self.alarms[name].triggered:
                protocol = self.alarms[name].protocol
                if protocol == "none":
                    label.config(text="TRIGGERED: NO PROTOCOL", bg="red")
                else:
                    label.config(text="TRIGGERED" + f": {protocol.upper()}", bg="red")
            else:
                label.config(text="CLEAR", bg="green")

        # Update hold, stop and dashboard buttons
        if self.experiment.holding or self.experiment.stopped:
            self.dash_button.config(state=tk.NORMAL)

            if self.experiment.holding:
                self.hold_button.config(text="Resume")
                self.stop_button.config(text="Stop")
            else:
                self.hold_button.config(text="Hold")
                self.stop_button.config(text="Resume")

            # Settable variable values can be edited
            for name, entry in self.variable_entries.items():
                if name != "Time" and self.variables[name].settable:
                    entry.config(state=tk.NORMAL)

        else:  # otherwise, experiment is running
            self.dash_button.config(state=tk.DISABLED)
            self.hold_button.config(text="Hold")
            self.stop_button.config(text="Stop")

            for entry in self.variable_entries.values():
                entry.config(state=tk.DISABLED)

        # Quit if experiment has ended
        if self.experiment.terminated:
            self.quit()

        # Plot data
        has_plotter = hasattr(self, "plotter")
        has_data = len(self.experiment.data) > 0
        not_stopped = not self.experiment.stopped
        if has_plotter and has_data and not_stopped:
            if time.time() > self.last_plot + self.plot_interval:
                start_plot = time.perf_counter()
                self.plotter.plot()
                end_plot = time.perf_counter()
                self.last_plot = time.time()

                self.plot_interval = np.max(
                    [self.plot_interval, 5 * int(end_plot - start_plot)]
                )  # adjust interval if drawing plots takes significant time

            # Save plots
            saving_needed = time.time() > self.last_save + self.save_interval
            if saving_needed and self.experiment.timestamp:
                start_save = time.perf_counter()
                self.plotter.save()
                end_save = time.perf_counter()
                self.last_save = time.time()

                self.save_interval = np.max(
                    [self.save_interval, 5 * int(end_save - start_save)]
                )  # adjust interval if saving plots takes significant time

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
        if "Holding" in prior_status:
            self.experiment.hold()
        elif "Ready" in prior_status or "Running" in prior_status:
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

        self.experiment.terminate(reason="user terminated")
        self.quit()

    def quit(self):
        if hasattr(self, "plotter"):
            self.plotter.close()

        self.status_label.config(text=self.experiment.TERMINATED)

        self.closed = True
        plt.pause(0.1)  # give GUI and plotter enough time to wrap up
        self.root.update()

        try:
            self.root.destroy()
            self.root.quit()
        except tk.TclError:  # happens when window has already been closed
            pass

    @staticmethod
    def _entry_enter(entry, variable, root):
        """Assigns the value to a variable if entered by the user"""

        variable.value = recast(
            entry.get(), to=variable._type if variable._type is not None else Type
        )

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
                entry.insert(0, "0.0")
            elif np.abs(np.log10(np.abs(value))) > 3:
                entry.insert(0, "%.3e" % value)
            else:
                entry.insert(0, "%.3f" % value)
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

        self.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))

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

        BasicDialog.__init__(self, parent, title="Dashboard")

    def body(self, master):
        tk.Label(master, text="Instruments:", font=("Arial", 14), justify=tk.LEFT).grid(
            row=0, column=0, sticky=tk.W
        )

        i = 1

        self.instrument_labels = {}
        self.config_buttons = {}

        for name, instrument in self.instruments.items():
            instrument_label = tk.Label(master, text=name)
            instrument_label.grid(row=i, column=0)

            self.instrument_labels[name] = instrument_label

            config_button = tk.Button(
                master,
                text="Config/Test",
                command=lambda instr=instrument: self.config(instr),
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
        BasicDialog.__init__(self, parent, title="Config/Test: " + instrument.name)

    def set_knob_entry(self, knob):
        value = self.knob_entries[knob].get()
        self.instrument.set(knob.replace(" ", "_"), recast(value))

    def get_knob_entry(self, knob):
        if hasattr(self.instrument, "get_" + knob.replace(" ", "_")):
            value = self.instrument.get(knob)
        else:
            value = getattr(self.instrument, knob.replace(" ", "_"))

        self.knob_entries[knob].delete(0, tk.END)
        self.knob_entries[knob].insert(0, str(value))

    def update_meter_entry(self, meter):
        value = self.instrument.measure(meter)

        if np.ndim(value) == 1:  # store array data as CSV files
            dataframe = pd.DataFrame({meter: value})
            path = self.instrument.name + "-" + meter.replace(" ", "_") + "_"
            now = datetime.datetime.now()
            path += now.strftime("%Y%m%d-%H%M%S") + ".csv"
            dataframe.to_csv(path)

            value = path

        self.meter_entries[meter].config(state=tk.NORMAL)
        self.meter_entries[meter].delete(0, tk.END)
        self.meter_entries[meter].insert(0, str(value))
        self.meter_entries[meter].config(state="readonly")

    def body(self, master):
        knobs = self.instrument.knobs
        knob_values = {
            knob: getattr(self.instrument, knob.replace(" ", "_")) for knob in knobs
        }
        self.knob_entries = {}

        meters = self.instrument.meters
        self.meter_entries = {}

        frame = tk.Frame(master)
        frame.grid(row=1, column=0, columnspan=7)

        label = tk.Label(frame, text="Knobs", font=("Arial", 14, "bold"))
        label.grid(row=1, column=0, sticky=tk.W)

        label = tk.Label(frame, text="Meters", font=("Arial", 14, "bold"))
        label.grid(row=1, column=3, sticky=tk.W)

        self.set_buttons = {}
        self.get_buttons = {}
        i = 2
        for knob in knobs:
            formatted_name = " ".join(
                [word[0].upper() + word[1:] for word in knob.split(" ")]
            )

            label = tk.Label(frame, text=formatted_name)
            label.grid(row=i, column=0, sticky=tk.W)

            self.knob_entries[knob] = tk.Entry(frame)
            self.knob_entries[knob].grid(row=i, column=1)
            self.knob_entries[knob].insert(0, str(knob_values[knob]))

            self.set_buttons[knob] = tk.Button(
                frame, text="Set", command=lambda knob=knob: self.set_knob_entry(knob)
            )
            self.set_buttons[knob].grid(row=i, column=2)

            self.get_buttons[knob] = tk.Button(
                frame, text="Get", command=lambda knob=knob: self.get_knob_entry(knob)
            )
            self.get_buttons[knob].grid(row=i, column=3)

            i += 1

        self.measure_buttons = {}
        i = 2
        for meter in meters:
            formatted_name = " ".join(
                [word[0].upper() + word[1:] for word in meter.split(" ")]
            )

            label = tk.Label(frame, text=formatted_name)
            label.grid(row=i, column=4, sticky=tk.W)

            self.meter_entries[meter] = tk.Entry(frame)
            self.meter_entries[meter].grid(row=i, column=5)
            self.meter_entries[meter].insert(0, "???")
            self.meter_entries[meter].config(state="readonly")

            self.measure_buttons[meter] = tk.Button(
                frame,
                text="Measure",
                command=lambda meter=meter: self.update_meter_entry(meter),
            )
            self.measure_buttons[meter].grid(row=i, column=6)

            i += 1


class BrowserGUI:

    shutdown = False

    port = 8080

    window = None

    variable_inputs = {}

    def __init__(self, experiment, title=None, **kwargs):

        self.experiment = experiment

        self.title = title if title is not None else 'Experiment'

        if "instruments" in kwargs:
            self.instruments = kwargs["instruments"]
        else:
            # If instruments are not specified,
            # get them from the experiment variables
            self.instruments = {}
            for var_name, variable in self.experiment.variables.items():
                if hasattr(variable, 'instrument'):

                    instrument = variable.instrument

                    if instrument.name not in self.instruments:
                        self.instruments[instrument.name] = instrument
                    elif instrument not in self.instruments.values():
                        # instrument name is duplicated; modify name
                        instrument.name += f' ({var_name})'

        self.knob_inputs = {}
        self.meter_inputs = {}

        self._make_header()

        if ('plots' in kwargs) or ('plotter' in kwargs):

            matplotlib.use('agg')  # make non-interactive

            with ui.splitter(value=33).classes('w-full') as self.splitter:
                with self.splitter.before:

                    with ui.scroll_area().style('height: 50vh'):
                        self._make_variable_panel()

                    ui.separator()

                    with ui.scroll_area().style('height: 50vh'):
                        self._make_routine_panel()

                with self.splitter.after:
                    with ui.scroll_area().style('height: 100vh'):
                        with ui.card().classes('w-full'):
                            with ui.row().classes('w-full justify-center'):

                                self._make_plot_panel(
                                    plotter=kwargs.get('plotter', None),
                                    settings=kwargs.get('plots', None)
                                )

            self.plot_updater = ui.timer(1.0, self._update_plots)
        else:
            with ui.scroll_area().style('height: 50vh'):
                self._make_variable_panel()

            ui.separator()

            with ui.scroll_area().style('height: 50vh'):
                self._make_routine_panel()

        with ui.dialog() as self.exit_message, ui.card():
            ui.label('Experiment has ended; you may close this window')

    def run(self):

        app.on_startup(
            lambda: print(
                f'\nStarting {self.title}\nView in browser at',
                ', '.join(list(app.urls)), '\n'
            )
        )

        async def await_end_of_experiment():
            while not self.experiment.terminated:
                await asyncio.sleep(0.25)

            await self.quit()

        app.on_startup(await_end_of_experiment)

        app.on_shutdown(
            lambda: print(
                f'{self.title} terminated\n'
            )
        )

        ui.run(
            reload=False, port=self.port, title=self.title,
            show_welcome_message=False
        )

    async def end(self):
        """
        User terminates the experiment and closes the GUI with the Terminate
        button; cancels any experiment follow-ups.
        """

        self.experiment.terminate(reason="user terminated")

        await self.quit()

    async def quit(self):

        with self.exit_message:
            self.exit_message.open()

        self.exit_message.update()

        await asyncio.sleep(1.0)

        app.shutdown()

    def _make_header(self):
        """Cantains Pause, Stop and Dashboard buttons"""

        with ui.header():
            ui.label(self.title).classes('text-h5')
            ui.space()
            with ui.row():

                self._make_config_dialog()  # defines self.config_dialog needed below

                self.dash_button = ui.button(
                    icon='developer_board', color='gray',
                    on_click=self._open_config_dialog
                )

                ui.space()

                self.hold_button = ui.button(
                    icon='pause', color='yellow',
                    on_click=self.hold_experiment,
                )

                self.stop_button = ui.button(
                    icon='stop', color='red',
                    on_click=self.stop_experiment,
                )

                ui.space()

                ui.space()

                self.end_button = ui.button(
                    icon='close', color='black',
                    on_click=self.end,
                )

    async def hold_experiment(self):

        self.hold_button.props(remove="icon color")

        if self.experiment.running:
            self.experiment.hold(reason='paused by user')
            self.hold_button.props(add="icon=play_arrow color=green")
        else:
            self.experiment.start()
            self.hold_button.props(add="icon=pause color=yellow")

        self.hold_button.update()

    async def stop_experiment(self):
        self.experiment.stop(reason="stopped by user")

        self.hold_button.props(remove="icon color")
        self.hold_button.props(add="icon=play_arrow color=green")

        self.hold_button.update()

    def _make_variable_panel(self):

        with ((((ui.card().classes('w-full'))))):
            ui.label('Variables').classes('text-h6')

            lbl_len = np.max([len(name) for name in self.experiment.variables.keys()] + [4])
            lbl_len = int(1.1 * lbl_len)

            with ui.list():
                with ui.row().classes('justify-start items-center'):
                    ui.label('Time').classes('font-semibold').style(f'width: {lbl_len}ch')
                    self.variable_inputs['Time'] = ui.input(
                    ).bind_value_from(self.experiment.clock, 'time')

                    self.variable_inputs['Time'].props('outlined dense')

                    self.variable_inputs['Time'].disable()

                for name, variable in self.experiment.variables.items():
                    with ui.row().classes('justify-start items-center'):
                        self._make_variable_row(name, variable, lbl_len)

    def _make_variable_row(self, name, variable, lbl_len):

        ui.label(name).classes('font-semibold').style(f'width: {lbl_len}ch')

        if variable._type == Toggle:
            self.variable_inputs[name] = ui.switch()
            self.variable_inputs[name].bind_value(variable, '_value')
        else:
            self.variable_inputs[name] = ui.input()
            self.variable_inputs[name].bind_value(variable, '_value')

            self.variable_inputs[name].props('outlined dense')

        if variable.settable:

            variable.gui_access = True

            self.variable_inputs[name].bind_enabled(
                variable, 'gui_access',
                backward=lambda value: not self.experiment.running
            )
        else:
            self.variable_inputs[name].disable()

    def _make_routine_panel(self):

        with ui.card().classes('w-full'):
            ui.label('Routines').classes('text-h6')

            lbl_len = np.max(
                [len(name) for name in self.experiment.routines.keys()] + [4]
            )
            lbl_len = int(1.1 * lbl_len)

            with ui.list():
                for name, routine in self.experiment.routines.items():
                    with ui.expansion() as expansion:

                        expansion.props('switch-toggle-side dense')

                        expansion.classes('p-0')

                        with expansion.add_slot('header'):
                            with ui.row().classes('items-center h-10'):

                                ui.label(name).classes(
                                    f'font-semibold'
                                )

                                spinner = ui.spinner('gears', size='40px')

                                spinner.bind_visibility(routine, 'running')

                        kind = [
                            _repr for _repr, supported_routine
                            in supported_routines.items()
                            if isinstance(routine, supported_routine)
                        ][0]

                        with ui.row():
                            ui.label(f'{kind}').classes('italic')

                        with ui.row():
                            start = datetime.timedelta(seconds=routine.start)
                            end = datetime.timedelta(seconds=routine.end) \
                                if np.isfinite(routine.end) else 'infinity'

                            ui.label(
                                f'Starting at {start}'
                                f' and ending at {end}'
                            )

                        is_server = isinstance(routine, ModbusServer) \
                            or isinstance(routine, SocketServer)

                        if is_server:
                            with ui.row():
                                ui.label(
                                    f'IP: {routine.ip_address}'
                                )
                                ui.space()
                                ui.label(
                                    f'port: {routine.port}'
                                )

    def _make_plot_panel(self, plotter=None, settings=None):

        if plotter is not None and isinstance(plotter, Plotter):
            n_plots = len(plotter.settings)
        elif settings is not None and isinstance(settings, dict):
            n_plots = len(settings)
        elif plotter is None and settings is None:
            settings = {
                f'{col}': {"y": col}
                for col in self.experiment.data.columns if col != 'Time'
            }
            n_plots = len(settings)
        else:
            return

        with ui.matplotlib(
            figsize=(8, n_plots*4),
            layout="compressed"
        ) as self.matplotlib_context:

            self.fig = self.matplotlib_context.figure

            axes = self.fig.subplots(nrows=n_plots, squeeze=True)

            if plotter is None:
                # Make a new Plotter instance
                self.plotter = Plotter(
                    self.experiment.data, fig=self.fig,
                    settings=settings
                )
            else:
                # Modify an existing Plotter instance
                self.plotter = plotter

                for i, plot_name in enumerate(self.plotter.plots.keys()):

                    # Close previously created figures
                    old_fig, _ = self.plotter.plots[plot_name]
                    plt.close(old_fig)

                    # Attach fig & axes created by NiceGUI to Plotter instance
                    self.plotter.plots[plot_name] = self.fig, axes[i]

    async def _update_plots(self):
        if len(self.experiment.data) > 0:
            self.plotter.plot()

        self.matplotlib_context.update()

    def _make_config_dialog(self):

        for name in self.instruments:
            self._make_instr_dialog(name)

        with ui.dialog() as self.config_dialog, ui.card().classes('w-full'):
            ui.label('Instrument Dashboard').classes('text-h6')

            with ui.scroll_area().classes('w-full h-32'):
                for name, instrument in self.instruments.items():
                    with ui.card().classes('bg-slate-100 w-full'):
                        with ui.row().classes('w-full items-center'):
                            ui.label(name).classes('flex-grow')
                            ui.button(
                                'Open', on_click=self.instr_dialog[name].open
                            ).classes('flex-shrink')

            with ui.row().classes('w-full justify-center items-center'):
                ui.button(
                    'Done', on_click=self._close_config_dialog
                )

    def _open_config_dialog(self):

        self.experiment.hold(reason='config dialog opened')
        self.config_dialog.open()

    def _close_config_dialog(self):

        self.config_dialog.close()
        self.experiment.start()

    def _make_instr_dialog(self, name):

        instrument = self.instruments[name]

        if not hasattr(self, 'instr_dialog'):
            self.instr_dialog = {}

        with ui.dialog() as self.instr_dialog[name]:

            with ui.card().style('width: 75%; max-width: 100vw;'):

                ui.label(name).classes('text-h6')

                with ui.grid(columns=7).classes('items-center justify-start'):

                    n_knobs = len(instrument.knobs)
                    n_meters = len(instrument.meters)

                    self.knob_inputs[name] = []
                    self.meter_inputs[name] = []

                    for i in range(max((n_knobs, n_meters))):

                        if i < n_knobs:

                            ui.label(instrument.knobs[i])

                            self.knob_inputs[name].append(ui.input(
                                value=str(instrument.get(instrument.knobs[i]))
                            ).props('outlined dense'))

                            ui.button(
                                'Set',
                                on_click=lambda instr_name=name, ii=i:
                                self.instruments[instr_name].set(
                                        self.instruments[instr_name].knobs[ii],
                                        self.knob_inputs[instr_name][ii].value
                                    )
                            )

                            ui.button(
                                'Get',
                                on_click=lambda instr_name=name, ii=i:
                                self.knob_inputs[instr_name][ii].set_value(
                                    self.instruments[instr_name].get(
                                        self.instruments[instr_name].knobs[ii]
                                    )
                                )
                            )
                        else:
                            for _ in range(4):
                                ui.space()

                        if i < n_meters:
                            ui.label(instrument.meters[i])

                            self.meter_inputs[name].append(ui.input(
                                value=str(instrument.measure(instrument.meters[i]))
                            ).props('outlined dense'))

                            ui.button(
                                'Measure',
                                on_click=lambda instr_name=name, ii=i:
                                    self.meter_inputs[instr_name][ii].set_value(
                                        self.instruments[instr_name].measure(
                                            self.instruments[instr_name].meters[ii]
                                        )
                                    )
                            ).classes('w-32')

                        else:
                            for _ in range(3):
                                ui.space()

                with ui.row().classes('w-full justify-center items-center'):
                    ui.button(
                        'Done',
                        on_click=self.instr_dialog[instrument.name].close
                    )
