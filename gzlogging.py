import datetime
import os

def read_log(num_events=0, twentyfourhtime=True):
	# *****************************************
	# Function: ReadLog
	# Input: none
	# Output: event_list, num_events
	# Description: Read event.log and populate
	#  an array of events.
	# *****************************************

	# Read all lines of events.log into an list(array)
	try:
		with open('events.log') as event_file:
			event_lines = event_file.readlines()
			event_file.close()
	# If file not found error, then create events.log file
	except(IOError, OSError):
		event_file = open('events.log', "w")
		event_file.close()
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
	# Description: Write event to event.log
	#  Event should be a string.
	# *****************************************
	now = str(datetime.datetime.now())
	now = now[0:19] # Truncate the microseconds

	logfile = open("events.log", "a")
	output = now + ' ' + '[' + logtype.upper() + '] ' + event + '\n'
	logfile.write(output)
	logfile.close()
