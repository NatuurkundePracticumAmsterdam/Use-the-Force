# Use-The-Force-Mjolnir

**Python software for force measurements using a Thorlabs setup and an HX711 load-cell amplifier.**

Mjolnir is a Python application developed for the Use-The-Force experiment. It provides a graphical interface for connecting to the force-sensor hardware, performing measurements, visualising results and saving measurement data. The project follows the Model-View-Controller (MVC) software architecture and includes a threaded GUI for live measurements.

## Features

- **Hardware communication:** Connect to an Arduino-based HX711 force-sensor setup through a serial interface using PyVISA.
- **Force calibration:** Tare the sensor and calibrate it against a known reference force.
- **Single measurements:** Acquire force measurements.
- **Live measurements:** Monitor force as a function of time while the experiment is running.
- **Live visualisation:** Display measurement data in real time using PyQtGraph.
- **Data export:** Save measurement results to CSV files for further analysis.

## Requirements

- Python 3.10 or later
- An Arduino-based force-sensor setup using an HX711 load-cell amplifier
- The required Arduino firmware
- A compatible serial connection to the hardware

The Python dependencies are managed through the project configuration. They include PySide6, PyQtGraph, NumPy, Matplotlib, PyVISA and PyVISA-py.

## Installation

### Option 1: Install the published package

If the package has been published to PyPI under the name `use-the-force-mjolnir`, install it with:

```bash
python -m pip install use-the-force-mjolnir
```

The threaded graphical interface can then be launched with:

```bash
Mjolnir
```

The package name used for installation is independent of the Python import package name, which remains `loadcell_hx711_mvc`.

### Option 2: Set up the project from source

Clone the repository and navigate to the project directory:

```bash
git clone <repository-url>
cd <repository-directory>
```

Install [uv](https://docs.astral.sh/uv/) if it is not already available. Then synchronise the project environment:

```bash
uv sync
```

This installs the project and its dependencies into the environment managed by uv.

## Usage

### Graphical interface

The recommended interface is the threaded GUI, launched with:

```bash
uv run Mjolnir
```

The general measurement workflow is:

1. Connect to the force-sensor device.
2. Tare the sensor to establish the zero-force reference.
3. Calibrate the sensor using a known reference force.
4. Start a measurement and monitor the force data.
5. Inspect the resulting plots.
6. Save the measurement data to a CSV file for further analysis.

The threaded implementation allows the GUI to remain responsive while measurement data are acquired and displayed.

## Hardware and communication

The software communicates with the Arduino through a serial connection using PyVISA and the PyVISA-py backend.

The Arduino firmware reads the HX711 load-cell amplifier and provides measurement data to the Python application. The firmware and Python controller must use compatible serial commands and settings.

Before starting a measurement:

- Ensure that the Arduino and force sensor are connected and powered.
- Upload the compatible firmware to the Arduino.
- Connect the Arduino to the computer.
- Check that the serial device is available to the application.
- Tare and calibrate the sensor as appropriate for the experiment.

The serial port and firmware configuration must match the connected hardware.

## Software architecture

The project follows the Model-View-Controller (MVC) design pattern. The Python package is named `loadcell_hx711_mvc` to describe both the hardware being controlled and the software architecture.

The main components are:

| Component | Responsibility |
|---|---|
| Controller | Communicates with the Arduino and handles low-level device operations. |
| Model | Manages the experiment, measurement operations, calibration and measurement data. |
| View / GUI | Provides the graphical interface for controlling the experiment and displaying results. |

### Main modules

The source code is located in `src/loadcell_hx711_mvc/`.

| Module | Purpose |
|---|---|
| `controller_LoadCell_HX711.py` | Handles device communication and low-level force-sensor operations. |
| `Threading_model_LoadCell_HX711.py` | Implements the experiment model and threaded measurement functionality. |
| `Threading_gui_LoadCell_HX711.py` | Implements the live, threaded graphical interface. |
| `Threading_ui_Mjolnir_designer.py` | Generated Python interface for the threaded Qt Designer GUI. |

The Qt Designer `.ui` files define the GUI layouts, while the corresponding generated Python modules provide the interface classes used by the application.

## Obsolete modules 

This is located in `ObsoluteOrUnusedFeatures/`, and contains the non-threaded implementation of the Mjolnir experiment, along with some unused or not completely developed features such as the CLI. 

| Main modules | Purpose |
|---|---|
| `gui_LoadCell_HX711.py` | Contains the earlier, non-threaded graphical interface. |
| `interactive_cli_LoadCell_HX711.py` | Implements the interactive command-line interface. |
| `ui_Mjolnir_designer.py` | Generated Python interface for the original Qt Designer GUI. |
| `interactive_cli_LoadCell_HX711.py` | An interactive CLI for the Mjolnir experiment. This module is not fully developed. |
| `cli_LoadCell_HX711.py` | A starter version of the CLI for the Mjolnir experiment, but this implementation does not work well with the current way UTF works. |

## Development

The project uses `pyproject.toml` to define its metadata, dependencies, entry points and development tasks. The `uv_build` backend is used to build distribution packages.

### Updating the graphical interface

If a Qt Designer `.ui` file is modified, regenerate its corresponding Python module before running the application.

The project defines two Poe tasks:

```bash
poe threadcompile
```

Regenerates the Python interface for the threaded GUI.

```bash
poe compile
```

Regenerates the Python interface for the original GUI, used in `ObsoluteOrUnusedFeatures/`.

These commands require Poe, provided by the `poethepoet` package, to be available in the environment.

### Building the package

To build a source distribution and a wheel:

```bash
uv build
```

The resulting distribution files are placed in the `dist/` directory.

## Dependencies

The main dependencies are:

- [PySide6](https://doc.qt.io/qtforpython-6/): Graphical interface.
- [PyQtGraph](https://www.pyqtgraph.org/): Live measurement plots.
- [NumPy](https://numpy.org/): Numerical calculations and measurement statistics.
- [Matplotlib](https://matplotlib.org/): Plotting and data visualisation.
- [PyVISA](https://pyvisa.readthedocs.io/): Instrument communication.
- [PyVISA-py](https://pyvisa.readthedocs.io/projects/pyvisa-py/en/latest/): Python-based VISA backend.
- [PySerial](https://pyserial.readthedocs.io/): Serial-port support.
- [Click](https://click.palletsprojects.com/): Command-line tooling.

## License

Add the project's chosen open-source licence here before publishing the package.

## Acknowledgements

Developed for the Use-The-Force experiment in the physics practical courses at the Vrije Universiteit Amsterdam and University of Amsterdam.
