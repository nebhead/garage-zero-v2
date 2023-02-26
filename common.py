import datetime
import json
import io

def default_settings():
	settings = {}

	settings['misc'] = {
		'public_url': '',
		'theme': 'bootstrap-darkly.css', # default to base theme, bootstrap-yeti.css is my second favorite 
		'themelist': [
			{
				'name' : 'Bootstrap',
			 	'filename' : 'bootstrap.css'
			},
			{
				'name' : 'Darkly (Default)',
			 	'filename' : 'bootstrap-darkly.css'
			},
			{
				'name' : 'Flatly',
			 	'filename' : 'bootstrap-flatly.css'
			},
			{
				'name' : 'Litera',
			 	'filename' : 'bootstrap-litera.css'
			},
			{
				'name' : 'Lumen',
			 	'filename' : 'bootstrap-lumen.css'
			},
			{
				'name' : 'Lux',
			 	'filename' : 'bootstrap-lux.css'
			},
			{
				'name' : 'Sandstone',
			 	'filename' : 'bootstrap-sandstone.css'
			},
			{
				'name' : 'Slate',
			 	'filename' : 'bootstrap-slate.css'
			},
			{
				'name' : 'Superhero',
			 	'filename' : 'bootstrap-superhero.css'
			},
			{
				'name' : 'Yeti (Best Light Theme)',
			 	'filename' : 'bootstrap-yeti.css'
			},
			{
				'name' : 'Zephyr',
			 	'filename' : 'bootstrap-zephyr.css'
			}
		],
		'notify_services' : [
			{
				'name' : 'E-Mail',
				'type' : 'email' 
			}, 
			{
				'name' : 'ifttt',
				'type' : 'ifttt' 
			}, 
			{
				'name' : 'Pushover',
				'type' : 'pushover' 
			}, 
			{
				'name' : 'Push Bullet',
				'type' : 'pushbullet' 
			},
						{
				'name' : 'Prototype(test)',
				'type' : 'proto' 
			}, 
		],
		'listorder': 'topdown', # default list order 'topdown' or 'bottomup'
		'24htime': True,  # default to 24hr time (commonly known as military time in the USA)
		'password': False  # default to not password protected 
	}

	settings['raspi'] = {
		'gpio_list' : [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]
	}

	settings['doors'] = []

	settings['doors'].append(default_door_obj_data())

	settings['notify'] = []

	settings['notify'].append(default_proto_notify_obj_data())

	settings['addons'] = []

	settings['addons'].append(default_raspi_heartbeat_obj_data())

	settings['debug'] = {
		'enable' : False
	}

	settings['api_config'] = {
		'enable' : True, 
		'apikey' : ''
	}

	return settings

def default_door_obj_data():
	door_obj_data = {} 

	door_obj_data = {
		'name' : 'Default Door',
		'id' : get_unique_id(),
		'inpins' : {
			'limitsensoropen' : 14,  # GPIO 14 Default Sensor 0 for GarageZero PCB
			'limitsensorclosed' : 22 # GPIO 22 Default Sensor 1 for GarageZero PCB
		},
		'outpins' : {
			'doorbutton' : 17, # GPIO 17 Default Relay 0 for GarageZero PCB
		},
		'triggerlevel' : True,
		'sensorlevel' : True, 
		'notify_events' : { 
			'on_open' : {
				'title' : 'Door Opened',
				'message' : 'The garage door was opened at [TIME].', 
				'sensor' : 'limitsensorclosed',
				'sensorlevel' : False,
				'time' : 0,
				'timer' : 0,
				'starttimer' : False,
				'timerendevent' : '',
				'remindevent' : '',
				'logtype' : 'OPENED',
				'notifylist' : []
			}, 
			'on_open_time' : {
				'title' : 'Door Open for 10 mins',
				'message' : 'The garage door has been open for 10 minutes (since [TIME]).', 
				'sensor' : 'limitsensorclosed',
				'sensorlevel' : False,
				'time' : 10,
				'timer' : 0,
				'starttimer' : True,
				'timerendevent' : 'on_close',
				'remindevent' : 'on_open_time_remind',
				'logtype' : 'OPEN',
				'notifylist' : []
			}, 
			'on_open_time_remind' : {
				'title' : 'Reminder: Door Open for [REMIND] minutes.',
				'message' : 'Remdiner that the garage door has been open for [REMIND] minutes.',
				'sensor' : 'limitsensorclosed',
				'sensorlevel' : False,
				'time' : 10,
				'timer' : 0,
				'starttimer' : False,
				'timerendevent' : 'on_close',
				'remindevent' : 'on_open_time_remind',
				'logtype' : 'REMIND',
				'notifylist' : []
			},
			'on_close' : {
				'title' : 'Garage Door Closed',
				'message' : 'The garage door was closed at [TIME].',
				'sensor' : 'limitsensorclosed',
				'sensorlevel' : True,
				'time' : 0,
				'timer' : 0,
				'starttimer' : False,
				'timerendevent' : '',
				'remindevent' : '',
				'logtype' : 'CLOSED',
				'notifylist' : []
			}, 
		}
	}

	return door_obj_data

def default_email_notify_obj_data():
	email_notify_obj = {
		'name' : 'Email Notification',
		'id' : get_unique_id(),
		'type' : 'email',
		'to_email': '', # E-mail address to send notification to
		'from_email': '', # E-mail address to log into system
		'username': '', # Username
		'password' : '', # Password
		'smtpserver' : 'smtp.gmail.com', # SMTP Server Name
		'smtpport' : 587, # SMTP Port
		'tls': True,
	}
	return email_notify_obj

def default_ifttt_notify_obj_data():
	ifttt_notify_obj = {
		'name' : 'IFTTT Notification',
		'id' : get_unique_id(),
		'type' : 'ifttt',
		'apikey': '', # API Key for WebMaker IFTTT App notification
		'iftttevent': ''  # Keyword for ifttt event
	}
	return ifttt_notify_obj

def default_pushover_notify_obj_data(): 
	pushover_notify_obj = {
		'name' : 'Pushover Notification',
		'id' : get_unique_id(), 
		'type' : 'pushover',
		'apikey': '', # API Key for Pushover notifications
		'userkeys': '', # Comma-separated list of user keys
	}
	return pushover_notify_obj

def default_pushbullet_notify_obj_data():
	pushbullet_notify_obj = {
		'name' : 'Pushbullet Notification',
		'id' : get_unique_id(),
		'type' : 'pushbullet',
		'apikey': ''
	}
	return pushbullet_notify_obj

def default_proto_notify_obj_data():
	proto_notify_obj = {
		'name' : 'Prototype Notification',
		'id' : get_unique_id(),
		'type' : 'proto',
	}
	return proto_notify_obj

def default_proto_heartbeat_obj_data():
	heartbeat_obj_data = {
		'addon_name' : 'addon_heartbeat_proto', 
		'name' : 'Prototype Heartbeat',
		'inpins' : {}, 
		'outpins' : {
			'led' : 0,  # Not used for prototype
		},
		'triggerlevel' : True,
		'sensorlevel' : True,
		'interval' : 3  # Number of seconds between heartbeats 
	}
	return(heartbeat_obj_data)

def default_raspi_heartbeat_obj_data():
	heartbeat_obj_data = {
		'addon_name' : 'addon_heartbeat_raspi',
		'name' : 'RasPi Heartbeat',
		'id' : get_unique_id(), 
		'inpins' : {}, 
		'outpins' : {
			'led' : 21, # GPIO 21 Default Relay 0 for GarageZero PCB
		},
		'triggerlevel' : True,
		'sensorlevel' : True,
		'interval' : 3 
	}
	return(heartbeat_obj_data)

def default_secrets():
	secrets = {
		'username' : 'default',
		'id' : get_unique_id(), 
		'pc_hash' : ''
	}
	return(secrets)

def read_settings():
	"""
		# Read settings from JSON
	"""
	# Read all lines of settings.json into an list(array)
	try:
		json_data_file = open("settings.json", "r")
		json_data_string = json_data_file.read()
		settings = json.loads(json_data_string)
		json_data_file.close()

	except(IOError, OSError):
		# Issue with reading settings JSON, so create one/write new one
		settings = default_settings()
		write_settings(settings)

	return(settings)

def write_settings(settings):
	# *****************************************
	# Write all control states to JSON file
	# *****************************************
	json_data_string = json.dumps(settings, indent=2, sort_keys=True)
	with open("settings.json", 'w') as settings_file:
	    settings_file.write(json_data_string)

def get_unique_id():
	now = str(datetime.datetime.now())
	now = now[0:19] # Truncate the microseconds

	ID = ''.join(filter(str.isalnum, str(datetime.datetime.now())))
	return(ID)

def read_secrets():
	"""
		# Read secrets from JSON
	"""
	try:
		json_data_file = open("secrets.json", "r")
		json_data_string = json_data_file.read()
		secrets = json.loads(json_data_string)
		json_data_file.close()

	except(IOError, OSError):
		# Issue with reading JSON, so create one/write new one
		secrets = []
		#secrets.append(default_secrets())
		write_secrets(secrets)

	return(secrets)

def write_secrets(secrets):
	# *****************************************
	# Write all control states to JSON file
	# *****************************************
	json_data_string = json.dumps(secrets, indent=2, sort_keys=True)
	with open("secrets.json", 'w') as secrets_file:
	    secrets_file.write(json_data_string)
	    
def is_raspberry_pi():
	"""
	Check if device is a Raspberry Pi
	:return: True if Raspberry Pi. False otherwise
	"""
	try:
		with io.open('/sys/firmware/devicetree/base/model', 'r') as m:
			if 'raspberry pi' in m.read().lower(): return True
	except Exception:
		pass
	return False