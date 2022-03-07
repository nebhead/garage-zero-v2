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

"""
 *****************************************
 	Parent Class Definition 
 *****************************************
"""

class HeartBeat_Proto(Add_On_Base):
	def __init__(self, name, outpins, inpins, triggerlevel, sensorlevel, interval):
		super().__init__(name, outpins, inpins, triggerlevel, sensorlevel)
		self.interval = interval  # Three second interval between blinks

	def status(self):
		print('Alive.')

	def run(self):
		now = time.time()
		if (now - self.lastevent > self.interval):  # Check if enough time has passed.
			print(' ... thump', end='')  # Heartbeat Signal
			time.sleep(0.5)
			print('-thump ... ')
			self.lastevent = now