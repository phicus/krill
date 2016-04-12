#!/usr/bin/env python

# none_object = object()

class Property(object):
    """
    Baseclass of all snmp properties.
    """

    def __init__(self, oid=None, default=None, method='get', kwargs={}):
        self.oid = oid
        self.default = default
        self.method = method
        self.kwargs = kwargs
