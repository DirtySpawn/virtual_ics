#!/usr/bin/env python
# NOTES:
# Values of 1 = ON, OPEN
# Values of 0 = OFF, CLOSED

import logging

# - Multithreading
from twisted.internet import reactor

# - Modbus
from pymodbus.server.async import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.transaction import ModbusRtuFramer, ModbusAsciiFramer

# - World Simulator
import sys, random, math
import pygame
from pygame.locals import *
from pygame.color import *
import pymunk

# Network
import socket

# Argument parsing
import argparse

import os
import sys
import time

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

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)


# Display settings
SCREEN_WIDTH = 728 #580
SCREEN_HEIGHT = 546 #460
FPS = 50.0 # 50.0

# Port the world will listen on
MODBUS_SERVER_PORT = 5020


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


# Collision Types

ball_collision = 0x5
condenser_outlet_valve_collision = 0x6
highpressure_outlet_valve_collision = 0x6

# Functions to set PLC Values
def PLCSetTag(addr, value):
    context[0x00].setValues(3, addr, [value])

# Helper function that returns PLC values
def PLCGetTag(addr):
    return context[0x00].getValues(3, addr, count=1)[0]

0
def to_pygame(p):
    """Small hack to convert pymunk to pygame coordinates"""
    return int(p.x), int(-p.y+600)

# Add "water" to the world space
def add_water(space):
    mass = 0.5
    radius = 2
    inertia = pymunk.moment_for_circle(mass, 0, radius, (0, 0))
    body = pymunk.Body(mass, inertia)
    body._bodycontents.v_limit = 120
    body._bodycontents.h_limit = 1
    body.tag = "VALVE"
    #x = random.randint(169, 170)
    #body.position = x, 348
    shape = pymunk.Circle(body, radius, (0, 0))
    #shape.tag = "VALVE"
    shape.friction = 0.0
    shape.collision_type = ball_collision #liquid
    space.add(body, shape)
    return shape

def add_steam(space):
    mass = 0.8
    radius = 3
    inertia = pymunk.moment_for_circle(mass, 0, radius, (0, 0))
    body = pymunk.Body(mass, inertia)
    body._bodycontents.v_limit = 120
    body._bodycontents.h_limit = 1
    x = random.randint(35,160)
    body.position = x, 250
    shape = pymunk.Circle(body, radius, (0, 0))
    shape.friction = 0.0
    shape.collision_type = ball_collision #liquid
    space.add(body, shape)
    return shape

def add_fire(space):
    mass = 0.01
    radius = 2
    inertia = pymunk.moment_for_circle(mass, 0, radius, (0, 0))
    body = pymunk.Body(mass, inertia)
    body._bodycontents.v_limit = 120
    body._bodycontents.h_limit = 1
    '''
    x = random.choice( [37, 97, 160] )
    x = random.randint( (x - 1), (x + 1) )
    '''
    body.position = 0, 0
    shape = pymunk.Circle(body, radius, (0, 0))
    shape.friction = 0.0
    shape.collision_type = ball_collision #liquid
    space.add(body, shape)
    return shape

def add_energy(space):
    mass = 0.1
    radius = 4 
    inertia = pymunk.moment_for_circle(mass, 0, radius, (0, 0))
    body = pymunk.Body(mass, inertia)
    body._bodycontents.v_limit = 120
    body._bodycontents.h_limit = 1
    body.position = 0, 0
    shape = pymunk.Circle(body, radius, (0, 0))
    shape.friction = 0.0
    #shape.collision_type = ball_collision #liquid
    space.add(body, shape)
    return shape

# Add a ball to the space
def draw_ball(screen, ball, color):
	color = THECOLORS[color]
	p = int(ball.body.position.x), 600-int(ball.body.position.y)
	pygame.draw.circle(screen, color, p, int(ball.radius), 2)

# Outlet valve that lets oil from oil tank to the pipes
def add_condenser_outlet_valve(space):
    body = pymunk.Body()
    body.position = (184,275)
    # Check these coords and adjust
    a = (0, -15)
    b = (0, 15)
    radius = 2
    shape = pymunk.Segment(body, a, b, radius)
    shape.collision_type = condenser_outlet_valve_collision
    space.add(shape)
    return shape

def add_burner(space):
    body = pymunk.Body()
    body.position = (160, 134)
    shape = pymunk.Poly.create_box(body, (12, 5), (0, 0), 0)
    space.add(shape)
    return shape

def add_watermain(space):
    body = pymunk.Body()
    body.position = (100, 360)
    shape = pymunk.Poly.create_box(body, (15, 20), (0, 0), 0)
    space.add(shape)
    return shape

def add_electricmain(space):

    body = pymunk.Body()
    body.position = (538, 445)
    shape = pymunk.Poly.create_box(body, (5, 5), (0, 0), 0)
    space.add(shape)
    return shape

def add_light(space):

    body = pymunk.Body()
    body.position = (478, 494)
    #y -45, 45
    #x 0, 120    
    lightminx = 1
    lightmaxx = 121
    lightminy = -45
    lightmaxy = 45

    i = 1
    multiple = 20

    x = random.randint( lightminx, i * multiple)
    y = random.randint( lightminy, lightmaxy )
    l1 = pymunk.Segment( body, (0,0),(x,y), 3 )

    xprev = x
    yprev = y
    i += 1

    x = random.randint( xprev, i * multiple)
    y = random.randint( lightminy, lightmaxy )
    l2 = pymunk.Segment( body, (xprev,yprev),(x,y), 3 )

    xprev = x
    yprev = y
    i += 1

    x = random.randint( xprev, i * multiple)
    y = random.randint( lightminy, lightmaxy )
    l3 = pymunk.Segment( body, (xprev,yprev),(x,y), 3 )

    xprev = x
    yprev = y
    i += 1

    x = random.randint( xprev, i * multiple)
    y = random.randint( lightminy, lightmaxy )
    l4 = pymunk.Segment( body, (xprev,yprev),(x,y), 3 )

    xprev = x
    yprev = y
    i += 1

    x = random.randint( xprev, i * multiple)
    y = random.randint( lightminy, lightmaxy )
    l5 = pymunk.Segment( body, (xprev,yprev),(x,y), 3 )

    xprev = x
    yprev = y
    i += 1

    x = random.randint( xprev, i * multiple)
    y = random.randint( lightminy, lightmaxy )
    l6 = pymunk.Segment( body, (xprev,yprev),(x,y), 3 )

    space.add( l1, l2, l3, l4, l5, l6 )

    return ( l1, l2, l3, l4, l5, l6 )


def add_boiler(space):
	body = pymunk.Body()
	body.position = (12, 170)
	#Boiler
	l1 = pymunk.Segment( body, (0,0), (0, 180), 3 )
	l2 = pymunk.Segment( body, (0,180), (20, 200), 3 )
	l3 = pymunk.Segment( body, (20,200), (20,295), 3 )
	l4 = pymunk.Segment( body, (40, 295), (40, 200), 3 )
	l5 = pymunk.Segment( body, (40, 200), (170, 180), 3 )
	l6 = pymunk.Segment( body, (170, 180), (170,115), 3 )
	l7 = pymunk.Segment( body, (170, 90), (170, 5), 3 )
	l8 = pymunk.Segment( body, (170,5), (0,0), 3 )

	space.add(l1, l2, l3, l4, l5, l6, l7, l8)

	return (l1, l2, l3, l4, l5, l6, l7, l8)

def add_condenser(space):
	body = pymunk.Body()
	body.position = (182, 260)

	#Condenser Lines

	l1 = pymunk.Segment( body, (0,0), (65, 35), 3 ) 
	l4 = pymunk.Segment( body, (0, 25), (35, 50), 3 )  # (100, 35), 3 ) 

	l9 = pymunk.Segment( body, (35,50), (35, 205), 3 )
	l10 = pymunk.Segment( body, (65, 35), (65, 205), 3)


	space.add(l1, l4, l9, l10)

	return (l1, l4, l9, l10)

def add_turbine(space):
    body = pymunk.Body()
    body.position = (32, 465)
    # Turbine Lines
    l1 = pymunk.Segment(body, (0, 0), (0, 70), 3)
    l2 = pymunk.Segment(body, (20, 0), (30, 10), 3)
    l3 = pymunk.Segment(body, (0, 70), (225, 80), 3)
    l5 = pymunk.Segment(body, (30, 10), (188, 0), 3)
    l6 = pymunk.Segment(body, (225, 80), (215, 0), 3)

    space.add(l1, l2, l3, l5, l6)

    return (l1, l2, l3, l5, l6)

def add_turbine_highpressure_release_valve(space):
    body = pymunk.Body()
    body.position = (250, 547)
    shape = pymunk.Poly.create_box(body, (15, 5), (0, 0), 0)
    space.add(shape)
    return shape

# Draw a defined polygon
def draw_polygon(bg, shape, color = None):
    points = shape.get_vertices()
    fpoints = []
    for p in points:
        fpoints.append(to_pygame(p))
    if color is None:
        pygame.draw.polygon(bg, THECOLORS['red'], fpoints)
    else:
        pygame.draw.polygon(bg, THECOLORS[color], fpoints)
    
# Draw a single line to the screen
def draw_line(screen, line, color = None):
    body = line.body
    pv1 = body.position + line.a.rotated(body.angle) # 1
    pv2 = body.position + line.b.rotated(body.angle)
    p1 = to_pygame(pv1) # 2
    p2 = to_pygame(pv2)
    if color is None:
        pygame.draw.lines(screen, THECOLORS["black"], False, [p1,p2])
    else:
        pygame.draw.lines(screen, THECOLORS[color], False, [p1,p2])
    
# Draw lines from an iterable list
def draw_lines(screen, lines, color = None):
    for line in lines:
        body = line.body
        pv1 = body.position + line.a.rotated(body.angle) # 1
        pv2 = body.position + line.b.rotated(body.angle)
        p1 = to_pygame(pv1) # 2
        p2 = to_pygame(pv2)
        if color is None:
            pygame.draw.lines(screen, THECOLORS['black'], False, [p1,p2])
        else:
            #color = THECOLORS[ color ] 
            pygame.draw.lines(screen, THECOLORS[color], False, [p1,p2])

# Default collision function for objects
# Returning true makes the two objects collide normally just like "walls/pipes"
def no_collision(space, arbiter, *args, **kwargs):
    return True 

def valve_open(space, arbiter, *args, **kwargs):
    return False

def valve_closed(space, arbiter, *args, **kwargs):
    return True

def run_world():
    pygame.init()
    pygame.font.init()
    myfont = pygame.font.SysFont('Comic Sans MS', 30 ) # font for on screen error handling

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Power Plant")
    clock = pygame.time.Clock()
    running = True

    # Create game space (world) and set gravity to normal
    space = pymunk.Space() #2
    space.gravity = (0.0, -900.0)

    # Second space for gravity pointing up. For fire and steam
    air = pymunk.Space()
    air.gravity = (0.0, 900.0)

    # Add the objects to the game world
    boiler = add_boiler(space)
    plate = add_boiler(air)
    condenser = add_condenser(space)
    condenser_valve = add_condenser_outlet_valve(space)
    watermain = add_watermain(space)
    turbine = add_turbine(space)
    turbinepressurereleasevalve = add_turbine_highpressure_release_valve(air)
    turbair = add_turbine(air)
    electricmain = add_electricmain(space)
    # 3 Burner objects for fire
    burner1 = add_burner(space)
    burner1.body.position = (37,134)
    burner2 = add_burner(space)
    burner2.body.position = (97,134)
    burner3 = add_burner(space)
    burner3.body.position = (160,134)
    # Array to hold burners to iterate while drawing
    burners = []
    burners.append(burner1)
    burners.append(burner2)
    burners.append(burner3)

    # Color for valve when  Closed / Open
    valve_color = [ 'black', 'white']

    # Water Flow Rate Settings
    waters = []
    ticks_to_next_water = 1

    # Fire Flow Rate Settings
    fires = []
    FUELRATE = 2
    ticks_to_next_fire = FUELRATE

    # Steam Creation
    steams = []
    steamstorelease = []
    STEAMCREATE = 3
    ticks_to_next_steam = STEAMCREATE
    STEAMRELEASE = 10
    ticks_to_release_steam = STEAMRELEASE

    # Set font settings - On Screen Error Handling
    fontBig = pygame.font.SysFont(None, 40)
    fontMedium = pygame.font.SysFont(None, 26)
    fontSmall = pygame.font.SysFont(None, 18)

    # When Condenser Valve Opens, gravity is shifted because of odd collisions
    # Water tends to get 'stuck'.  Gravity shift helps
    shift = True    
    gravity_tick = 5
    sensor_tick = 1

    # Turbine Valve - Same as Condenser
    airshift = True    
    airgravity_tick = 5
    airsensor_tick = 1


    # Condenser Volume Tracker
    condenservolume = PLCGetTag( PLC_CONDENSER_WATER_VOLUME )
    condenserwater = []
    CONDENSERTICKS = 90
    ticks_to_condenser = CONDENSERTICKS


    # Generator
    ticks_to_generator = 1 # place holder.  gets set inside loop
    generatorsparks = []
    SPARKCOLORS = ( 'red', 'white', 'yellow', 'green' )

    # Pylon / Power Guage
    powerguage = []
    POWERRATE = 5
    ticks_to_power = POWERRATE


    #  NEW VARIABLES OUTSIDE OF ANIMATION
    plcFUELRATE = 5
    PLCSetTag(PLC_FUEL_VALVE, plcFUELRATE)

    plcWATERRATE = 5
    PLCSetTag(PLC_WATERPUMP_RATE, plcWATERRATE)

    while running:
        # Advance the game clock
        clock.tick(FPS)
                
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == KEYDOWN and event.key == K_ESCAPE:
                running = False
            elif event.type == KEYDOWN and event.key == K_LEFT:
                for water in waters:
                    PLCSetTag( PLC_BOILER_WATER_VOLUME, 5000)
                    PLCSetTag( PLC_WATERPUMP_VALVE, 0)
                    PLCSetTag( PLC_FUEL_VALVE, 1)
                    PLCSetTag( PLC_TURBINE_PRESSURE, 250)
                

        # Load the background picture for the pipe images
        bg = pygame.image.load("powerplant.jpg") #pygame.image.load("oil_unit.png")
        # Background color
        screen.fill(THECOLORS["white"])

        if PLCGetTag(PLC_CONDENSER_VALVE) == 1:
            space.add_collision_handler( condenser_outlet_valve_collision, ball_collision, begin=valve_open )
            if(shift):
                shift = False
                space.gravity = (500.0, 0.0)

        elif PLCGetTag(PLC_CONDENSER_VALVE) == 0:
            space.add_collision_handler( condenser_outlet_valve_collision, ball_collision, begin=valve_closed )
            shift = True


        if( shift == False):
            if (gravity_tick < 1 ):
                shift == True
                space.gravity = (0.0, -900.0)
                gravity_tick = 5
            else:
                gravity_tick -= 1

        # Rate Changes
        # Fuel
        if (PLCGetTag(PLC_FUEL_RATE)) - 2 < 1:
            change = PLCGetTag(PLC_FUEL_RATE) - 1
            change += plcFUELRATE
            if change < 2:
                change = 2
            elif change > 6: #21:
                change = 6 # 21
            plcFUELRATE = change
            PLCSetTag(PLC_FUEL_RATE, plcFUELRATE )

        # Water
        if (PLCGetTag(PLC_WATERPUMP_RATE)) - 2 < 1 :
            change = int(PLCGetTag(PLC_WATERPUMP_RATE)) - 1
            change += plcWATERRATE
            if change < 2:
                change = 2
            elif change > 6 :
                change = 6
            plcWATERRATE = change
            PLCSetTag(PLC_WATERPUMP_RATE, plcWATERRATE)    


        fire_to_remove = []          
        if PLCGetTag(PLC_FUEL_VALVE) == 1:
            ticks_to_next_fire -= 1

            if ticks_to_next_fire <= 0 :
                ticks_to_next_fire = PLCGetTag(PLC_FUEL_RATE) - 2
                for burner in burners:
                    fire_shape = add_fire(air)
                    fire_shape.body.position = burner.body.position
                    fires.append(fire_shape)

        for fire in fires:
            if fire.body.position.y < 0 or fire.body.position.y > 170:
                fire_to_remove.append(fire)

            draw_ball(bg, fire, 'red')

        for fire in fire_to_remove:
            air.remove(fire, fire.body)
            fires.remove(fire)
        # end - Fuel / Fire


        # Water Pump

        if ( PLCGetTag( PLC_WATERPUMP_VALVE ) ):
            ticks_to_next_water -= 1
            if ticks_to_next_water <= 0 : 
                ticks_to_next_water = PLCGetTag( PLC_WATERPUMP_RATE ) - 2
                water_shape = add_water(space)
                water_shape.body.position = watermain.body.position
                water_shape.body.position.y -= 12
                water_shape.body.position.x = random.randint( watermain.body.position.x - 1, watermain.body.position.x + 1 )
                waters.append(water_shape)

        water_to_remove = []

        if (PLCGetTag( PLC_BOILER_WATER_VOLUME ) > len(waters) * 10 ) and (PLCGetTag(PLC_WATERPUMP_VALVE) == 0):
            ticks_to_next_water = PLCGetTag( PLC_WATERPUMP_RATE )
            water_shape = add_water(space)
            water_shape.body.position = watermain.body.position
            water_shape.body.position.y -= 180
            water_shape.body.position.x = random.randint( watermain.body.position.x - 80, watermain.body.position.x + 80 )
            waters.append(water_shape)
        elif ( int(PLCGetTag( PLC_BOILER_WATER_VOLUME ) / 10 ) < len(waters) ) and (PLCGetTag(PLC_WATERPUMP_VALVE) == 0):
            for water in waters:
                water_to_remove.append(water)
                break

        if PLCGetTag(PLC_CONDENSER_WATER_VOLUME) > len(condenserwater) :
            water_shape = add_water(space)
            water_shape.body.position.x = 240
            water_shape.body.position.y = 325
            condenserwater.append(water_shape)
        elif (PLCGetTag(PLC_CONDENSER_VALVE) == 1) and (PLCGetTag(PLC_TURBINE_PRESSURE) > 0 ) :
            ticks_to_condenser -= 1
            if ticks_to_condenser <= 0:
                ticks_to_condenser = CONDENSERTICKS
                water_shape = add_water(space)
                water_shape.body.position.x = 240
                water_shape.body.position.y = 325
                condenserwater.append(water_shape)

        for water in waters:
            draw_ball( bg, water, 'blue')

        for water in condenserwater:
            draw_ball( bg, water, 'purple')
            if water.body.position.x < condenser_valve.body.position.x:
                if (water.body.position.y + 10) < condenser_valve.body.position.y:
                    waters.append(water)
                    condenserwater.remove(water)

        for water in water_to_remove:
        	space.remove(water, water.body)
        	waters.remove(water)

        # end - Boiler

        # Adding Steam
        if ( PLCGetTag(PLC_BOILER_TEMP) >= 99 ) and ( PLCGetTag( PLC_BOILER_WATER_VOLUME ) > 0):
            if (PLCGetTag(PLC_FUEL_RATE) - 2) != 4 :
                ticks_to_next_steam -= 1
                if ticks_to_next_steam <= 0:
                    steam_shape = add_steam(air)
                    steams.append(steam_shape)
                    ticks_to_next_steam = PLCGetTag(PLC_FUEL_RATE) + 5 # STEAMCREATE

        if len(steams) < PLCGetTag(PLC_TURBINE_PRESSURE):
            steam_shape = add_steam(air)
            steam_shape.body.position = turbinepressurereleasevalve.body.position
            steam_shape.body.position.x -= 10
            steam_shape.body.position.y -= 10
            steams.append(steam_shape)

        if PLCGetTag(PLC_TURBINE_PRESSURE_HIGH):
            ticks_to_release_steam -= 1
            if ticks_to_release_steam <= 0:
                ticks_to_release_steam = STEAMRELEASE
                steam_shape = add_steam(air)
                steam_shape.body.position = turbinepressurereleasevalve.body.position
                steam_shape.body.position.y = turbinepressurereleasevalve.body.position.y + 5
                steamstorelease.append(steam_shape)

        steamtoremove = []
        steamsturbine = []


        for steam in steams:
            draw_ball(bg, steam, 'gray')
            if steam.body.position.y > 465:
                steamsturbine.append(steam)

        if PLCGetTag( PLC_TURBINE_PRESSURE ) < len(steamsturbine):
            steamtoremove.append(steamsturbine[0])
            steamsturbine.remove( steamsturbine[0] )

        for steam in steamtoremove:
            air.remove(steam, steam.body)
            steams.remove(steam)

        steamtoremove = []

        for steam in steamstorelease:
            draw_ball(bg, steam, 'gray')
            if steam.body.position.y > 600:
                steamtoremove.append(steam)

        for steam in steamtoremove:
            air.remove(steam, steam.body)
            steamstorelease.remove(steam)


        # Generator
        if PLCGetTag(PLC_GENERATOR_STATUS) == 1:
            if PLCGetTag(PLC_TURBINE_RPMs) > 0:
                ticks_to_generator -= 1
                if ticks_to_generator <= 0:
                    rate = PLCGetTag(PLC_TURBINE_RPMs)
                    if rate == 1:
                        ticks_to_generator = 10
                    elif rate == 2:
                        ticks_to_generator = 5
                    elif rate == 3 :
                        ticks_to_generator = 1
                    for spark in generatorsparks:
                        space.remove(spark)
                        generatorsparks.remove(spark)
                    spark = add_light(space)
                    generatorsparks.append(spark)

        if (PLCGetTag(PLC_GENERATOR_STATUS) == 0) or (PLCGetTag(PLC_TURBINE_RPMs) == 0):
            if len(generatorsparks) > 0:
                for spark in generatorsparks:
                    space.remove(spark)
                    generatorsparks.remove(spark)

        for spark in generatorsparks:
            draw_lines(bg, spark, random.choice(SPARKCOLORS) )


        if (PLCGetTag(PLC_PYLON_STATUS) == 1) and (PLCGetTag(PLC_GENERATOR_OUTPUT) > 0) and (PLCGetTag(PLC_GENERATOR_STATUS) == 1) :
            ticks_to_power -= 1
            if ticks_to_power <= 0:
                ticks_to_power = POWERRATE
                power_shape = add_energy(space)
                power_shape.body.position = electricmain.body.position
                power_shape.body.position.y -= 3
                powerguage.append(power_shape)

        powerguageremove = []

        for power in powerguage :
            color = ('gold', 'green', 'red')
            select = PLCGetTag(PLC_GENERATOR_OUTPUT) - 1
            draw_ball(bg, power, color[select])
            if power.body.position.y <= 200:
                powerguageremove.append(power)

        for power in powerguageremove:
            space.remove(power)
            powerguage.remove(power)        

        # Drawing Objects on Screen
        draw_lines(bg, boiler)
        draw_lines(bg, condenser)
        draw_line(bg, condenser_valve, valve_color[( PLCGetTag(PLC_CONDENSER_VALVE)) ] )
        draw_polygon(bg, watermain)
        draw_lines(bg, turbine)
        draw_polygon(bg, electricmain)
        draw_polygon(bg, turbinepressurereleasevalve, 'black')
        


        for burner in burners:
            draw_polygon(bg, burner, 'black')

        # Used to display number of water 
        #inside Boiler
        stuff = str(len(steams))
        text = stuff #"Log: " + str( log )
        textsurface = myfont.render( text, False, (0,0,0))



        screen.blit(bg, (0, 0))
        screen.blit(textsurface, (0,0))

        space.step(1/FPS) 
        air.step(1/FPS)
        pygame.display.flip()

    if reactor.running:
        reactor.callFromThread(reactor.stop)


store = ModbusSlaveContext(
    di = ModbusSequentialDataBlock(0, [0]*100),
    co = ModbusSequentialDataBlock(0, [0]*100),
    hr = ModbusSequentialDataBlock(0, [0]*100),
    ir = ModbusSequentialDataBlock(0, [0]*100))


context = ModbusServerContext(slaves=store, single=True)

# Modbus PLC server information
identity = ModbusDeviceIdentification()
identity.VendorName  = 'Simmons Oil Refining Platform'
identity.ProductCode = 'SORP'
identity.VendorUrl   = 'http://simmons.com/markets/oil-gas/pages/refining-industry.html'
identity.ProductName = 'SORP 3850'
identity.ModelName   = 'Simmons ORP 3850'
identity.MajorMinorRevision = '2.09.01'

def startModbusServer():
    # Run a modbus server on specified address and modbus port (5020)
    StartTcpServer(context, identity=identity, address=(args.server_addr, MODBUS_SERVER_PORT))

def main():
    reactor.callInThread(run_world)
    startModbusServer()

if __name__ == '__main__':
    sys.exit(main())
