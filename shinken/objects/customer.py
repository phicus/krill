#!/usr/bin/python
# -*- coding: utf-8 -*-

from shinken.objects.item import Item, Items
from shinken.property import IntegerProp, StringProp
from shinken.log import logger

from shinken.util import safe_print

class Customer(Item):
    id = 1  # zero is always special in database, so we do not take risk here
    my_type = 'customer'

    properties = Item.properties.copy()
    properties.update({
        'id': IntegerProp(),
        'name': StringProp(fill_brok=['full_status']),
        'surname': StringProp(fill_brok=['full_status']),
        'customerid': IntegerProp(fill_brok=['full_status']),
        'customer_label': StringProp(fill_brok=['full_status']),
        'comment': StringProp(fill_brok=['full_status']),
        'created': StringProp(fill_brok=['full_status']),
        'updated': StringProp(fill_brok=['full_status']),
    })

    running_properties = Item.running_properties.copy()
    running_properties.update({
        'cpes': StringProp(default=[], fill_brok=['full_status']),
    })

    def __init__(self, params={}):
        self.id = None
        self.name = None
        self.surname = None
        self.comment = None
        self.created = None
        self.updated = None
        self.cpes = []
        for key in params:
            if key in ['id', 'name', 'surname', 'comment', 'created', 'updated']:
                safe_print("TFLK Customer %s -> %s" % (key, self.properties[key].pythonize(params[key])))
                setattr(self, key, self.properties[key].pythonize(params[key]))
            elif key == 'cpes':
                self.cpes = params[key]
        self.set_additional_attributes()


    def set_additional_attributes(self):
        self.customerid = self.id
        self.customer_label = unicode(self)

    def get_name(self):
        return self.name

    def get_full_name(self):
        return self.customer_label

    def __repr__(self):
        return u'<customer name=%s surname=%s />' % (self.name, self.surname)

    __str__ = __repr__

    def add_cpe_link(self, cpe):
        self.cpes.append(cpe)

class Customers(Items):
    name_property = 'id'
    inner_class = Customer

    def find_by_id(self, id):
        logger.debug("TFLK %s", self.items)
        return self.items.get(id, None)
