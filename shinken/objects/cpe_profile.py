#!/usr/bin/python
# -*- coding: utf-8 -*-

from shinken.objects.item import Item, Items
from shinken.property import IntegerProp, BoolProp, StringProp, ListProp

class CpeProfile(Item):
    id = 1  # zero is always special in database, so we do not take risk here
    my_type = 'cpe_profile'

    properties = Item.properties.copy()
    properties.update({
        'id': IntegerProp(fill_brok=['full_status']),
        'name': StringProp(fill_brok=['full_status']),
        'tech': StringProp(fill_brok=['full_status']),
    })

    running_properties = Item.running_properties.copy()
    running_properties.update({
        'cpes': StringProp(default=[], fill_brok=['full_status']),
    })

    def __init__(self, params={}):
        self.id = None
        self.name = None
        self.cpes = []
        for key in params:
            if key in ['id', 'name', 'tech']:
                setattr(self, key, self.properties[key].pythonize(params[key]))

    def __repr__(self):
        return '<cpe_profile#%d/>' % (self.id)

    def __str__(self):
        return self.name

    def add_cpe_link(self, cpe):
        self.cpes.append(cpe)


class CpeProfiles(Items):
    name_property = 'id'
    inner_class = CpeProfile

    def find_by_id(self, id):
        return self.items.get(id, None)
