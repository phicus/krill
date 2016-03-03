#!/usr/bin/python
# -*- coding: utf-8 -*-

from pysnmp.proto import errind

from shinken.log import logger

from client import SnmpRuntimeError

def get_snmp_objects(snmp_client, cls, subindex=None):

    def _get_walk_data_up_to_len(up_to_len, oid, **kwargs):
        # logger.info("[PON] _get_walk_data_up_to_len0 %d/%s" % (up_to_len, symbol))

        walk_data_len = -100
        retries_count = 0
        errind_OidNotIncreasing = False

        MAX_RETRIES = 3
        DIFF_THRESHOLD = 10
        TIME_TO_WAIT_BETWEEN_RETRIES = 5

        while walk_data_len + DIFF_THRESHOLD < up_to_len and retries_count <= MAX_RETRIES and not errind_OidNotIncreasing:
            if retries_count > 0:
                logger.warning("[PON] _get_walk_data_up_to_len (%s) upto=%d, but only=%d (retries=%d)" % (symbol, up_to_len, walk_data_len, retries_count))
                time.sleep(TIME_TO_WAIT_BETWEEN_RETRIES)

            try:
                walk_data = snmp_client.walk(oid, subindex, **kwargs)
            except errind.OidNotIncreasing:
                # logger.info("[PON] get_snmp_objects errind.OidNotIncreasing %s" % (oid))
                errind_OidNotIncreasing = True
                walk_data = []
            except SnmpRuntimeError, exc:
                print 'SnmpRuntimeError', exc
                walk_data = []

            walk_data_len = len(walk_data)
            retries_count += 1

        if walk_data_len + DIFF_THRESHOLD < up_to_len and not errind_OidNotIncreasing:
            logger.warning("[PON] _get_walk_data_up_to_len (%s) upto=%d, but only=%d -> SKIP" % (symbol, up_to_len, walk_data_len))
        return walk_data


    snmp_objects = []
    cls_properties = getattr(cls, 'properties')
    data_len = 0
    for field, field_def in cls_properties.iteritems():

        if len(field_def) == 3:
            oid, _, kwargs = field_def
        else:
            oid, _ = field_def
            kwargs = {}

        if not oid:
            continue

        walk_data = _get_walk_data_up_to_len(len(snmp_objects), oid, **kwargs)

        for object_index, object_data in walk_data:
            # logger.info("[PON] get_snmp_objects object_index/object_data %r/%r" % (object_index, object_data))
            current_index = None
            current_subindex = None
            for index, _ in snmp_objects:
                if object_index == index:
                    current_index = index
                elif object_index[0:len(index)] == index:
                    current_index = index
                    current_subindex = object_index[len(index):]

            #logger.info("[PON]get_snmp_objects current_index/current_subindex %r/%r" % (current_index, current_subindex))
            if current_index:
                o, = [o for i,o in snmp_objects if i == current_index]
            else:
                o = cls()
                snmp_objects.append((object_index, o))

            # logger.info("[PON]get_snmp_objects->setattr %s/%s/%s/%s/%s -> %d" % (field, object_data[symbol], object_index, current_index, current_subindex, id(o)))
            o.setattr(field, object_data.itervalues().next(), current_subindex)

    return snmp_objects


class SnmpObject(object):
    properties = {}
    perf_data_properties = []

    def __getattribute__(self, name):
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            try:
                return self.data[name]
            except KeyError:
                return None


    def __getstate__(self):
        return self.__dict__


    def __setstate__(self, state):
        self.__dict__ = state


    def setattr(self, field, data, subindex=None):
        if subindex:
            data_to_assign = self.getattr(field)
            if not data_to_assign:
                data_to_assign = {}
            data_to_assign['%s' % (','.join(subindex))] = data
        else:
            data_to_assign = data

        #setattr(self, field, data_to_assign)
        self.data[field] = data_to_assign


    def getattr(self, field):
        return self.data.get(field)


    @property
    def perf_data(self):
        cls = self.__class__

        ret = {}
        for prop in cls.perf_data_properties:
            data = getattr(self, prop, None)
            f = getattr(self, 'perf_data_%s' % prop, None)
            if f and callable(f):
                ret[prop] = f()
            else:
                ret[prop] = data

        ret.update(self.additional_perf_data())
        return ret

    def additional_perf_data(self):
        return {}


class WalkObject(SnmpObject):

    def __init__(self):
        self.data = {}
        for prop_key,prop_definition in self.properties.iteritems():
            default_value_def = prop_definition[1]
            if isinstance(default_value_def, dict):
                #setattr(self, prop_key, dict().copy())
                self.setattr(prop_key, dict().copy())
            else:
                #setattr(self, prop_key, default_value_def)
                self.setattr(prop_key, default_value_def)


class GetObject(SnmpObject):

    def __init__(self, community, ip, port=161):
        self.community = community
        self.ip = ip
        self.port = port

        self.data = {}
        for prop_key in self.properties.keys():
            self.setattr(prop_key, None)
