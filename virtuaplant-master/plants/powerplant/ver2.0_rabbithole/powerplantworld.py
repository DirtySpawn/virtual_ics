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
FPS = 60.0 # 50.0

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

PLC_TEST = 0x1f


RPM = 0

# Collision Types

ball_collision = 0x5
condenser_outlet_valve_collision = 0x6
highpressure_outlet_valve_collision = 0x6
turbine_rpm_collision = 0x7

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
    mass = 0.1
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
    radius = 2
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
    radius = 2
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

def add_light1(space):

    body = pymunk.Body()
    body.position = (480, 494)
    #y -45, 45
    #x 0, 120    
    lightminx = 1
    lightmaxx = 119
    lightminy = -45
    lightmaxy = 45

    x = random.randint( lightminx, lightmaxx )
    y = random.randint( lightminy, lightmaxy )
    l1 = pymunk.Segment( body, (0,0),(x,y), 3 )

    xprev = x
    yprev = y

    x = random.randint( lightminx, lightmaxx )
    y = random.randint( lightminy, lightmaxy )

    l2 = pymunk.Segment( body, (xprev, yprev), (x, y), 3)

    xprev = x
    yprev = y

    x = random.randint( lightminx, lightmaxx )
    y = random.randint( lightminy, lightmaxy )

    l3 = pymunk.Segment( body, (xprev, yprev), (x, y), 3)

    xprev = x
    yprev = y

    x = random.randint( lightminx, lightmaxx )
    y = random.randint( lightminy, lightmaxy )

    l4 = pymunk.Segment( body, (xprev, yprev), (x, y), 3)

    xprev = x
    yprev = y

    x = random.randint( lightminx, lightmaxx )
    y = random.randint( lightminy, lightmaxy )

    l5 = pymunk.Segment( body, (xprev, yprev), (x, y), 3)

    xprev = x
    yprev = y

    x = random.randint( lightminx, lightmaxx )
    y = random.randint( lightminy, lightmaxy )

    l6 = pymunk.Segment( body, (xprev, yprev), (x, y), 3)

    xprev = x
    yprev = y

    x = random.randint( lightminx, lightmaxx )
    y = random.randint( lightminy, lightmaxy )

    l7 = pymunk.Segment( body, (xprev, yprev), (x, y), 3)

    xprev = x
    yprev = y

    #x = random.randint( lightminx, lightmaxx )
    y = random.randint( lightminy, lightmaxy )

    l8 = pymunk.Segment( body, (xprev, yprev), (120, y), 3)

    space.add( l1, l2, l3, l4, l5, l6, l7, l8 )

    return ( l1, l2, l3, l4, l5, l6, l7, l8  )

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
    l3 = pymunk.Segment(body, (0, 70), (210, 80), 3)
    l5 = pymunk.Segment(body, (30, 10), (188, 0), 3)
    l6 = pymunk.Segment(body, (225, 70), (215, 0), 3)

    space.add(l1, l2, l3, l5, l6)

    return (l1, l2, l3, l5, l6)

def add_turbine_sensor(space):
    body = pymunk.Body()
    body.position = (43,465)
    # Check these coords and adjust
    a = (-10, 0)
    b = (10, 0)
    radius = 4
    shape = pymunk.Segment(body, a, b, radius)
    shape.collision_type = turbine_rpm_collision
    space.add(shape)
    return shape

def add_turbine_highpressure_release_valve(space):
    pass

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
            pygame.draw.lines(screen, THECOLORS["black"], False, [p1,p2])
        else:
            color = THECOLORS[ color] 
            pygame.draw.lines(screen, color, False, [p1,p2])

# Default collision function for objects
# Returning true makes the two objects collide normally just like "walls/pipes"
def no_collision(space, arbiter, *args, **kwargs):
    return True 

def valve_open(space, arbiter, *args, **kwargs):
    return False

def valve_closed(space, arbiter, *args, **kwargs):
    return True

def turbine_rpm(space, arbiter, *args, **kwargs):
    global RPM 
    RPM += 5
    return False

def temperature_adjustment(amountwarm, tempwarm, amountcold, tempcold):
    a = float(amountwarm) * tempwarm
    b = float(amountcold) * tempcold
    top = float( a + b )
    bottom = float(amountcold + amountwarm)
    temp = float(top / bottom)

    return temp

def increase_temperature_from_fuel(currenttemp, amount, heatenergy):
    # Q = mc DT
    # Q = Heat    m = Mass   c = Specific Heat Capacity  DT = Change in temp: Tf - To (final - original)
    # with Math.  Tf = Q / mc  + To
    '''
    q = float(heatenergy)
    m = float(amount * 20) # 1 ball is 20L - 20kg
    c = 4186.0  # J / kg * C
    To = float( currenttemp )

    Tf = float( (q / ( m * c) ) + To )
    '''
    # Ignoring Physics
    
    rate = heatenergy - 1
    rate *= -10
    rate = ( rate + 120 ) / 10

    Tf = currenttemp + rate 

    return Tf

def boiling_from_fuel(amount, heatenergy):
    # Q = mc 
    # Q = Heat    m = Mass   c = Specific Heat Capacity  DT = Change in temp: Tf - To (final - original)
    # with Math.  Tf = Q / mc  + To
    q = heatenergy
    m = amount * 20 # 1 ball is 20L - 20kg
    c = 2260  # J / kg * C - to boil and break bonds in water to create steam
    heatneeded = m * c

    #1100 balls need 83,720,000 to boil
    #400 balls needs 18,080,000
    # 1,000,000 - 100,000,000 for Heat Energy
    return heatneeded

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
    return temp 

def run_world():
    pygame.init()
    pygame.font.init()
    myfont = pygame.font.SysFont('Comic Sans MS', 30 )

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Power Plant")
    clock = pygame.time.Clock()
    running = True



    # Create game space (world) and set gravity to normal
    space = pymunk.Space() #2
    space.gravity = (0.0, -900.0)

    air = pymunk.Space()
    air.gravity = (0.5, 900.0)
    # Add the objects to the game world
    boiler = add_boiler(space)
    plate = add_boiler(air)
    condenser = add_condenser(space)
    condenser_valve = add_condenser_outlet_valve(space)
    watermain = add_watermain(space)
    turbine = add_turbine(space)
    turbair = add_turbine(air)

    turbine_sensor = add_turbine_sensor(air)

    electricmain = add_electricmain(space)

    burner1 = add_burner(space)
    burner1.body.position = (37,134)

    burner2 = add_burner(space)
    burner2.body.position = (97,134)

    burner3 = add_burner(space)
    burner3.body.position = (160,134)

    burners = []
    burners.append(burner1)
    burners.append(burner2)
    burners.append(burner3)

    valve_color = [ 'black', 'white']

    # Water Flow Rate Settings
    waters = []
    WATERRATE = 2
    ticks_to_next_water = WATERRATE

    # Fire Flow Rate Settings
    fires = []
    FUELRATE = 2
    ticks_to_next_fire = FUELRATE


    electricenergies = []
    ELECTRICENERGYRATE = 10
    ticks_to_next_electric_energy = ELECTRICENERGYRATE

    sparks = []
    SPARKRATE = 2
    SPARKCOLORS = ( 'red', 'white', 'yellow', 'green')
    ticks_to_next_spark = SPARKRATE


    ISBOILING = False   # Flag to determine if heat energy is enough to boil when water is over 100 Celsius
    BOILINGRATE = 0

    # Rate of how water converts to steam
    STEAMRATE = 2000 # ( FPS * 1000 ) / 2
    STEAMMAXDIST = 600
    ticks_to_convert_to_steam = BOILINGRATE # * 20 #STEAMRATE

    # Rate of how much steam is created    STEAMRATE to NEXTSTEAMRATE is Water to Steam Ratio
    steams = []
    NEXTSTEAMRATE = 1
    ticks_to_next_steam = 0 #BOILINGRATE # NEXTSTEAMRATE

    # Steam to Water Rate
    #CONVERTFROMSTEAM = BOILINGRATE * 200 #1000
    ticks_to_convert_to_water = 10 #BOILINGRATE * 200

    WATERBALLTOSTEAMRATIO = 20  #1 WATER TO 20 STEAM
    steamconvertedtowater = WATERBALLTOSTEAMRATIO

    # Set font settings
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

    #Start of Low and High Settings for the Boiler
    LOWAMOUNT = 0
    HIGHAMOUNT = 100
    
    TEMPUPDATE = 60
    ticks_til_temp_update = TEMPUPDATE
    boilerempty = True

    FUELTEMPUPDATE = 30
    ticks_til_fuel_temp = FUELTEMPUPDATE

    COOLINGRATE = 120
    ticks_to_cooling = COOLINGRATE

    fromvalvetemp = 75.0
    fromcondensertemp = 90.0

    RPMFRICTION = 5
    ticks_to_rpm_friction = RPMFRICTION
    RPMDECREASEAMOUNT = 5

    #Default Settings
    PLCSetTag(PLC_WATERPUMP_RATE, WATERRATE + 1)
    PLCSetTag(PLC_FUEL_RATE, FUELRATE + 1 )
    PLCSetTag(PLC_BOILER_WATER_VOLUME_LOW, LOWAMOUNT)
    PLCSetTag(PLC_BOILER_WATER_VOLUME_HIGH, HIGHAMOUNT)
    PLCSetTag(PLC_TURBINE_PRESSURE_HIGH, 0)
    #PLCSetTag( PLC_FUEL_RATE, 100000)
    HEATTRANSFER = 0 # Joules

    waterfromvalve = 0
    waterfromcondenser = 0
    condenserwateramount = 0

    TEMPERATURE = 0.0
    TURBINESTEAM = 0

    air.add_collision_handler( turbine_rpm_collision, ball_collision, begin=turbine_rpm)

    while running:
        # Advance the game clock
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == KEYDOWN and event.key == K_ESCAPE:
                running = False
            elif event.type == KEYDOWN and event.key == K_LEFT:
                if PLCGetTag( PLC_TURBINE_PRESSURE_HIGH ):
                    PLCSetTag( PLC_TURBINE_PRESSURE_HIGH, 0)
                else:
                    PLCSetTag( PLC_TURBINE_PRESSURE_HIGH, 1 )
            elif event.type == KEYDOWN and event.key == K_UP:
                FUELRATE = 5
                WATERRATE = 5
                PLCSetTag( PLC_FUEL_RATE, FUELRATE + 1)
                PLCSetTag( PLC_WATERPUMP_RATE, WATERRATE + 1)
                PLCSetTag( PLC_FUEL_VALVE, 1 )
                TEMPERATURE = 100
                for i in range(200):
                    water_shape = add_water(space)
                    water_shape.body.position = watermain.body.position
                    water_shape.body.position.y -= 12
                    water_shape.body.position.x = random.randint( watermain.body.position.x - 1, watermain.body.position.x + 1 )
                    waters.append(water_shape)

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

        if PLCGetTag( PLC_TURBINE_PRESSURE_HIGH) == 1:
            pass

        elif PLCGetTag( PLC_TURBINE_PRESSURE_HIGH) == 0:
            pass

        if( shift == False):
            if (gravity_tick < 1 ):
                shift == True
                space.gravity = (0.0, -900.0)
                gravity_tick = 5
            else:
                gravity_tick -= 1

        if( airshift == False):
            if (airgravity_tick < 1 ):
                airshift == True
                air.gravity = (0.5, 900.0)
                airgravity_tick = 5
            else:
                airgravity_tick -= 1

        # FUEL / FIRE
        if (PLCGetTag(PLC_FUEL_RATE)) - 2 < 1:
         	change = int(PLCGetTag(PLC_FUEL_RATE)) - 1
         	change += FUELRATE
         	if change < 2:
         		change = 2
     		elif change > 11: #21:
     			change = 11 # 21

     		FUELRATE = change
    		PLCSetTag(PLC_FUEL_RATE, FUELRATE + 1 )
            

        fire_to_remove = []          
        if PLCGetTag(PLC_FUEL_VALVE) == 1:
            ticks_to_next_fire -= 1
            #HEATTRANSFER = 100000000 - ( (FUELRATE - 2 ) * 5000000  )
            if ticks_to_next_fire <= 0 :
                ticks_to_next_fire = FUELRATE
                for burner in burners:
                    fire_shape = add_fire(air)
                    fire_shape.body.position = burner.body.position
                    fires.append(fire_shape)
        else:
            pass #HEATTRANSFER = 0

        for fire in fires:
            if fire.body.position.y < 0 or fire.body.position.y > 170:
                fire_to_remove.append(fire)

            draw_ball(bg, fire, 'red')

        for fire in fire_to_remove:
            air.remove(fire, fire.body)
            fires.remove(fire)
        # end - Fuel / Fire


        # Water Pump
        if (PLCGetTag(PLC_WATERPUMP_RATE)) - 2 < 1 :
         	change = int(PLCGetTag(PLC_WATERPUMP_RATE)) - 1
	    	change += WATERRATE
	    	if change < 2:
	    			change = 2
    		elif change > 11 :
    			change = 11

      		WATERRATE = change

    		PLCSetTag(PLC_WATERPUMP_RATE, WATERRATE + 1) 

        if PLCGetTag(PLC_WATERPUMP_VALVE) == 1:
            ticks_to_next_water -= 1
            if ticks_to_next_water <= 0 : #and PLCGetTag(PLC_FEED_PUMP) == 1:
                ticks_to_next_water = WATERRATE
                PLCSetTag(PLC_WATERPUMP_RATE, WATERRATE + 1 )
                water_shape = add_water(space)
                water_shape.body.position = watermain.body.position
                water_shape.body.position.y -= 12
                water_shape.body.position.x = random.randint( watermain.body.position.x - 1, watermain.body.position.x + 1 )
                waters.append(water_shape)
        # end - Water Pump

        water_to_remove = []

        boilerwateramount = 0
        condenserwateramount = 0

        # Drawing Water
        for water in waters:
            draw_ball(bg, water, 'blue')
            if water.body.position.x < 184 and water.body.position.y < 300: # for water in boiler
                boilerwateramount += 1
                if water.body.tag == "VALVE":
                    waterfromvalve += 1
                    water.body.tag = "BOILER"
                elif water.body.tag == "CONDENSER":
                    waterfromcondenser += 1
                    water.body.tag = "BOILER"
            else:
                if water.body.position.x > 184:                    
                    condenserwateramount += 1

        if (TEMPERATURE >= 100) and ISBOILING:
            #ticks_to_convert_to_steam -= 1
            ticks_to_next_steam -= 1
            if ticks_to_next_steam <= 0:
                ticks_to_next_steam = FUELRATE # BOILINGRATE
                steam_shape = add_steam(air)
                steams.append( steam_shape )

            ticks_to_convert_to_steam -=1
            if ticks_to_convert_to_steam <= 0:
                for water in waters:
                    if( water.body.position.x < 184 and water.body.position.y < 300 ):
                        water_to_remove.append(water)
                        ticks_to_convert_to_steam = FUELRATE * 20 #BOILINGRATE * 20
                        break

                '''
                    if( water.body.position.x < 184 and water.body.position.y < 300 ):
                        water_to_remove.append(water)
                        ticks_to_convert_to_steam = STEAMRATE

                        ticks_to_next_steam -= 1
                        if ticks_to_next_steam <= 0 :
                            ticks_to_next_steam = NEXTSTEAMRATE
                            steam_shape = add_steam(air)
                            steams.append( steam_shape )'''


        # BOILER TEMP
        ticks_til_temp_update -= 1
        if ticks_til_temp_update <= 0:
            ticks_til_temp_update = TEMPUPDATE 
            if boilerwateramount == 0:
                PLCSetTag( PLC_BOILER_TEMP, 0.0)
                TEMPERATURE = 0.0
            else:
                amount = boilerwateramount - waterfromvalve - waterfromcondenser
                if waterfromvalve > 0:
                    if (TEMPERATURE > fromvalvetemp ):
                        TEMPERATURE = temperature_adjustment( amount, TEMPERATURE, waterfromvalve, fromvalvetemp)
                    else:
                        TEMPERATURE = temperature_adjustment( waterfromvalve, fromvalvetemp, amount, TEMPERATURE )
                    PLCSetTag( PLC_BOILER_TEMP, TEMPERATURE )
                    amount += waterfromvalve
                    waterfromvalve = 0
                if waterfromcondenser > 0:
                    if (PLCGetTag(PLC_BOILER_TEMP) > fromcondensertemp ):
                        TEMPERATURE = temperature_adjustment( amount, TEMPERATURE, waterfromcondenser, fromcondensertemp)
                    else:
                        TEMPERATURE = temperature_adjustment( waterfromcondenser, fromcondensertemp, amount,TEMPERATURE )
                    PLCSetTag( PLC_BOILER_TEMP, TEMPERATURE )
                    waterfromcondenser = 0

        if (PLCGetTag( PLC_FUEL_VALVE ) == 1 ):
            if boilerwateramount > 0:
                ticks_til_fuel_temp -= 1
                if ticks_til_fuel_temp <= 0:
                    ticks_til_fuel_temp = FUELTEMPUPDATE
                    if TEMPERATURE < 99:
                        TEMPERATURE = increase_temperature_from_fuel( TEMPERATURE, boilerwateramount, FUELRATE ) #HEATTRANSFER ) # currenttemp, amount, heat
                        #temp += PLCGetTag(PLC_BOILER_TEMP)
                        if TEMPERATURE < 100:
                            PLCSetTag( PLC_BOILER_TEMP, TEMPERATURE )
                        else:
                            TEMPERATURE = 100.00
                            PLCSetTag( PLC_BOILER_TEMP, TEMPERATURE )
                        #BOILINGRATE = 0
                        ISBOILING = False
                    else:
                        TEMPERATURE = 100.00
                        PLCSetTag( PLC_BOILER_TEMP, TEMPERATURE )
                        '''
                        heatneeded = boiling_from_fuel( boilerwateramount, HEATTRANSFER )
                        above =  ( HEATTRANSFER - heatneeded ) / 1000000
                        if above > 0:
                            ISBOILING = True
                            if above < 70:
                                rate = above * 120
                                rate /= 70
                                rate = rate - 120
                                rate *= -1
                                BOILINGRATE = rate
                            else:
                                BOILINGRATE = 1
                        else:
                            BOILINGRATE = 0
                            ISBOILING = False
                        '''
                        ISBOILING = True

        else:
            if TEMPERATURE < 100:
                ISBOILING = False
            ticks_to_cooling -= 1
            if ticks_to_cooling <= 0:
                ticks_to_cooling = COOLINGRATE
            if boilerwateramount > 0:
                if TEMPERATURE > 25:
                    TEMPERATURE = temperature_from_cooling( TEMPERATURE )
                    PLCSetTag( PLC_BOILER_TEMP, TEMPERATURE)

        steam_to_remove = []
        TURBINESTEAM = 0
        for steam in steams:
            if steam.body.position.y > 450:
                TURBINESTEAM += 1
                if steam.body.position.x > 225:
                    ticks_to_convert_to_water -= 1
                    if ticks_to_convert_to_water <= 0:
                        steam_to_remove.append(steam)
                        ticks_to_convert_to_water = FUELRATE * 50 # BOILINGRATE * 200


        for steam in steam_to_remove:
            pos = steam.body.position
            steamconvertedtowater -= 1
            if steamconvertedtowater <= 0:
                watershape = add_water(space)
                watershape.body.position = pos
                watershape.body.tag = "CONDENSER"
                waters.append( watershape)
                steamconvertedtowater = WATERBALLTOSTEAMRATIO
            air.remove(steam, steam.body)
            steams.remove(steam)

        
        for water in water_to_remove:
        	space.remove(water, water.body)
        	waters.remove(water)

        steam_to_remove = []

        for steam in steams:
            if steam.body.position.y > STEAMMAXDIST:
                steam_to_remove.append(steam)

            draw_ball( bg, steam, 'gray')

        for steam in steam_to_remove:
            air.remove( steam, steam.body )
            steams.remove(steam)
          
        spark_to_remove = []
        steamcount = 0
        
        for spark in spark_to_remove:
            space.remove( spark)
            sparks.remove(spark)

        for spark in sparks:
            draw_lines(bg, spark, THECOLORS[ random.choice(SPARKCOLORS) ] ) # THECOLORS['red'])

        electricenergy_to_remove = []

        if( PLCGetTag(PLC_PYLON) == 1 ):
        	if( len(sparks) > 0 ):
	            for energy in electricenergies:
	                draw_ball(bg, energy,random.choice(SPARKCOLORS))

	            ticks_to_next_electric_energy -= 1
	            if ticks_to_next_electric_energy <= 0:
	                energy_shape = add_energy(space)
	                energy_shape.body.position = electricmain.body.position
	                energy_shape.body.position.y -= 5
	                electricenergies.append( energy_shape )

        for energy in electricenergies:
            if energy.body.position.y < 300:
                electricenergy_to_remove.append(energy)

        for energy in electricenergy_to_remove:
            space.remove( energy)
            electricenergies.remove(energy)


        # Boiler

        if (PLCGetTag(PLC_BOILER_WATER_VOLUME_LOW) - 1) < 2:
            change = PLCGetTag(PLC_BOILER_WATER_VOLUME_LOW) - 1
            LOWAMOUNT += change
            if LOWAMOUNT <= 0:
                LOWAMOUNT = 0
            elif LOWAMOUNT >= HIGHAMOUNT:
                LOWAMOUNT = HIGHAMOUNT - 1

        if (PLCGetTag(PLC_BOILER_WATER_VOLUME_HIGH) - 1) < 2:
            change = PLCGetTag(PLC_BOILER_WATER_VOLUME_HIGH) - 1
            HIGHAMOUNT += change
            if HIGHAMOUNT <= LOWAMOUNT:
                HIGHAMOUNT = LOWAMOUNT + 1

        if len(steams) > 0:
            ticks_to_rpm_friction -= 1
            if ticks_to_rpm_friction <= 0:
                ticks_to_rpm_friction = RPMFRICTION
                global RPM
                RPM -= RPMDECREASEAMOUNT
                if TURBINESTEAM < 100:
                    RPM += 3
                elif TURBINESTEAM > 200:
                    RPM -= 3
                if RPM < 0:
                    RPM = 0


        PLCSetTag(PLC_BOILER_WATER_VOLUME_LOW, LOWAMOUNT + 3)
        PLCSetTag(PLC_BOILER_WATER_VOLUME_HIGH, HIGHAMOUNT)
        PLCSetTag(PLC_BOILER_WATER_VOLUME, boilerwateramount)
        PLCSetTag(PLC_CONDENSER_WATER_VOLUME, condenserwateramount)

        # end - Boiler


        # Drawing Objects on Screen
        draw_lines(bg, boiler)
        draw_lines(bg, condenser)
        draw_line(bg, condenser_valve, valve_color[( PLCGetTag(PLC_CONDENSER_VALVE)) ] )
        draw_polygon(bg, watermain)
        draw_lines(bg, turbine)
        draw_polygon(bg, electricmain)
        draw_line(bg, turbine_sensor, 'gray')

        for burner in burners:
            draw_polygon(bg, burner, 'black')

        # Used to display number of water inside Boiler
        text = "RPM: " + str(RPM) + " Turbine Steam: " + str(TURBINESTEAM) + " Fuel Rate: " + str(FUELRATE)
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
