import matplotlib.pyplot as plt

from loadcell_hx711_mvc.model_LoadCell_HX711 import (
    MjolnirExperiment,
    model_list_resources,
)


def main():
    """An interactive CLI for the Use The Force experiment using Thorlabs Mjolnir."""

    experiment = None

    print(
        "Welcome to the Use The Force interactive environment: Mjolnir. You can use this app to carry out measurements using commands in the terminal."
    )
    print("Type 'help' for available commands.")
    print("Type 'quit' to exit.")

    while True:
        command = input("Mjolnir > ")

        if command == "quit":
            break

        elif command == "help":  # List all commands (manually added this information)
            print("Available commands:")
            print("  list -- List all available devices.")
            print("  connect -- Connect to an Arduino device.")
            print("  deviceinfo")
            print("  tare")
            print("  calibrate")
            print("  measure")
            print("  time-measurement")
            print("  quit")

        elif command == "list":
            resources = model_list_resources()

            print("The available ports are:")
            for resource in resources:
                print(resource)

        elif command.startswith("connect "):
            portname = command.split(" ", 1)[1]

            experiment = MjolnirExperiment(portname)

            print(f"Connected to {portname}")
            print(f"Device: {experiment.device_identification}")

        elif command == "deviceinfo":
            if experiment is None:
                print(
                    "Error: no device connected. You must connect to a device before you can request info."
                )
                continue
            print(f"You are currently using the {experiment.device_identification}")

        elif command == "tare":
            if experiment is None:
                print(
                    "Error: no device connected. You must connect to a device before you can tare."
                )
                continue

            print(experiment.tare())

        elif command.startswith("calibrate "):
            if experiment is None:
                print(
                    "Error: no device connected. You must connect to a device before you can calibrate."
                )
                continue

            reference_force = float(command.split(" ", 1)[1])

            print(experiment.calibrate(reference_force))

        elif command.startswith("measure"):
            if experiment is None:
                print("Error: no device connected.")
                continue

            parts = command.split()

            if len(parts) == 1:
                nmeasurements = 10
            else:
                nmeasurements = int(parts[1])

            force, uncertainty = experiment.take_average_measurement(nmeasurements)

            print(f"Measured force: {force:.4f} N")
            print(f"Statistical uncertainty: {uncertainty:.4f} N")

        elif command.startswith("time-measurement"):
            if experiment is None:
                print("Error: no device connected.")
                continue

            parts = command.split()

            if len(parts) != 2:
                print("Usage: time-measurement <duration in seconds>")
                continue

            duration = float(parts[1])

            times, forces = experiment.measure_over_time_with_single_measurements(
                duration
            )

            plt.figure()
            plt.plot(times, forces, "o")

            plt.xlabel("Time [s]")
            plt.ylabel("Force [N]")
            plt.title("Force vs. Time")
            plt.show()

        else:
            print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
