#!/usr/bin/python
# -*- coding: utf-8 -*-

from shinken.objects.item import Item, Items
from shinken.property import IntegerProp, BoolProp, StringProp

class Pots(Item):
    id = 1  # zero is always special in database, so we do not take risk here
    my_type = 'pots'

    properties = Item.properties.copy()
    properties.update({
        'id': IntegerProp(fill_brok=['full_status']),
        'cpeid': IntegerProp(fill_brok=['full_status']),
        'order': IntegerProp(fill_brok=['full_status']),
        'cli': StringProp(fill_brok=['full_status']),
        'contextid': IntegerProp(fill_brok=['full_status']),
        'contextname': StringProp(fill_brok=['full_status']),
        'username': StringProp(fill_brok=['full_status'], default=None),
        'password': StringProp(fill_brok=['full_status'], default=None),
    })

    running_properties = Item.running_properties.copy()
    running_properties.update({
        'cpe': StringProp(default=None, fill_brok=['full_status']),
        'context': StringProp(default=None, fill_brok=['full_status']),
    })

    def __repr__(self):
        return '<pots#%s/>' % (self.id)

    def __str__(self):
        return '<cli#%s/>' % (self.cli)

class Potses(Items):
    name_property = 'id'
    inner_class = Pots

    def linkify(self, cpes):
        for pots in self:
            cpe = cpes.items[pots.cpeid]
            pots.cpe = cpe
            cpe.potses.append(pots)

    def find_by_id(self, id):
        return self.items.get(id, None)
