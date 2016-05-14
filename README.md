# Mip

WowWeeMip Mip robot module for pythonista
_________________________________________
##use:

from WowWeeMip import Mip

    def on_event(event,data):  # delegate function to handle the messages sent by Mip

    &nbsp;&nbsp;pass


    Mip.delegate(on_event)     # define on_event() as delegate function

    Mip.connect()

    Mip.playSound([Mip.sound.beep,0])

_________________________________________
##Read functions:

getValue(a)       # Get Mip.attribute

getUserValue(a)   # Get user value at address a 0-15



##Action functions:

playSound( [s1,t1], [s2,t2],... )

setMipPosition( Mip.position.onBack )

distanceDrive( distance=20, angle=0 )

driveWithTime( speed=70, t=1000 )

turnByAngle( angle=180, speed=100 )

stop()

continuousDrive( speed=20, spin=1, crazy=False )

setGameMode( mode=Mip.gamemode.app )

mipGetUp( mode=Mip.getupmode.fromAny)

setChestLed( '#ff0000' )

flashChestLed( r, g, b, time_on, time_off )

setHeadLed( l1=Mip.headled.on, l2=Mip.headled.on, l3=Mip.headled.on, l4=Mip.headled.on )

setMipVolume( volume=7 )

setRadarMode( mode=Mip.radarmode.disabled )

connected()
