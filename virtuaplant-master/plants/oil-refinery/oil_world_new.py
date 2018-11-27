#!/usr/bin/env python
from __future__ import division
import argparse
import os
import sys
import time
import threading
from termcolor import colored
import socket
import RPi.GPIO as GPIO

# PWM Module
import Adafruit_PCA9685

# - Modbus
from pymodbus.server.async import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.transaction import ModbusRtuFramer, ModbusAsciiFramer


# GPIO Class
class RasPi:
    # Register sizes
    separator_tank_reg_size = 5
    storage_tank_reg_size = 8

    # Shift register pins
    storage_tank_pin = 17
    separator_tank_pin = 22
    status_led_pin = 27

    data_clock_pin = 4
    data_latch_pin = 23

    # Initialise the PCA9685 using the default address (0x40).
    pwm = Adafruit_PCA9685.PCA9685()
    # Servo Variables
    servo_off = 150
    servo_on = 375
    servo_addr_outlet = 2
    servo_addr_sep = 0
    servo_addr_waste = 1
    
    # Setup the shift register control ports
    def setup_gpio(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.storage_tank_pin, GPIO.OUT)
        GPIO.setup(self.separator_tank_pin, GPIO.OUT)
        GPIO.setup(self.status_led_pin, GPIO.OUT)
        GPIO.setup(self.data_clock_pin, GPIO.OUT)
        GPIO.setup(self.data_latch_pin, GPIO.OUT)
        self.pwm.set_pwm_freq(60)


    def shift_out_values(self, storage_decimal, separator_decimal):
        GPIO.output(self.data_latch_pin, 0)
        for x in range(8):
            GPIO.output(self.storage_tank_pin,
                        (self.calc_leds_from_decimal(storage_decimal, self.storage_tank_reg_size)) >> x & 1)
            GPIO.output(self.separator_tank_pin,
                        (self.calc_leds_from_decimal(separator_decimal, self.separator_tank_reg_size)) >> x & 1)
            GPIO.output(self.status_led_pin, self.calc_status_leds() >> x & 1)
            # Push data out
            GPIO.output(self.data_clock_pin, 1)
            GPIO.output(self.data_clock_pin, 0)
        GPIO.output(self.data_latch_pin, 1)

    @staticmethod
    def calc_leds_from_decimal(decimal, register_size):
        leds = [128, 64, 32, 16, 8, 4, 2, 1]
        number_of_leds = int(round(register_size * decimal))
        leds_base2 = 0
        for x in range(number_of_leds):
            leds_base2 += leds[x]
        return leds_base2

    @staticmethod
    def calc_status_leds():
        leds_base2 = 0
        leds_base2 += 128 if plc_get_tag(PLC_FEED_PUMP) == 1 else 0
        leds_base2 += 64 if plc_get_tag(PLC_TANK_LEVEL) == 1 else 0
        leds_base2 += 32 if plc_get_tag(PLC_OUTLET_VALVE) == 1 else 0
        leds_base2 += 16 if plc_get_tag(PLC_SEP_VALVE) == 1 else 0
        leds_base2 += 8 if plc_get_tag(PLC_WASTE_VALVE) == 1 else 0
        leds_base2 += 5 if plc_get_tag(PLC_OIL_UPPER) == 1 else 0
        # Spare Register value
        # leds_base2 += 2 if PLCGetTag(PLC_SPARE) == 1 else 0
        # Buzzer Shiz (todo)
        # leds_base2 += 1 if PLCGetTag(PLC_ALARM) == 1 else 0
        return leds_base2

    def set_servos(self):
        self.pwm.set_pwm(self.servo_addr_outlet,0,self.servo_on if plc_get_tag(PLC_OUTLET_VALVE) == 1 else self.servo_off)
        self.pwm.set_pwm(self.servo_addr_sep,0,self.servo_on if plc_get_tag(PLC_SEP_VALVE) == 1 else self.servo_off)
        self.pwm.set_pwm(self.servo_addr_waste,0,self.servo_on if plc_get_tag(PLC_WASTE_VALVE) == 1 else self.servo_off)
                
    
world_running = True

class World:

    
    @staticmethod
    def run_world():
        # Remove Game with Hacky values
        tank_storage_vol = 500
        tank_storage_sensor_vol = 5500
        tank_storage_max_vol = 6000
        tank_separator_vol = 4000
        tank_separator_vol_overflow = 4550
        tank_separator_sensor_vol = 5000
        oil_flow_rate_in = 50
        oil_flow_processed = 20
        oil_flow_rate_sto_to_sep = 40
        oil_flow_rate_overflow = 40
        water_flow_rate_waste = 20
        oil_processed = 0
        oil_spilt = 0

        # Setup the PI!
        RasPi().setup_gpio()

        while True:
            error = "\nCurrent Errors \n"

            if plc_get_tag(PLC_FEED_PUMP) == 1:
                tank_storage_vol += oil_flow_rate_in

            if plc_get_tag(PLC_OUTLET_VALVE) == 1 and tank_storage_vol > 0:
                if oil_flow_rate_sto_to_sep > tank_storage_vol:
                    tank_separator_vol += tank_storage_vol
                    tank_storage_vol =0
                else:
                    tank_separator_vol += oil_flow_rate_sto_to_sep
                    tank_storage_vol -= oil_flow_rate_sto_to_sep

            if tank_storage_vol > tank_storage_sensor_vol and plc_get_tag(PLC_TANK_LEVEL) == 1:
                plc_set_tag(PLC_FEED_PUMP, 0)
                error += "\nStorage safety level reached pump off"

            if tank_storage_vol > tank_storage_max_vol:
                oil_spilt = tank_storage_vol - tank_storage_max_vol + oil_spilt
                tank_storage_vol = tank_storage_max_vol
                error += "\nStorage tank overflow!"

            if tank_separator_vol > tank_separator_vol_overflow:
                plc_set_tag(PLC_OIL_UPPER,1)
                tank_separator_vol -= oil_flow_rate_overflow
                oil_spilt += oil_flow_rate_overflow
                error += "\nSeperator tank safety level reached"
            else:
                plc_set_tag(PLC_OIL_UPPER,0)

            if tank_separator_vol > 0 and plc_get_tag(PLC_SEP_VALVE) == 1:
                if oil_flow_processed > tank_separator_vol:
                    oil_processed += tank_separator_vol
                    tank_separator_vol = 0
                else:
                    tank_separator_vol -= oil_flow_processed
                    oil_processed += oil_flow_processed

            if plc_get_tag(PLC_WASTE_VALVE) == 1 and tank_separator_vol > 0:
                oil_spilt += water_flow_rate_waste
                tank_separator_vol -= water_flow_rate_waste

            # Update Modbus Registars
            plc_set_tag(PLC_OIL_SPILL, oil_spilt)
            plc_set_tag(PLC_OIL_PROCESSED, oil_processed)

            # Update decimals
            tank_storage_decimal = tank_storage_vol / tank_storage_max_vol
            tank_separator_decimal = tank_separator_vol / tank_separator_sensor_vol

            # Display on Raspberry Pi
            RasPi().shift_out_values(tank_storage_decimal, tank_separator_decimal)
            RasPi().set_servos()

            # Print info
            os.system("clear")
            print('Oil Refinery Status\n')
            print("Storage Tank Volume:    %s" % tank_storage_vol)
            print("Storage Tank %% Full:    %.2f %%" % (tank_storage_decimal * 100))
            print("Separator Tank Volume:  %s" % tank_separator_vol)
            print("Separator Tank %% Full:  %.2f %%" % (tank_separator_decimal * 100))

            print(colored("\nOil Feed Pump:          Stop", "red") if plc_get_tag(PLC_FEED_PUMP) == 0 else colored(
                "\nOil Feed Pump:          Start", "green"))
            print(colored("Storage Valve:          Off", "red") if plc_get_tag(PLC_OUTLET_VALVE) == 0 else colored(
                "Storage Valve:          On", "green"))
            print(colored("Separator Valve:        Off", "red") if plc_get_tag(PLC_SEP_VALVE) == 0 else colored(
                "Seperator Valve:        On", "green"))
            print(colored("Waste Valve:            Off", "red") if plc_get_tag(PLC_WASTE_VALVE) == 0 else colored(
                "Waste Valve:            On", "green"))

            print(colored("\nOil Processed:          %s" % oil_processed, "green"))
            print(colored("Oil Spilt:              %s" % oil_spilt, "red"))
            print(colored(error, "red"))
            time.sleep(1)


# Modbus stuff
store = ModbusSlaveContext(
    di=ModbusSequentialDataBlock(0, [0] * 100),
    co=ModbusSequentialDataBlock(0, [0] * 100),
    hr=ModbusSequentialDataBlock(0, [0] * 100),
    ir=ModbusSequentialDataBlock(0, [0] * 100))

context = ModbusServerContext(slaves=store, single=True)

# Modbus PLC server information
identity = ModbusDeviceIdentification()
identity.VendorName = 'Simmons Oil Refining Platform'
identity.ProductCode = 'SORP'
identity.VendorUrl = 'http://simmons.com/markets/oil-gas/pages/refining-industry.html'
identity.ProductName = 'SORP 3850'
identity.ModelName = 'Simmons ORP 3850'
identity.MajorMinorRevision = '2.09.01'

# Port the world will listen on
MODBUS_SERVER_PORT = 5020
# MODBUS_SERVER_ADDR = "127.0.0.1"

# PLC Register values for various control functions
PLC_FEED_PUMP = 0x01
PLC_TANK_LEVEL = 0x02
PLC_OUTLET_VALVE = 0x03
PLC_SEP_VALVE = 0x04
PLC_OIL_SPILL = 0x06
PLC_OIL_PROCESSED = 0x07
PLC_WASTE_VALVE = 0x08
PLC_OIL_UPPER = 0x09

#PLC_ALARM = 0x05


# Helper function to set PLC values
def plc_set_tag(addr, value):
    context[0x0].setValues(3, addr, [value])


# Helper function that returns PLC values
def plc_get_tag(addr):
    return context[0x0].getValues(3, addr, count=1)[0]


def start_modbus_server():
    # Run a modbus server on specified address and modbus port (5020)
    StartTcpServer(context, identity=identity, address=(args.server_addr , MODBUS_SERVER_PORT))


def main():
    oil_world = World()
    world_thread = threading.Thread(target=oil_world.run_world)
    try:
        world_thread.daemon = True
        world_thread.start()
        start_modbus_server()

    except KeyboardInterrupt:
        world_running = False
        world_thread.join(0)
        # server_thread.stop()
        GPIO.cleanup()
        # cleanup_stop_thread()
        sys.exit()

# Override Argument parser to throw error and generate help message
# if undefined args are passed
class MyParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('error: %s\n' % message)
        self.print_help()
        sys.exit(2)
        
# Create argparser object to add command line args and help option
parser = MyParser(
	description = 'This Python script starts the SCADA/ICS World Server',
	epilog = '',
	add_help = True)
	
# Add a "-i" argument to receive a filename
parser.add_argument("-t", action = "store", dest="server_addr",
					help = "Modbus server IP address to listen on")

# Print help if no args are supplied
if len(sys.argv)==1:
	parser.print_help()
	sys.exit(1)
	
# Split and process arguments into "args"
args = parser.parse_args()

if __name__ == '__main__':
    sys.exit(main())
