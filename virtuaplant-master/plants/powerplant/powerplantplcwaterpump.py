#!/usr/bin/env python

# IMPORTS #
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk, Gdk, GObject
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from pymodbus.exceptions import ConnectionException

import argparse
import os
import sys
import time

# Argument Parsing
class MyParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('error: %s\n' % message)
        self.print_help()
        sys.exit(2)
        
# Create argparser object to add command line args and help option
parser = MyParser(
	description = 'This Python script runs the SCADA HMI to control the PLC',
	epilog = '',
	add_help = True)
	
# Add a "-i" argument to receive a filename
parser.add_argument("-t", action = "store", dest="server_addr",
					help = "Modbus server IP address to connect the HMI to")

# Print help if no args are supplied
if len(sys.argv)==1:
	parser.print_help()
	sys.exit(1)

# Split and process arguments into "args"
args = parser.parse_args()

MODBUS_SLEEP=1


# ******************* PLCs ************************
# WATER PUMP
PLC_WATERPUMP_VALVE = 0x01
PLC_WATERPUMP_RATE = 0x02

# FUEL
PLC_FUEL_VALVE = 0x03
PLC_FUEL_RATE = 0x04

# BOILER
PLC_BOILER = 0x05
PLC_BOILER_TEMP = 0x06
PLC_BOILER_WATER_VOLUME = 0x07
PLC_BOILER_WATER_VOLUME_LOW = 0x08
PLC_BOILER_WATER_VOLUME_HIGH = 0X09

# CONDENSER
PLC_CONDENSER_VALVE = 0x0a
PLC_CONDENSER_WATER_VOLUME = 0x0b

# TURBINE
PLC_TURBINE_PRESSURE_HIGH = 0x0c
PLC_TURBINE_PRESSURE_LOW = 0x0d

# GENERATOR
PLC_GENERATOR = 0x0e
PLC_GENERATOR_OUTPUT = 0x0f

# PYLON
PLC_PYLON = 0x10

# *************************************************
BUTTONACTIVE = 5
ticks_button_up_active = BUTTONACTIVE
ticks_button_down_active = BUTTONACTIVE

class HMIWindow(Gtk.Window):
    
    def initModbus(self):
        # Create modbus connection to specified address and port
        self.modbusClient = ModbusClient(args.server_addr, port=5020)

    # Default values for the HMI labels
    def resetLabels(self):
        self.waterpump_plc_online_value.set_markup("<span weight='bold' foreground='red'>OFF</span>")
        self.waterpump_plc_valve_value.set_markup("<span weight='bold' foreground='black'>N/A</span>")
        self.waterpump_plc_water_rate_value.set_markup("<span weight='bold' foreground='black'>N/A</span>")
        self.waterpump_plc_valve_value.set_markup("<span weight='bold' foreground='black'>N/A</span>")
        

        
    def __init__(self):
        # Window title
        Gtk.Window.__init__(self, title="WATER PUMP PLC")
        self.set_border_width(100)
        
        #Create modbus connection
        self.initModbus()

        elementIndex = 0
        # Grid
        grid = Gtk.Grid()
        grid.set_row_spacing(15)
        grid.set_column_spacing(10)
        self.add(grid)

        # Main title label
        label = Gtk.Label()
        label.set_markup("<span weight='bold' size='xx-large' color='black'>PLC : WATER PUMP</span>")
        grid.attach(label, 4, elementIndex, 4, 1)
        elementIndex += 1

        # Water Pump
        # Connected to World / HMI
        waterpump_plc_online_label = Gtk.Label("Online: ")
        waterpump_plc_online_value = Gtk.Label()

        # Valve / Button to Turn ON/OFF
        waterpump_plc_valve_label = Gtk.Label("Water Valve: ")
        waterpump_plc_valve_value = Gtk.Label()
        waterpump_plc_valve_on_button = Gtk.Button("ON")
        waterpump_plc_valve_off_button = Gtk.Button("OFF")
        waterpump_plc_valve_on_button.connect("clicked", self.setWaterPumpValve, 1)
        waterpump_plc_valve_off_button.connect("clicked", self.setWaterPumpValve, 0)
        
        waterpump_plc_water_rate_label = Gtk.Label("Water Rate: ")
        waterpump_plc_water_rate_value = Gtk.Label()        
        waterpump_plc_rate_up_button = Gtk.Button("+")
        waterpump_plc_rate_down_button = Gtk.Button("-")

        waterpump_plc_rate_up_button.connect("clicked", self.setWaterPumpRate, 0)
        waterpump_plc_rate_down_button.connect("clicked", self.setWaterPumpRate, 2)

        grid.attach(waterpump_plc_online_label, 4, elementIndex, 1, 1)
        grid.attach(waterpump_plc_online_value, 5, elementIndex, 1, 1)
        elementIndex += 1

        grid.attach(waterpump_plc_valve_label, 4, elementIndex, 1, 1)
        grid.attach(waterpump_plc_valve_value, 5, elementIndex, 1, 1)
        grid.attach(waterpump_plc_valve_on_button, 6, elementIndex, 1, 1)
        grid.attach(waterpump_plc_valve_off_button, 7, elementIndex, 1, 1)        
        elementIndex += 1

        grid.attach(waterpump_plc_water_rate_label, 4, elementIndex, 1, 1)
        grid.attach(waterpump_plc_water_rate_value, 5, elementIndex, 1, 1)
        grid.attach(waterpump_plc_rate_up_button, 6, elementIndex, 1, 1)
        grid.attach(waterpump_plc_rate_down_button, 7, elementIndex, 1, 1)

        elementIndex += 1
        
        errorlabel = Gtk.Label()
        grid.attach(errorlabel, 4, elementIndex, 1, 1)

        elementIndex += 1
        # Attach Value Labels
        self.waterpump_plc_online_value = waterpump_plc_online_value
        self.waterpump_plc_valve_value = waterpump_plc_valve_value
        self.waterpump_plc_water_rate_value = waterpump_plc_water_rate_value
        self.waterpump_plc_valve_value = waterpump_plc_valve_value


        # Set default label values
        self.resetLabels()
        GObject.timeout_add_seconds(MODBUS_SLEEP, self.update_status)

    # Control the Water Pump Register Values
    def setWaterPumpValve(self, widget, data=None):
        try:
            self.modbusClient.write_register(PLC_WATERPUMP_VALVE, data)
        except:
            pass
    
    # Controls the Water Pump Flow Rate
    def setWaterPumpRate(self, widget, data=None):
        try:
            self.modbusClient.write_register(PLC_WATERPUMP_RATE, data)
        except:
            pass
    
    def update_status(self):

        try:
            # Store the registers of the PLC in "rr"
            rr = self.modbusClient.read_holding_registers(1,16)
            regs = []

            # If we get back a blank response, something happened connecting to the PLC
            if not rr or not rr.registers:
                raise ConnectionException
            
            # Regs is an iterable list of register key:values
            regs = rr.registers

            if not regs or len(regs) < 16:
                raise ConnectionException

            
            self.waterpump_plc_online_value.set_markup("<span weight='bold' foreground='green'>ON</span>")
            
            if regs[PLC_WATERPUMP_RATE - 1] > 1:
                rate = int(regs[PLC_WATERPUMP_RATE - 1]) - 2
                rate *= -5
                rate += 105
                self.waterpump_plc_water_rate_value.set_markup("<span weight='bold' foreground='green'>" + str(rate) + "%</span>")

            if regs[PLC_WATERPUMP_VALVE - 1] == 0:
                self.waterpump_plc_valve_value.set_markup("<span weight='bold' foreground='red'>OFF</span>")
            if regs[ PLC_WATERPUMP_VALVE - 1 ] == 1:
                self.waterpump_plc_valve_value.set_markup("<span weight='bold' foreground='green'>ON</span>")
           

        except ConnectionException:
            if not self.modbusClient.connect():
                self.resetLabels()
        except:
            raise
        finally:
            return True



def app_main():
    win = HMIWindow()
    win.connect("delete-event", Gtk.main_quit)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()


if __name__ == "__main__":
    GObject.threads_init()
    app_main()
    Gtk.main()
