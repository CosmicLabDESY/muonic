"""
Provides the canvases for plots in muonic
"""
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg \
    import FigureCanvasQTAgg as FigureCanvas
try:
    from matplotlib.backends.backend_qt4agg \
        import NavigationToolbar2QTAgg as NavigationToolbar
except ImportError:
    from matplotlib.backends.backend_qt4agg \
        import NavigationToolbar2QT as NavigationToolbar

import numpy as np


class BasePlotCanvas(FigureCanvas):
    """
    Base class for plot canvases

    :param parent: the parent widget
    :param logger: logger object
    :type logger: logging.Logger
    :param ymin: minimum y-value
    :type ymin: float
    :param ymax: maximum y-value
    :type ymax: float
    :param xmin: minimum x-value
    :type xmin: float
    :param xmax: maximum x-value
    :type xmax: float
    :param xlabel: label of the x-axis
    :type xlabel: str
    :param ylabel: label of the y-axis
    :type ylabel: str
    :param grid: draw grid
    :type grid: bool
    :param spacing: left and right spacing of the subplots
    :type spacing: tuple
    """
    
    def __init__(self, parent, logger, ymin=0, ymax=10, xmin=0, xmax=10,
                 xlabel="xlabel", ylabel="ylabel", grid=True,
                 spacing=(0.1, 0.9)):
       
        self.logger = logger

        # initialization of the canvas
        self.fig = Figure(facecolor="white", dpi=72)
        self.fig.subplots_adjust(left=spacing[0], right=spacing[1])
        FigureCanvas.__init__(self, self.fig)

        # setup subplot, axis and grid
        self.ax = self.fig.add_subplot(111)
        self.ax.set_ylim(ymin=ymin, ymax=ymax)
        self.ax.set_xlim(xmin=xmin, xmax=xmax)
        self.ax.set_xlabel(xlabel)
        self.ax.set_ylabel(ylabel)
        self.ax.set_autoscale_on(False)
        self.ax.grid(grid)
        
        # store the limits for later use
        self.xmin = xmin
        self.xmax = xmax
        self.ymin = ymin
        self.ymax = ymax
        self.xlabel = xlabel
        self.ylabel = ylabel
        
        # force a redraw of the Figure
        self.fig.canvas.draw() 
        self.setParent(parent)

    # FIXME: is this of any use here? remove?
    @staticmethod
    def color(string, color="none"):
        """
        Color string via ANSI escape sequences

        :param string: the string to color
        :type string: str
        :param color: the color of the string, eg.: 'blue', 'green'
        :type color: str
        :returns: str
        """
        colors = {"green": '\033[92m', "yellow": '\033[93m',
                  "red": '\033[91m', "blue": '\033[94m', "none": '\033[0m'}
        return colors[color] + string + colors["none"]   

    def update_plot(self, *args):
        """
        Instructions to update the plot. Needs to be implemented in subclasses.

        :Returns: None
        """
        raise NotImplementedError("implement this method")


class BaseHistogramCanvas(BasePlotCanvas):
    """
    A base class for all canvases with a histogram

    :param parent: parent widget
    :param logger: logger object
    :type logger: logging.Logger
    :param binning: the binning to use for this canvas
    :type binning: list or tuple or numpy.ndarray
    :param hist_color: the color of the histogram
    :type hist_color: str
    :param **kwargs: additional keyword arguments
    :param **kwargs: dict
    """

    def __init__(self, parent, logger, binning, hist_color="b", **kwargs):
        BasePlotCanvas.__init__(self, parent, logger, **kwargs)

        # setup binning
        self.binning = np.asarray(binning)
        self.bincontent = np.zeros(len(self.binning))
        self.hist_patches = self.ax.hist(np.array([self.binning[0] - 1]),
                                         self.binning, fc=hist_color,
                                         alpha=0.25)[2]
        self.heights = []
        self.dimension = r"$\mu$s"

        # FIXME the current implementation does not know about outliers
        self.underflow = 0
        # FIXME the current implementation does not know about outliers
        self.overflow = 0

        # fixed xrange for histogram
        self.xmin = self.binning[0]
        self.xmax = (self.binning[-1] +
                     (self.binning[:-1] - self.binning[1:])[-1])

    def update_plot(self, data):
        """
        Update the plot

        :param data: the data to plot
        :type data: list of lists
        :return: None
        """
        if not data:
            return

        # avoid memory leak
        self.ax.clear()

        # we have to do some bad hacking here,
        # because the p histogram is rather
        # simple and it is not possible to add two of them...
        # however, since we do not want to run into a memory leak
        # and we also be not dependent on dashi (but maybe
        # sometimes in the future?) we have to do it
        # by manipulating rectangles...

        # we want to find the non-empty bins
        # tmp_hist is compatible with the decay_time hist...
        tmp_hist = self.ax.hist(data, self.binning, fc="b", alpha=0.25)[0]

        for hist_bin in enumerate(tmp_hist):
            if hist_bin[1]:
                self.hist_patches[hist_bin[0]].set_height(
                        self.hist_patches[hist_bin[0]].get_height() +
                        hist_bin[1])

        # we want to get the maximum for the ylims
        # self.heights contains the bincontent!

        self.heights = []
        for patch in self.hist_patches:
            self.heights.append(patch.get_height())

        self.logger.debug("Histogram patch heights %s" % self.heights)
        self.ax.set_ylim(ymax=max(self.heights) * 1.1)
        self.ax.set_ylim(ymin=0)
        self.ax.set_xlabel(self.xlabel)
        self.ax.set_ylabel(self.ylabel)
        self.ax.set_xlim(xmin=self.xmin, xmax=self.xmax)

        # always get rid of unused stuff
        del tmp_hist

        # some beautification
        self.ax.grid()

        # we now have to pass our new patches
        # to the figure we created..
        self.ax.patches = self.hist_patches
        self.fig.canvas.draw()

    def show_fit(self, bin_centers, bincontent, fitx, decay, p, covar,
                 chisquare, nbins):
        """
        Plot the fit onto the diagram

        :param bin_centers: bin centers
        :param bincontent: bincontents
        :param fitx: the fit
        :type fitx: numpy.ndarray
        :param decay: decay function
        :type decay: function
        :param p: fit parameters
        :type p: list
        :param covar: covariance matrix
        :type covar: matrix
        :param chisquare: chi-squared
        :type chisquare: float
        :param nbins: number of bins
        :type nbins: int
        :returns: None
        """

        # clears a previous fit from the canvas
        self.ax.lines = []
        self.ax.plot(bin_centers, bincontent, "b^", fitx, decay(p, fitx), "b-")

        # FIXME: this seems to crop the histogram
        # self.ax.set_ylim(0,max(bincontent)*1.2)
        self.ax.set_xlabel(self.xlabel)
        self.ax.set_ylabel(self.ylabel)

        # compute the errors on the fit, nb that this calculation assumes that
        # scipy.optimize.leastsq was used
        error = []
        for i in range(len(p)):
            try:
                error.append(np.absolute(covar[i][i]) ** 0.5)
            except Exception:
                error.append(0.00)

        perr_leastsq = np.array(error)

        try:
            self.ax.legend(("Data", ("Fit: (%4.2f $\pm$ %4.2f) %s  \n" +
                                     " chisq/ndf=%4.2f") %
                            (p[1], perr_leastsq[2], self.dimension,
                             chisquare / (nbins-len(p)))), loc=1)
        except TypeError:
            self.logger.warn("Covariance Matrix is 'None', could " +
                             "not calculate fit error!")
            self.ax.legend(("Data", "Fit: (%4.2f) %s \n chisq/ndf=%4.2f" %
                            (p[1], self.dimension, chisquare/(nbins-len(p)))),
                           loc=1)

        self.fig.canvas.draw()

        
class PulseCanvas(BasePlotCanvas):
    """
    Canvas to display pulses

    :param parent: parent widget
    :param logger: logger object
    :type logger: logging.Logger
    """
    def __init__(self, parent, logger):
        BasePlotCanvas.__init__(self, parent, logger, ymin=0, ymax=1.2,
                                xmin=0, xmax=40, xlabel="Time (ns)",
                                ylabel="ylabel", grid=True)
        self.ax.set_title("Oscilloscope")
        self.ax.yaxis.set_visible(False)

    def update_plot(self, pulses):
        # do a complete redraw of the plot to avoid memory leak!
        self.ax.clear()

        # set specific limits for x and y axes
        self.ax.set_xlim(0, 100)
        self.ax.set_ylim(ymax=1.5)
        self.ax.grid()
        self.ax.set_xlabel('Time (ns)')
        self.ax.yaxis.set_visible(False)
        self.ax.set_title("Oscilloscope")

        # and disable figure-wide auto scale
        self.ax.set_autoscale_on(False)

        # we have only the information that the pulse is over the threshold,
        # besides that we do not have any information about its height
        # TODO: It would be nice to implement the thresholds as scaling factors

        colors = ['b', 'g', 'r', 'c']
        labels = ['c0', 'c1', 'c2', 'c3']

        pulse_height = 1.0
        pulse_max = []

        if pulses is None:
            self.logger.warning("Pulses have no value - " +
                                "channels not connected?")
        else:
            for chan in enumerate(pulses[1:]):
                for pulse in chan[1]:
                    self.ax.plot([pulse[0], pulse[0], pulse[1], pulse[1]],
                                 [0, pulse_height, pulse_height, 0],
                                 colors[chan[0]], label=labels[chan[0]], lw=2)
                    pulse_max.append(pulse[0])
                    pulse_max.append(pulse[1])

            pulse_max = max(pulse_max)*1.2
            # TODO: the trick below does not really work as expected. 
            # if pulse_max < self.ax.get_xlim()[1]:
            #    pulse_max = self.ax.get_xlim()[0]
            self.ax.set_xlim(0, pulse_max)

            try:
                self.ax.legend(loc=1, ncol=5, mode="expand",
                               borderaxespad=0., handlelength=1)
            except Exception:
                self.logger.info("An error with the legend occured!")
                self.ax.legend(loc=2)

            self.fig.canvas.draw()
        
        
class ScalarsCanvas(BasePlotCanvas):
    """
    A plot canvas to display scalars

    :param parent: parent widget
    :param logger: logger object
    :type logger: logging.Logger
    :param max_length: maximum number of values to plot
    :type max_length: int
    """
    DEFAULT_CHANNEL_CONFIG = [True, True, True, True]
    CHANNEL_COLORS = ['y', 'm', 'c', 'b']
    TRIGGER_COLOR = 'g'

    def __init__(self, parent, logger, max_length=40):
        
        BasePlotCanvas.__init__(self, parent, logger, ymin=0, ymax=20,
                                xlabel="Time (s)", ylabel="Rate (1/s)")
        self.show_trigger = True
        self.max_length = max_length
        self.channel_data = [[], [], [], []]
        self.trigger_data = []
        self.time_data = []
        self.time_window = 0
        self.reset()
        
    def reset(self, show_pending=False):
        """
        Reset all cached plot data

        :param show_pending: indicate pending state
        :type show_pending: bool
        :returns: None
        """
        self.ax.clear()
        self.ax.grid()
        self.ax.set_xlabel(self.xlabel)
        self.ax.set_ylabel(self.ylabel)
        self.ax.set_xlim((self.xmin, self.xmax))
        self.ax.set_ylim((self.ymin, self.ymax))

        self.channel_data = [[], [], [], []]
        self.trigger_data = []
        self.time_data = []
        self.time_window = 0

        for ch in range(4):
            self.ax.plot(self.time_data, self.channel_data[ch],
                         c=self.CHANNEL_COLORS[ch],
                         label=("ch%d" % ch), lw=3)
        if self.show_trigger:
            self.ax.plot(self.time_data, self.trigger_data, c='g',
                         label='trigger', lw=3)

        if show_pending:
            left, width = .25, .5
            bottom, height = .35, .8
            right = left + width
            top = bottom + height
            self.ax.text(0.5 * (left + right), 0.5 * (bottom + top),
                         'Measuring...', horizontalalignment='center',
                         verticalalignment='center', fontsize=56, color='red',
                         fontweight="heavy", alpha=.8, rotation=30,
                         transform=self.fig.transFigure)

        self.fig.canvas.draw()

    def update_plot(self, data, show_trigger=True,
                    enabled_channels=DEFAULT_CHANNEL_CONFIG):
        """
        Update plot

        :param data: plot data
        :type data: list of lists
        :param show_trigger: show trigger in plot
        :type show_trigger: bool
        :param enabled_channels: enabled channels
        :type enabled_channels: list of bool
        :returne: None
        """
        # do a complete redraw of the plot to avoid memory leak!
        self.ax.clear()
        self.show_trigger = show_trigger

        self.ax.grid()
        self.ax.set_xlabel(self.xlabel)
        self.ax.set_ylabel(self.ylabel)

        self.logger.debug("result : %s" % data)

        # update lines data using the lists with new data
        self.time_window += data[5]
        self.time_data.append(self.time_window)

        for ch in range(4):
            self.channel_data[ch].append(data[ch])
            if enabled_channels[ch]:
                self.ax.plot(self.time_data, self.channel_data[ch],
                             c=self.CHANNEL_COLORS[ch],
                             label=("ch%d" % ch), lw=2, marker='v')

        self.trigger_data.append(data[4])

        if self.show_trigger:
            self.ax.plot(self.time_data, self.trigger_data,
                         c=self.TRIGGER_COLOR,
                         label='trg', lw=2, marker='x')

        try:
            # get count of active cannels
            channels = enabled_channels + [show_trigger]
            active_count = len(filter(lambda x: x is True, channels))
            
            self.ax.legend(bbox_to_anchor=(0., 1.02, 1., .102), loc=3,
                           ncol=active_count, mode="expand", borderaxespad=0.,
                           handlelength=2)
        except Exception:
            self.logger.info("An error with the legend occured!")
            self.ax.legend(loc=2)

        if len(self.channel_data[0]) > self.max_length:
            for ch in range(4):
                self.channel_data[ch].remove(self.channel_data[ch][0])
            self.trigger_data.remove(self.trigger_data[0])
            self.time_data.remove(self.time_data[0])
        
        ma = max(max(self.channel_data[0]), max(self.channel_data[1]),
                 max(self.channel_data[2]), max(self.channel_data[3]),
                 max(self.trigger_data))
            
        self.ax.set_ylim(0, ma * 1.1)
        self.ax.set_xlim(self.time_data[0], self.time_data[-1])

        self.fig.canvas.draw()


class LifetimeCanvas(BaseHistogramCanvas):
    """
    A simple histogram for the use with mu lifetime
    measurement

    :param parent: parent widget
    :param logger: logger object
    :type logger: logging.Logger
    :param binning: the binning to use for this canvas
    :type binning: list or tuple or numpy.ndarray
    """
    def __init__(self, parent, logger, binning=(0, 10, 21)):
        BaseHistogramCanvas.__init__(
                self, parent, logger,
                np.linspace(binning[0], binning[1], binning[2]),
                xlabel="Time between Pulses ($\mu$s)", ylabel="Events")

     
class VelocityCanvas(BaseHistogramCanvas):
    """
    A simple histogram for the use with mu velocity measurement

    :param parent: parent widget
    :param logger: logger object
    :type logger: logging.Logger
    :param binning: the binning to use for this canvas
    :type binning: list or tuple or numpy.ndarray
    """
    def __init__(self, parent, logger, binning=(0., 30, 25)):
        BaseHistogramCanvas.__init__(
                self, parent, logger,
                np.linspace(binning[0], binning[1], binning[2]),
                xmin=0., xmax=30, ymin=0, ymax=2,
                ylabel="Events", xlabel="Flight Time (ns)")
        self.dimension = r"$ns$"


class PulseWidthCanvas(BaseHistogramCanvas):
    """
    A simple histogram for the use with pulse width measurement

    :param parent: parent widget
    :param logger: logger object
    :type logger: logging.Logger
    :param hist_color: the color of the histogram
    :type hist_color: str
    """
    def __init__(self, parent, logger, hist_color="r"):
        BaseHistogramCanvas.__init__(
                self, parent, logger, np.linspace(0., 100, 30),
                hist_color=hist_color, xmin=0., xmax=100, ymin=0, ymax=2,
                ylabel="Events", xlabel="Pulse Width (ns)")
        self.ax.set_title("Pulse widths")

    def update_plot(self, data):
        BaseHistogramCanvas.update_plot(self, data)
        self.ax.set_title("Pulse widths")