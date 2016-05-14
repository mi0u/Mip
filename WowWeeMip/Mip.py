# coding: utf-8
"""
WowWeeMip Mip robot module for pythonista
_________________________________________
use:
from WowWeeMip import Mip

def on_event(event,data):  # delegate function to handle the messages sent by Mip
    pass

Mip.delegate(on_event)     # define on_event() as delegate function
Mip.connect()
Mip.playSound([Mip.sound.beep,0])

_________________________________________
Read functions:

getValue(a)       # Get Mip.attribute
getUserValue(a)   # Get user value at address a 0-15

Action functions:

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
"""

import cb
import time
import threading
import logging


class _Manager (object):

  events={0x00:'unhandled', 0xffff:'disconnected', 0x79:'status', 0x0A:'gesture', 0x0C:'radar', 0x04:'mipDetected', 0x1A:'shake', 0x03:'irCode', 0xFA:'sleep', 0x1D:'clap', 0x81:'weight', 0x82:'gameMode', 0x83:'chestLed', 0x8B:'headLed', 0x85:'odometer', 0x0D:'radarStatus', 0x11:'irStatus', 0x13:'userData', 0x14:'version', 0x19:'hardware', 0x16:'volume', 0x1F:'clapStatus'}
  #gesture
  gesture={10:'left', 11:'right', 12:'sweepLeft', 13:'sweepRight', 14:'hold', 15:'forward', 16:'backward' }
  #status
  position={0:'onBack', 1:'faceDown', 2:'upRight', 3:'pickedUp', 4:'handStand', 5:'faceDownOnTray', 6:'onBackStand'}
  #radar
  value={1:'clear', 2:'30cm', 3:'10cm'}
  #gameMode
  mode={1:'app', 2:'cage', 3:'tracking', 4:'dance', 5:'default', 6:'stack', 7:'trick', 8:'roam'}
  #radarStatus
  status={0:'disabled', 2:'gesture', 4:'radar'}

  @classmethod
  def _percentage(self,x):
    if x>80:
      return int((x-77)*100.0/47)
    else:
      return x/30

  def __init__(self,h):
    self.log = logging.getLogger('_Manager')
    logging.basicConfig()
    #level = logging.getLevelName('DEBUG')
    level = logging.getLevelName('ERROR')
    self.log.setLevel(level)
    self.log.info('__init__ %s',self)
    self.peripheral = None
    self.read_c = None
    self.write_c = None
    self.readvalue = None
    self.ready = False
    self.cv = threading.Condition()
    self.handler = h

  def __del__(self):
    self.log.info('__del__ %s',self)

  def did_discover_peripheral(self, p):
    self.log.info('did_discover_peripheral')
    if p.name and 'WowWee-MiP' in p.name and not self.peripheral:
      self.peripheral = p
      self.log.info('Connecting to %s', p.name)
      cb.connect_peripheral(p)
    else:
      self.log.debug(p.name)
      pass

  def did_connect_peripheral(self, p):
    self.log.info( 'Connected')
    self.log.info( 'Discovering services...')
    p.discover_services()

  def did_fail_to_connect_peripheral(self, p, error):
    self.log.error( 'Failed to connect: %s' % (error,))

  def did_disconnect_peripheral(self, p, error):
    self.log.warning( 'Disconnected, error: %s' % (error,))
    self.ready = False
    self.peripheral = None
    self.read_c = None
    self.write_c = None
    self.readvalue = None
    cb.reset()
    value_list = [0xffff]
    self._on_receive(value_list)

  def did_discover_services(self, p, error):
    for s in p.services:
      if s.uuid == 'FFE5':
        self.log.info('Discovering characteristics for writing (%s)...' % s.uuid)
        p.discover_characteristics(s)
      elif s.uuid == 'FFE0':
        self.log.info( 'Discovering characteristics for reading (%s)...' % s.uuid)
        p.discover_characteristics(s)
      else:
        self.log.debug('unused service: %s',s.uuid)
        pass

  def did_discover_characteristics(self, s, error):
    self.log.info( 'Did discover characteristics...')
    for c in s.characteristics:
      if c.uuid == 'FFE9':
        self.write_c = c
        self.log.info( 'service: %s characteristic: %s value: %s', s.uuid, c.uuid, c.value)
      elif c.uuid == 'FFE4':
        self.read_c = c
        self.peripheral.set_notify_value(c)
        self.log.info( 'service: %s characteristic: %s value: %s', s.uuid, c.uuid, c.value)
      else:
        self.log.debug( 'Not used service: %s characteristic: %s value: %s', s.uuid, c.uuid, c.value)
    if self.write_c and self.read_c:
      with self.cv:
        self.ready = True
        self.cv.notifyAll()

  def did_writes_value(self, c, error):
    self.log.info( 'did_write_value: %s %s', c.uuid,c.value)

  def did_update_value(self, c, error):
    self.log.info('did_update_value')
    value_list = [int(c.value[i:i+2],16) for i in range(0,len(c.value), 2)]
    self._on_receive(value_list)

  def _on_receive(self,value_list):
    self.log.info('_on_receive')
    data={}
    #------ Notification events ------
    if value_list[0] == 0xffff: # disconnect
      self.log.info( 'disconnected' )
      data={'info':'disconnected'}
    elif value_list[0] == 0x0A: # gesture detection 1b
      self.log.info( 'gesture detection %s', map(hex,value_list))
      data={'gesture':_Manager.gesture[value_list[1]]}
    elif value_list[0] == 0x0C: # radar response 1b
      self.log.info( 'radar response %s', map(hex,value_list))
      data={'value':_Manager.value[value_list[1]]}
    elif value_list[0] == 0x04: # mip detection 1b
      self.log.info( 'mip detected %s', map(hex,value_list))
      data={'id':value_list[1]}
    elif value_list[0] == 0x1A: # shake detection 0b
      self.log.info( 'shake detection %s', map(hex,value_list))
    elif value_list[0] == 0x03: # ir code 3-5b
      self.log.info( 'ir code %s', map(hex,value_list))
      data={'irCode':value_list[1:]}
    elif value_list[0] == 0xFA: # sleep 0b
      self.log.warning( 'sleep %s', map(hex,value_list))
      self.ready = False
      cb.reset()
    elif value_list[0] == 0x1D: # clap times 1b
      self.log.info( 'clap times %s', map(hex,value_list))
      data={'clap':value_list[1]}
    elif value_list[0] == 0x79: # mip status 2b
      p=_Manager._percentage(value_list[1])
      self.log.info( 'mip status %s', map(hex,value_list))
      data={'battery':p, 'position':_Manager.position[value_list[2]]}
    elif value_list[0] == 0x81: # weight update 1b
      self.log.info( 'weight update %s', map(hex,value_list))
      deg=value_list[1]
      if deg>45:
        deg=deg-257
      data={'deg':deg}
    #------- Requested events --------
    elif value_list[0] == 0x82: #game mode
      self.log.info( 'gameMode %s', map(hex,value_list))
      v = _Manager.mode[value_list[1]]
      data={'mode':v}
    elif value_list[0] == 0x83: #chest led
      self.log.info( 'chestLed %s', map(hex,value_list))
      v = value_list[1:]
      data={'ledRGB':v}
    elif value_list[0] == 0x8B: #head led
      self.log.info( 'headLed %s', map(hex,value_list))
      v = value_list[1:]
      data={'led1234':v}
    elif value_list[0] == 0x85: #odometer
      self.log.info( 'odometer %s', map(hex,value_list))
      v = (16**6*value_list[1]+16**4*value_list[2]+16**2*value_list[3]+value_list[4])/4850.0
      data={'meters':v}
    elif value_list[0] == 0x0D: #radar status
      self.log.info( 'radarStatus %s', map(hex,value_list))
      v = _Manager.status[value_list[1]]
      data={'status':v}
    elif value_list[0] == 0x11: #Ir status
      self.log.info( 'irStatus %s', map(hex,value_list))
      v = 'on' if value_list[1] else 'off'
      data={'status':v}
    elif value_list[0] == 0x13: #user data
      self.log.info( 'userData %s', map(hex,value_list))
      v = hex(value_list[1])
      data={'address':v, 'data':value_list[2]}
    elif value_list[0] == 0x14: #software version
      self.log.info( 'version %s', map(hex,value_list))
      d = str(value_list[3])+'-'+str(value_list[2])+'-'+str(value_list[1])
      v = value_list[4]
      data={'date':d, 'version':v}
    elif value_list[0] == 0x19: #hardware version
      self.log.info( 'hardware %s', map(hex,value_list))
      c = value_list[1]
      v = value_list[2]
      data={'voiceChip':c, 'version':v}
    elif value_list[0] == 0x16: #volume
      self.log.info( 'volume %s', map(hex,value_list))
      v = value_list[1]
      data={'value':v}
    elif value_list[0] == 0x1F: #clap status
      self.log.info( 'clapStatus %s', map(hex,value_list))
      s = 'on' if value_list[1] else 'off'
      v = 16**2*value_list[2]+value_list[3]
      data={'status':s, 'delay':v}
    else:
      self.log.warning( 'unhandled event received %s', map(hex,value_list))
      data={'data':value_list}
      value_list[0] = 0x00
    self.on_event(_Manager.events[value_list[0]],data)

  def on_event(self, event, data={}):
    self.log.info( 'on_event %s %s',event,data)
    if (type(self.readvalue)is not dict) and (self.readvalue in _Manager.events) and (event == _Manager.events[self.readvalue]):
      self.log.info( 'The value is: %s', data)
      self.readvalue = data
      with self.cv:
        self.cv.notifyAll()
    else:
      self.log.info('call Mip on-event, handler: %s',self.handler)
      self.handler(event,data)
      #thread = threading.Thread(target=self.handler.on_event, args=(event,data))
      #thread.daemon = True            # Daemonize thread
      #thread.start()                  # Start the execution

  def send(self,message):
    self.log.info( 'send %s',message)
    if not self.ready:
      self.log.warning( 'MiP is not connected')
      return
    self.peripheral.write_characteristic_value(self.write_c, bytes(bytearray(message)), False)

  def read(self,message):
    self.log.info('read %s',message)
    if not self.ready:
      self.log.warning( 'MiP is not connected')
      return
    self.readvalue = message[0]
    self.peripheral.write_characteristic_value(self.write_c, bytes(bytearray(message)), True)
    with self.cv:
      self.log.info( 'waiting...')
      self.cv.wait(1)
    return self.readvalue

  def disconnect(self):
    if self.ready:
      #self.ready = False
      self.log.info( 'Disconnecting...')
      time.sleep(.5)
      self.send([0xFC])
    time.sleep(.5)
    cb.reset()
    self.ready = False
    self.peripheral = None
    self.write_c = None
    self.read_c = None
    self.readvalue = None
    #time.sleep(.5)
    self.log.info( 'Disconnected')

  def connect(self):
    self.log.info('Connecting...')
    self.peripheral = None
    if cb.get_state() <> 5:
      self.log.warning('Bluetooth not enabled...')
      while cb.get_state() <> 5:
        time.sleep(1)
    cb.set_central_delegate(self)
    self.log.info( '## Scanning for peripherals... ##')
    with self.cv:
      cb.scan_for_peripherals()
      self.cv.wait(15)
    if not self.ready:
      self.disconnect()
      result = False
    else:
      result = True
    self.log.info(result)
    return result

  def playSound(self, *argv):
    #playSound([sound,time_wait],[sound,time_wait],...)
    self.log.info( 'playSound')
    wait=0.0
    args=[0x06]
    for arg in argv:
      wait+=1.5
      wait+=arg[1]*3/100
      args.append(arg[0])
      args.append((arg[1]/30)%256)
    self.send(args)
    return wait

  def setMipPosition(self,p=0):
    #0 or 1
    self.log.info( 'setMipPosition')
    args=[0x08]
    if p:
      p=1
    else:
      p=0
    args.append(p)
    self.send(args)

  def distanceDrive(self,distance=20,angle=0):
    #distance:(-255cm - +255cm) angle:(-360deg - +360deg)
    self.log.info('distanceDrive')
    direction=0
    turn=0
    if distance<0:
      direction=1
    if angle<0:
      turn=1
    angle=int(abs(angle)%361)
    distance=abs(distance)%256
    args=[0x70]
    args.append(direction)
    args.append(distance)
    args.append(turn)
    args.append(angle/256)
    args.append(angle%256)
    self.send(args)
    time.sleep(distance*6/100+angle/45)

  def driveWithTime(self, speed=100, t=1000):
    #speed:(-100 - +100) t:(0-1785ms)
    self.log.info( 'driveWithTime')
    args=[0x72]
    if speed>0:
      args=[0x71]
    speed=int((abs(speed)%101)*3/10)
    args.append(speed)
    args.append(int((t%1786)/7))
    self.send(args)
    time.sleep(t/1000.0)

  def turnByAngle(self, angle=180, speed=100):
    #angle:(-1275deg - +1275deg) speed:(0-100)
    self.log.info( 'turnByAngle')
    args=[0x73]
    if angle>0:
      args=[0x74]
    speed=int((abs(speed)%101)*24/100)
    angle=int((abs(angle)%1276)/5)
    args.append(angle)
    args.append(speed)
    self.send(args)
    time.sleep(angle*(64/36)/(speed+1))

  def stop(self):
    self.log.info( 'stop')
    self.send([0x77])

  def continuousDrive(self, speed=20, spin=1, crazy=False):
    #speed:(-+1 - 32) spin:(-+1 - 32)
    self.log.info( 'continuousDrive')
    if speed<0:
      speed=abs(speed)+0x20
    if spin<0:
      spin=abs(spin)+0x20
    if crazy:
      spin=spin+0x80
      speed=speed+0x80
    spin=spin+0x40
    args=[0x78]
    args.append(speed)
    args.append(spin)
    self.send(args)
    time.sleep(0.05)

  def setGameMode(self, mode=1):
    self.log.info( 'setGameMode')
    self.send([0x76,mode%9])

  def mipGetUp(self, mode=2):
    self.log.info( 'mipGetUp')
    self.send([0x23,mode%3])

  def setChestLed(self, r, g, b):
    self.log.info( 'setChestLed')
    self.send([0x84,r%256,g%256,b%256])

  def flashChestLed(self, r, g, b, time_on = 500, time_off = 500):
    self.log.info( 'flashChestLed')
    time_on = int(abs(time_on/20))%256
    time_off = int(abs(time_off/20))%256
    self.send([0x89,r%256,g%256,b%256,time_on,time_off])

  def setHeadLed(self, l1=1, l2=1, l3=1, l4=1):
    #0-3,0-3,0-3,0-3
    self.log.info( 'setHeadLed')
    self.send([0x8A,l4%4,l3%4,l2%4,l1%4])

  def setMipVolume(self, volume=7):
    #0-7
    self.log.info( 'setMipVolume')
    self.send([0x15,volume%8])

  def setRadarMode(self, mode=0):
    #0,2,4
    self.log.info( 'setRadarMode')
    self.send([0x0C, mode])


class attribute:
  clapStatus,volume,harware,version,irStatus,radarStatus,odometer,headLed,chestLed,gameMode = 0x1F,0x16,0x19,0x14,0x11,0xD,0x85,0x8B,0x83,0x82

class sound:
  beep, burp, ewwp_ah, lalalala, fart, rerrr, punching_sound_1, punching_sound_2, punching_sound_3, mip_1, mip_2, mip_3, mip_4, ahhh, arhhh, oh_yeah, meh, beh, see_yah, bad_a_bad_a_1, bad_a_bad_a_2, stop, goodnight, bang_of_drum_1, bang_of_drum_2, hi_yah, blabla_1, hahahalep, lets_go, bahbahbah, her, eigh, narrrh, lets_do_it, hellllooo, bah_questioning, ohaye, huh, durdurdurdurdooo, lalalalalaaa, hahhahah_hahhahhahaha, heaaahhh, harp_sound_plus_something, letsMiP, talks_to_himself, okay, music_1, music_2, out_of_power, happy_1, yeuh, yahhahaha, say_music, ohah, ohoh, ohyeah, happy_2, howell_1, howell_2, play, lets_fish, fire, click_click, rar, lalalalala, ah_choo, snoring, feck, whish_1, whish_2, vox, lets_trick, duhduhduhduhduh, waaaah, wakey_wakey, yay, roam_whistle, waaaaahhhh, wuuuy, yeuh, yeah, you, yammy, oooee, aaeeeh, ribit, boring, errr, lets_go, yipppee, hohohohoho, crafteee, crafty, haha, this_is_mip, sigharhhh, mip_crying, nuh, snifty, aaahhhh, funny_beeping_sound, drum, laser_beam, swanny_whistle_sound, no_sound, mip = 1,  2,  3,  4,  5,  6,  7,  8,  9,  10,  11,  12,  13,  14,  15,  16,  17,  18,  19,  20,  21,  22,  23,  24,  25,  26,  27,  28,  29,  30,  31,  32,  33,  34,  35,  36,  37,  38,  39,  40,  41,  42,  43,  44,  45,  46,  47,  48,  49,  50,  51,  52,  53,  54,  55,  56,  57,  58,  59,  60,  61,  62,  63,  64,  65,  66,  67,  68,  69,  70,  71,  72,  73,  74,  75,  76,  77,  78,  79,  80,  81,  82,  83,  84,  85,  86,  87,  88,  89,  90,  91,  92,  93,  94,  95,  96,  97,  98,  99,  100,  101,  102,  103,  104,  105, 106

soundTuple =sorted( (i for i in sound.__dict__.keys() if i[0] is not '_') )

class position:
  onBack, faceDown = 0, 1

class gamemode:
  app, cage, tracking, dance, default, stack, trick, roam = 1, 2, 3, 4, 5, 6, 7, 8

class getupmode:
  fromFront, fromBack, fromAny = 0, 1, 2

class headled:
  off, on, blink, blinkFast = 0, 1, 2, 3

class radarmode:
  disabled, gesture, radar = 0, 2, 4


def on_event(event,data):
  log.info( 'on_event %s %s',event,data)
  if _func:
    try:
      _func(event,data)
    except Exception as err:
      log.error( '%s, the delegate function must have 2 arguments',err)
      raise
  else:
    log.warning( 'Use delegate_function(f) to set the \'f\' as a delegate and implement the f(event,data) ')

def connected():
  '''
  connected()
  Check the connection
  Return: True or False
  '''
  return _manager.ready

def setManagerLogLevel(level):
  '''
  setManagerLogLevel(level)
  Set the manager log level default value is 'ERROR'
  setManagerLogLevel('INFO')
  '''
  level = logging.getLevelName(level)
  _manager.log.setLevel(level)

def setMipLogLevel(level):
  '''
  setMipLogLevel(level)
  Set the Mip log level default value is 'ERROR'
  setMipLogLevel('INFO')
  '''
  level = logging.getLevelName(level)
  log.setLevel(level)

def connect():
  '''
  connect()
  Connect with Mip
  Return: True or False
  '''
  log.info('connect')
  if _manager.ready:
    return True
  else:
    return _manager.connect()

def disconnect():
  '''
  disconnect()
  Disconnect from Mip
  '''
  log.info('disconnect')
  _manager.disconnect()


def getValue(message):
  '''
  getValue(attribute)
  Get the value of a Mip attribute
  Return: a dictionary with the attribute values or None in case of failure
  dict = Mip.getValue(Mip.attribute.odometer)
  '''
  log.info('getValue')
  if (type(message) is not int) or (message not in _Manager.events):
    log.error('%s is invalid value', str(message))
    return {'info':str(message)+' is not a valid attribute'}
  r = _manager.read([message])
  log.info('Value for %s is %s', _manager.events[message], r)
  if type(r) is not dict:
    r = None
  return r

def getUserValue( address):
  '''
  getUserValue(addr)
  Get user value stored in Mip memory (1 byte per address tottaly 16 bytes)
  Return: dictionary {'address':addr, 'data':val}
  addr: ( 0-15 )
  '''
  log.info('getUserValue')
  address = address+32
  if address<0x20 or address>0x2F:
    log.warning('Value out of range 0-15')
    return {'address':hex(address), 'data':None}
  args=[0x13]
  args.append(address)
  r = _manager.read(args)
  log.info('Value for address %s is %s', hex(address), r)
  return r

def delegate_function(o):
  '''
  delegate_function(function)
  Set the delegate function
  The function must have two arguments 'event' and 'data'
  '''
  log.info('Delegate: %s', o)
  global _func
  _func = o

#---------------------------------------
def playSound( *argv):
  '''
  playSound([s1,t1],[s2,t2],...)
  Play sound s and wait for time t
  Mip.playSound([Mip.sound.beep,500])
  '''
  log.info('playSound:')
  for i in argv:
    log.info('%s',i)
  wait = _manager.playSound(*argv)
  if _waitForSound:
    time.sleep(wait)

def setMipPosition(p=0):
  '''
  setMipPosition(p=Mip.position.onBack)
  Mip falls on back or face down
  '''
  log.info('setMipPosition, %d', p)
  _manager.setMipPosition(p)

def distanceDrive(distance=20,angle=0):
  '''
  distanceDrive(distance=20,angle=0)
  Move Mip forward/backward for a given distance with turn
  No speed control, 20 commands are queued
  distance:(-255cm - +255cm) angle:(-360deg - +360deg)
  '''
  log.info('distanceDrive, dist %dcm, angle %ddeg', distance, angle)
  _manager.distanceDrive(distance,angle)

def driveWithTime(speed=70, t=1000):
  '''
  driveWithTime(speed=70, t=1000)
  Drive forward/backword with time
  speed:-100 - +100. t: 0 - 1785ms
  '''
  log.info('driveWithTime, speed %d, time %dms', speed, t)
  _manager.driveWithTime(speed,t)

def turnByAngle( angle=180, speed=100):
  '''
  turnByAngle( angle=180, speed=100)
  Turn the Mip, angle: -1275deg - +1275deg, speed: 0-100
  '''
  log.info('turnByAngle, angle %ddeg, speed %d', angle, speed)
  _manager.turnByAngle(angle,speed)

def stop():
  '''
  stop()
  Stop any Mip movement
  '''
  log.info('stop')
  _manager.stop()

def continuousDrive(speed=20, spin=1, crazy=False):
  '''
  continuousDrive(speed=20, spin=1, crazy=False)
  This command is for single drive or turn and
  should be called in a loop for continuous movement
  speed = 1 - 32 for forward or -1 - -32 for backward
  spin = 1 - 32 for left or -1 - -32 for right
  while True:
      Mip.continuousDrive(speed=32, spin=10, crazy=False)
  '''
  log.info('continuousDrive, speed=%d, spin=%d', speed, spin)
  _manager.continuousDrive(speed,spin,crazy)

def setGameMode( mode=1):
  '''
  setGameMode(mode=Mip.gamemode.app)
  Set game mode
  '''
  log.info('setGameMode, %d', mode)
  _manager.setGameMode(mode)

def mipGetUp(mode=2):
  '''
  mipGetUp( mode=Mip.getupmode.fromAny )
  Mip will attempt to get up from front, back or both if angle is correct
  '''
  log.info('mipGetUp, %d', mode)
  _manager.mipGetUp(mode)

def setChestLed(r ='#00ff00' , g = None, b = None):
  '''
  Set chest led color
  setChestLed('#ff0000') or
  setChestLed(0xff, 0x00, 0x00) or
  setChestLed(255, 0, 0)
  '''
  if g is None:
    log.info('setChestLed, r=%s', r)
    _manager.setChestLed(int(r[1:3],16),int(r[3:5],16),int(r[5:7],16))
  else:
    log.info('setChestLed, r=%d, g=%d, b=%d', r, g, b)
    _manager.setChestLed(r, g, b)

def flashChestLed(r, g, b, time_on=500, time_off=500):
  '''
  flashChestLed(r, g, b, time_on=500, time_off=500)
  Flash chest led on/off time (0-5100ms)
  Mip.flashChestLed(0xff, 0x00, 0x00, time_on=100, time_off=500)
  '''
  log.info('flashChestLed, r=%d, g=%d, b=%d, on=%d, off=%d', r, g, b, time_on, time_off)
  _manager.flashChestLed(r, g, b, time_on, time_off)

def setHeadLed(l1=1, l2=1, l3=1, l4=1):
  '''
  setHeadLed(l1=Mip.headled.on, l2=Mip.headled.on, l3=Mip.headled.on, l4=Mip.headled.on)
  Set 4 head leds on, off, blink or blink fast
  Mip.setHeadLed( l1=Mip.headled.on, l2=Mip.headled.off, l3=Mip.headled.blink, l4=Mip.headled.blinkFast )
  '''
  log.info('setHeadLed, led1=%d, led2=%d, led3=%d, led4=%d', l1, l2, l3, l4)
  _manager.setHeadLed(l1,l2,l3,l4)

def setMipVolume(volume=7):
  '''
  setMipVolume(volume=7)
  Set the sound volume 0-7
  '''
  log.info('setMipVolume, %d', volume)
  _manager.setMipVolume(volume)

def setRadarMode(mode=0):
  '''
  setRadarMode(mode=Mip.radarmode.disabled)
  Set the radar/gesture mode
  Mip.setRadarMode(mode=Mip.radarmode.gesture)
  '''
  log.info( 'setRadarMode, %d', mode)
  _manager.setRadarMode(mode)

_func = None
_waitForSound = False
log = logging.getLogger('Mip')
logging.basicConfig()
#level = logging.getLevelName('DEBUG')
level = logging.getLevelName('ERROR')
log.setLevel(level)
_manager = _Manager(on_event)


#---------------------------------------

if __name__ == "__main__":

  def on_event(event,data):
    print event,data

  delegate_function(on_event)
  #setMipLogLevel('INFO')
  #setManagerLogLevel('INFO')
  print 'connecting...'
  if not connect():
    print 'oooops...'
    exit()

  setMipVolume(1)

  print getValue(0x09)#error
  print getValue('fff')#error

  print getValue(0x82)#gameMode
  print getValue(0x83)
  print getValue(0x8b)
  print getValue(0x85)
  print getValue(0x11)
  print getValue(0x0d)
  print getValue(0x14)
  print getValue(0x19)
  print getValue(0x16)
  print getValue(0x1F)

  print getValue(attribute.gameMode)
  print getValue(attribute.chestLed)
  print getValue(attribute.headLed)
  print getValue(attribute.odometer)
  print getValue(attribute.radarStatus)
  print getValue(attribute.irStatus)
  print getValue(attribute.version)
  print getValue(attribute.harware)
  print getValue(attribute.volume)
  print getValue(attribute.clapStatus)

  print getUserValue(0x19)#error
  print getUserValue(0x00)
  print getUserValue(5)
  print getUserValue(15)
  print getUserValue(16)#error

  distanceDrive(30,10)

  playSound([ sound.hellllooo ,1000 ], [ sound.ah_choo ,0])

  setChestLed('#7355ff')
  time.sleep(3)
  setChestLed(45,65,0)
  time.sleep(3)
  disconnect()
