#!/bin/sh

NOW=$(date +"%Y-%m-%d")
LOGFILE="/usr/local/bin/garage-zero-v2/logs/backuplog-$NOW.log"

mv /usr/local/bin/garage-zero-v2/events.log $LOGFILE
touch /usr/local/bin/garage-zero-v2/events.log
