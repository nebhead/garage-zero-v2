#!/usr/bin/env python3

"""
 *****************************************
 	Garage Zero Add-On HeartBeat
 *****************************************

 Description: This library supports 
  providing a heartbeat signal. 

 *****************************************
"""

"""
 *****************************************
 	Imported Libraries
 *****************************************
"""

from addon_base import Add_On_Base
import time
import RPi.GPIO as GPIO

"""
 *****************************************
 	Parent Class Definition 
 *****************************************
"""

class HeartBeat_RasPi(Add_On_Base):
	def __init__(self, name, outpins, inpins, triggerlevel, sensorlevel, interval):
		super().__init__(name, outpins, inpins, triggerlevel, sensorlevel)
		GPIO.setwarnings(False) # Suppress warning if a device is already configured
		GPIO.setmode(GPIO.BCM) # Address pins in BCM mode

		self.interval = interval  # Second(s) interval between blinks
		self.currentoutputs = []

		for item in self.outpins:
			GPIO.setup(self.outpins[item], GPIO.OUT, initial=(not self.triggerlevel))

		# self.currentoutputs = self.get_output_status()

	def status(self):
		#print('Alive.')
		pass

	def run(self):
		now = time.time()
		if (now - self.lastevent > self.interval):  # Check if enough time has passed.
			for item in self.outpins:
				GPIO.output(self.outpins[item], self.triggerlevel)

			time.sleep(0.5)

			for item in self.outpins:
				GPIO.output(self.outpins[item], (not self.triggerlevel))

			self.lastevent = now
	
	def get_output_status(self):
		for item, value in self.outpins.items():
			self.currentoutputs[item] = GPIO.input(self.outpins[item])
		return self.currentoutputs


