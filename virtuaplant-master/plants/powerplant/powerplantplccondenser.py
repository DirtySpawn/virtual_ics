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
PLC_CONDENSER = 0x05
PLC_CONDENSER_WATER_VALVE = 0X09


class HMIWindow(Gtk.Window):
    
    def initModbus(self):
        # Create modbus connection to specified address and port
        self.modbusClient = ModbusClient(args.server_addr, port=5020)

    # Default values for the HMI labels
    def resetLabels(self):
        self.condenser_plc_online_value.set_markup("<span weight='bold' foreground='red'>OFF</span>")
        #self.condenser_plc_operational_value.set_markup("<span weight='bold' foreground='black'>N/A</span>")
        self.condenser_plc_waterlevel_value.set_markup("<span weight='bold' foreground='black'>N/A</span>")
        self.condenser_plc_valve_value.set_markup("<span weight='bold' foreground='red'>CLOSED</span>")
        self.condenser_plc_water_valve_value.set_markup("<span weight='bold' foreground='red'>CLOSED</span>")
    
    def __init__(self):
        # Window title
        Gtk.Window.__init__(self, title="Generic PLC")
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

        # Crude Oil Feed Pump
        condenser_plc_online_label = Gtk.Label("Online: ")
        condenser_plc_online_value = Gtk.Label()

        #condenser_plc_operational_label = Gtk.Label("Operational: ")
        #condenser_plc_operational_value = Gtk.Label()

        condenser_plc_waterlevel_label = Gtk.Label("Water Level: ")
        condenser_plc_waterlevel_value = Gtk.Label()
        
        condenser_plc_open_button = Gtk.Button("OPEN")
        condenser_plc_closed_button = Gtk.Button("CLOSED")
        
        condenser_plc_open_button.connect("clicked", self.setCondenserValve, 1)
        condenser_plc_closed_button.connect("clicked", self.setCondenserValve, 0)

        condenser_plc_valve_label = Gtk.Label("Condenser Valve:")
        condenser_plc_valve_value = Gtk.Label()

        condenser_plc_water_valve_label = Gtk.Label("Water Valve:")
        condenser_plc_water_valve_value = Gtk.Label()

        condenser_plc_water_valve_open_button = Gtk.Button("OPEN")
        condenser_plc_water_valve_closed_button = Gtk.Button("CLOSED")

        condenser_plc_water_valve_open_button.connect("clicked", self.setWaterValve, 1)
        condenser_plc_water_valve_closed_button.connect("clicked", self.setWaterValve, 0)


        grid.attach(condenser_plc_online_label, 4, elementIndex, 1, 1)
        grid.attach(condenser_plc_online_value, 5, elementIndex, 1, 1)
        elementIndex += 1

        #grid.attach(condenser_plc_operational_label, 4, elementIndex, 1, 1)
        #grid.attach(condenser_plc_operational_value, 5, elementIndex, 1, 1)
        #elementIndex += 1

        grid.attach(condenser_plc_waterlevel_label, 4, elementIndex, 1, 1)
        grid.attach(condenser_plc_waterlevel_value, 5, elementIndex, 1, 1)
        elementIndex += 1

        grid.attach( condenser_plc_valve_label, 4, elementIndex, 1, 1)
        grid.attach( condenser_plc_valve_value, 5, elementIndex, 1, 1)
        grid.attach(condenser_plc_open_button, 6, elementIndex, 1, 1)
        grid.attach(condenser_plc_closed_button, 7, elementIndex, 1, 1)
        elementIndex += 1

        grid.attach(condenser_plc_water_valve_label, 4, elementIndex, 1, 1)
        grid.attach( condenser_plc_water_valve_value, 5, elementIndex, 1, 1)
        grid.attach(condenser_plc_water_valve_open_button, 6, elementIndex, 1, 1)
        grid.attach(condenser_plc_water_valve_closed_button, 7, elementIndex, 1, 1)
        elementIndex += 1


        # Attach Value Labels
        self.condenser_plc_online_value = condenser_plc_online_value
        #self.condenser_plc_operational_value = condenser_plc_operational_value
        self.condenser_plc_waterlevel_value = condenser_plc_waterlevel_value
        self.condenser_plc_valve_value = condenser_plc_valve_value
        self.condenser_plc_water_valve_value = condenser_plc_water_valve_value

        
        # Set default label values
        self.resetLabels()
        GObject.timeout_add_seconds(MODBUS_SLEEP, self.update_status)

    # Control the feed pump register values
    def setCondenserValve(self, widget, data=None):
        try:
            self.modbusClient.write_register(PLC_CONDENSER, data)
        except:
            pass

    def setWaterValve(self, widget, data=None):
        try:
            self.modbusClient.write_register(PLC_CONDENSER_WATER_VALVE, data)
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
            
            # If the feed pump "0x01" is set to 1, then the pump is running
            if regs[4] == 1:
                #self.condenser_plc_operational_value.set_markup("<span weight='bold' foreground='green'>ON</span>")
                self.condenser_plc_valve_value.set_markup("<span weight='bold' foreground='green'>OPEN</span>")
            elif regs[4] == 0:
                #self.condenser_plc_operational_value.set_markup("<span weight='bold' foreground='red'>OFF</span>")
                self.condenser_plc_valve_value.set_markup("<span weight='bold' foreground='red'>CLOSED</span>")

            if ( (regs[5] == 0) and (regs[6] == 0) and (regs[7] == 0) ):
                self.condenser_plc_waterlevel_value.set_markup("<span weight='bold' foreground='red'>EMPTY</span>")
            if regs[5] == 1:
                self.condenser_plc_waterlevel_value.set_markup("<span weight='bold' foreground='orange'>LOW</span>")
            if regs[6] == 1:
                self.condenser_plc_waterlevel_value.set_markup("<span weight='bold' foreground='gold'>MIN</span>")
            if regs[7] == 1:
                self.condenser_plc_waterlevel_value.set_markup("<span weight='bold' foreground='green'>MAX</span>")
            if regs[8] == 1:
                self.condenser_plc_water_valve_value.set_markup("<span weight='bold' foreground='green'>OPEN</span>")
            elif regs[8] == 0:
                self.condenser_plc_water_valve_value.set_markup("<span weight='bold' foreground='red'>CLOSED</span>")
            
             

        except ConnectionException:
            if not self.modbusClient.connect():
                self.resetLabels()
        except:
            raise
        finally:
            return True

    def setCondenserValve(self, widget, data=None):
        try:
            self.modbusClient.write_register(PLC_CONDENSER, data)
        except:
            pass


def app_main():
    win = HMIWindow()
    win.connect("delete-event", Gtk.main_quit)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()


if __name__ == "__main__":
    GObject.threads_init()
    app_main()
    Gtk.main()
