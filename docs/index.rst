.. empyric documentation master file, created by
   sphinx-quickstart on Sun Mar 21 18:00:52 2021.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Empyric: Experiment Automation
===================================

Empyric is an experiment automation library, which offers easy access to instruments connected to a computer for custom Python scripting, as well as tools for building, executing and monitoring experiments in a very general framework.

.. toctree::
   :maxdepth: 3
   
   instruments
   adapters
   experiments
   variables
   types
   routines
   runcards
   graphics


Empyric contains a collection of :ref:`instruments<instruments-section>` that represent the functionality of physical instruments, which can be imported into Python scripts and used on their own to quickly start communicating with instruments for simple measurements.

Communication with instruments is facilitated with a set of :ref:`adapters<adapters-section>`, which handle the boring details of inter-device communication. The most common modes of communication, such as serial, USB and. GPIB, are implemented through these adapters.

The user is typically interested in :ref:`controlling/tracking a set of variables<experiment-section>` that is a subset of all the knobs/meters associated with the connected instruments. Empyric's experiment control system makes it easy to access these variables of interest and enables automation through the highly generalized built-in routines (and even your own custom routines).

While it is straightforward to use Empyric to control your experiments through Python scripting, with the highly modular tools provided by this library, an easy alternative is to make use of the :ref:`runcard<runcard-section>` formalism, which is very human readable (and makes for good experiment documentation on its own) and requires no Python knowledge.

In addition to helping you run experiments, Empyric also allows you to interact with and visualize your experiment through a simple :ref:`GUI and plotting tool<gui-section>`, which can be used in custom applications and can be invoked by using the experiment Manager class.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`