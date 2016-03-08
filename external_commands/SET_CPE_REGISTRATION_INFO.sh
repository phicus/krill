#!/bin/sh
#
# This is a sample shell script showing how you can submit the
# CHANGE_CONTACT_HOST_NOTIFICATION_TIMEPERIOD command to Nagios.
# Adjust variables to fit your environment as necessary.

now=$(date +%s)
commandfile='/var/lib/shinken/nagios.cmd'

printf "[%lu] SET_CPE_REGISTRATION_INFO;2;olt;3:7;1;{'up': 456}" $now > $commandfile

printf "[%lu] PROCESS_HOST_CHECK_RESULT;cpe10;0;demo" $now > $commandfile


printf "[%lu] PROCESS_SERVICE_CHECK_RESULT;localhost;memory;0;MEMORY" $now > $commandfile

printf "[%lu] PROCESS_HOST_CHECK_RESULT;cpe89;0;tflk" $(date +%s) > $commandfile



/opt/fos/bin/push_dhcp_lease --transaction=commit --lease-time=3600 --leased-address=10.142.0.44 --hardware=30:c:23:be:3b:3b --host-name=atadevice30:0c:23:be:3b:3b --circuit-id=pon/422/OLTZTE/1/1/2/5/6/1 --remote-id=5a544547c15383f2

