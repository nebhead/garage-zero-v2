#!/usr/bin/env python3

"""
 *****************************************
 	Garage Zero Door Class (BASE)
 *****************************************

 Description: This library supports 
  controlling the outputs and observing
  inputs from doors

 *****************************************
"""

"""
 *****************************************
 	Imported Libraries
 *****************************************
"""

import redis
import time
from gzlogging import write_log

"""
 *****************************************
 	Parent Class Definition 
 *****************************************
"""

class DoorObj: 
	def __init__(self, name, id, outpins, inpins, triggerlevel, sensorlevel, notify_events, notify_objects_list):
		self.cmdsts = redis.Redis()
		self.id = id
		self.name = name
		self.outpins = outpins
		self.inpins = inpins
		self.triggerlevel = triggerlevel
		self.sensorlevel = sensorlevel
		self.notify_events = notify_events 
		self.notify_objects_list = notify_objects_list

		self.currentinputs = {}
		self.currentoutputs = {}
		self.lastinputs = {}  # Used to store last value

		if not self.triggerlevel: # Defines for Active LOW relay (false = LOW)
			self.RELAY_ON = 0
			self.RELAY_OFF = 1
		else: # Defines for Active HIGH relay (true = HIGH)
			self.RELAY_ON = 1
			self.RELAY_OFF = 0 

		if not self.sensorlevel: # Defines for Active LOW sensors (false = LOW)
			self.SENSOR_ON = 0
			self.SENSOR_OFF = 1
		else: # Defines for Active HIGH sesnors (true = HIGH)
			self.SENSOR_ON = 1
			self.SENSOR_OFF = 0 

		# Init Redis Structure for inpins / outpins
		#  For each of the sensors, create a key / value pair with the name of the sensor, and current value
		for item, value in self.inpins.items():
			self.cmdsts.hset('doorobj:' + self.id, item, self.SENSOR_OFF)

		#  For each of the relays, create a key / value pair with the name of the relay
		for item, value in self.outpins.items():
			self.cmdsts.hset('doorobj:' + self.id, item, self.RELAY_OFF)
		
		#  Add accumulators for reminder events
		for item, value in self.notify_events.items():
			if self.notify_events[item]['remindevent'] == item:
				# If the event name matches the name of the remind event, then this is a reminder event
				self.notify_events[item]['remind_acc'] = 0  # Add an accumulator for total time in reminder

	def toggle_output(self, outputname):
		pass

	def _coerce_redis_int(self, value, default=0):
		if value is None:
			return default
		if isinstance(value, bytes):
			value = value.decode().strip()
		if isinstance(value, bool):
			return int(value)
		if isinstance(value, int):
			return value
		if isinstance(value, str):
			lowered = value.lower()
			if lowered in ("true", "on", "yes"):
				return 1
			if lowered in ("false", "off", "no"):
				return 0
			try:
				return int(value)
			except ValueError:
				return default
		try:
			return int(value)
		except (TypeError, ValueError):
			return default

	def get_input_status(self):
		return self.currentinputs

	def get_output_status(self):
		return self.currentoutputs

	def set_input(self, input, value):
		pass

	def set_output(self, output, value):
		pass

	def update_status(self):
		# Get currentinputs from sensors
		#print(f'\n * Last Inputs: {self.lastinputs}')
		self.currentinputs = self.get_input_status()
		#print(f' * Current Inputs: {self.currentinputs}\n')

		# If sensors have changed 
		if (self.currentinputs != self.lastinputs):
			#print('**** Current Inputs != Last Inputs ****')
			for item, value in self.currentinputs.items():
				if(self.lastinputs[item] != self.currentinputs[item]):
					# Set/Clear associated Redis hash value
					self.cmdsts.hset('doorobj:' + self.id, item, self.currentinputs[item])
					# Check notify
					#print(f'Notify Check -> {item}')
					self.notify_sensor_check(item)
					self.lastinputs[item] = self.currentinputs[item]  # set lastinputs so we can detect future sensor changes
		# Check for active timers
		self.check_timers()
		# Get currentoutputs from Redis
		self.check_output_command()

	def notify_sensor_check(self, sensorname):
		# Loop through notify_events
		for item, value in self.notify_events.items():
			if self.notify_events[item]['sensor'] == sensorname:
				if self.notify_events[item]['sensorlevel'] == bool(self.currentinputs[sensorname]):
					if(self.notify_events[item]['starttimer']):
						# In the case where this is a time event and the starttimer flag is set, then start timer
						self.notify_events[item]['timer'] = time.time()
					elif(self.notify_events[item]['time'] != 0):
						# In the case where this is a time event, but does not indicate to start the timer (i.e. Reminders)
						pass
					else:
						self.handle_notify(item)

	def handle_notify(self, notify_event):
		# Loop through notification list within the specific event
		for item_id in self.notify_events[notify_event]['notifylist']:
			# Loop through the notifcation objects to search for any matching notify objects
			for object in self.notify_objects_list: 
				objectid = object.id
				if(item_id == objectid):
					if(self.notify_events[notify_event]['remindevent'] == notify_event):
						object.send(self.notify_events[notify_event]['title'], self.notify_events[notify_event]['message'], remind_acc=self.notify_events[notify_event]['remind_acc'])
					else:
						object.send(self.notify_events[notify_event]['title'], self.notify_events[notify_event]['message'])
	
		# Log this event
		write_log(self.notify_events[notify_event]['title'], logtype=self.notify_events[notify_event]['logtype'])

	def check_timers(self):
		#  Checktimers
		for item, value in self.notify_events.items():
			# Check if this is a time based event and if it's timer is set
			if(self.notify_events[item]['time'] > 0) and (self.notify_events[item]['timer'] > 0):
				# Check if timer is expired for this timer event
				now = time.time()
				if (now >= (self.notify_events[item]['timer'] + (self.notify_events[item]['time'] * 60))):
					self.notify_events[item]['timer'] = 0  # Reset the timer to 0 (deactivate timer)
					# Check if there is a linked remindevent and set that timer to now
					if(self.notify_events[item]['remindevent'] != ''):
						remindevent = self.notify_events[item]['remindevent']
						self.notify_events[remindevent]['timer'] = now
						# Also add time to the accumulator
						self.notify_events[remindevent]['remind_acc'] += self.notify_events[item]['time']
					# Send any associated notifications for this timer event
					self.handle_notify(item)
		
				# Check if timer event has an early end event associated with it
				if(self.notify_events[item]['timerendevent'] != ''):
					timerendevent = self.notify_events[item]['timerendevent']
					sensorendevent = self.notify_events[timerendevent]['sensor']
					sensorendlevel = self.notify_events[timerendevent]['sensorlevel']
					# If the end event occurred, then clear the timer
					if(bool(self.currentinputs[sensorendevent]) == sensorendlevel):
						self.notify_events[item]['timer'] = 0
						if self.notify_events[item]['remindevent'] == item:
							# If the event name matches the name of the remind event, then this is a reminder event
							self.notify_events[item]['remind_acc'] = 0  # Clear the accumulator

	def check_output_command(self):
		#  For each of the relays, check key / value pair
		for item, value in self.outpins.items():
			output_value = self._coerce_redis_int(self.cmdsts.hget('doorobj:' + self.id, item))
			# If button press is requested, toggle output and clear Redis status
			if output_value == self.RELAY_ON:
				self.toggle_output(item)
				self.cmdsts.hset('doorobj:' + self.id, item, self.RELAY_OFF)
				event = self.name + " " + item + " pressed via GarageZero UI."
				write_log(event, logtype='BUTTON')

	def __repr__(self):
		return self.name

	def update(self):
		pass
