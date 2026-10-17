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
	# Order oldest to newest so the last lines are the most recent events
	log_files = []
	for i in range(3, 0, -1):  # Check for .3, .2, .1 backup files
		backup_file = f'logs/events.log.{i}'
		if os.path.exists(backup_file):
			log_files.append(backup_file)
	log_files.append('logs/events.log')

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
		if ((num_events == 0) or (num_events >= event_line_length)):
			# Get all events in file
			for x in range(event_line_length):
				event_list.append(event_lines[x].split(" ",3))
			num_events = event_line_length
		else:
			# Get just the last num_events in list
			for x in range(event_line_length-num_events, event_line_length):
				event_list.append(event_lines[x].split(" ",3))

		if (twentyfourhtime == False): 
			for x in range(num_events):
				convertedtime = datetime.datetime.strptime(event_list[x][1], "%H:%M:%S")  # Get 24 hour time from log
				event_list[x][1] = convertedtime.strftime("%I:%M:%S %p") # Convert to 12 hour time for display

	return(event_list, num_events)

LOG_FILES = {'events': 'logs/events.log', 'health': 'logs/health.log'}

def log_exists(logname):
	"""Return True if the named log ('events' or 'health') exists on disk."""
	return os.path.exists(LOG_FILES.get(logname, ''))

def read_log_page(logname='events', page=1, per_page=50, twentyfourhtime=True):
	# *****************************************
	# Function: read_log_page
	# Output: event_list (oldest to newest within the page), total_events, page, total_pages
	# Description: Page 1 is the most recent set of records. Includes rotated backups.
	# *****************************************
	base = LOG_FILES.get(logname, LOG_FILES['events'])
	files = [f'{base}.{i}' for i in range(3, 0, -1)] + [base]
	lines = []
	for path in files:
		if os.path.exists(path):
			try:
				with open(path, 'r', encoding='utf-8', errors='replace') as f:
					lines.extend(l for l in f.read().splitlines() if l.strip())
			except (IOError, OSError):
				pass

	total = len(lines)
	per_page = max(1, per_page)
	total_pages = max(1, -(-total // per_page))
	page = min(max(1, page), total_pages)

	end = total - (page - 1) * per_page
	start = max(0, end - per_page)

	event_list = []
	for line in lines[start:end]:
		parts = line.split(" ", 3)
		parts += [''] * (4 - len(parts))
		if not twentyfourhtime:
			try:
				parts[1] = datetime.datetime.strptime(parts[1], "%H:%M:%S").strftime("%I:%M:%S %p")
			except ValueError:
				pass
		event_list.append(parts)

	return event_list, total, page, total_pages

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

def _setup_health_logger():
	"""Initialize a separate rotating logger for health/debug messages."""
	logger = logging.getLogger('garage_zero_health')
	logger.setLevel(logging.INFO)

	os.makedirs('logs', exist_ok=True)

	handler = RotatingFileHandler(
		'logs/health.log',
		maxBytes=500000,   # 500 KB
		backupCount=3,
		encoding='utf-8'
	)
	formatter = logging.Formatter('%(asctime)s %(message)s',
								  datefmt='%Y-%m-%d %H:%M:%S')
	handler.setFormatter(formatter)
	logger.addHandler(handler)
	return logger

_health_logger = _setup_health_logger()

def write_health_log(event, logtype='HEALTH'):
	"""Write a message to the separate health/debug log (logs/health.log)."""
	message = '[' + logtype.upper() + '] ' + event
	_health_logger.info(message)
