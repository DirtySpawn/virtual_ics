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


STEAMRATE = [ 3, 2, 1, 0 ]
RPMS = [50000, 30000, 10000, 0 ]

WATERTOSTEAMRATE = [15, 5, 1, 0]

FUEL_RATE = [ 'MAX', 'HIGH', 'MED', 'LOW' ] 

CONDENSERATE = 6 # seconds to condense 


PRESSUREMIN = 300
PRESSUREMAX = 400

PRESSURERELEASE = False
# *************************************************

class HMIWindow(Gtk.Window):
    
    def initModbus(self):
        # Create modbus connection to specified address and port
        self.modbusClient = ModbusClient(args.server_addr, port=5020)

    # Default values for the HMI labels
    def resetLabels(self):
        self.turbine_plc_online_value.set_markup("<span weight='bold' foreground='red'>OFF</span>")
        self.turbine_plc_pressure_valve_value.set_markup("<span weight='bold' foreground='black'>N/A</span>")
        
    def __init__(self):
        # Window title
        Gtk.Window.__init__(self, title="Turbine PLC")
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
        label.set_markup("<span weight='bold' size='xx-large' color='black'>PLC : Turbine</span>")
        grid.attach(label, 4, elementIndex, 4, 1)
        elementIndex += 1

        # Crude Oil Feed Pump
        turbine_plc_online_label = Gtk.Label("Online: ")
        turbine_plc_online_value = Gtk.Label()

        grid.attach(turbine_plc_online_label, 4, elementIndex, 1, 1)
        grid.attach(turbine_plc_online_value, 5, elementIndex, 1, 1)
        elementIndex += 1
        
        turbine_plc_rpm_label = Gtk.Label("RPMS: ")
        turbine_plc_rpm_value = Gtk.Label()

        grid.attach(turbine_plc_rpm_label, 4, elementIndex, 1, 1)
        grid.attach(turbine_plc_rpm_value, 5, elementIndex, 1, 1)
        elementIndex += 1
        
        turbine_plc_pressure_label = Gtk.Label("Pressure: ")
        turbine_plc_pressure_value = Gtk.Label()
        
        grid.attach(turbine_plc_pressure_label, 4, elementIndex, 1, 1)
        grid.attach(turbine_plc_pressure_value, 5, elementIndex, 1, 1)
        elementIndex += 1

        turbine_plc_pressure_valve_label = Gtk.Label("Pressure Valve: ")
        turbine_plc_pressure_valve_value = Gtk.Label()

        grid.attach(turbine_plc_pressure_valve_label, 4, elementIndex, 1, 1)
        grid.attach(turbine_plc_pressure_valve_value, 5, elementIndex, 1, 1)
        elementIndex += 1 

        # Attach Value Labels
        self.turbine_plc_online_value = turbine_plc_online_value
        self.turbine_plc_rpm_value = turbine_plc_rpm_value
        self.turbine_plc_pressure_value = turbine_plc_pressure_value
        self.turbine_plc_pressure_valve_value = turbine_plc_pressure_valve_value

        self.CONDENSERATE = CONDENSERATE
        self.ticks_to_condense = self.CONDENSERATE

        # Set default label values
        self.resetLabels()
        GObject.timeout_add_seconds(MODBUS_SLEEP, self.update_status)

    # Control the feed pump register values
    def setTurbineOperational(self, widget, data=None):
        try:
            self.modbusClient.write_register(PLC_TURBINE, data)
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
            
            self.turbine_plc_online_value.set_markup("<span weight='bold' foreground='green'>ON</span>")
            
            self.turbine_plc_pressure_value.set_markup("<span weight='bold' foreground='green'>" + str(regs[PLC_TURBINE_PRESSURE - 1]) + "</span>")
            
            '''
            STEAMRATE = [ 3, 2, 1, 0 ]
            RPMS = [50000, 30000, 10000, 0 ]

            WATERTOSTEAMRATE = [15, 5, 1, 0]

            FUEL_RATE = [ 'MAX', 'HIGH', 'MED', 'LOW' ] 

            if pressure > 500 open value until < 200

            CONDENSERATE = 10
            ticks_to_condense = CONDENSERATE
            '''
                                #3, 4, 5, 6
            if regs[ PLC_BOILER_WATER_VOLUME - 1] > 0:
                if regs[ PLC_FUEL_VALVE - 1] == 1:
                    if regs[ PLC_BOILER_TEMP - 1 ] > 99: # BOILING                    
                        rate = regs[PLC_FUEL_RATE - 1] - 3
                        #index = FUEL_RATE.index( rate )
                        self.turbine_plc_rpm_value.set_markup("<span weight='bold' foreground='green'>" + str( RPMS[ rate ] )  + "</span>")
                        self.modbusClient.write_register( PLC_TURBINE_RPMs, STEAMRATE[ rate ] )
                        currentpressure = regs[PLC_TURBINE_PRESSURE - 1]
                        change = currentpressure + WATERTOSTEAMRATE[ rate ]
                        self.modbusClient.write_register( PLC_TURBINE_PRESSURE, change)

            if regs[ PLC_TURBINE_PRESSURE - 1 ] > PRESSUREMAX:
                #PRESSURERELEASE = True
                self.modbusClient.write_register( PLC_TURBINE_PRESSURE_HIGH, 1 )
                

            if regs[ PLC_TURBINE_PRESSURE_HIGH - 1 ] == 1:
                self.turbine_plc_pressure_valve_value.set_markup("<span weight='bold' foreground='green'>OPEN</span>")
                if regs[ PLC_TURBINE_PRESSURE - 1 ] < PRESSUREMIN:
                    #PRESSURERELEASE = False
                    self.modbusClient.write_register( PLC_TURBINE_PRESSURE_HIGH, 0 )
                else:
                    currentpressure = regs[PLC_TURBINE_PRESSURE - 1]
                    change = currentpressure - 15 # WATERTOSTEAMRATE[ rate ]
                    self.modbusClient.write_register( PLC_TURBINE_PRESSURE, change)
            else:
                self.turbine_plc_pressure_valve_value.set_markup("<span weight='bold' foreground='red'>CLOSED</span>")
                             

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
