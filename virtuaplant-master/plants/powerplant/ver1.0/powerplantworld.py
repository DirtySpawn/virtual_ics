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


# PLC Registers
PLC_FUEL = 0x01
PLC_BOILER = 0x02
PLC_TURBINE = 0x03
PLC_GENERATOR = 0x04
PLC_CONDENSER = 0x05
PLC_CONDENSER_WATER_LEVEL_LOW = 0X06
PLC_CONDENSER_WATER_LEVEL_MIN = 0X07
PLC_CONDENSER_WATER_LEVEL_MAX = 0X08
PLC_CONDENSER_WATER_VALVE = 0X09
PLC_BOILER_WATER_VOLUME = 0x10

PLC_PYLON = 0x0d

# Collision Types

ball_collision = 0x5
condenser_outlet_valve_collision = 0x6
water_low_collision = 0x7
water_min_collision = 0x8
water_max_collision = 0x9

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
    #x = random.randint(169, 170)
    #body.position = x, 348
    shape = pymunk.Circle(body, radius, (0, 0))
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
	x = random.randint(25,165)
	body.position = x, 135
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

	l1 = pymunk.Segment( body, (0,0), (65, 35), 3 ) # (220,25), 3 ) #bottom line
	#l2 = pymunk.Segment( body, (220,15), (220, 200), 3) # right line
	#l3 = pymunk.Segment( body, (220, 200), (100, 200), 3 ) #top line

	l4 = pymunk.Segment( body, (0, 25), (35, 50), 3 )  # (100, 35), 3 ) 

	#l5 = pymunk.Segment( body, (100, 55), (100, 65), 3)
	#l6 = pymunk.Segment( body, (100, 55), (100, 200), 3)
	#l7 = pymunk.Segment( body, (100, 35), ( 35, 45), 3)
	#l8 = pymunk.Segment( body, (100, 55), (65, 55), 3)
	l9 = pymunk.Segment( body, (35,50), (35, 205), 3 )
	l10 = pymunk.Segment( body, (65, 35), (65, 205), 3)


	space.add(l1, l4, l9, l10)

	return (l1, l4, l9, l10)

def add_turbine(space):
    body = pymunk.Body()
    body.position = (32, 465)
    #Boiler
    l1 = pymunk.Segment(body, (0, 0), (0, 70), 3)
    l2 = pymunk.Segment(body, (20, 0), (30, 10), 3)
    l3 = pymunk.Segment(body, (0, 70), (225, 80), 3)
    l5 = pymunk.Segment(body, (30, 10), (188, 0), 3)
    l6 = pymunk.Segment(body, (225, 80), (215, 0), 3)

    space.add(l1, l2, l3, l5, l6)

    return (l1, l2, l3, l5, l6)

# Draw a defined polygon
def draw_polygon(bg, shape):
    points = shape.get_vertices()
    fpoints = []
    for p in points:
        fpoints.append(to_pygame(p))
    pygame.draw.polygon(bg, THECOLORS['red'], fpoints)
    
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
        pygame.draw.lines(screen, color, False, [p1,p2])
    
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
            pygame.draw.lines(screen, color, False, [p1,p2])

# Default collision function for objects
# Returning true makes the two objects collide normally just like "walls/pipes"
def no_collision(space, arbiter, *args, **kwargs):
    return True 

def condenser_valve_open(space, arbiter, *args, **kwargs):
    log.debug("Condenser Valve Opened")
    return False

def condenser_valve_closed(space, arbiter, *args, **kwargs):
    log.debug("Condenser Valve Closed")
    return True

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
    air.gravity = (0.0, 900.0)


    space.add_collision_handler(water_low_collision, ball_collision, begin=None ) 
    space.add_collision_handler(water_min_collision, ball_collision, begin=None ) 
    space.add_collision_handler(water_max_collision, ball_collision, begin=None ) 

    
    # Add the objects to the game world

    
    boiler = add_boiler(space)
    plate = add_boiler(air)
    condenser = add_condenser(space)
    condenser_valve = add_condenser_outlet_valve(space)
    watermain = add_watermain(space)
    turbine = add_turbine(space)
    turbair = add_turbine(air)
    electricmain = add_electricmain(space)

    electricenergies = []
    ELECTRICENERGYRATE = 10
    ticks_to_next_electric_energy = ELECTRICENERGYRATE

    sparks = []
    SPARKRATE = 2
    SPARKCOLORS = ( 'red', 'white', 'yellow', 'green')
    ticks_to_next_spark = SPARKRATE

    waters = []
    WATERRATE = 1
    ticks_to_next_water = WATERRATE

    STEAMRATE = 1600
    STEAMMAXDIST = 600
    ticks_to_convert_steam = STEAMRATE

    fires = []
    FIRERATE = 2
    ticks_to_next_fire = FIRERATE

    steams = []
    NEXTSTEAMRATE = 2
    ticks_to_next_steam = NEXTSTEAMRATE

    CONVERTFROMSTEAM = 10
    ticks_to_convert_to_water = CONVERTFROMSTEAM

    # Set font settings
    fontBig = pygame.font.SysFont(None, 40)
    fontMedium = pygame.font.SysFont(None, 26)
    fontSmall = pygame.font.SysFont(None, 18)

    shift = True    
    gravity_tick = 5
    sensor_tick = 1
    previous_tag = ''

    LOWAMOUNT = 100
    MINAMOUNT = 500
    MAXAMOUNT = 1000
    
    while running:
        # Advance the game clock
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == KEYDOWN and event.key == K_ESCAPE:
                running = False
            elif event.type == KEYDOWN and event.key == pygame.K_LEFT :
            	if PLCGetTag( PLC_CONDENSER ) == 0:
            		PLCSetTag( PLC_CONDENSER, 1 )
            	else:
            		PLCSetTag( PLC_CONDENSER, 0 )

        # Load the background picture for the pipe images
        bg = pygame.image.load("powerplant.jpg") #pygame.image.load("oil_unit.png")
        # Background color
        screen.fill(THECOLORS["white"])

        if PLCGetTag(PLC_CONDENSER) == 1:
            space.add_collision_handler( condenser_outlet_valve_collision, ball_collision, begin=condenser_valve_open )
            if(shift):
                shift = False
                space.gravity = (500.0, 0.0)

        elif PLCGetTag(PLC_CONDENSER) == 0:
            space.add_collision_handler( condenser_outlet_valve_collision, ball_collision, begin=condenser_valve_closed )
            shift = True
        elif ( PLCGetTag(PLC_CONDENSER) > 1 and PLCGetTag(PLC_CONDENSER) < 6 ):
            pass
            #if( sensor_tick == 0 ):
            #    PLCSetTag(PLC_CONDENSER, previous_tag)
            #    sensor_tick = 1
            #else:
            #    sensor_tick -= 1
		
        if( shift == False):
            if (gravity_tick < 1 ):
                shift == True
                space.gravity = (0.0, -900.0)
                gravity_tick = 5
            else:
                gravity_tick -= 1

        fire_to_remove = []          
        if PLCGetTag(PLC_FUEL) == 1:
            ticks_to_next_fire -= 1

            if ticks_to_next_fire <= 0 : #and PLCGetTag(PLC_FEED_PUMP) == 1:
                ticks_to_next_fire = FIRERATE
                fire_shape = add_fire(air)
                fires.append(fire_shape)

            for fire in fires:
                if fire.body.position.y < 0 or fire.body.position.y > 170:
                    fire_to_remove.append(fire)

                draw_ball(bg, fire, 'red')

        for fire in fire_to_remove:
            air.remove(fire, fire.body)
            fires.remove(fire)

        if PLCGetTag(PLC_CONDENSER_WATER_VALVE) == 1:
            ticks_to_next_water -= 1

            if ticks_to_next_water <= 0 : #and PLCGetTag(PLC_FEED_PUMP) == 1:
                ticks_to_next_water = WATERRATE
                water_shape = add_water(space)
                water_shape.body.position = watermain.body.position
                water_shape.body.position.y -= 12
                water_shape.body.position.x = random.randint( watermain.body.position.x - 1, watermain.body.position.x + 1 )
                waters.append(water_shape)
            
        water_to_remove = []

        wateramount = 0

        for water in waters:
            draw_ball(bg, water, 'blue')
            if water.body.position.x < 180 and water.body.position.y < 300: # for water in boiler
                wateramount += 1
            if (PLCGetTag(PLC_FUEL) == 1):
                if ticks_to_convert_steam <= 0:
                    if( water.body.position.x < 180 and water.body.position.y < 300 ):
                        water_to_remove.append(water)
                        ticks_to_convert_steam = STEAMRATE

                        ticks_to_next_steam -= 1
                        if ticks_to_next_steam <= 0 :
                            ticks_to_next_steam = NEXTSTEAMRATE
                            steam_shape = add_steam(air)
                            steams.append( steam_shape )

                else:
                    ticks_to_convert_steam -= 1

        steam_to_remove = []
        for steam in steams:
            if steam.body.position.x > 225 and steam.body.position.y > 400:
                if ticks_to_convert_to_water <= 0:
                    steam_to_remove.append(steam)
                    ticks_to_convert_to_water = CONVERTFROMSTEAM
                else:
                    ticks_to_convert_to_water -= 1

        for steam in steam_to_remove:
            pos = steam.body.position
            watershape = add_water(space)
            watershape.body.position = pos
            waters.append( watershape)
            air.remove(steam, steam.body)
            steams.remove(steam)

        if wateramount  <= 0:
            PLCSetTag(PLC_CONDENSER_WATER_LEVEL_LOW,0 )
            PLCSetTag(PLC_CONDENSER_WATER_LEVEL_MIN,0 )
            PLCSetTag(PLC_CONDENSER_WATER_LEVEL_MAX,0 )
        elif( (wateramount >= LOWAMOUNT) and ( wateramount < MINAMOUNT) ):
            PLCSetTag( PLC_CONDENSER_WATER_LEVEL_LOW, 1)
            PLCSetTag(PLC_CONDENSER_WATER_LEVEL_MIN,0 )
            PLCSetTag(PLC_CONDENSER_WATER_LEVEL_MAX,0 )
        elif( (wateramount >= MINAMOUNT) and ( wateramount < MAXAMOUNT) ):
            PLCSetTag( PLC_CONDENSER_WATER_LEVEL_MIN, 1)
            PLCSetTag(PLC_CONDENSER_WATER_LEVEL_LOW,0 )
            PLCSetTag(PLC_CONDENSER_WATER_LEVEL_MAX,0 )
        elif( wateramount >= MAXAMOUNT ) :
            PLCSetTag( PLC_CONDENSER_WATER_LEVEL_MAX, 1)
            PLCSetTag(PLC_CONDENSER_WATER_LEVEL_MIN,0 )
            PLCSetTag(PLC_CONDENSER_WATER_LEVEL_LOW,0 )


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
        if( PLCGetTag(PLC_TURBINE) == 1):
            for steam in steams:
                if steam.body.position.y > 460:
                    steamcount += 1
            if steamcount > 15:    
                ticks_to_next_spark -= 1
                if ticks_to_next_spark <= 0:
                    for spark in sparks:
                        spark_to_remove.append(spark)

                    ticks_to_next_spark = SPARKRATE
                    spark = add_light1(space)
                    sparks.append(spark)
            else:
                for spark in sparks:
                    spark_to_remove.append(spark)

        elif( PLCGetTag(PLC_TURBINE) == 0 and len(sparks) > 0):
            for spark in sparks:
                spark_to_remove.append(spark)

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


        # Drawing Objects on Screen
        draw_lines(bg, boiler)
        draw_lines(bg, condenser)
        draw_line(bg, condenser_valve, THECOLORS['red'])
        draw_polygon(bg, watermain)
        draw_lines(bg, turbine)
        draw_polygon(bg, electricmain)
        

        # Used to display number of water inside Boiler
        #text = str(wateramount)
        #textsurface = myfont.render( text, False, (0,0,0))
        

        screen.blit(bg, (0, 0))
        #screen.blit(textsurface, (0,0))

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
