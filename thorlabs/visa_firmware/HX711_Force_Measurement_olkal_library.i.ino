#include <HX711_ADC.h> // olkal library

// Define a set of commands:
#define COM_IDN        "*IDN?"       // Gives the identification number
#define COM_TARE       "TARE"        // Command to tare the load cell
#define COM_CALIBRATE  "CALIBRATE "  // Command to calibrate the load cell
#define COM_MEASURE    "MEASURE?"    // Command to measure and read out from load cell

// Arduino pins:
const int HX711_dout = 4; // Arduino pin #4
const int HX711_sck = 5;  // Arduino pin #5

//HX711 constructor:
HX711_ADC LoadCell(HX711_dout, HX711_sck); // Creating an object called LoadCell using these specific Arduino pins

// Identification string:
const char IDN_STRING[] = "Arduino HX711 Force Sensor v0.1.0";

void setup() {
  // This runs only once as soon as you start up
  Serial.begin(57600); // The argument here is the baud rate, i.e. the speed at which the adruino and computer communicate over serial
  Serial.setTimeout(100); // Prevents teh Arduino from getting stuck indefinitely if there is something wrong with the serial communication

  Serial.println("STARTING"); // Used for troubleshooting


  LoadCell.begin();
  unsigned long stabilizingtime = 2000; // precision right after power-up can be improved by adding a few seconds of stabilizing time (from olkal example) -> 2000 corresponds to a 2 second stabilization period
  bool _tare = true; //set this to false if you don't want tare to be performed in the next step

  LoadCell.start(stabilizingtime, _tare); // Actually starts the process


  Serial.println("READY"); // A little printed out message showing that the system has started up properly
}

void loop() {
  // Put your main code here, to run repeatedly:

  LoadCell.update(); // The update() function checks for new data and starts the next conversion

  if (Serial.available()) { // Here you can type someting into the serial monitor in order to give a command
    
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == COM_IDN){
      Serial.println(IDN_STRING);
    }
    
    else if (command == COM_TARE) {
      // Tare the load cell
      LoadCell.tare(); // This comes from the olkal library
      Serial.println("TARE COMPLETE");
    }

    else if (command.startsWith(COM_CALIBRATE)) {
      // Calibrate the load cell -> The unit used to calibrate the load cell is also the unit that all subsequent measurements return
      String valueString = command.substring(strlen(COM_CALIBRATE));
      float known_mass = valueString.toFloat();

      LoadCell.refreshDataSet();
      float newCalibrationValue = LoadCell.getNewCalibration(known_mass);
      LoadCell.setCalFactor(newCalibrationValue);

      // Serial.print("CALIBRATION FACTOR: ");
      // Serial.println(newCalibrationValue);
      Serial.println("CALIBRATION COMPLETE");
      }

    else if (command == COM_MEASURE) {
      // Measure the mass of a load. The units of this measurement are the same as the units that were used during calibration
      float value = LoadCell.getData();
      Serial.println(value); // This prints the measured value onto the serial monitor
    }

    // Unknown command
    else {

      Serial.print("ERROR: UNKNOWN COMMAND ");
      Serial.println(command);
    }

  }


}
