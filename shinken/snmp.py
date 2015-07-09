#!/usr/bin/python
# -*- coding: utf-8 -*-

def zte_decode_optical_level(snmp_data_as_integer):
    return int((snmp_data_as_integer-15000)*2)
