# Use the Force
[![GitHub license](https://img.shields.io/github/license/NatuurkundePracticumAmsterdam/Use-the-Force
)](LICENSE)
[![PyPI - Version](https://img.shields.io/pypi/v/use_the_force)
](https://pypi.org/project/use_the_force/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/use_the_force)](https://pypi.org/project/use_the_force/)


Python package for physics practicum at Vrije Universiteit Amsterdam.

## Features
Allows for communication with the M5Din Meter given in the practicum.
Gives a GUI that includes various settings when using the M5Din Meter.

## Using the GUI
The GUI can be called upon with the `start()` function in `use_the_force.gui`. 

Or by rewriting the `start()` function yourself:
```py
import sys
from PySide6 import QtWidgets
import use_the_force.gui as gui

app = QtWidgets.QApplication(sys.argv)
ui = gui.UserInterface()
ui.show()
ret = app.exec_()
sys.exit(ret)
```

## Additional Info
#### Motorstage speed:
`SV(100)` = 1 + 2/3 mm/s\
`SV(100)` ~ 1.666... mm/s\
`SV(60)` = 1 mm/s\
`SV(30)` = 0.5 mm/s

## License
Distributed under the MIT License. See [LICENSE](LICENSE) for more information.
