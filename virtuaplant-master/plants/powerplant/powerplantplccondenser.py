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

PLC_BOILER_NEED_WATER = 0x13
PLC_BOILER_STOP_WATER = 0x14

# CONDENSER
PLC_CONDENSER_VALVE = 0x0a
PLC_CONDENSER_WATER_VOLUME = 0x0b

# TURBINE
PLC_TURBINE_PRESSURE_HIGH = 0x0c
PLC_TURBINE_PRESSURE = 0x0d
PLC_TURBINE_RPMs = 0x11

# GENERATOR
PLC_GENERATOR_STATUS = 0x0e
PLC_GENERATOR_OUTPUT = 0x0f

# PYLON
PLC_PYLON_STATUS = 0x10
PLC_PYLON_POWER = 0x12

# *************************************************

CONDENSATION = 30
ticks_to_condensing = CONDENSATION


class HMIWindow(Gtk.Window):
    
    def initModbus(self):
        # Create modbus connection to specified address and port
        self.modbusClient = ModbusClient(args.server_addr, port=5020)

    # Default values for the HMI labels
    def resetLabels(self):
        self.condenser_plc_online_value.set_markup("<span weight='bold' foreground='red'>OFF</span>")
        self.condenser_plc_valve_value.set_markup("<span weight='bold' foreground='red'>CLOSED</span>")
        self.condenser_plc_water_volume_value.set_markup("<span weight='bold' foreground='black'>0</span>")

    
    def __init__(self):
        # Window title
        Gtk.Window.__init__(self, title="Condenser PLC")
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
        label.set_markup("<span weight='bold' size='xx-large' color='black'>PLC : CONDENSER</span>")
        grid.attach(label, 4, elementIndex, 4, 1)
        elementIndex += 1

        # Condenser Online
        condenser_plc_online_label = Gtk.Label("Online: ")
        condenser_plc_online_value = Gtk.Label()

        # Condenser Valve
        condenser_plc_valve_label = Gtk.Label("Water Valve: ")
        condenser_plc_valve_value = Gtk.Label()
        condenser_plc_water_valve_open_button = Gtk.Button("OPEN")
        condenser_plc_water_valve_close_button = Gtk.Button("CLOSE")
        condenser_plc_water_valve_open_button.connect("clicked", self.setCondenserValve, 1)
        condenser_plc_water_valve_close_button.connect("clicked", self.setCondenserValve, 0)

        # Condenser - Holds amount of water in condenser
        condenser_plc_water_volume_label = Gtk.Label("Volume: ")
        condenser_plc_water_volume_value = Gtk.Label()

        grid.attach(condenser_plc_online_label, 4, elementIndex, 1, 1)
        grid.attach(condenser_plc_online_value, 5, elementIndex, 1, 1)
        elementIndex += 1

        grid.attach(condenser_plc_valve_label, 4, elementIndex, 1, 1)
        grid.attach(condenser_plc_valve_value, 5, elementIndex, 1, 1)
        grid.attach(condenser_plc_water_valve_open_button, 6, elementIndex, 1, 1)
        grid.attach(condenser_plc_water_valve_close_button, 7, elementIndex, 1, 1)
        elementIndex += 1

        grid.attach(condenser_plc_water_volume_label, 4, elementIndex, 1, 1)
        grid.attach(condenser_plc_water_volume_value, 5, elementIndex, 1, 1)
        elementIndex += 1

        # Attach Value Labels
        self.condenser_plc_online_value = condenser_plc_online_value
        self.condenser_plc_valve_value = condenser_plc_valve_value
        self.condenser_plc_water_volume_value = condenser_plc_water_volume_value
        self.condenservolume = 0.0
        self.pressurechange = 0.0
        self.ticks_to_condensing = 2
        self.flowrate = 10.0
        self.rateboiling = 1
        self.ratenotboiling = 2
        self.rate = 1

        try:
            self.modbusClient.write_register(PLC_CONDENSER_VALVE, 1)
            self.modbusClient.write_register(PLC_CONDENSER_WATER_VOLUME, 0.0)
        except:
            pass
        
        # Set default label values
        self.resetLabels()
        GObject.timeout_add_seconds(MODBUS_SLEEP, self.update_status)

    # Control the feed pump register values
    def setCondenserValve(self, widget, data=None):
        try:
            self.modbusClient.write_register(PLC_CONDENSER_VALVE, data)
        except:
            pass

    def setCondenserVolume(self, widget, data=None):
        try:
            self.modbusClient.write_register(PLC_CONDENSER_WATER_VOLUME, data)
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
            
            self.condenser_plc_online_value.set_markup("<span weight='bold' foreground='green'>ON</span>")
            self.condenser_plc_water_volume_value.set_markup("<span weight='bold' foreground='black'>" + str(regs[PLC_CONDENSER_WATER_VOLUME - 1])  + "</span>")

            # Valve Open
            if regs[PLC_CONDENSER_VALVE - 1] == 1:
                self.condenser_plc_valve_value.set_markup("<span weight='bold' foreground='green'>OPEN</span>")
            elif regs[PLC_CONDENSER_VALVE - 1] == 0:
                self.condenser_plc_valve_value.set_markup("<span weight='bold' foreground='red'>CLOSED</span>")


            if regs[PLC_CONDENSER_VALVE - 1] == 1:
                vol = regs[PLC_BOILER_WATER_VOLUME - 1]
                if self.condenservolume > 10.0:
                    self.condenservolume -= self.flowrate
                    self.modbusClient.write_register(PLC_CONDENSER_WATER_VOLUME, self.condenservolume)
                    self.modbusClient.write_register(PLC_BOILER_WATER_VOLUME, vol + self.flowrate)
                else:
                    self.modbusClient.write_register(PLC_BOILER_WATER_VOLUME, vol + self.condenservolume)
                    self.condenservolume = 0.0
                    self.modbusClient.write_register(PLC_CONDENSER_WATER_VOLUME, 0) 

            if regs[ PLC_TURBINE_PRESSURE - 1 ] > 0:
                self.ticks_to_condensing -= 1
                if self.ticks_to_condensing <= 0:
                    if (regs[PLC_BOILER_TEMP - 1] < 100) or (regs[PLC_FUEL_RATE - 1] - 3) == 3 :
                        self.rate = self.ratenotboiling
                    else:
                        self.rate = self.rateboiling
                    self.ticks_to_condensing = 2
                    self.condenservolume += 1 * self.rate
                    self.modbusClient.write_register(PLC_CONDENSER_WATER_VOLUME, self.condenservolume )
                    self.modbusClient.write_register( PLC_TURBINE_PRESSURE, regs[PLC_TURBINE_PRESSURE - 1] - (1 * self.rate) )



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
