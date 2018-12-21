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

import math

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


WATERPUMPMAXGPM = 22712.47  # in liters. 6000 GPM pump

GPMRATE = [ 1, 0.75, 0.50, 0.25 ]  # percentage of pump rate

TEMPRATE = [ 25, 10, 5, 1 ] # how fast temp goes up

WATERTOSTEAM = [15, 5, 1, 0]

WATERFROMVALVETEMP = 80 # Degrees C

gallontoliter = 3.78541 # 1 Gallon to Liter

degree = u"\u2103"  # symbol to print



class HMIWindow(Gtk.Window):
    
    def initModbus(self):
        # Create modbus connection to specified address and port
        self.modbusClient = ModbusClient(args.server_addr, port=5020)

    # Default values for the HMI labels
    def resetLabels(self):
        self.boiler_plc_online_value.set_markup("<span weight='bold' foreground='red'>OFF</span>")
        self.boiler_plc_water_volume_value.set_markup("<span weight='bold' foreground='black'>N/A</span>")
        self.boiler_plc_water_temp_value.set_markup("<span weight='bold' foreground='black'>N/A</span>")
        self.boiler_plc_water_volume_low_value.set_markup("<span weight='bold' foreground='black'>N/A</span>")
        self.boiler_plc_water_volume_high_value.set_markup("<span weight='bold' foreground='black'>N/A</span>")
        

    def __init__(self):
        # Window title
        Gtk.Window.__init__(self, title="Boiler PLC")
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

        # Boiler
        boiler_plc_online_label = Gtk.Label("Online: ")
        boiler_plc_online_value = Gtk.Label()

        # Water Volume
        boiler_plc_water_volume_label = Gtk.Label("Volume: ")
        boiler_plc_water_volume_value = Gtk.Label()       

        # Low Water Setting
        boiler_plc_water_volume_low_label = Gtk.Label("Low Volume Alarm: ") 
        boiler_plc_water_volume_low_value = Gtk.Label()
        adj = Gtk.Adjustment(value=250, lower=0, upper=5000, step_incr=1, page_incr=50, page_size=0)
        adj.connect("value_changed", self.low_adjustment_changed)
        adj.emit("value_changed")
        boiler_plc_water_volume_low_scale = Gtk.HScale(adjustment=adj)
        boiler_plc_water_volume_low_scale.set_digits(0)

        # High Water Setting
        boiler_plc_water_volume_high_label = Gtk.Label("High Volume Alarm: ")
        boiler_plc_water_volume_high_value = Gtk.Label()
        adj = Gtk.Adjustment(value=1000, lower=0, upper=5000, step_incr=1, page_incr=50, page_size=0)
        adj.connect("value_changed", self.high_adjustment_changed)
        adj.emit("value_changed")
        boiler_plc_water_volume_high_scale = Gtk.HScale(adjustment=adj)
        boiler_plc_water_volume_high_scale.set_digits(0)

        # Water Temp
        boiler_plc_water_temp_label = Gtk.Label("Water Temp: ")
        boiler_plc_water_temp_value = Gtk.Label()


        # Attaching all GTK Widgets to Grid in Window
        grid.attach(boiler_plc_online_label, 4, elementIndex, 1, 1)
        grid.attach(boiler_plc_online_value, 5, elementIndex, 1, 1)
        elementIndex += 1

        grid.attach(boiler_plc_water_volume_label, 4, elementIndex, 1, 1)
        grid.attach(boiler_plc_water_volume_value, 5, elementIndex, 1, 1)
        elementIndex += 1
        
        grid.attach(boiler_plc_water_volume_low_label, 4, elementIndex, 1, 1)
        grid.attach(boiler_plc_water_volume_low_value, 5, elementIndex, 1, 1)
        grid.attach(boiler_plc_water_volume_low_scale, 6, elementIndex, 10, 1)
        elementIndex += 1

        grid.attach(boiler_plc_water_volume_high_label, 4, elementIndex, 1, 1)
        grid.attach(boiler_plc_water_volume_high_value, 5, elementIndex, 1, 1)
        grid.attach(boiler_plc_water_volume_high_scale, 6, elementIndex, 10, 1)
        elementIndex += 1
        
        grid.attach(boiler_plc_water_temp_label, 4, elementIndex, 1, 1)
        grid.attach(boiler_plc_water_temp_value, 5, elementIndex, 1, 1)
        elementIndex += 1


        # Attach Value Labels
        self.boiler_plc_online_value = boiler_plc_online_value
        self.boiler_plc_water_volume_value = boiler_plc_water_volume_value
        self.boiler_plc_water_volume_low_value = boiler_plc_water_volume_low_value
        self.boiler_plc_water_volume_high_value = boiler_plc_water_volume_high_value
        self.boiler_plc_water_temp_value = boiler_plc_water_temp_value

        self.boiler_plc_water_volume_low_scale = boiler_plc_water_volume_low_scale

        self.boiler_plc_water_volume_high_scale = boiler_plc_water_volume_high_scale



        # Set default label values
        self.resetLabels()
        GObject.timeout_add_seconds(MODBUS_SLEEP, self.update_status)

        # Setting Default Numbers to Registers
        try:
            self.modbusClient.write_register(PLC_BOILER_WATER_VOLUME_LOW, self.boiler_plc_water_volume_low_scale.get_value())
        except:
            pass

        try:
            self.modbusClient.write_register(PLC_BOILER_WATER_VOLUME_HIGH, self.boiler_plc_water_volume_high_scale.get_value())
        except:
            pass

    # Low Scale. Set Low Alarm
    def low_adjustment_changed( self, adj):
        try:
            self.modbusClient.write_register(PLC_BOILER_WATER_VOLUME_LOW, self.boiler_plc_water_volume_low_scale.get_value())
        except:
            pass

    # High Scale. Set High Alarm
    def high_adjustment_changed( self, adj):
        try:
            self.modbusClient.write_register(PLC_BOILER_WATER_VOLUME_HIGH, self.boiler_plc_water_volume_high_scale.get_value())
        except:
            pass
    
    def setWaterAmount( self, num ):
        try:
            self.modbusClient.write_register(PLC_BOILER_WATER_VOLUME, num)
        except:
            pass

    def setTemperature( self, num ):
        try:
            self.modbusClient.write_register(PLC_BOILER_TEMP, num)
        except:
            pass


    def temperature_from_cooling(currenttemp):
        # T(t) = Ts + (To - Ts)e(-kt)
        # T(t) = Temp of object at given time =  time = 1 second = final temp
        # Ts = Temp from outside  To = Starting temp   k = cooling constant   t = time = 1 second

        waterconstant = -0.03  # k
        roomtemp = 75 # Ts

        ts = currenttemp - roomtemp # ( To - Ts)  : Ignore variable name
        #exponent = math.exp( waterconstant )
        power = math.pow(ts, math.exp(waterconstant)) # puts to e(-kt) power
        temp = roomtemp + power # temp = T(t)

        return (currenttemp - 1) 

    def temperature_adjustment(amountwarm, tempwarm, amountcold, tempcold):
        a = float(amountwarm) * tempwarm
        b = float(amountcold) * tempcold
        top = float( a + b )
        bottom = float(amountcold + amountwarm)
        temp = float(top / bottom)

        return temp


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
            
            self.boiler_plc_online_value.set_markup("<span weight='bold' foreground='green'>ON</span>")
            
            self.boiler_plc_water_volume_value.set_markup("<span weight='bold' foreground='black'>" + str( regs[PLC_BOILER_WATER_VOLUME - 1] ) + " liters</span>")

            #self.boiler_plc_water_temp_value.set_markup("<span weight='bold' foreground='black'>" + str( (regs[PLC_BOILER_TEMP - 1]) ) + degree + "</span>")
            
            VOLUME = regs[ PLC_BOILER_WATER_VOLUME - 1 ]
            
            if regs[PLC_BOILER_WATER_VOLUME - 1] == 0:
                self.setTemperature(0)
            elif regs[PLC_BOILER_WATER_VOLUME - 1] > 0:
                if regs[ PLC_BOILER_TEMP - 1] == 0:
                    self.setTemperature(WATERFROMVALVETEMP)

            if regs[PLC_WATERPUMP_VALVE - 1] == 1:
                rate = regs[PLC_WATERPUMP_RATE - 1] - 3  # should be 0, 1, 2, or 3 to select from GPMRATE
                gpm = WATERPUMPMAXGPM * GPMRATE[ rate ]
                gps = gpm / 60
                VOLUME = VOLUME + gps
                self.setWaterAmount(VOLUME)
 
            # ******* TEMP change from adding water.  go off of rate to call function *********


            if regs[PLC_FUEL_VALVE - 1] == 1:
                if VOLUME > 0 : # regs[PLC_BOILER_WATER_VOLUME - 1] > 0:
                    rate = regs[ PLC_FUEL_RATE - 1] - 3
                    temp = regs[PLC_BOILER_TEMP - 1] + TEMPRATE[rate]
                    if temp >= 100:
                        temp = 100
                        #vol = regs[PLC_BOILER_WATER_VOLUME - 1]
                        VOLUME -= WATERTOSTEAM[rate]
                        self.setWaterAmount(VOLUME)

                    self.setTemperature(temp)

            #TICKS_TO_STEAM -= TICKS_TO_STEAM
            self.boiler_plc_water_temp_value.set_markup("<span weight='bold' foreground='black'>" + str( regs[PLC_BOILER_TEMP - 1])  + "</span>")
            

            if self.boiler_plc_water_volume_low_scale.get_value() > regs[PLC_BOILER_WATER_VOLUME_HIGH - 1]:
                self.boiler_plc_water_volume_low_scale.set_value( regs[PLC_BOILER_WATER_VOLUME_HIGH - 1])
            elif self.boiler_plc_water_volume_high_scale.get_value() < regs[PLC_BOILER_WATER_VOLUME_LOW - 1]:
                self.boiler_plc_water_volume_high_scale.set_value( regs[PLC_BOILER_WATER_VOLUME_LOW - 1])
            

            self.boiler_plc_water_volume_low_value.set_markup("<span weight='bold' foreground='black'>" + str( regs[PLC_BOILER_WATER_VOLUME_LOW - 1] ) + "</span>")
            self.boiler_plc_water_volume_high_value.set_markup("<span weight='bold' foreground='black'>" + str( regs[PLC_BOILER_WATER_VOLUME_HIGH - 1] ) + "</span>")
            
            
            if regs[PLC_BOILER_WATER_VOLUME - 1] < regs[PLC_BOILER_WATER_VOLUME_LOW - 1]:
                # request turn on pump
                try:
                    self.modbusClient.write_register(PLC_BOILER_NEED_WATER, 1)
                    self.modbusClient.write_register(PLC_BOILER_STOP_WATER, 0)
                except:
                    pass 
            else:
                self.modbusClient.write_register(PLC_BOILER_NEED_WATER, 0)

            if regs[PLC_BOILER_WATER_VOLUME - 1] > regs[PLC_BOILER_WATER_VOLUME_HIGH - 1]:
                # request turn off pump
                try:
                    self.modbusClient.write_register(PLC_BOILER_NEED_WATER, 0)
                    self.modbusClient.write_register(PLC_BOILER_STOP_WATER, 1)
                except:
                    pass
            

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
