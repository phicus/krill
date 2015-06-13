#!/usr/bin/python
# -*- coding: utf-8 -*-

from shinken.objects.item import Item, Items
from shinken.property import IntegerProp, BoolProp, StringProp, ListProp

class Cpe(Item):
    id = 1  # zero is always special in database, so we do not take risk here
    my_type = 'cpe'

    properties = Item.properties.copy()
    properties.update({
        'id': IntegerProp(fill_brok=['full_status']),
        'contractid': IntegerProp(fill_brok=['full_status']),
        'sn': StringProp(fill_brok=['full_status']),
        'mac': StringProp(fill_brok=['full_status']),
        'mtamac': StringProp(fill_brok=['full_status']),
        'model': StringProp(fill_brok=['full_status']),
        'profileid': IntegerProp(fill_brok=['full_status']),
        'access': BoolProp(fill_brok=['full_status']),
    })

    running_properties = Item.running_properties.copy()
    running_properties.update({
        'contract': StringProp(default=None, fill_brok=['full_status']),
        'profile': StringProp(default=None, fill_brok=['full_status']),
        'potses': ListProp(fill_brok=['full_status'], default=None),
    })

    def __init__(self, params={}):
        self.id = None
        self.contractid = None
        self.sn = None
        self.mac = None
        self.mtamac = None
        self.model = None
        self.profileid = None
        self.access = None
        self.potses = []
        for key in params:
            if key in ['id', 'contractid', 'sn', 'mac', 'mtamac', 'model', 'profileid', 'access']:
                setattr(self, key, self.properties[key].pythonize(params[key]))

    def __repr__(self):
        return '<cpe#%d/>' % (self.id)

    def __str__(self):
        return 'mac%s' % self.mac

class Cpes(Items):
    name_property = 'id'
    inner_class = Cpe

    def linkify(self, contracts):
        for cpe in self:
            contract = contracts.items[cpe.contractid]
            cpe.contract = contract
            contract.cpe = cpe

    def find_by_id(self, id):
        return self.items.get(id, None)
