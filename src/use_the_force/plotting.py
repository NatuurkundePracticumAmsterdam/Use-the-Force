from matplotlib import pyplot as plt
import matplotlib

# Use TkAgg backend for interactive plotting
# TkAgg is way less laggy than the default Agg backend
matplotlib.use("TkAgg")
# self.plt.ion()

__all__ = ["Plotting"]


class Plotting:
    def __init__(
        self, xlabel: str = "Time (s)", ylabel: str = "Force (mN)", **kwargs
    ) -> None:
        """Class to start with plots.

        :param xlabel: Text displayed on x-axes
        :type xlabel: str
        :param ylabel: Text displayed on y-axes
        :type ylabel: str
        :param startTime: Offsets xlimit of the plot
        :type startTime: int
        :rtype: None
        """
        ### ===PARAMETERS THAT ONE CAN ALTER=== ###
        self.xlabel: str = xlabel
        self.ylabel: str = ylabel
        self.startTime: float = float(kwargs.pop("startTime", 0.0))

        ### ===START A NEW FIG=== ###
        self._init_fig()

    def _init_fig(self) -> None:
        """
        Initializes a new figure
        """
        # 1: Create plot
        self.fig, self.ax1 = plt.subplots(1)
        (self.lines,) = self.ax1.plot([], [])

        # 2: Making the axis prettier.
        # self.ax1.set_autoscalex_on(True)
        self.ax1.set_xlabel(self.xlabel)
        self.ax1.set_ylabel(self.ylabel)
        # self.ax1.set_autoscaley_on(True)
        # self.ax1.set_ylim( self.MinY, self.MaxY )
        self.ax1.grid(visible=True)
        self.ax1.set_xlim(left=self.startTime)

        # 3: Alternative text boxes, will report the time between two points,
        # and all the current heights.
        # self.txtR = self.ax1.text( 0, self.MinY , "" )

        self.fig.show()
        self.fig.canvas.draw()

    ### ===ANIMATION FUNCTION===###
    # Each loop this function is performed. I return the graph.

    def Update(self, data) -> None:
        """
        Updates the canvas to contain new data

        Replaces the entire data set with the new one, should be fine for smaller data sets.

        :param data: The new data set to be drawn
        :type data: list
        :rtype: None
        """
        # Set new data
        self.lines.set_data(data)

        self.ax1.set_ylim(
            bottom=min(data[1]) - abs(min(data[1])) / 10,
            top=max(data[1]) + abs(max(data[1])) / 10,
        )
        self.ax1.set_xlim(left=self.startTime, right=data[0][-1])
        self.ax1.autoscale_view()
        # We need to draw *and* flush
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
