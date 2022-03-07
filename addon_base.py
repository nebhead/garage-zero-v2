#!/usr/bin/env python3

"""
 *****************************************
 	Garage Zero Add-On Class (BASE)
 *****************************************

 Description: This library supports 
  controlling Add-Ons

 *****************************************
"""

"""
 *****************************************
 	Imported Libraries
 *****************************************
"""

import time

"""
 *****************************************
 	Parent Class Definition 
 *****************************************
"""

class Add_On_Base():
	def __init__(self, name, outpins, inpins, triggerlevel, sensorlevel):
		self.name = name
		self.outpins = outpins
		self.inpins = inpins
		self.triggerlevel = triggerlevel
		self.sensorlevel = sensorlevel
		self.lastevent = time.time()

	def status(self):
		pass

	def run(self):
		pass
