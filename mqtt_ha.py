#!/usr/bin/env python3

"""
 *****************************************
 	MQTT Home Assistant Integration
 *****************************************

 Description: This module provides MQTT Discovery support for Home Assistant.
  It automatically configures garage door entities in Home Assistant and
  provides real-time status updates and command handling.

 Benefits over REST API:
  - Auto-discovery (no YAML configuration needed)
  - Real-time updates (no polling delays)
  - Bi-directional communication
  - Future-proof (MQTT protocol is stable)

 *****************************************
"""

"""
 *****************************************
 	Imported Libraries
 *****************************************
"""

import json
import time
from gzlogging import write_log
import redis

try:
	import paho.mqtt.client as mqtt
	MQTT_AVAILABLE = True
except ImportError:
	MQTT_AVAILABLE = False
	print("Warning: paho-mqtt not installed. MQTT integration disabled.")

"""
 *****************************************
 	MQTT Home Assistant Class
 *****************************************
"""

class MQTTHomeAssistant:
	"""
	Manages MQTT communication with Home Assistant using MQTT Discovery.
	
	Each garage door is automatically discovered as a cover entity with:
	- Real-time state updates (open/closed/opening/closing)
	- Command support (open/close/stop)
	- Proper device information
	"""
	
	def __init__(self, config, doors_list):
		"""
		Initialize MQTT connection and setup.
		
		Args:
			config: MQTT configuration dict with keys:
				- broker: MQTT broker address
				- port: MQTT broker port (default 1883)
				- username: Optional MQTT username
				- password: Optional MQTT password
				- discovery_prefix: HA discovery prefix (default "homeassistant")
				- base_topic: Base topic for garage-zero (default "garage-zero")
			doors_list: List of DoorObj instances to publish
		"""
		self.cmdsts = redis.Redis()

		if not MQTT_AVAILABLE:
			self.enabled = False
			return
			
		self.config = config
		self.doors_list = doors_list
		self.enabled = config.get('enabled', False)
		
		if not self.enabled:
			return
			
		self.broker = config.get('broker', 'localhost')
		self.port = config.get('port', 1883)
		self.username = config.get('username', '')
		self.password = config.get('password', '')
		self.discovery_prefix = config.get('discovery_prefix', 'homeassistant')
		self.base_topic = config.get('base_topic', 'garage-zero')
		
		# Track last known states to avoid redundant publishes
		self.last_states = {}
		
		# Initialize MQTT client
		self.client = mqtt.Client(client_id="garage-zero-controller")
		self.client.on_connect = self._on_connect
		self.client.on_message = self._on_message
		self.client.on_disconnect = self._on_disconnect
		
		# Set authentication if provided
		if self.username and self.password:
			self.client.username_pw_set(self.username, self.password)
		
		# Connect to broker
		try:
			self.client.connect(self.broker, self.port, 60)
			self.client.loop_start()
			write_log(f"MQTT: Connected to broker at {self.broker}:{self.port}", logtype='MQTT_STATUS')
		except Exception as e:
			write_log(f"MQTT: Failed to connect to broker: {e}", logtype='MQTT_ERROR')
			self.enabled = False
	
	def _on_connect(self, client, userdata, flags, rc):
		"""Callback when connected to MQTT broker."""
		if rc == 0:
			write_log("MQTT: Successfully connected to broker", logtype='MQTT_STATUS')
			# Publish discovery configs for all doors
			self._publish_discovery()
			# Subscribe to command topics
			self._subscribe_commands()
			# Publish initial states
			self._publish_all_states()
		else:
			write_log(f"MQTT: Connection failed with code {rc}", logtype='MQTT_ERROR')
	
	def _on_disconnect(self, client, userdata, rc):
		"""Callback when disconnected from MQTT broker."""
		if rc != 0:
			write_log(f"MQTT: Unexpected disconnection (code {rc}). Reconnecting...", logtype='MQTT_WARN')
	
	def _on_message(self, client, userdata, msg):
		"""Callback when a message is received on a subscribed topic."""
		try:
			# Parse topic to get door ID and command
			# Format: garage-zero/{door_id}/set
			topic_parts = msg.topic.split('/')
			if len(topic_parts) >= 3 and topic_parts[-1] == 'set':
				door_id = topic_parts[-2]
				command = msg.payload.decode('utf-8').upper()
				
				# Find the door object
				door_obj = None
				for door in self.doors_list:
					if self._sanitize_id(door.id) == door_id:
						door_obj = door
						break
				
				if door_obj:
					self._handle_command(door_obj, command)
				else:
					write_log(f"MQTT: Unknown door ID in command: {door_id}", logtype='MQTT_WARN')
		except Exception as e:
			write_log(f"MQTT: Error processing message: {e}", logtype='MQTT_ERROR')
	
	def _handle_command(self, door_obj, command):
		"""
		Handle commands from Home Assistant.
		
		Args:
			door_obj: DoorObj instance to control
			command: Command string (OPEN, CLOSE, STOP)
		"""
		write_log(f"MQTT: Received command '{command}' for door '{door_obj.name}'", logtype='MQTT_CALL')
		
		if command in ['OPEN', 'CLOSE', 'STOP']:
			# Get current door state
			current_state = self._get_door_state(door_obj)
			
			# Validate command against current state for security
			if command == 'OPEN' and current_state == 'closed':
				# Only open if door is closed
				self.cmdsts.hset('doorobj:' + door_obj.id, 'doorbutton', '1')
				self._publish_state(door_obj, 'opening')
			elif command == 'CLOSE' and current_state == 'open':
				# Only close if door is open
				self.cmdsts.hset('doorobj:' + door_obj.id, 'doorbutton', '1')
				self._publish_state(door_obj, 'closing')
			elif command == 'STOP' and current_state in ['opening', 'closing']:
				# Only stop if door is moving
				self.cmdsts.hset('doorobj:' + door_obj.id, 'doorbutton', '1')
			else:
				# Command doesn't match current state - ignore it
				write_log(f"MQTT: Ignoring '{command}' command - door is {current_state}", logtype='MQTT_WARN')
		else:
			write_log(f"MQTT: Unknown command: {command}", logtype='MQTT_WARN')
	
	def _sanitize_id(self, door_id):
		"""
		Sanitize door ID for use in MQTT topics.
		
		Args:
			door_id: Original door ID
			
		Returns:
			Sanitized ID safe for MQTT topics
		"""
		return door_id.replace(' ', '_').replace('/', '_').lower()
	
	def _get_door_state(self, door_obj):
		"""
		Get current state of door for Home Assistant.
		
		Args:
			door_obj: DoorObj instance
			
		Returns:
			State string: 'open', 'closed', 'opening', 'closing', or 'unknown'
		"""
		# Check if we're in a transitional state from command
		door_id = self._sanitize_id(door_obj.id)
		if door_id in self.last_states:
			last_state = self.last_states[door_id]
			# If last published state was opening/closing, check if enough time passed
			if last_state in ['opening', 'closing']:
				# We'll rely on actual sensor updates to change to open/closed
				pass
		
		# Read actual sensor states from Redis
		has_open_sensor = 'limitsensoropen' in door_obj.inpins
		has_closed_sensor = 'limitsensorclosed' in door_obj.inpins
		
		# Get sensor values
		open_state = None
		closed_state = None
		
		if has_open_sensor:
			open_state = self.cmdsts.hget('doorobj:' + door_obj.id, 'limitsensoropen')
			open_state = open_state == b'1' or open_state == '1'
		
		if has_closed_sensor:
			closed_state = self.cmdsts.hget('doorobj:' + door_obj.id, 'limitsensorclosed')
			closed_state = closed_state == b'1' or closed_state == '1'
		
		# Determine state based on available sensors
		if has_open_sensor and has_closed_sensor:
			# Both sensors available
			if open_state:
				return 'open'
			elif closed_state:
				return 'closed'
			else:
				# Neither sensor triggered - infer direction from previous state
				if door_id in self.last_states:
					last_state = self.last_states[door_id]
					# If already in transitional state, keep it
					if last_state in ['opening', 'closing']:
						return last_state
					# Otherwise infer from previous stable state
					elif last_state == 'closed':
						return 'opening'
					elif last_state == 'open':
						return 'closing'
				# Default if no previous state
				return 'open'
		elif has_open_sensor:
			# Only open sensor
			if open_state:
				return 'open'
			else:
				return 'closed'
		elif has_closed_sensor:
			# Only closed sensor
			if closed_state:
				return 'closed'
			else:
				return 'open'
		
		# No sensors configured
		return 'unknown'
	
	def _publish_discovery(self):
		"""Publish MQTT discovery messages for all doors."""
		for door in self.doors_list:
			door_id = self._sanitize_id(door.id)
			
			# Build discovery config
			config = {
				"name": f"{door.name}",
				"unique_id": f"garage_zero_{door_id}",
				"command_topic": f"{self.base_topic}/{door_id}/set",
				"state_topic": f"{self.base_topic}/{door_id}/state",
				"payload_open": "OPEN",
				"payload_close": "CLOSE",
				"payload_stop": "STOP",
				"state_open": "open",
				"state_closed": "closed",
				"state_opening": "opening",
				"state_closing": "closing",
				"optimistic": False,
				"device_class": "garage",
				"device": {
					"identifiers": [f"garage_zero_{door_id}"],
					"name": door.name,
					"manufacturer": "Ben.Parmeter",
					"model": "Garage-Zero",
					"sw_version": "2.0"
				}
			}
			
			# Publish discovery message
			discovery_topic = f"{self.discovery_prefix}/cover/{door_id}/config"
			self.client.publish(discovery_topic, json.dumps(config), retain=True)
			
			write_log(f"MQTT: Published discovery for door '{door.name}'", logtype='MQTT_STATUS')
	
	def _subscribe_commands(self):
		"""Subscribe to command topics for all doors."""
		for door in self.doors_list:
			door_id = self._sanitize_id(door.id)
			command_topic = f"{self.base_topic}/{door_id}/set"
			self.client.subscribe(command_topic)
		
		write_log(f"MQTT: Subscribed to command topics for {len(self.doors_list)} door(s)", logtype='MQTT_STATUS')
	
	def _publish_state(self, door_obj, state=None):
		"""
		Publish state for a specific door.
		
		Args:
			door_obj: DoorObj instance
			state: Optional state override (for intermediate states like 'opening')
		"""
		if not self.enabled:
			return
		
		door_id = self._sanitize_id(door_obj.id)
		
		# Get current state if not overridden
		if state is None:
			state = self._get_door_state(door_obj)
		
		# Only publish if state changed
		if self.last_states.get(door_id) != state:
			state_topic = f"{self.base_topic}/{door_id}/state"
			self.client.publish(state_topic, state, retain=True)
			self.last_states[door_id] = state
			# Note: We don't log every state change to avoid log spam
	
	def _publish_all_states(self):
		"""Publish current state for all doors."""
		for door in self.doors_list:
			self._publish_state(door)
	
	def update(self):
		"""
		Update and publish states for all doors.
		Should be called from the main control loop.
		"""
		if not self.enabled:
			return
		
		for door in self.doors_list:
			self._publish_state(door)
	
	def cleanup(self):
		"""Cleanup MQTT connection."""
		if self.enabled:
			# Publish empty discovery messages to remove from HA
			for door in self.doors_list:
				door_id = self._sanitize_id(door.id)
				discovery_topic = f"{self.discovery_prefix}/cover/{door_id}/config"
				self.client.publish(discovery_topic, "", retain=True)
			
			self.client.loop_stop()
			self.client.disconnect()
			write_log("MQTT: Disconnected and cleaned up", logtype='MQTT_STATUS')
