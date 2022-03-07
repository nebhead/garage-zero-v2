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
import RPi.GPIO as GPIO

# *****************************************
# Child Class for Raspberry Pi
# *****************************************

class RasPiDoorObj(DoorObj):
	def __init__(self, name, id, outpins, inpins, triggerlevel, sensorlevel, notifyevents, notify_objects_list):
		super().__init__(name, id, outpins, inpins, triggerlevel, sensorlevel, notifyevents, notify_objects_list)
		GPIO.setwarnings(False) # Suppress warning if a device is already configured
		GPIO.setmode(GPIO.BCM) # Address pins in BCM mode
		for item in self.inpins:
			GPIO.setup(self.inpins[item], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

		self.currentinputs = self.get_input_status()
		self.lastinputs = self.get_input_status()

		for item in self.outpins:
			GPIO.setup(self.outpins[item], GPIO.OUT, initial=self.RELAY_OFF)

		self.currentoutputs = self.get_output_status()

		# Set initial state in Redis DB
		for item, value in self.currentinputs.items():
			#print({f'Door {self.name} Input Item: {item} Value: {value}'})
			self.cmdsts.hset('doorobj:' + self.id, item, value)

	def toggle_output(self, outputname):
		GPIO.output(self.outpins[outputname], self.RELAY_ON)
		time.sleep(0.5)
		GPIO.output(self.outpins[outputname], self.RELAY_OFF)

	def get_input_status(self):
		current = {}
		for item, value in self.inpins.items():
			current[item] = GPIO.input(value)
			
		return current

	def get_output_status(self):
		for item, value in self.outpins.items():
			self.currentoutputs[item] = GPIO.input(value)
		return self.currentoutputs
