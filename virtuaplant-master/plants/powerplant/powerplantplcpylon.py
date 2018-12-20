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
PLC_TURBINE_PRESSURE_LOW = 0x0d
PLC_TURBINE_RPMs = 0x11

# GENERATOR
PLC_GENERATOR_STATUS = 0x0e
PLC_GENERATOR_OUTPUT = 0x0f

# PYLON
PLC_PYLON_STATUS = 0x10
PLC_PYLON_POWER = 0x12

# *************************************************



class HMIWindow(Gtk.Window):

    def initModbus(self):
        # Create modbus connection to specified address and port
        self.modbusClient = ModbusClient(args.server_addr, port=5020)

    # Default values for the HMI labels
    def resetLabels(self):
        self.pylon_plc_online_value.set_markup("<span weight='bold' foreground='red'>OFF</span>")
        self.pylon_plc_status_value .set_markup("<span weight='bold' foreground='black'>N/A</span>")


    def __init__(self):
        # Window title
        Gtk.Window.__init__(self, title="PYLON PLC")
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
        label.set_markup("<span weight='bold' size='xx-large' color='black'>PLC : PYLON/POWER GAUGE</span>")
        grid.attach(label, 4, elementIndex, 4, 1)
        elementIndex += 1

        # PYLON
        # Connected to World / HMI
        pylon_plc_online_label = Gtk.Label("Online: ")
        pylon_plc_online_value = Gtk.Label()

        # Valve / Button to Turn ON/OFF
        pylon_plc_status_label = Gtk.Label("Pylon Status: ")
        pylon_plc_status_value = Gtk.Label()
        pylon_plc_status_on_button = Gtk.Button("ON")
        pylon_plc_status_off_button = Gtk.Button("OFF")
        pylon_plc_status_on_button.connect("clicked", self.setPylonStatus, 1)
        pylon_plc_status_off_button.connect("clicked", self.setPylonStatus, 0)

        #pylon power gauge
        pylon_plc_power_label = Gtk.Label("Power Level: ")
        pylon_plc_power_value = Gtk.Label()

        # pylon
        # Connected to World / HMI *****PART 2
        grid.attach(pylon_plc_online_label, 4, elementIndex, 1, 1)
        grid.attach(pylon_plc_online_value, 5, elementIndex, 1, 1)
        elementIndex += 1

        # Valve / Button to Turn ON/OFF *****PART 2
        grid.attach(pylon_plc_status_label, 4, elementIndex, 1, 1)
        grid.attach(pylon_plc_status_value, 5, elementIndex, 1, 1)
        grid.attach(pylon_plc_status_on_button, 6, elementIndex, 1, 1)
        grid.attach(pylon_plc_status_off_button, 7, elementIndex, 1, 1)
        elementIndex += 1

        grid.attach(pylon_plc_power_label, 4, elementIndex, 1, 1)
        grid.attach(pylon_plc_power_value, 5, elementIndex, 1, 1)
        elementIndex += 1

        ## attach  # column number
        # Attach Value Labels
        self.pylon_plc_online_value = pylon_plc_online_value
        self.pylon_plc_status_value = pylon_plc_status_value
        self.pylon_plc_power_value = pylon_plc_power_value


        # Set default label values
        self.resetLabels()
        GObject.timeout_add_seconds(MODBUS_SLEEP, self.update_status)

    # Control the feed pump register values
    def setPylonStatus(self, widget, data=None):
        try:
            self.modbusClient.write_register(PLC_PYLON_STATUS, data)
        except:
            pass

    def update_status(self):

        try:
            # Store the registers of the PLC in "rr"
            rr = self.modbusClient.read_holding_registers(1,24)
            regs = []

            # If we get back a blank response, something happened connecting to the PLC
            if not rr or not rr.registers:
                raise ConnectionException

            # Regs is an iterable list of register key:values
            regs = rr.registers

            if not regs or len(regs) < 16:
                raise ConnectionException

            self.pylon_plc_online_value.set_markup("<span weight='bold' foreground='green'>ON</span>")

        # Change to match
# exmaple follows

            if regs[ PLC_GENERATOR_STATUS - 1 ] == 0:
                if regs[PLC_PYLON_STATUS - 1] == 0:
                    self.pylon_plc_status_value.set_markup("<span weight='bold' foreground='red'>OFF</span>")
                    self.pylon_plc_power_value.set_markup("<span weight='bold' foreground='red'>No Power</span>")
            if regs[ PLC_GENERATOR_STATUS - 1 ] == 1:
                if regs[ PLC_PYLON_STATUS - 1 ] == 1:
                    self.pylon_plc_status_value.set_markup("<span weight='bold' foreground='green'>ON</span>")
                    if regs[PLC_TURBINE_RPMs - 1] == 0:
                        self.pylon_plc_power_value.set_markup("<span weight='bold' foreground='red'>No Output</span>")
                    if regs[PLC_TURBINE_RPMs - 1] == 1:
                        self.pylon_plc_power_value.set_markup("<span weight='bold' foreground='gold'>Low Power</span>")
                    if regs[PLC_TURBINE_RPMs - 1] == 2:
                        self.pylon_plc_power_value.set_markup("<span weight='bold' foreground='green'>Normal Power</span>")
                    if regs[PLC_TURBINE_RPMs - 1] == 3:
                        self.pylon_plc_power_value.set_markup("<span weight='bold' foreground='crimson'>DANGER</span>")


            # If the feed pump "0x01" is set to 1, then the pump is running
            '''
            if regs[0] == 1:
                self.fuel_plc_operational_value.set_markup("<span weight='bold' foreground='green'>ON</span>")
            else:
                self.fuel_plc_operational_value.set_markup("<span weight='bold' foreground='red'>OFF</span>")
            if regs[12] == 0:
                self.pylon_plc_operational_value .set_markup("<span weight='bold' foreground='red'>OFF</span>")
            elif regs[12] == 1:
                self.pylon_plc_operational_value.set_markup("<span weight='bold' foreground='green'>ON</span>")
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