#!/usr/bin/env python3

"""
 *****************************************
 	Garage Zero Control Script
 *****************************************

 Description: This script monitors the door sensors and can activate relays
  for button pushes.  Notifications are sent from this script if enabled.  

 This script runs as a separate process from the Flask / Gunicorn
  implementation which handles the web interface.

 *****************************************
"""

"""
 *****************************************
 	Imported Libraries
 *****************************************
"""

from common import read_settings
import redis
import notify
from gzlogging import write_log, write_health_log
import time
import os
import socket
from mqtt_ha import MQTTHomeAssistant

"""
 *****************************************
 	Init Variables
 *****************************************
"""
event = 'Control Script Starting.'
write_log(event, logtype='STARTUP')

settings = read_settings()  # Get initial settings

# Special import for debug purposes 
if settings['debug']['enable'] == True:
	from door_proto import ProtoDoorObj as DoorObject
	#print('... Loading Prototype Module ...')
else:
	from door_raspi import RasPiDoorObj as DoorObject
	#print('... Loading Raspberry Pi Module ...')
while True:
	try:
		cmdsts = redis.Redis()  # Setup connection to Redis DB
		event = '(control) Redis Server connection established.'
		write_log(event, logtype='STARTUP')
		break
	except:
		event = '(control) Redis Server not running.  Retrying in 1 second...'
		write_log(event, logtype='ERROR')
		time.sleep(1)
cmdsts.flushall()  # Destroy any existing information in Redis DB

"""
 *****************************************
 	Main Function
 *****************************************
"""
def main():
	global settings
	global cmdsts 

	notify_objects_list = setup_notify_objects()
	door_objects_list = setup_door_objects(notify_objects_list)
	add_on_objects_list = setup_add_on_objects()

	# Setup MQTT Home Assistant Integration
	mqtt_ha = None
	if settings.get('mqtt_ha', {}).get('enabled', False):
		mqtt_ha = MQTTHomeAssistant(settings['mqtt_ha'], door_objects_list)

	# Setup Redis Key/Value for settings change notification
	cmdsts.set('settings_update', 'false')

	# Periodic health log cadence (seconds)
	health_log_interval = 300
	next_health_log = time.time() + health_log_interval

	# Main Loop
	while True:
		# Loop through all defined doors and check status
		for door in door_objects_list:
			door.update_status()
		
		for addon in add_on_objects_list:
			addon.run()

		# Update MQTT states
		if mqtt_ha:
			try:
				mqtt_ha.update()
			except Exception as e:
				write_log(f"MQTT: Unhandled error in update loop: {e}", logtype='MQTT_ERROR')

		# Check for any settings changes and update if needed
		if(cmdsts.get('settings_update') == b'true'):
			event = "Settings update detected.  Reloading settings into control script."
			write_log(event, logtype='SETTINGS')
			#print(event)
			
			# Cleanup MQTT before reloading
			if mqtt_ha:
				mqtt_ha.cleanup()
			
			cmdsts.flushall()  # Destroy any existing information in Redis DB
			settings = read_settings()  # Get initial settings
			notify_objects_list = setup_notify_objects()
			door_objects_list = setup_door_objects(notify_objects_list)
			
			# Reinitialize MQTT with new settings
			mqtt_ha = None
			if settings.get('mqtt_ha', {}).get('enabled', False):
				mqtt_ha = MQTTHomeAssistant(settings['mqtt_ha'], door_objects_list)
			
			cmdsts.set('settings_update', 'false')

		# Periodic health heartbeat for long-run diagnostics
		now = time.time()
		if now >= next_health_log:
			if settings.get('debug', {}).get('health_log', False):
				log_health_status(mqtt_ha)
			next_health_log = now + health_log_interval
			
		#print('... looping ...')
		time.sleep(0.1)
"""
 *****************************************
 	Supporting Functions
 *****************************************
"""
def setup_notify_objects():
	global settings

	notify_objects_list = []
	for object in settings['notify']:
		if object['type'] == 'email':
			notify_objects_list.append(notify.EmailService(object['name'], object['id'], settings['misc']['public_url'], object['to_email'], object['from_email'], object['smtpserver'], object['smtpport'], object['username'], object['password'], object['tls']))
		elif object['type'] == 'ifttt':
			notify_objects_list.append(notify.IFTTTService(object['name'], object['id'], settings['misc']['public_url'], object['apikey'], object['iftttevent']))
		elif object['type'] == 'pushover':
			notify_objects_list.append(notify.PushoverService(object['name'], object['id'], settings['misc']['public_url'], object['apikey'], object['userkeys']))
		elif object['type'] == 'pushbullet':
			notify_objects_list.append(notify.PushBulletService(object['name'], object['id'], settings['misc']['public_url'], object['apikey']))
		else:
			notify_objects_list.append(notify.ProtoService(object['name'], object['id'], settings['misc']['public_url'])) 

	return notify_objects_list

def setup_door_objects(notify_objects_list):
	global settings
	global cmdsts

	door_objects_list = []
	for object in settings['doors']: 
		door_objects_list.append(DoorObject(object['name'], object['id'], object['outpins'], object['inpins'], object['triggerlevel'], object['sensorlevel'], object['notify_events'], notify_objects_list))

	return door_objects_list

def setup_add_on_objects():
	global settings

	add_on_objects_list = []
	
	for object in settings['addons']:
		if object['addon_name'] == 'addon_heartbeat_proto':
			from addon_heartbeat import HeartBeat_Proto
			add_on_objects_list.append(HeartBeat_Proto(object['name'], object['outpins'], object['inpins'], object['triggerlevel'], object['sensorlevel'], object['interval']))
		elif object['addon_name'] == 'addon_heartbeat_raspi':
			from addon_heartbeat_pi import HeartBeat_RasPi
			add_on_objects_list.append(HeartBeat_RasPi(object['name'], object['outpins'], object['inpins'], object['triggerlevel'], object['sensorlevel'], object['interval']))

	return add_on_objects_list

def _read_mem_available_kb():
	"""Return MemAvailable from /proc/meminfo in kB, or -1 when unavailable."""
	try:
		with open('/proc/meminfo', 'r', encoding='utf-8') as meminfo:
			for line in meminfo:
				if line.startswith('MemAvailable:'):
					return int(line.split()[1])
	except Exception:
		pass
	return -1

def _get_primary_ip():
	"""Best-effort local IP discovery without generating external traffic."""
	try:
		with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
			s.connect(('8.8.8.8', 80))
			return s.getsockname()[0]
	except Exception:
		try:
			return socket.gethostbyname(socket.gethostname())
		except Exception:
			return 'unknown'

def log_health_status(mqtt_ha=None):
	"""Write a periodic health line to help diagnose long-run instability."""
	global cmdsts

	redis_ok = False
	redis_ms = -1.0
	try:
		start = time.perf_counter()
		cmdsts.ping()
		redis_ms = (time.perf_counter() - start) * 1000
		redis_ok = True
	except Exception:
		redis_ok = False

	try:
		load1, load5, load15 = os.getloadavg()
	except Exception:
		load1, load5, load15 = -1.0, -1.0, -1.0

	mem_avail_kb = _read_mem_available_kb()
	ip_address = _get_primary_ip()
	mqtt_enabled = bool(settings.get('mqtt_ha', {}).get('enabled', False))
	mqtt_connected = bool(getattr(mqtt_ha, 'connected', False)) if mqtt_ha else False

	health_message = (
		f"redis_ok={redis_ok} redis_ms={redis_ms:.2f} "
		f"mqtt_enabled={mqtt_enabled} mqtt_connected={mqtt_connected} "
		f"load=({load1:.2f},{load5:.2f},{load15:.2f}) "
		f"mem_avail_kb={mem_avail_kb} ip={ip_address}"
	)
	write_health_log(health_message, logtype='HEALTH')

if __name__ == "__main__":
	main()

event = 'Control Script Exiting.'
write_log(event, logtype='EXIT')
exit()