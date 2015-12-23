#!/usr/bin/python
# -*- coding: utf-8 -*-


def _itemid_callback(itemid):
    return itemid


def _itemdata_callback(itemdata, field):
    try:
      return itemdata[field]
    except:
      pass


def print_snmptable(snmp_client, mib, table, prefixlen=0, itemid_callback=None):
    print mib, table, prefixlen
    snmptable = snmp_client.snmptable(mib, table, prefixlen)
    if not snmptable:
        return
    do_print_snmptable(snmptable)


def do_print_snmptable(snmptable, itemid_callback=None):
    real_itemid_callback = itemid_callback if itemid_callback else _itemid_callback
    try:
      idW = max([len(real_itemid_callback(i)) for i,d in table]) + 1
    except:
      idW = 10
    print '-' * idW,

    snmptable_fields = snmptable[0][1].keys()
    fieldsW={}
    for field in snmptable_fields:
        width = len(field)
        for i,d in snmptable:
            internal_field = CamelCase2_(field)
            string_to_len = _itemdata_callback(d, internal_field) or '--'
            width = max([width, len(string_to_len)])
        width += 1
        fieldsW[field] = width
        print ('{0:>{width}s}'.format(field, width=width)),
    print

    for i,d in snmptable:
        print ('{0:>{width}s}'.format(real_itemid_callback(i), width=idW)),
        for field in snmptable_fields:
            print ('{0:>{width}s}'.format(_itemdata_callback(d, CamelCase2_(field)), width=fieldsW[field])),
        print


def print_snmplist(snmp_client, mib, table, prefixlen=0, itemid_callback=None):
    print mib, table, prefixlen
    snmptable = snmp_client.snmptable(mib, table, prefixlen)
    if not snmptable:
        return
    do_print_snmplist(snmptable, itemid_callback)


def do_print_snmplist(snmptable, itemid_callback=None):
    real_itemid_callback = itemid_callback if itemid_callback else _itemid_callback
    #width = max([len(field) for field in snmptable_fields]) + 3
    width = 25
    for itemid,itemdata in snmptable:
        print 'id:', real_itemid_callback(itemid)
        for field in itemdata.keys():
            print '  {0:{width}s}: {1:s}'.format(field, _itemdata_callback(itemdata, field), width=width)


def CamelCase2_(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
