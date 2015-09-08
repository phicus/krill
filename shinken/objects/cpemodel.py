#!/usr/bin/python
# -*- coding: utf-8 -*-

from shinken.objects.item import Item, Items
from shinken.property import IntegerProp, BoolProp, StringProp, ListProp

class CpeModel(Item):
    id = 1  # zero is always special in database, so we do not take risk here
    my_type = 'cpemodel'

    properties = Item.properties.copy()
    properties.update({
        'id': StringProp(fill_brok=['full_status'], default=0),
        'label': StringProp(fill_brok=['full_status'], default='model'),
        'tech': StringProp(fill_brok=['full_status'], default='xxx'),
        'pots': IntegerProp(fill_brok=['full_status'], default=0),
        'is_router': BoolProp(fill_brok=['full_status'], default=False),
        'tr069': BoolProp(fill_brok=['full_status'], default=False),
    )

    running_properties = Item.running_properties.copy()
    running_properties.update({
        'cpes': StringProp(default=[], fill_brok=['full_status']),
    })

    def __repr__(self):
        return '<cpemodel#%s/>' % self.id

    def __str__(self):
        return self.id

    def add_cpe_link(self, cpe):
        self.cpes.append(cpe)

    @property
    def type(self):
        return 'router' if self.is_router else 'bridge'


class CpeModels(Items):
    name_property = 'id'
    inner_class = CpeModel

    def find_by_id(self, id):
        return self.items.get(id, None)
