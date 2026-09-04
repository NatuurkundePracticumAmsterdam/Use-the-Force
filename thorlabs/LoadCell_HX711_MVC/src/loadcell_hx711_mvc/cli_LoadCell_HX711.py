import click

from loadcell_hx711_mvc.model_LoadCell_HX711 import (
    MjolnirExperiment,
    model_list_resources,
)


@click.group()
def cmd_group():
    """An app to measure force using the Thorlabs Mjolnir setup."""
    pass


@cmd_group.command()
@click.argument("portname", required=True)
def info(portname):
    """Obtain the identification string of the device at PORTNAME.

    PORTNAME is the name of the port under investigation.
    Use 'list' to see available ports.
    """

    experiment = MjolnirExperiment(portname)

    print(f"The identification string of the {portname} port is:")
    print(experiment.device_identification)


@cmd_group.command()
def list():
    """Print all available ports on the system."""

    resources = model_list_resources()

    print("The available ports are:")
    for resource in resources:
        print(resource)


@cmd_group.command()
@click.argument("portname", required=True)
def tare(portname):
    """Tare the load cell connected to PORTNAME"""

    experiment = MjolnirExperiment(portname)

    response = experiment.tare()

    print(response)


@cmd_group.command()
@click.argument("portname", required=True)
@click.argument("reference_force", type=float)
def calibrate(portname, reference_force):
    """Calibrate the load cell using a known reference force in NEWTONS.

    PORTNAME is the name of the Arduino port.

    REFERENCE_FORCE is the known force applied to the load cell, in N.
    """

    experiment = MjolnirExperiment(portname)

    response = experiment.calibrate(reference_force)

    print(response)


@cmd_group.command()
@click.argument("portname", required=True)
@click.option(
    "-n",
    "--nmeasurements",
    default=10,
    type=click.IntRange(min=2),
    show_default=True,
    help="Number of measurements used to calculate the average force.",
)
def measure(portname, nmeasurements):
    """Measure force using the load cell connected to PORTNAME."""

    experiment = MjolnirExperiment(portname)

    force, uncertainty = experiment.take_average_measurement(nmeasurements)

    print(f"Measured force: {force:.4f} N")
    print(f"Statistical uncertainty: {uncertainty:.4f} N")


if __name__ == "__main__":
    cmd_group()
