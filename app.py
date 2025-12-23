from flask import Flask, request, render_template, make_response, redirect, jsonify, session, abort
from flask_wtf import FlaskForm
from flask_bcrypt import Bcrypt  # Re-enabling bcrypt ror Raspberry Pi 6/24
from wtforms import StringField, PasswordField, IntegerField, BooleanField, HiddenField, Form, FormField, FieldList, TextAreaField, SelectField, SelectMultipleField
from wtforms.fields.simple import SubmitField
from wtforms.validators import InputRequired, NumberRange
import os
from common import *
from gzlogging import *
import redis
import secrets

"""
Globals
"""
app = Flask(__name__)
bcrypt = Bcrypt(app)  # Re-enabling bcrypt ror Raspberry Pi 6/24
app.config['SECRET_KEY'] = 'ADD_YOUR_SECRET_HERE'
settings = read_settings()
cmdsts = redis.Redis()
INPIN_TYPES = ['limitsensoropen', 'limitsensorclosed']
OUTPIN_TYPES = ['doorbutton']
temp_door = {}

"""
Local Class Definitions
"""
class NotifyServiceForm(FlaskForm):
	sname = StringField('Name')
	id = HiddenField('ID')
	ntype = HiddenField('Notify Type')

class EmailForm(NotifyServiceForm):
	to_email = StringField('To E-mail', validators=[InputRequired()])
	from_email = StringField('From E-mail', validators=[InputRequired()])
	username = StringField('Username', validators=[InputRequired()])
	password = PasswordField('Password')
	smtpserver = StringField('SMTP Server', validators=[InputRequired()])
	smtpport = IntegerField('SMTP Port', validators=[InputRequired(), NumberRange(min=1, max=65535)])
	tls = BooleanField('TLS')

class IftttForm(NotifyServiceForm):
	apikey = StringField('API Key', validators=[InputRequired()])
	iftttevent = StringField('IFTTT Event', validators=[InputRequired()])

class PushbulletForm(NotifyServiceForm):
	apikey = StringField('API Key', validators=[InputRequired()])

class PushoverForm(NotifyServiceForm):
	apikey = StringField('API Key', validators=[InputRequired()])
	userkeys = StringField('User Key(s)', validators=[InputRequired()])

class ProtoNotifyForm(NotifyServiceForm):
	pass

class InPinFieldForm(Form):
	inpin = SelectField('Sensor', choices=[('limitsensoropen', 'Limit Sensor - OPEN'), ('limitsensorclosed', 'Limit Sensor - CLOSED')])
	gpio_pin = SelectField('GPIO Pin', choices=[0,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27])

class OutPinFieldForm(Form):
	outpin = SelectField('Output', choices=[('doorbutton', 'Door Button')])
	gpio_pin = SelectField('GPIO Pin', choices=[0,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27])

class DoorForm(FlaskForm):
	dname = StringField('Door Name')
	id = HiddenField('ID')
	inpins = FieldList(FormField(InPinFieldForm), min_entries=0)
	outpins = FieldList(FormField(OutPinFieldForm), min_entries=0)
	triggerlevel = BooleanField('Button/Relay Trigger Level High')
	sensorlevel = BooleanField('Sensor Trigger Level High')

class EventForm(FlaskForm):
	id = HiddenField('ID')
	event_type = SelectField('Event Type', choices=[('on_open', 'On Open'), ('on_open_time', 'Open for Time'), ('on_open_time_remind', 'Open Periodic Reminder'), ('on_close', 'On Close'), ('on_closed_time', 'Closed for Time'), ('closed_time_remind', 'Closed Periodic Reminder')])
	title = StringField('Title', validators=[InputRequired()])
	message = TextAreaField('Message', validators=[InputRequired()], render_kw={"rows": 3})
	sensor = SelectField('Watch Sensor', choices=[('limitsensoropen', 'Limit Sensor - OPEN'), ('limitsensorclosed', 'Limit Sensor - CLOSED')])
	sensorlevel = SelectField('Sensor Trigger Level', choices=[('True', 'HIGH'), ('False', 'LOW')])
	time = IntegerField('Time Delay Before Notification(m)', validators=[NumberRange(min=0, max=1440)])
	starttimer = BooleanField('Start the Timer')  # True for simple time events
	timerendevent = SelectField('Timer End on Event', choices=[('', 'None'), ('on_open', 'On Open'), ('on_open_time', 'Open for Time'), ('on_open_time_remind', 'Open Periodic Reminder'), ('on_close', 'On Close'), ('on_closed_time', 'Closed for Time'), ('closed_time_remind', 'Closed Periodic Reminder')])
	remindevent = SelectField('Reminder on Event', choices=[('', 'None'), ('on_open', 'On Open'), ('on_open_time', 'Open for Time'), ('on_open_time_remind', 'Open Periodic Reminder'), ('on_close', 'On Close'), ('on_closed_time', 'Closed for Time'), ('closed_time_remind', 'Closed Periodic Reminder')])
	logtype = SelectField('Log Type (Displayed in Log)', choices=['OPENED', 'OPEN', 'REMIND', 'CLOSED'])
	notifylist = SelectMultipleField('Select Notification Services', choices=[], validate_choice=False)

"""
App Route Functions Begin
"""

@app.route('/login', methods=['POST', 'GET'])
def loginpage():
	global settings 
	
	# Create Alert Structure for Alert Notification
	alert = { 
		'type' : '', 
		'text' : ''
		}

	if request.method == 'POST':
		if('password' in request.form):
			password = request.form['password']
			secrets = read_secrets()
			for secret in secrets:
				if bcrypt.check_password_hash(secret['pc_hash'], password):
					session.permanent = True
					session['active'] = secret['username']
					event = f'{secret["username"]} Logged In.'
					write_log(event, logtype='LOGIN')
					return redirect('/')
			alert['type'] = 'error'
			alert['text'] = 'Incorrect Passcode.'
			event = f'Login Denied: Passcode Incorrect.'
			write_log(event, logtype='DENIED')
		elif('logout' in request.form):
			username = session['active']
			session.pop('active', None)  # Logout
			alert['type'] = 'success'
			alert['text'] = f'User {username} logged out.'
			event = f'{username} Logged In.'
			write_log(event, logtype='LOGOUT')
	
	return render_template('login.html', alert=alert, settings=settings)

@app.route('/', methods=['POST','GET'])
def index():
	global settings
	# Check if password protected AND not logged in 
	if (settings['misc']['password'] == True) and ('active' not in session):
		return redirect('/login')

	button_list, errorlevel = build_button_list()  # This structure is used to build the initial buttons to render on the dash

	# Create Alert Structure for Alert Notification
	alert = { 
		'type' : '', 
		'text' : ''
		}

	if(errorlevel > 0):
		alert['type'] = 'error'
		alert['text'] = 'Unable to find door definitions in redis, is "control.py" running?'
		write_log(alert['text'], logtype='ERROR')
		return render_template('settings.html', alert=alert, settings=settings)

	if (request.method == 'POST'):
		response = request.form
		if('listorder' in response):
			if(response['listorder'] == 'topdown'):
				settings['misc']['listorder'] = 'topdown'
			else:
				settings['misc']['listorder'] = 'bottomup'
			write_settings(settings)
		if('24htime' in response): 
			if(response['24htime'] == 'true'):
				settings['misc']['24htime'] = True
			else:
				settings['misc']['24htime'] = False 
			write_settings(settings)

	return render_template('index.html', settings=settings, button_list=button_list)

@app.route('/test', methods=['POST','GET'])
def testpage():
	global settings
	# Check if password protected AND not logged in 
	if (settings['misc']['password'] == True) and ('active' not in session):
		return redirect('/login')

	button_list, errorlevel = build_button_list()  # This structure is used to build the initial buttons to render on the dash

	# Create Alert Structure for Alert Notification
	alert = { 
		'type' : '', 
		'text' : ''
		}

	if(errorlevel > 0):
		alert['type'] = 'error'
		alert['text'] = 'Unable to find door definitions in redis, is "control.py" running?'
		write_log(alert['text'], logtype='ERROR')
		return render_template('settings.html', alert=alert, settings=settings)

	if (request.method == 'POST'):
		response = request.form
		if(('keyname' in response) and ('button' in response)):
			cmdsts.hset(response['keyname'], response['button'], 1)
		if(('keyname' in response) and ('status' in response)):
			tempval = 1 if int(cmdsts.hget(response['keyname'], response['status'])) == 0 else 0
			cmdsts.hset(response['keyname'], response['status'], tempval)
		return jsonify({ 'result' : 'success' })
	
	if (request.method == 'GET'):
		return render_template('testpage.html', settings=settings, button_list=button_list)

	return redirect('/')

@app.route('/status')
def doorstatus():
	global settings
	# Check if password protected AND not logged in 
	if (settings['misc']['password'] == True) and ('active' not in session):
		return redirect('/login')

	button_list, errorlevel = build_button_list()  # This structure is used to build the initial buttons to render on the dash

	# Create Alert Structure for Alert Notification
	alert = { 
		'type' : '', 
		'text' : ''
		}

	if(errorlevel > 0):
		alert['type'] = 'error'
		alert['text'] = 'Unable to find door definitions in redis, is "control.py" running?'
		write_log(alert['text'], logtype='ERROR')
		return render_template('settings.html', alert=alert, settings=settings)
	
	return jsonify(button_list)

@app.route('/button', methods=['POST'])
def button():
	global settings
	# Check if password protected AND not logged in 
	if (settings['misc']['password'] == True) and ('active' not in session):
		return redirect('/login')

	if (request.method == 'POST'):
		global cmdsts
		response = request.form

		if(('keyname' in response) and ('button' in response)):
			cmdsts.hset(response['keyname'], response['button'], 1)
		return jsonify({ 'result' : 'success' })
	return jsonify({ 'result' : 'failed' })

@app.route('/shortlog')
def shortlog():
	global settings
	# Check if password protected AND not logged in 
	if (settings['misc']['password'] == True) and ('active' not in session):
		return redirect('/login')

	door_history, events = read_log(10, twentyfourhtime=settings['misc']['24htime'])
	return render_template('shortlog.html', door_history=door_history, events=events, settings=settings)

@app.route('/history', methods=['POST','GET'])
def history():
	global settings
	# Check if password protected AND not logged in 
	if (settings['misc']['password'] == True) and ('active' not in session):
		return redirect('/login')

	if (request.method == 'POST'):
		response = request.form

		if('listorder' in response):
			if(response['listorder'] == 'topdown'):
				settings['misc']['listorder'] = 'topdown'
			else:
				settings['misc']['listorder'] = 'bottomup'
			write_settings(settings)
		if('24htime' in response): 
			if(response['24htime'] == 'true'):
				settings['misc']['24htime'] = True
			else:
				settings['misc']['24htime'] = False 
			write_settings(settings)

	door_history, events = read_log(twentyfourhtime=settings['misc']['24htime'])

	return render_template('history.html', door_history=door_history, events=events, pagetheme=settings['misc']['theme'], settings=settings)

@app.route('/settings', methods=['POST','GET'])
def settings_base(action=None):
	global settings
	# Check if password protected AND not logged in 
	if (settings['misc']['password'] == True) and ('active' not in session):
		return redirect('/login')

	global temp_door
	settings = read_settings()

	# Create Alert Structure for Alert Notification
	alert = { 
		'type' : '', 
		'text' : ''
		}

	# Update the system theme
	if('theme' in request.form):
		for theme in settings['misc']['themelist']:
			if theme['name'] == request.form['theme']:
				settings['misc']['theme'] = theme['filename']
				write_settings(settings)
				alert['type'] = 'success'
				alert['text'] = 'Theme updated to ' + theme['name'] + "."

	# Delete a notification service
	if('del_service' in request.form):
		delete_service_id = request.form['del_service']
		alert['type'] = 'error'
		alert['text'] = 'Could not delete service.  Service ID not found. ' + delete_service_id + "."
		for index in range(len(settings['notify'])):
			if(settings['notify'][index]['id'] == delete_service_id):
				service_name = settings['notify'][index]['name']
				# If referenced in notify events of doors, delete from those
				for door in settings['doors']:
					for notify_event in door['notify_events']:
						if delete_service_id in door['notify_events'][notify_event]['notifylist']:
							door['notify_events'][notify_event]['notifylist'].remove(delete_service_id)
				# Delete notification service from structure
				del settings['notify'][index]
				write_settings(settings)
				cmdsts.set('settings_update', 'true')
				alert['type'] = 'success'
				alert['text'] = 'Deleted "' + service_name + '" notification service.'
				return render_template('settings.html', alert=alert, settings=settings)

	# Notify Service Settings
	if('edit_service' in request.form):
		notify_forms_list = build_notify_forms()
		notify_form_id = request.form['edit_service']
		if(notify_form_id in notify_forms_list):
			return render_template('settings_notify_service.html', alert=alert, settings=settings, form=notify_forms_list[notify_form_id])
		else:
			alert['type'] = 'error'
			alert['text'] = 'Edit Notification Service Failed. Unrecognized service ID: ' + request.form['edit_service']
			return render_template('settings.html', alert=alert, settings=settings)

	if('add_service' in request.form):
		if(request.form['add_service'] == 'email'):
			notify_service_form = EmailForm()
			notify_service_form.ntype.data = 'email'
			notify_service_form.id.data = ''  # Indicate that this is a new service
		elif(request.form['add_service'] == 'ifttt'):
			notify_service_form = IftttForm()
			notify_service_form.ntype.data = 'ifttt'
			notify_service_form.id.data = ''  # Indicate that this is a new service
		elif(request.form['add_service'] == 'pushbullet'):
			notify_service_form = PushbulletForm()
			notify_service_form.ntype.data = 'pushbullet'
			notify_service_form.id.data = ''  # Indicate that this is a new service
		elif(request.form['add_service'] == 'pushover'):
			notify_service_form = PushoverForm()
			notify_service_form.ntype.data = 'pushover'
			notify_service_form.id.data = ''  # Indicate that this is a new service
		elif(request.form['add_service'] == 'proto'):
			notify_service_form = ProtoNotifyForm()
			notify_service_form.ntype.data = 'proto'
			notify_service_form.id.data = ''  # Indicate that this is a new service
		elif(request.form['add_service'] == 'none'):
			return render_template('settings.html', alert=alert, settings=settings)
		else:
			notify_service_form = NotifyServiceForm()
			notify_service_form.ntype.data = 'error'
			alert['type'] = 'warning'
			alert['text'] = 'Add service failed. Unrecognized service type: ' + request.form['add_service']
		return render_template('settings_notify_service.html', alert=alert, settings=settings, form=notify_service_form)

	# Update the public / local URL
	if('public_url' in request.form):
		settings['misc']['public_url'] = request.form['public_url']
		write_settings(settings)
		cmdsts.set('settings_update', 'true')
		newurl = settings['misc']['public_url'] if settings['misc']['public_url'] != '' else 'BLANK'
		alert['type'] = 'success'
		alert['text'] = 'Public / Local URL updated to ' + newurl + '.'

	# Update MQTT Settings
	if('mqtt_broker' in request.form):
		settings['mqtt_ha']['enabled'] = True if 'mqtt_enabled' in request.form else False
		settings['mqtt_ha']['broker'] = request.form['mqtt_broker']
		settings['mqtt_ha']['port'] = int(request.form['mqtt_port'])
		settings['mqtt_ha']['username'] = request.form['mqtt_username']
		settings['mqtt_ha']['password'] = request.form['mqtt_password']
		settings['mqtt_ha']['discovery_prefix'] = request.form['mqtt_discovery_prefix']
		settings['mqtt_ha']['base_topic'] = request.form['mqtt_base_topic']
		write_settings(settings)
		cmdsts.set('settings_update', 'true')
		alert['type'] = 'success'
		alert['text'] = 'MQTT Home Assistant settings updated. Changes will take effect when control.py reloads.'

	if('del_door' in request.form):
		delete_door_id = request.form['del_door']
		alert['type'] = 'error'
		alert['text'] = 'Could not delete door.  Door ID not found. ' + delete_door_id + "."
		for index in range(len(settings['doors'])):
			if(settings['doors'][index]['id'] == delete_door_id):
				door_name = settings['doors'][index]['name']
				# Delete Door from settings
				del settings['doors'][index]
				write_settings(settings)
				cmdsts.set('settings_update', 'true')
				alert['type'] = 'success'
				alert['text'] = 'Deleted "' + door_name + '" profile.'
				return render_template('settings.html', alert=alert, settings=settings)

	if('add_door' in request.form):
		temp_door = default_door_obj_data()		
		temp_door['id'] = 'new'
		door_form = build_door_form(temp_door)
		event_list = build_event_list(temp_door)
		return render_template('settings_door.html', alert=alert, settings=settings, dform=door_form, elist=event_list)

	if('edit_door' in request.form):
		door_id = request.form["edit_door"]
		for door in settings['doors']:
			if door_id == door['id']:
				door_form = build_door_form(door)
				event_list = build_event_list(door)
				return render_template('settings_door.html', alert=alert, settings=settings, dform=door_form, elist=event_list)

	return render_template('settings.html', alert=alert, settings=settings)

# Route for Adding / Editing Notification Service
@app.route('/addeditnotify', methods=['POST'])
def addeditnotify(action=None):
	global settings
	# Check if password protected AND not logged in 
	if (settings['misc']['password'] == True) and ('active' not in session):
		return redirect('/login')

	settings = read_settings()
	
	# Create Alert Structure for Alert Notification
	alert = { 
		'type' : '', 
		'text' : ''
		}

	if('add_service' in request.form):
		print(f'Add Service: {request.form["add_service"]}')
		if(request.form['add_service'] == 'email'):
			add_notify_form = EmailForm()
			add_notify_form.ntype.data = 'email'
			add_notify_form.id.data = ''  # Indicate that this is a new service
		elif(request.form['add_service'] == 'ifttt'):
			add_notify_form = IftttForm()
			add_notify_form.ntype.data = 'ifttt'
			add_notify_form.id.data = ''  # Indicate that this is a new service
		elif(request.form['add_service'] == 'pushbullet'):
			add_notify_form = PushbulletForm()
			add_notify_form.ntype.data = 'pushbullet'
			add_notify_form.id.data = ''  # Indicate that this is a new service
		elif(request.form['add_service'] == 'pushover'):
			add_notify_form = PushoverForm()
			add_notify_form.ntype.data = 'pushover'
			add_notify_form.id.data = ''  # Indicate that this is a new service
		else:
			add_notify_form = ProtoNotifyForm()
			add_notify_form.ntype.data = 'proto'
			add_notify_form.id.data = ''  # Indicate that this is a new service

		if add_notify_form.validate():
			if(add_notify_form.ntype.data == 'email'):
				add_notify_service = default_email_notify_obj_data()
				add_notify_service['to_email'] = add_notify_form.to_email.data
				add_notify_service['from_email'] = add_notify_form.from_email.data
				add_notify_service['username'] = add_notify_form.username.data
				add_notify_service['password'] = add_notify_form.password.data
				add_notify_service['smtpserver'] = add_notify_form.smtpserver.data
				add_notify_service['smtpport'] = add_notify_form.smtpport.data
				add_notify_service['tls'] = add_notify_form.tls.data
			elif(add_notify_form.ntype.data =='ifttt'):
				add_notify_service = default_ifttt_notify_obj_data()
				add_notify_service['apikey'] = add_notify_form.apikey.data
				add_notify_service['iftttevent'] = add_notify_form.iftttevent.data
			elif(add_notify_form.ntype.data =='pushover'):
				add_notify_service = default_pushover_notify_obj_data()
				add_notify_service['apikey'] = add_notify_form.apikey.data
				add_notify_service['userkeys'] = add_notify_form.userkeys.data
			elif(add_notify_form.ntype.data =='pushbullet'):
				add_notify_service = default_pushbullet_notify_obj_data()
				add_notify_service['apikey'] = add_notify_form.apikey.data
			else:
				add_notify_service = default_proto_notify_obj_data()

			# Global Settings Apply
			#add_notify_service['id'] = add_notify_form.id.data
			add_notify_service['name'] = add_notify_form.sname.data
			# Write udpate to settings.json
			settings['notify'].append(add_notify_service)
			write_settings(settings)
			cmdsts.set('settings_update', 'true')
			alert['type'] = 'success'
			alert['text'] = 'Added notification service "' + add_notify_service['name'] + '".'
			return render_template('settings.html', alert=alert, settings=settings)
		else:
			# Something failed, so get the error message and notify user
			for fieldName, errorMessages in add_notify_form.errors.items():
				for err in errorMessages:
					print(f'Error: {fieldName} {err} {errorMessages}')
					message = err 
			alert['type'] = 'warning'
			alert['text'] = 'Add notificiation service failed: ' + message
			return render_template('settings_notify_service.html', alert=alert, settings=settings, form=add_notify_form)

	if('edit_service' in request.form):
	# If EDIT Service is requested, check the form and apply changes
		notifyforms = {}
		notifyforms = build_notify_forms()
		for notifyservice in notifyforms:
			# Look for selected service ID in current list of forms
			if notifyservice == request.form['edit_service']:
				# Found the ID, now check ntype and build form
				if(notifyforms[notifyservice].ntype.data == 'email'):
					edit_notify_form = EmailForm()
					edit_notify_form.ntype.data = 'email'
				elif(notifyforms[notifyservice].ntype.data == 'ifttt'):
					edit_notify_form = IftttForm()
					edit_notify_form.ntype.data = 'ifttt'
				elif(notifyforms[notifyservice].ntype.data == 'pushbullet'):
					edit_notify_form = PushbulletForm()
					edit_notify_form.ntype.data = 'pushbullet'
				elif(notifyforms[notifyservice].ntype.data == 'pushover'):
					edit_notify_form = PushoverForm()
					edit_notify_form.ntype.data = 'pushover'
				else:
					edit_notify_form = ProtoNotifyForm()
					edit_notify_form.ntype.data = 'proto'

				if edit_notify_form.validate():
					for service in settings['notify']:
						if service['id'] == edit_notify_form.id.data:
							if(edit_notify_form.ntype.data == 'email'):
								service['to_email'] = edit_notify_form.to_email.data
								service['from_email'] = edit_notify_form.from_email.data
								service['username'] = edit_notify_form.username.data
								if edit_notify_form.password.data != '':
									service['password'] = edit_notify_form.password.data 
								service['smtpserver'] = edit_notify_form.smtpserver.data
								service['smtpport'] = edit_notify_form.smtpport.data
								service['tls'] = edit_notify_form.tls.data
							elif(edit_notify_form.ntype.data =='ifttt'):
								service['apikey'] = edit_notify_form.apikey.data
								service['iftttevent'] = edit_notify_form.iftttevent.data
							elif(edit_notify_form.ntype.data =='pushover'):
								service['apikey'] = edit_notify_form.apikey.data
								service['userkeys'] = edit_notify_form.userkeys.data
							elif(edit_notify_form.ntype.data =='pushbullet'):
								service['apikey'] = edit_notify_form.apikey.data
			
							# Global Settings Apply
							service['name'] = edit_notify_form.sname.data
							write_settings(settings)
							cmdsts.set('settings_update', 'true')
							break
					alert['type'] = 'success'
					alert['text'] = 'Edited notification service "' + edit_notify_form.sname.data + '".'
					# Reload notify forms
					notifyforms = build_notify_forms()
					return render_template('settings.html', alert=alert, settings=settings)
				else:
					# Something failed, so get the error message and notify user
					for fieldName, errorMessages in edit_notify_form.errors.items():
						for err in errorMessages:
							print(f'Error: {fieldName} {err} {errorMessages}')
							message = err 
					alert['type'] = 'error'
					alert['text'] = 'Add notificiation service failed: ' + message
					return render_template('settings_notify_service.html', alert=alert, settings=settings, form=edit_notify_form)

	return render_template('settings.html', alert=alert, settings=settings)

# Route for Adding / Editing Notification Service
@app.route('/addeditdoor', methods=['POST'])
def addeditdoor(action=None):
	global settings
	# Check if password protected AND not logged in 
	if (settings['misc']['password'] == True) and ('active' not in session):
		return redirect('/login')

	global temp_door
	settings = read_settings()
	
	# Create Alert Structure for Alert Notification
	alert = { 
		'type' : '', 
		'text' : ''
		}

	if('edit_door' in request.form):
		door_id = request.form["edit_door"]
		for door in settings['doors']:
			if door['id'] == door_id:
				edit_door_form = DoorForm()
				if(edit_door_form.validate()):
					door['name'] = edit_door_form.dname.data
					door['triggerlevel'] = edit_door_form.triggerlevel.data 
					door['sensorlevel'] = edit_door_form.sensorlevel.data 
					del door['inpins']
					door['inpins'] = {}
					for field in edit_door_form.inpins:
						pin_type = field.inpin.data
						door['inpins'][pin_type] = int(field.gpio_pin.data)
					del door['outpins']
					door['outpins'] = {}
					for field in edit_door_form.outpins:
						pin_type = field.outpin.data
						door['outpins'][pin_type] = int(field.gpio_pin.data)
					write_settings(settings)
					cmdsts.set('settings_update', 'true')
					alert['type'] = 'success'
					alert['text'] = 'Edited door "' + door['name'] + '".'
					return render_template('settings.html', alert=alert, settings=settings)
				else:
					# Something failed, so get the error message and notify user
					for fieldName, errorMessages in edit_door_form.errors.items():
						for err in errorMessages:
							print(f'Error: {fieldName} {err} {errorMessages}')
							message = err 
					alert['type'] = 'error'
					alert['text'] = 'Edit door failed: ' + message
					door_form = build_door_form(door)
					event_list = build_event_list(door)
					return render_template('settings_door.html', alert=alert, settings=settings, dform=door_form, elist=event_list)
		# Door ID not found so return fail
		alert['type'] = 'error'
		alert['text'] = 'Edit door failed: Door ID not found'
		return render_template('settings.html', alert=alert, settings=settings)

	if('add_door' in request.form):
		edit_door_form = DoorForm()
		door = temp_door.copy()
		if(edit_door_form.validate()):
			door['name'] = edit_door_form.dname.data
			door['id'] = get_unique_id()
			door['triggerlevel'] = edit_door_form.triggerlevel.data 
			door['sensorlevel'] = edit_door_form.sensorlevel.data 
			door['inpins'] = {}
			for field in edit_door_form.inpins:
				pin_type = field.inpin.data
				door['inpins'][pin_type] = int(field.gpio_pin.data)
			del door['outpins']
			door['outpins'] = {}
			for field in edit_door_form.outpins:
				pin_type = field.outpin.data
				door['outpins'][pin_type] = int(field.gpio_pin.data)
			settings['doors'].append(door)
			write_settings(settings)
			cmdsts.set('settings_update', 'true')
			alert['type'] = 'success'
			alert['text'] = 'Added door "' + door['name'] + '".'
			return render_template('settings.html', alert=alert, settings=settings)
		else:
			# Something failed, so get the error message and notify user
			for fieldName, errorMessages in edit_door_form.errors.items():
				for err in errorMessages:
					print(f'Error: {fieldName} {err} {errorMessages}')
					message = err 
			alert['type'] = 'error'
			alert['text'] = 'Edit door failed: ' + message
			event_list = build_event_list(door)
			return render_template('settings_door.html', alert=alert, settings=settings, dform=edit_door_form, elist=event_list)

	if('add_event' in request.form):
		# First build notify services list 
		choices = []
		for notify_service in settings['notify']:
			choices.append((notify_service['id'], notify_service['name']))
		# Create Empty Event Form		
		event_form = EventForm()
		event_form.notifylist.choices = choices
		event_form.process()
		event_form.id.data = request.form['add_event']
		event_form.time.data = 0
		action = 'add_event'

		return render_template('settings_event.html', alert=alert, settings=settings, eform=event_form, action=action)

	if('edit_event' in request.form):
		event_type, door_id = request.form['edit_event'].split(':', 2)
		event_form = build_event_form(door_id, event_type)
		return render_template('settings_event.html', alert=alert, settings=settings, eform=event_form)

	if('del_event' in request.form):
		event_type, door_id = request.form['del_event'].split(':', 2)
		if door_id == 'new':
			temp_door['notify_events'].pop(event_type)
			alert['type'] = 'success'
			alert['text'] = 'Deleted Event "' + event_type + '".'
			door_form = build_door_form(temp_door)
			event_list = build_event_list(temp_door)
			return render_template('settings_door.html', alert=alert, settings=settings, dform=door_form, elist=event_list)
		else:
			for door in settings['doors']:
				if door_id == door['id']:
					# Remove dict 'event_type' from door['notify_events']
					door['notify_events'].pop(event_type)
					write_settings(settings)
					cmdsts.set('settings_update', 'true')
					alert['type'] = 'success'
					alert['text'] = 'Deleted Event "' + event_type + '".'
					door_form = build_door_form(door)
					event_list = build_event_list(door)
					return render_template('settings_door.html', alert=alert, settings=settings, dform=door_form, elist=event_list)

	return render_template('settings.html', alert=alert, settings=settings)

@app.route('/addeditevent', methods=['POST'])
def addeditevent(action=None):
	global settings
	# Check if password protected AND not logged in 
	if (settings['misc']['password'] == True) and ('active' not in session):
		return redirect('/login')

	global temp_door
	settings = read_settings()
	
	# Create Alert Structure for Alert Notification
	alert = { 
		'type' : '', 
		'text' : ''
		}

	if('add_event' in request.form):
		# First build notify services list 
		choices = []
		for notify_service in settings['notify']:
			choices.append((notify_service['id'], notify_service['name']))
		# Create Empty Event Form		
		event_form = EventForm()
		event_form.notifylist.choices = choices

		if event_form.validate():
			event_data = {}
			event_data['title'] = event_form.title.data 
			event_data['message'] = event_form.message.data
			event_data['sensor'] = event_form.sensor.data
			event_data['sensorlevel'] = True if event_form.sensorlevel.data == 'True' else False
			event_data['time'] = event_form.time.data
			event_data['starttimer'] = event_form.starttimer.data
			event_data['timerendevent'] = event_form.timerendevent.data
			event_data['remindevent'] = event_form.remindevent.data
			event_data['logtype'] = event_form.logtype.data
			event_data['notifylist'] = event_form.notifylist.data
			event_type_name = event_form.event_type.data
			
			door_id = event_form.id.data
			if door_id == 'new':
				temp_door['notify_events'][event_type_name] = event_data
				door_form = build_door_form(temp_door)
				event_list = build_event_list(temp_door)
				return render_template('settings_door.html', alert=alert, settings=settings, dform=door_form, elist=event_list)
			else:
				for door in settings['doors']:
					if door['id'] == door_id:
						door['notify_events'][event_type_name] = event_data 
						write_settings(settings)
						cmdsts.set('settings_update', 'true')
						door_form = build_door_form(door)
						event_list = build_event_list(door)
						return render_template('settings_door.html', alert=alert, settings=settings, dform=door_form, elist=event_list)
		else:
			# Something failed, so get the error message and notify user
			for fieldName, errorMessages in event_form.errors.items():
				for err in errorMessages:
					message = err 
			alert['type'] = 'error'
			alert['text'] = 'Add event failed: ' + message
			return render_template('settings_event.html', alert=alert, settings=settings, eform=event_form, action='add_event')

	if('edit_event' in request.form):
		event_type, door_id = request.form['edit_event'].split(':', 2)
		# First build notify services list 
		choices = []
		for notify_service in settings['notify']:
			choices.append((notify_service['id'], notify_service['name']))
		# Create Empty Event Form		
		event_form = EventForm()
		event_form.notifylist.choices = choices
		#event_form.process()

		if event_form.validate():
			if door_id == 'new':
				for event in temp_door['notify_events']:
					if event == event_type:
						temp_door['notify_events'][event]['title'] = event_form.title.data 
						temp_door['notify_events'][event]['message'] = event_form.message.data
						temp_door['notify_events'][event]['sensor'] = event_form.sensor.data
						temp_door['notify_events'][event]['sensorlevel'] = True if event_form.sensorlevel.data == 'True' else False
						temp_door['notify_events'][event]['time'] = event_form.time.data
						temp_door['notify_events'][event]['starttimer'] = event_form.starttimer.data
						temp_door['notify_events'][event]['timerendevent'] = event_form.timerendevent.data
						temp_door['notify_events'][event]['remindevent'] = event_form.remindevent.data
						temp_door['notify_events'][event]['logtype'] = event_form.logtype.data
						temp_door['notify_events'][event]['notifylist'] = event_form.notifylist.data
						door_form = build_door_form(temp_door)
						event_list = build_event_list(temp_door)
						return render_template('settings_door.html', alert=alert, settings=settings, dform=door_form, elist=event_list)
			else:
				for door in settings['doors']:
					if door['id'] == door_id:
						for event in door['notify_events']:
							if event == event_type:
								door['notify_events'][event]['title'] = event_form.title.data 
								door['notify_events'][event]['message'] = event_form.message.data
								door['notify_events'][event]['sensor'] = event_form.sensor.data
								door['notify_events'][event]['sensorlevel'] = True if event_form.sensorlevel.data == 'True' else False
								door['notify_events'][event]['time'] = event_form.time.data
								door['notify_events'][event]['starttimer'] = event_form.starttimer.data
								door['notify_events'][event]['timerendevent'] = event_form.timerendevent.data
								door['notify_events'][event]['remindevent'] = event_form.remindevent.data
								door['notify_events'][event]['logtype'] = event_form.logtype.data
								door['notify_events'][event]['notifylist'] = event_form.notifylist.data
								write_settings(settings)
								cmdsts.set('settings_update', 'true')
								door_form = build_door_form(door)
								event_list = build_event_list(door)
								return render_template('settings_door.html', alert=alert, settings=settings, dform=door_form, elist=event_list)
			alert['type'] = 'error'
			alert['text'] = 'Edit event failed: Door ID or Event ID not found'
		else:
			# Something failed, so get the error message and notify user
			for fieldName, errorMessages in event_form.errors.items():
				for err in errorMessages:
					print(f'Error: {fieldName} {err} {errorMessages}')
					message = err 
			alert['type'] = 'error'
			alert['text'] = 'Edit event failed: ' + message
			return render_template('settings_event.html', alert=alert, settings=settings, eform=event_form)

	return render_template('settings.html', alert=alert, settings=settings)

@app.route('/pinsdata',  methods=['POST','GET'])
def pinsdata(action=None):
	global settings
	# Check if password protected AND not logged in 
	if (settings['misc']['password'] == True) and ('active' not in session):
		return redirect('/login')

	global temp_door 

	if('action' in request.form):
		door_id = request.form['id']
		door = {}
		if door_id == 'new':
			door = temp_door 
		else:
			for door_obj in settings['doors']:
				if door_obj['id'] == door_id:
					door = door_obj 
					break 

		if(request.form['action'] == 'get_inpins'):
			door_form = build_door_form(door)
			return render_template('settings_inpins.html', dform=door_form)
		if(request.form['action'] == 'get_outpins'):
			door_form = build_door_form(door)
			return render_template('settings_outpins.html', dform=door_form)
		if(request.form['action'] == 'get_avail_inpins'):
			avail_inpins = INPIN_TYPES.copy()
			for inpin in door['inpins']:
				if inpin in avail_inpins:
					avail_inpins.remove(inpin)
			if avail_inpins == []:
				htmlout='<option value="none">No Sensor Types Available</option>'
			else:
				htmlout=''
				for inpin in avail_inpins:
					htmlout += f'<option value="{inpin}">{inpin}</option>'
			return(htmlout)
		if(request.form['action'] == 'get_avail_outpins'):
			avail_outpins = OUTPIN_TYPES.copy()
			for outpin in door['outpins']:
				if outpin in avail_outpins:
					avail_outpins.remove(outpin)
			if avail_outpins == []:
				htmlout='<option value="none">No Button Types Available</option>'
			else:
				htmlout=''
				for outpin in avail_outpins:
					htmlout += f'<option value="{outpin}">{outpin}</option>'
			return(htmlout)
		if(request.form['action'] == 'add_inpin'):
			pintype = request.form['pintype']
			if (pintype != 'none') and (pintype != ''):
				door['inpins'][pintype] = 0
				write_settings(settings)
				cmdsts.set('settings_update', 'true')
			door_form = build_door_form(door)
			return render_template('settings_inpins.html', dform=door_form)
		if(request.form['action'] == 'add_outpin'):
			pintype = request.form['pintype']
			if (pintype != 'none') and (pintype != ''):
				door['outpins'][pintype] = 0
				write_settings(settings)
				cmdsts.set('settings_update', 'true')
			door_form = build_door_form(door)
			return render_template('settings_outpins.html', dform=door_form)
		if(request.form['action'] == 'del_inpin'):
			pintype = request.form['pintype']
			del door['inpins'][pintype]
			write_settings(settings)
			cmdsts.set('settings_update', 'true')
			door_form = build_door_form(door)
			return render_template('settings_inpins.html', dform=door_form)
		if(request.form['action'] == 'del_outpin'):
			pintype = request.form['pintype']
			del door['outpins'][pintype]
			write_settings(settings)
			cmdsts.set('settings_update', 'true')
			door_form = build_door_form(door)
			return render_template('settings_outpins.html', dform=door_form)

	return ('Error Retrieving Table Data')

@app.route('/admin/<action>', methods=['POST','GET'])
@app.route('/admin', methods=['POST','GET'])
def admin(action=None):
	global settings

	# Check if password protected AND not logged in 
	if (settings['misc']['password'] == True) and ('active' not in session):
		return redirect('/login')

	settings = read_settings()
	secrets = read_secrets()

	# Create Alert Structure for Alert Notification
	alert = { 
		'type' : '', 
		'text' : ''
		}

	if action == 'reboot':
		event = "Reboot Requested."
		write_log(event, logtype="REBOOT")
		os.system("sleep 3 && sudo reboot &")

		#Show Reboot Splash
		return render_template('shutdown.html', action=action, settings=settings)

	if action == 'shutdown':
		event = "Shutdown Requested."
		write_log(event, logtype="SHUTDOWN")
		os.system("sleep 3 && sudo shutdown -h now &")

		#Show Shutdown Splash
		return render_template('shutdown.html', action=action, settings=settings)

	if (request.method == 'POST'):
		response = request.form
		if('enable_security' in response):
			pass
			'''
			# Bcrypt Issue on Raspberry Pi, enabling login security is disabled (2/2023)
			if response['enable_security'] == 'true':
				if len(secrets) > 0:
					settings['misc']['password'] = True
					write_settings(settings)
					event = 'Enabled security / password access.'
					write_log(event, logtype='SETTINGS')
					alert['type'] = 'success'
					alert['text'] = event
				else: 
					event = 'No users/passcodes defined.  You must have at least one user/passcode to enable security.'
					write_log(event, logtype='SETTINGS')
					alert['type'] = 'warning'
					alert['text'] = event
			else:
				settings['misc']['password'] = False
				write_settings(settings)
				event = 'Disabled security / password access.'
				write_log(event, logtype='SETTINGS')
				alert['type'] = 'success'
				alert['text'] = event
			'''
		if('del_user' in response):
			for index in range(len(secrets)):
				if(secrets[index]['id'] == response['del_user']):
					del secrets[index]
					write_secrets(secrets)
					event = 'Deleted User. '
					write_log(event, logtype='SETTINGS')
					alert['type'] = 'success'
					alert['text'] = event
					# If there are no more users in the secrets file, then disable password security to prevent lockout
					if len(secrets) == 0:
						settings['misc']['password'] = False
						write_settings(settings)
						event = 'Disabled security / password access since there are no users.'
						write_log(event, logtype='SETTINGS')
						alert['text'] += event
		if('add_user' in response):
			password = response['password']
			if(password.isnumeric()) and (len(password) > 3) and (response['username'] != ''):
				newuser = {}
				newuser['id'] = get_unique_id()
				newuser['username'] = response['username']
				newuser['pc_hash'] = bcrypt.generate_password_hash(response['password']).decode('UTF-8')
				secrets.append(newuser)
				write_secrets(secrets)
				event = f'Added User {response["username"]}'
				write_log(event, logtype='SETTINGS')
				alert['type'] = 'success'
				alert['text'] = event
			else: 
				alert['type'] = 'error'
				alert['text'] = 'Passcode must be numeric only and at least four digits long.  Please try again.'

	uptime = os.popen('uptime').readline()

	cpuinfo = os.popen('cat /proc/cpuinfo').readlines()

	return render_template('admin.html', alert=alert, uptime=uptime, cpuinfo=cpuinfo, settings=settings, secrets=secrets)

@app.route('/sec', methods=['POST','GET'])
def sec_check():
	global settings

	# Check if password protected AND not logged in 
	if (settings['misc']['password'] == True) and ('active' not in session):
		return redirect('/login')

	if('enable_security' in request.form):
		if request.form['enable_security'] == 'true':
			secrets = read_secrets()
			if len(secrets) > 0:
				settings['misc']['password'] = True
				write_settings(settings)
				return jsonify({ 'result' : 'success'})
		else:
			settings['misc']['password'] = False
			write_settings(settings)
			return jsonify({ 'result' : 'success'})

	if('enable_api' in request.form):
		if request.form['enable_api'] == 'true':
			settings['api_config']['enable'] = True
			if settings['api_config']['apikey'] == '':
				settings['api_config']['apikey'] = gen_api_key(32)
			write_settings(settings)
			return jsonify({ 'result' : 'success', 'apikey' : settings['api_config']['apikey'] })
		else:
			settings['api_config']['enable'] = False
			write_settings(settings)
			return jsonify({ 'result' : 'success'})

	if('gen_api' in request.form):
		if request.form['gen_api'] == 'true':
			settings['api_config']['apikey'] = gen_api_key(32)
			write_settings(settings)
			return jsonify({ 'result' : 'success', 'apikey' : settings['api_config']['apikey'] })

	return jsonify({ 'result' : 'fail'})

@app.route('/manifest')
def manifest():
    res = make_response(render_template('manifest.json'), 200)
    res.headers["Content-Type"] = "text/cache-manifest"
    return res

@app.route('/api/<action>', methods=['POST','GET'])
def api(action=None):
	global settings 

	apikey = settings['api_config']['apikey']

	if (settings['api_config']['enable'] == True) and (apikey == action):
		if (request.method == 'POST'):
			if not request.json:
				event = 'Local API Call Failed - Local API interface not enabled.'
				write_log(event, logtype='API')
				abort(400)
			else:
				if('DoorButton' in request.json):
					for door in settings['doors']:
						if door['name'] == request.json['DoorButton']:
							keyname = 'doorobj:' + door['id']
							cmdsts.hset(keyname, 'doorbutton', 1)
							event = f'Local API Call Success. Door button [{door["name"]}] pressed.'
							print(event)
							write_log(event, logtype='API')
							return jsonify({'result': 'success'}), 201
			return jsonify({'result': 'failed'}), 201

		if (request.method == 'GET'):
			doors_output = {}
			for door in settings['doors']:
				keyname = 'doorobj:' + door['id']

				doors_output[door['name']] = {
					'id' : door['id'],
					'status' : {}
				}

				for index in door['inpins']:
					sensor = cmdsts.hget(keyname, index)
					if (sensor != None): 
						doors_output[door['name']]['status'][index] = 'open' if int(cmdsts.hget(keyname, index)) == 0 else 'closed'
					else:
						errorlevel=1
						break
		
			event = 'Local API Call Success. [GET]'
			#WriteLog(event)
			return jsonify(doors_output), 201

	event = 'Local API Call Failed.'	
	write_log(event, logtype='API')

	abort(404)

@app.route('/haexample')
def haexample():
	global settings 

	# Check if password protected AND not logged in 
	if (settings['misc']['password'] == True) and ('active' not in session):
		return redirect('/login')

	for door in settings['doors']:
		doorname = door['name']
		break

	server_ip = request.environ['HTTP_HOST']
	#server_ip = '192.168.10.164'
	print(request.environ)
	site_url_api = f"http://{server_ip}/api/{settings['api_config']['apikey']}"
	value_template = "{{ value_json['" + doorname + "']['status']['limitsensorclosed'] }}"
	
	resp = make_response(render_template('ha_example.yaml', site_url_api=site_url_api, value_template=value_template, doorname=doorname))
	resp.mimetype = 'text/plain'
	return resp

"""
Supporting Functions
"""

# Attribution to Vladimir Ignatyev on Stack Overflow
# https://stackoverflow.com/questions/41969093/how-to-generate-passwords-in-python-2-and-python-3-securely
def gen_api_key(length, charset="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"):
    return "".join([secrets.choice(charset) for _ in range(0, length)])

def build_button_list():
	global settings
	global cmdsts

	errorlevel=0
	button_list = []
	for door in settings['doors']:
		# Create a unique keyname for the door structure in Redis
		keyname = 'doorobj:' + door['id']

		if(keyname.encode('UTF-8') in cmdsts.keys()):
			button_definition = {
				'id' : door['id'],
				'name' : door['name'], # Display Name
				'keyname' : keyname, # Redis keyname for HGET/HSET
				'status' : {},
				'command' : {}
			}

			for index in door['inpins']:
				sensor = cmdsts.hget(keyname, index)
				if (sensor != None): 
					button_definition['status'][index] = int(cmdsts.hget(keyname, index))
				else:
					errorlevel=1
					break
	
			for index in door['outpins']:
				button = cmdsts.hget(keyname, index)
				if (button != None):
					button_definition['command'][index] = int(cmdsts.hget(keyname, index))
				else:
					errorlevel=1
					break
			
			button_list.append(button_definition)

		else:
			errorlevel=1
			break

	return(button_list, errorlevel)

def available_gpios():
	global settings

	available_raspi_gpios = settings['raspi']['gpio_list'].copy()

	# Loop through door objects
	for object in settings['doors']:
		for pin in object['inpins']:
			if(object['inpins'][pin] > 1) and (object['inpins'][pin] < 28):
				available_raspi_gpios.remove(object['inpins'][pin])
		for pin in object['outpins']:
			if(object['outpins'][pin] > 1) and (object['outpins'][pin] < 28):
				available_raspi_gpios.remove(object['outpins'][pin])

	# Loop through door objects
	for object in settings['addons']:
		for pin in object['inpins']:
			if(object['inpins'][pin] > 1) and (object['inpins'][pin] < 28):
				available_raspi_gpios.remove(object['inpins'][pin])
		for pin in object['outpins']:
			if(object['outpins'][pin] > 1) and (object['outpins'][pin] < 28):
				available_raspi_gpios.remove(object['outpins'][pin])
	
	return (available_raspi_gpios)

def build_notify_forms():
	global settings
	
	notifyforms = {}
	
	for service in settings['notify']:
		id = service['id']
		if service['type'] == 'email': 
			notifyforms[id] = EmailForm()
			notifyforms[id].to_email.data = service['to_email']
			notifyforms[id].from_email.data = service['from_email']
			notifyforms[id].username.data = service['username']
			notifyforms[id].password.data = service['password']
			notifyforms[id].smtpserver.data = service['smtpserver']
			notifyforms[id].smtpport.data = service['smtpport']
			notifyforms[id].tls.data = service['tls']

		elif service['type'] == 'ifttt':
			notifyforms[id] = IftttForm()
			notifyforms[id].apikey.data = service['apikey']
			notifyforms[id].iftttevent.data = service['iftttevent']

		elif service['type'] == 'pushbullet':
			notifyforms[id] = PushbulletForm()
			notifyforms[id].apikey.data = service['apikey']

		elif service['type'] == 'pushover':
			notifyforms[id] = PushoverForm()
			notifyforms[id].apikey.data = service['apikey']
			notifyforms[id].userkeys.data = service['userkeys']

		elif service['type'] == 'proto':
			notifyforms[id] = ProtoNotifyForm()

		notifyforms[id].sname.data = service['name']
		notifyforms[id].id.data = service['id']
		notifyforms[id].ntype.data = service['type']
	
	return(notifyforms)

def build_door_form(door):
	global settings

	# Create DoorForm
	door_form = DoorForm()
	# Populate top level data
	door_form.dname.data = door['name']
	door_form.id.data = door['id']
	door_form.sensorlevel.data = door['sensorlevel']
	door_form.triggerlevel.data = door['triggerlevel']

	for _inpin in door['inpins']:
		temp_inpin_form = InPinFieldForm()
		temp_inpin_form.inpin = _inpin
		temp_inpin_form.gpio_pin = door['inpins'][_inpin]
		door_form.inpins.append_entry(temp_inpin_form)

	for _outpin in door['outpins']:
		temp_outpin_form = OutPinFieldForm()
		temp_outpin_form.outpin = _outpin
		temp_outpin_form.gpio_pin = door['outpins'][_outpin]
		door_form.outpins.append_entry(temp_outpin_form)
	# Done, break out of loop

	return(door_form)

def build_event_list(door):
	global settings

	event_list = []

	# First build notify services list of id : name
	notify_services = {}
	for notify_service in settings['notify']:
		notify_services[notify_service['id']] = notify_service['name']

	# Get door_id['notify_events'] as dictionary
	events = door['notify_events']
	door_name = door['name']

	for event in events:
		temp_event = {}
		temp_event['name'] = event
		temp_event['title'] = events[event]['title']
		temp_event['logtype'] = events[event]['logtype']
		temp_event['id'] = door['id']
		event_list.append(temp_event)

	return(event_list)

def build_event_form(door_id, event_type):
	global settings
	global temp_door

	# First build notify services list of id : name
	notify_services = {}
	for notify_service in settings['notify']:
		notify_services[notify_service['id']] = notify_service['name']

	# Get door_id['notify_events'] as dictionary
	events = []
	door_name = ''
	if door_id == 'new':
		events = temp_door['notify_events']
		door_name = temp_door['name']
		door = temp_door
	else: 
		for door_obj in settings['doors']:
			if door_obj['id'] == door_id:
				events = door_obj['notify_events']
				door_name = door_obj['name']
				door = door_obj
				break

	event_form = EventForm()
	for event in events:
		if event == event_type:
			selected = []
			choices = []
			for service_id in notify_services:
				if service_id in door['notify_events'][event]['notifylist']:
					selected.append(service_id)
				choices.append((service_id, notify_services[service_id]))
			event_form.notifylist.choices = choices
			event_form.notifylist.default = selected
			event_form.process()

			event_form.id.data = door_id
			event_form.event_type.data = event
			event_form.title.data = door['notify_events'][event]['title']
			event_form.message.data = door['notify_events'][event]['message']
			event_form.sensor.data = door['notify_events'][event]['sensor']
			event_form.sensorlevel.data = 'True' if door['notify_events'][event]['sensorlevel'] else 'False'
			event_form.time.data = door['notify_events'][event]['time']
			event_form.starttimer.data = door['notify_events'][event]['starttimer']
			event_form.timerendevent.data = door['notify_events'][event]['timerendevent']
			event_form.remindevent.data = door['notify_events'][event]['remindevent']
			event_form.logtype.data = door['notify_events'][event]['logtype']

			break  # Break out of upper loop if door_id matched
		
	return(event_form)

if __name__ == '__main__':
	if is_raspberry_pi():
		app.run(host='0.0.0.0')  # Production Mode if on Raspberry Pi
	else:
		app.run(host='0.0.0.0', debug=True)  # Debug Mode on non-Raspberry Pi / Development System