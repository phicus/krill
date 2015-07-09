#!/bin/sh
#
# This is a sample shell script showing how you can submit the
# CHANGE_CONTACT_HOST_NOTIFICATION_TIMEPERIOD command to Nagios.
# Adjust variables to fit your environment as necessary.

now=$(date +%s)
commandfile='/var/lib/shinken/nagios.cmd'

printf "[%lu] SET_CPE_REGISTRATION_INFO;2;olt;3:7;1;{'up': 456}" $now > $commandfile
