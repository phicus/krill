#!/usr/bin/python
# -*- coding: utf-8 -*-

from shinken.objects.item import Item, Items
from shinken.property import IntegerProp, BoolProp, StringProp
from shinken.log import logger

class Contract(Item):
    id = 1  # zero is always special in database, so we do not take risk here
    my_type = 'contract'

    properties = Item.properties.copy()
    properties.update({
        #'id': IntegerProp(fill_brok=['full_status']),
        'id': IntegerProp(fill_brok=['full_status']),
        'access': BoolProp(fill_brok=['full_status']),
        'comment': StringProp(fill_brok=['full_status']),
        'created': StringProp(fill_brok=['full_status']),
        'updated': StringProp(fill_brok=['full_status']),
    })
    running_properties = Item.running_properties.copy()
    running_properties.update({
        'customer': StringProp(default=None, fill_brok=['full_status']),
        'customerid': IntegerProp(fill_brok=['full_status']),
        'customer_label': StringProp(fill_brok=['full_status']),
        'cpe': StringProp(fill_brok=['full_status']),
    })

    def __repr__(self):
        return '<th#%d/>' % (self.id)

    def __str__(self):
        return '<th#%d/>' % (self.id)

    def get_full_name(self):
        return "%s/%s" % (self.customer.customer_label, self.id)

class Contracts(Items):
    name_property = 'id'
    inner_class = Contract

    def linkify(self, customers):
        for contract in self:
            customer = customers.items[contract.customerid]
            contract.customer = customer
            contract.customer_label = customer.customer_label
            customer.add_contract_link(contract)

    def find_by_id(self, id):
        logger.debug("TFLK %s", self.items)
        return self.items.get(id, None)

