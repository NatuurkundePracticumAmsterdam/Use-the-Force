#include <HX711_ADC.h> // olkal library (https://github.com/olkal/HX711_ADC)

// Define a set of commands:
#define COM_IDN        "*IDN?"       // Gives the identification number
#define COM_TARE       "TARE"        // Command to tare the load cell
#define COM_CALIBRATE  "CALIBRATE "  // Command to calibrate the load cell
// #define COM_MEASURE    "MEASURE?"    // Command to measure and read out from load cell 
#define COM_START       "START"      // Start continuous measurement (Needed for implementation of continuous readout)
#define COM_STOP        "STOP"       // Stop continuous measurement (Needed for implementation of continuous readout)

// Arduino pins:
const int HX711_dout = 4; // Arduino pin #4
const int HX711_sck = 5;  // Arduino pin #5

//HX711 constructor:
HX711_ADC LoadCell(HX711_dout, HX711_sck); // Creating an object called LoadCell using these specific Arduino pins

// Identification string:
const char IDN_STRING[] = "Arduino HX711 Force Sensor v0.3.0";

// A variable to keep track of whether we are measuring or not (needed for implementation of continuous readout):
bool measuring = false;

void setup() {
  // This runs only once as soon as you start up
  Serial.begin(57600); // The argument here is the baud rate, i.e. the speed at which the adruino and computer communicate over serial
  Serial.setTimeout(100); // Prevents teh Arduino from getting stuck indefinitely if there is something wrong with the serial communication

  Serial.println("STARTING"); // Used for troubleshooting


  LoadCell.begin();
  unsigned long stabilizingtime = 2000; // precision right after power-up can be improved by adding a few seconds of stabilizing time (from olkal example) -> 2000 corresponds to a 2 second stabilization period
  bool _tare = true; //set this to false if you don't want tare to be performed in the next step

  LoadCell.start(stabilizingtime, _tare); // Actually starts the process

  // Some tests to see the conversion time and sampling rates
  while (!LoadCell.update());

  Serial.print("HX711 conversion time: ");
  Serial.print(LoadCell.getConversionTime());
  Serial.println(" ms");

  Serial.print("HX711 sampling rate: ");
  Serial.print(LoadCell.getSPS());
  Serial.println(" Hz");

  Serial.print("HX711 settling time: ");
  Serial.print(LoadCell.getSettlingTime());
  Serial.println(" ms");
  // Sampling rate tests done


  Serial.println("READY"); // A little printed out message showing that the system has started up properly
}

void loop() {
  // Put your main code here, to run repeatedly:

  if (LoadCell.update()) { // The update() function checks for new data (a new conversion)-> whenever any new data is in, if you are in the measuring state, data is printed

    if (measuring) { // If we are in the "measuring" state, constantly print out new data whenever it is available (continuous readout)
      float value = LoadCell.getData();

      Serial.print("DATA,"); // Have every line with data start with "DATA," so that you can distinguish this from other things that the Arduino is printing (related to taring or calibration, for example)
      Serial.println(value);
    }
  }

  // Check whether a command has been received
  if (Serial.available()) { // Here you can type someting into the serial monitor in order to give a command
    
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == COM_IDN){
      Serial.println(IDN_STRING);
    }
    
    else if (command == COM_TARE) {
      // Tare the load cell
      measuring = false; // Make sure we are not in the "measuring" state

      LoadCell.tare(); // This comes from the olkal library
      Serial.println("TARE COMPLETE");
    }

    else if (command.startsWith(COM_CALIBRATE)) {
      // Calibrate the load cell -> The unit used to calibrate the load cell is also the unit that all subsequent measurements return
      measuring = false; // Make sure we are not in the "measuring" state

      String valueString = command.substring(strlen(COM_CALIBRATE));
      float known_force = valueString.toFloat();

      LoadCell.refreshDataSet();
      float newCalibrationValue = LoadCell.getNewCalibration(known_force);
      LoadCell.setCalFactor(newCalibrationValue);

      // Serial.print("CALIBRATION FACTOR: ");
      // Serial.println(newCalibrationValue);
      Serial.println("CALIBRATION COMPLETE");
      }

      else if (command == COM_START) {
        measuring = true; // Turn on the "measuring" state
        Serial.println("MEASURING STATE STARTED");
      }

      else if (command == COM_STOP) {
        measuring = false; // Turn off the "measuring" state
        Serial.println("MEASURING STATE STOPPED");
      }

    // The COM_MEASURE command is obsolute after implementing continuous streaming
    // else if (command == COM_MEASURE) {
    //   // Measure the force of a load exerted on the sensor. The units of this measurement are the same as the units that were used during calibration
    //   float value = LoadCell.getData();
    //   Serial.println(value); // This prints the measured value onto the serial monitor
    // }

    // Unknown command
    else {

      Serial.print("ERROR: UNKNOWN COMMAND ");
      Serial.println(command);
    }

  }


}
