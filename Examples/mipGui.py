# coding: utf-8
import ui
import threading
from time import sleep
from WowWeeMip import Mip

# Disconnect on exit
class MyView (ui.View):

  def did_load(self):
    self.h = Handler(self)
    # Populate table with sounds
    self['soundtable'].data_source.items = Mip.soundTuple
    # Set action functions
    self['connect'].action = self.h.connect_action
    self['red'].action = self.h.slider_action
    self['green'].action = self.h.slider_action
    self['blue'].action = self.h.slider_action
    self['button0'].action = self.h.button_action
    self['button1'].action = self.h.button_action
    self['button2'].action = self.h.button_action
    self['button3'].action = self.h.button_action
    self['soundtable'].data_source.action = self.h.table_action

  # Disconnect on exit
  def will_close(self):
    Mip.disconnect()
    pass


# Implement the touchpad
class TouchView(ui.View):
  def __init__(self):
    self.touched = False
    self.speed = 0
    self.turn = 0

  # Move the mip
  def move(self):
    while self.touched:
      Mip.continuousDrive(self.speed,self.turn)

  # Start the thread on first touch
  def touch_began(self, touch):
    self.touched = True
    x, y = touch.location
    self.convert(x,y)
    thread = threading.Thread(target=self.move, args=())
    thread.daemon = True            # Daemonize thread
    thread.start()                  # Start the execution

  # Update speed and turn
  def touch_moved(self, touch):
    x, y = touch.location
    self.convert(x,y)

  # Touch ended, thread will be stopped
  def touch_ended(self, touch):
    self.touched = False

# Convert touch coordinates to speed and turn
  def convert(self,x,y):
    self.turn = int((x-self.width/2)*64/self.width)
    self.speed = int((self.height/2-y)*64/self.height)
    if abs(self.turn)>32:
      self.turn = 32*self.turn/abs(self.turn)
    if abs(self.speed)>32:
      self.speed = 32*self.speed/abs(self.speed)


class Handler(object):
  def __init__(self,v):
    self.v = v
    self.l=[1,1,1,1]
    # create robot
    #self.ro=Mip()
    # set self as delegate object, see on_event() method
    Mip.delegate_function(self.on_event)
    #self.ro.setMipLogLevel('DEBUG')
    #self.ro.setManagerLogLevel('DEBUG')

  # Read and update the odometer
  def update(self):
    sm = Mip.getValue(Mip.attribute.odometer)['meters']
    while Mip.connected():
      m = Mip.getValue(Mip.attribute.odometer)
      if m:
        m=m['meters']
        self.v['textTotal'].text = str(int(100*m)/100.0)
        self.v['textOdometer'].text = str(int(100*(m-sm))/100.0)
      sleep(2)

  # Create thread to continuously read and update the odometer
  def update_counter(self):
    thread = threading.Thread(target=self.update, args=())
    thread.daemon = True            # Daemonize thread
    thread.start()                  # Start the execution

  # Delegate function handles status event from Mip and update the battery
  def on_event(self,event,data):
    #print event,data
    if event == 'status':
      self.v['textBattery'].text = str(data['battery'])+'%'
    elif event == 'disconnected':
      self.v['connect'].title = 'Connect'

  # handle sliders and update mip chest led
  def slider_action(self,sender):
    v = sender.superview
    # Get the sliders:
    r = v['red'].value
    g = v['green'].value
    b = v['blue'].value
    # Create the new color from the slider values:
    v['chestled'].background_color = (r, g, b)
    # Change the chest color
    Mip.setChestLed(int(255*r),int(255*g),int(255*b))
    sleep(.1)

  # Handle eye buttons and update mip head leds
  def button_action(self,sender):
    #v = sender.superview
    self.l[sender.index] = self.l[sender.index]+1
    Mip.setHeadLed(self.l[0]%4,self.l[1]%4,self.l[2]%4,self.l[3]%4)

  # Handle sound table selection and play the selected sound
  def table_action(self,sender):
    v = self.v
    d = Mip.sound.__dict__
    Mip.playSound([d[sender.items[sender.selected_row]],0])

  # Connect/disconnect button handler
  def connect_action(self,sender):
    v = sender.superview
    if Mip.connected():
      Mip.disconnect()      # disconnect
      sender.title = 'Connect'
    else:
      try:
        Mip.connect() # connect
        sender.title = 'Disconnect'
        # Get head leds value and update the view
        self.l = Mip.getValue(Mip.attribute.headLed)['led1234']
        # Get chest led value and update the view
        rgb = Mip.getValue(Mip.attribute.chestLed)['ledRGB']
        v['red'].value = rgb[0]/255.0
        v['green'].value = rgb[1]/255.0
        v['blue'].value = rgb[2]/255.0
        v['chestled'].background_color = (rgb[0]/255.0, rgb[1]/255.0, rgb[2]/255.0)
        self.update_counter()
      except Exception as e:
        #print 'exception:', e
        sender.title = 'Connect'

if __name__ == "__main__":

  v = ui.load_view('mip')

  if ui.get_screen_size()[1] >= 768:
    # iPad
    v.present('sheet')
  else:
    # iPhone
    v.present()
