#!/usr/bin/env python3

# *****************************************
# Garage Zero Interface Library
# *****************************************
#
# Description: This library supports 
#  controlling the outputs and observing inputs.
#
# *****************************************

# *****************************************
# Imported Libraries
# *****************************************
import time
from door_base import DoorObj

# *****************************************
# Child Class for Prototyping (test)
# *****************************************

class ProtoDoorObj(DoorObj):
	def __init__(self, name, id, outpins, inpins, triggerlevel, sensorlevel, notifyevents, notify_objects_list):
		super().__init__(name, id, outpins, inpins, triggerlevel, sensorlevel, notifyevents, notify_objects_list)
		for item in self.inpins:
			self.currentinputs[item] = self.SENSOR_OFF
			self.lastinputs[item] = self.SENSOR_OFF
		for item in self.outpins:
			self.currentoutputs[item] = self.RELAY_OFF

		for item, value in self.currentinputs.items():
			print({f'Door {self.name} Input Item: {item} Value: {value}'})
			self.cmdsts.hset('doorobj:' + self.id, item, value)

	def toggle_output(self, outputname):
		self.currentoutputs[outputname] = self.RELAY_ON
		time.sleep(0.5)
		self.currentoutputs[outputname] = self.RELAY_OFF

	def get_input_status(self): 
		#  For each of the relays, check key / value pair
		for item, value in self.inpins.items():
			self.currentinputs[item] = int(self.cmdsts.hget('doorobj:' + self.id, item))
		return self.currentinputs

	def set_input(self, input, value):
		self.currentinputs[input] = value
