import datetime
import os
import logging
from logging.handlers import RotatingFileHandler

# Set up rotating file handler
# Max file size: 500KB, Keep 3 backup files (events.log.1, events.log.2, events.log.3)
def _setup_logger():
	"""Initialize the rotating logger for event logging"""
	logger = logging.getLogger('garage_zero_events')
	logger.setLevel(logging.INFO)
	
	# Ensure logs directory exists
	os.makedirs('logs', exist_ok=True)
	
	# Create rotating file handler
	# maxBytes=500000 is 500KB, backupCount=3 keeps 3 backup files
	handler = RotatingFileHandler(
		'logs/events.log',
		maxBytes=500000,  # 500KB
		backupCount=3,
		encoding='utf-8'
	)
	
	# Set format to match the existing log format: "YYYY-MM-DD HH:MM:SS message"
	# Note: logtype will be included in the message itself
	formatter = logging.Formatter('%(asctime)s %(message)s', 
								  datefmt='%Y-%m-%d %H:%M:%S')
	handler.setFormatter(formatter)
	
	logger.addHandler(handler)
	return logger

# Initialize the logger at module level
_event_logger = _setup_logger()

def read_log(num_events=0, twentyfourhtime=True):
	# *****************************************
	# Function: ReadLog
	# Input: num_events (int), twentyfourhtime (bool)
	# Output: event_list, num_events
	# Description: Read event.log and rotated backup files and populate
	#  an array of events. Reads from events.log and events.log.1, .2, .3 if needed.
	# *****************************************

	# Collect all available log files in order (newest to oldest)
	log_files = ['logs/events.log']
	for i in range(1, 4):  # Check for .1, .2, .3 backup files
		backup_file = f'logs/events.log.{i}'
		if os.path.exists(backup_file):
			log_files.append(backup_file)

	# Read all lines from all log files
	event_lines = []
	try:
		for log_file in log_files:
			if os.path.exists(log_file):
				with open(log_file, 'r', encoding='utf-8') as event_file:
					event_lines.extend(event_file.readlines())
	# If file not found error, then create events.log file
	except(IOError, OSError):
		os.makedirs('logs', exist_ok=True)
		with open('logs/events.log', 'w') as event_file:
			pass
		event_lines = []

	# Initialize event_list list
	event_list = []
	event_line_length = len(event_lines)

	# Check if there are no events in the list
	if (event_line_length == 0):
		num_events = 0
	else: 
		if ((num_events == 0) or (num_events > event_line_length)):
			# Get all events in file
			for x in range(event_line_length):
				event_list.append(event_lines[x].split(" ",3))
			num_events = event_line_length
		elif (num_events < event_line_length): 
			# Get just the last num_events in list
			for x in range(event_line_length-num_events, event_line_length):
				event_list.append(event_lines[x].split(" ",3))

		if (twentyfourhtime == False): 
			for x in range(num_events):
				convertedtime = datetime.datetime.strptime(event_list[x][1], "%H:%M:%S")  # Get 24 hour time from log
				event_list[x][1] = convertedtime.strftime("%I:%M:%S %p") # Convert to 12 hour time for display

	return(event_list, num_events)

def write_log(event, logtype='NONE'):
	# *****************************************
	# Function: WriteLog
	# Input: str event
	# Description: Write event to event.log using rotating file handler
	#  Event should be a string.
	#  Logs automatically rotate when reaching 500KB, keeping 3 backup files
	# *****************************************
	# Format message with logtype prefix to maintain original format
	message = '[' + logtype.upper() + '] ' + event
	_event_logger.info(message)
