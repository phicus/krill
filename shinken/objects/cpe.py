#!/usr/bin/python
# -*- coding: utf-8 -*-

from shinken.objects.item import Item, Items
from shinken.property import IntegerProp, BoolProp, StringProp, ListProp

from shinken.log import logger

class Cpe(Item):
    id = 1  # zero is always special in database, so we do not take risk here
    my_type = 'cpe'

    properties = Item.properties.copy()
    properties.update({
        'id': IntegerProp(fill_brok=['full_status']),
        'customerid': IntegerProp(fill_brok=['full_status']),
        'sn': StringProp(fill_brok=['full_status']),
        'mac': StringProp(fill_brok=['full_status']),
        'mtamac': StringProp(fill_brok=['full_status']),
        'model': StringProp(fill_brok=['full_status']),
        'profileid': IntegerProp(fill_brok=['full_status']),
        'access': BoolProp(fill_brok=['full_status']),

        'state': StringProp(default='PENDING', fill_brok=['full_status'], retention=True),
        'comments': StringProp(default=[], fill_brok=['full_status'], retention=True),
        'actions': StringProp(default=[]), # put here checks and notif raised
        'broks': StringProp(default=[]), # and here broks raised
    })

    running_properties = Item.running_properties.copy()
    running_properties.update({
        'customer': StringProp(default=None, fill_brok=['full_status']),
        'profile': StringProp(default=None, fill_brok=['full_status']),
        'potses': ListProp(fill_brok=['full_status'], default=None),
    })

    def __init__(self, params={}):
        self.id = None
        self.customerid = None
        self.sn = None
        self.mac = None
        self.mtamac = None
        self.model = None
        self.profileid = None
        self.access = None
        self.potses = []

        self.state = 'PENDING'
        for key in params:
            if key in ['id', 'customerid', 'sn', 'mac', 'mtamac', 'model', 'profileid', 'access']:
                setattr(self, key, self.properties[key].pythonize(params[key]))

    def __repr__(self):
        return '<cpe#%d/>' % (self.id)

    def __str__(self):
        if self.mac:
            return 'mac%s' % self.mac
        elif self.sn:
            return 'sn%s' % self.sn
        else:
            return 'id%d' % self.id

    def set_state(self, state):
        self.state = str(state)
        #comment_type = 3 #1:host 2:service?
        #c = Comment(self, persistent, author, comment, comment_type, 4, 0, False, 0)
        #self.add_comment(c)
        self.broks.append(self.get_update_status_brok())



class Cpes(Items):
    name_property = 'id'
    inner_class = Cpe

    def linkify(self, customers, cpe_profiles):
        for cpe in self:
            customer = customers.items[cpe.customerid]
            cpe.customer = customer
            customer.add_cpe_link(cpe)

            cpe_profile = cpe_profiles.items[cpe.profileid]
            cpe.profile = cpe_profile
            cpe_profile.add_cpe_link(cpe)

    def find_by_id(self, id):
        return self.items.get(int(id), None)
