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
from gzlogging import write_log
import time

"""
 *****************************************
 	Init Variables
 *****************************************
"""
settings = read_settings()  # Get initial settings

# Special import for debug purposes 
if settings['debug']['enable'] == True:
	from door_proto import ProtoDoorObj as DoorObject
	#print('... Loading Prototype Module ...')
else:
	from door_raspi import RasPiDoorObj as DoorObject
	#print('... Loading Raspberry Pi Module ...')

cmdsts = redis.Redis()  # Setup connection to Redis DB
cmdsts.flushall()  # Destroy any existing information in Redis DB

event = 'Control Script Starting.'
write_log(event, logtype='STARTUP')

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

	# Setup Redis Key/Value for settings change notification
	cmdsts.set('settings_update', 'false')

	# Main Loop
	while True:
		# Loop through all defined doors and check status
		for door in door_objects_list:
			door.update_status()
		
		for addon in add_on_objects_list:
			addon.run()

		# Check for any settings changes and update if needed
		if(cmdsts.get('settings_update') == b'true'):
			event = "Settings update detected.  Reloading settings into control script."
			write_log(event, logtype='SETTINGS')
			#print(event)
			cmdsts.flushall()  # Destroy any existing information in Redis DB
			settings = read_settings()  # Get initial settings
			notify_objects_list = setup_notify_objects()
			door_objects_list = setup_door_objects(notify_objects_list)
			cmdsts.set('settings_update', 'false')
			
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

if __name__ == "__main__":
	main()

event = 'Control Script Exiting.'
write_log(event, logtype='EXIT')
exit()