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
PLC_BOILER = 0x02


class HMIWindow(Gtk.Window):
    
    def initModbus(self):
        # Create modbus connection to specified address and port
        self.modbusClient = ModbusClient(args.server_addr, port=5020)

    # Default values for the HMI labels
    def resetLabels(self):
        self.boiler_plc_online_value.set_markup("<span weight='bold' foreground='red'>OFF</span>")
        self.boiler_plc_wateramount_value.set_markup("<span weight='bold' foreground='black'>N/A</span>")
        #self.fuel_plc_rate_value.set_markup("<span weight='bold' foreground='black'>N/A</span>")
        
        
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
        label.set_markup("<span weight='bold' size='xx-large' color='black'>PLC : BOILER</span>")
        grid.attach(label, 4, elementIndex, 4, 1)
        elementIndex += 1

        # Crude Oil Feed Pump
        boiler_plc_online_label = Gtk.Label("Online: ")
        boiler_plc_online_value = Gtk.Label()

        boiler_plc_wateramount_label = Gtk.Label("Water Amount: ")
        boiler_plc_wateramount_value = Gtk.Label()
        
        
        grid.attach(boiler_plc_online_label, 4, elementIndex, 1, 1)
        grid.attach(boiler_plc_online_value, 5, elementIndex, 1, 1)
        elementIndex += 1

        grid.attach(boiler_plc_wateramount_label, 4, elementIndex, 1, 1)
        grid.attach(boiler_plc_wateramount_value, 5, elementIndex, 1, 1)
        elementIndex += 1

        
        # Attach Value Labels
        self.boiler_plc_online_value = boiler_plc_online_value
        self.boiler_plc_wateramount_value = boiler_plc_wateramount_value
        

        # Set default label values
        self.resetLabels()
        GObject.timeout_add_seconds(MODBUS_SLEEP, self.update_status)

    # Control the feed pump register values
    def setCondenserValve(self, widget, data=None):
        try:
            self.modbusClient.write_register(PLC_BOILER, data)
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
            
            self.boiler_plc_online_value.set_markup("<span weight='bold' foreground='green'>ON</span>")
            
            # If the feed pump "0x01" is set to 1, then the pump is running
            '''
            if regs[0] == 1:
                self.fuel_plc_operational_value.set_markup("<span weight='bold' foreground='green'>ON</span>")
            else:
                self.fuel_plc_operational_value.set_markup("<span weight='bold' foreground='red'>OFF</span>")
            '''
             

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
