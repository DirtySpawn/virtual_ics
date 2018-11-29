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
PLC_FUEL = 0x01

AUTOMATION = False  

class HMIWindow(Gtk.Window):
    
    def initModbus(self):
        # Create modbus connection to specified address and port
        self.modbusClient = ModbusClient(args.server_addr, port=5020)

    # Default values for the HMI labels
    def resetLabels(self):
        self.fuel_plc_online_value.set_markup("<span weight='bold' foreground='red'>OFF</span>")
        self.fuel_plc_valve_value.set_markup("<span weight='bold' foreground='red'>OFF</span>")
        self.fuel_plc_rate_value.set_markup("<span weight='bold' foreground='black'>N/A</span>")
        self.fuel_plc_automation_value.set_markup("<span weight='bold' foreground='red'>OFF</span>")
        
    def __init__(self):
        # Window title
        Gtk.Window.__init__(self, title="Fuel PLC")
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
        label.set_markup("<span weight='bold' size='xx-large' color='black'>PLC : Fuel</span>")
        grid.attach(label, 4, elementIndex, 4, 1)
        elementIndex += 1

        # Crude Oil Feed Pump
        fuel_plc_online_label = Gtk.Label("Online: ")
        fuel_plc_online_value = Gtk.Label()

        fuel_plc_automation_on_button = Gtk.Button("ON")
        fuel_plc_automation_off_button = Gtk.Button("OFF")

        fuel_plc_automation_on_button.connect("clicked", self.setAutomation, 1)
        fuel_plc_automation_off_button.connect("clicked", self.setAutomation, 0)

        fuel_plc_automation_label = Gtk.Label("Automation: ")
        fuel_plc_automation_value = Gtk.Label()

        fuel_plc_valve_label = Gtk.Label("Fuel Valve: ")
        fuel_plc_valve_value = Gtk.Label()
        
        fuel_plc_rate_label = Gtk.Label("Rate: ")
        fuel_plc_rate_value = Gtk.Label()

        fuel_plc_valve_on_button = Gtk.Button("ON")
        fuel_plc_valve_off_button = Gtk.Button("OFF")
        
        fuel_plc_valve_on_button.connect("clicked", self.setFuelPLCOperation, 1)
        fuel_plc_valve_off_button.connect("clicked", self.setFuelPLCOperation, 0)

        #condenser_valve_start_button.connect("clicked", self.setCondenserValve, 1)
        #condenser_valve_stop_button.connect("clicked", self.setCondenserValve, 0 )
        
        grid.attach(fuel_plc_online_label, 4, elementIndex, 1, 1)
        grid.attach(fuel_plc_online_value, 5, elementIndex, 1, 1)
        elementIndex += 1

        grid.attach(fuel_plc_automation_label, 4, elementIndex, 1, 1)
        grid.attach(fuel_plc_automation_value, 5, elementIndex, 1, 1)
        grid.attach(fuel_plc_automation_on_button, 6, elementIndex, 1, 1)
        grid.attach(fuel_plc_automation_off_button, 7, elementIndex, 1, 1)
        elementIndex += 1

        '''grid.attach(fuel_plc_operational_label, 4, elementIndex, 1, 1)
        grid.attach(fuel_plc_operational_value, 5, elementIndex, 1, 1)
        elementIndex += 1
        '''
        grid.attach(fuel_plc_rate_label, 4, elementIndex, 1, 1)
        grid.attach(fuel_plc_rate_value, 5, elementIndex, 1, 1)
        elementIndex += 1

        grid.attach(fuel_plc_valve_label, 4, elementIndex, 1, 1)
        grid.attach(fuel_plc_valve_value, 5, elementIndex, 1, 1)
        grid.attach(fuel_plc_valve_on_button, 6, elementIndex, 1, 1)
        grid.attach(fuel_plc_valve_off_button, 7, elementIndex, 1, 1)
        elementIndex += 1

        # Attach Value Labels
        self.fuel_plc_online_value = fuel_plc_online_value
        self.fuel_plc_automation_value = fuel_plc_automation_value
        self.fuel_plc_rate_value = fuel_plc_rate_value
        self.fuel_plc_valve_value = fuel_plc_valve_value

        # Set default label values
        self.resetLabels()
        GObject.timeout_add_seconds(MODBUS_SLEEP, self.update_status)

    # Control the feed pump register values

    def setAutomation(self, widget, data=None):
        global AUTOMATION
        try:
            if data == 0:
                AUTOMATION = False
            elif data == 1:
                AUTOMATION = True
        except:
            pass

        
    def update_status(self):

        try:
            global AUTOMATION
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
            
            self.fuel_plc_online_value.set_markup("<span weight='bold' foreground='green'>ON</span>")

            if AUTOMATION:
                self.fuel_plc_automation_value.set_markup("<span weight='bold' foreground='green'>ON</span>")
                if ( (regs[5] == 0) and (regs[6] == 0) and (regs[7] == 0) ):
                    try:
                        self.modbusClient.write_register(PLC_FUEL, 0)
                    except:
                        pass
                if regs[5] == 1:
                    try:
                        self.modbusClient.write_register(PLC_FUEL, 1)
                    except:
                        pass
            else:
                self.fuel_plc_automation_value.set_markup("<span weight='bold' foreground='red'>OFF</span>")

            # If the feed pump "0x01" is set to 1, then the pump is running
            if regs[0] == 1:
                self.fuel_plc_valve_value.set_markup("<span weight='bold' foreground='green'>ON</span>")
            else:
                self.fuel_plc_valve_value.set_markup("<span weight='bold' foreground='red'>OFF</span>")

            
             

        except ConnectionException:
            if not self.modbusClient.connect():
                self.resetLabels()
        except:
            raise
        finally:
            return True

    def setFuelPLCOperation(self, widget, data=None):
        try:
            self.modbusClient.write_register(PLC_FUEL, data)
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
