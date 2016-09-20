#/usr/bin/python
# -*- coding: utf-8 -*-

import time

from pysnmp.proto import errind

from shinken.log import logger

from client import SnmpRuntimeError


def get_snmp_object(snmp_client, cls, subindex):

    # print 'get_snmp_object1'
    snmp_object = cls()
    cls_properties = getattr(cls, 'properties')
    try:
        for field, field_property in cls_properties.iteritems():
            snmp_client_method = getattr(snmp_client, field_property.method)
            # print 'snmp_client_method', field, snmp_client_method, field_property.oid, subindex
            if field_property.method == 'get':
                try:
                    get_data = snmp_client.get(
                        oid=field_property.oid,
                        subindex=subindex,
                        timeout=getattr(cls, 'timeout', 3),
                        retries=getattr(cls, 'retries', 1),
                    )
                    # print 'snmp_client_method field, get_data', field, get_data
                    snmp_object.setattr(field, get_data)
                except Exception, exc:
                    logger.info("[SNMP] get_snmp_object get client=%s field=%s Exception=%s", snmp_client, field, exc)
            else:
                try:
                    walk_data_list = snmp_client.walk(
                        oid=field_property.oid,
                        subindex=subindex,
                        timeout=getattr(cls, 'timeout', 3),
                        retries=getattr(cls, 'retries', 1),
                    )
                    # print 'snmp_client_method walk_data_list', field, walk_data_list
                    snmp_object_data = []
                    for walk_index, walk_data in walk_data_list:
                        snmp_object_data.append((tuple(list(walk_index)[1:]), walk_data.itervalues().next()))
                    snmp_object.setattr(field, snmp_object_data)
                except Exception, exc:
                    logger.info("[SNMP] get_snmp_object walk field=%s Exception=%s", field, exc)
    except SnmpRuntimeError, exc:
        # print 'SnmpRuntimeError', exc
        pass
    return snmp_object


def get_snmp_objects(snmp_client, cls, subindex=None):

    def _get_walk_data_up_to_len(up_to_len, oid, timeout, retries, **kwargs):
        # logger.info("[SNMP] _get_walk_data_up_to_len0 %d/%s" % (up_to_len, oid))

        walk_data_len = -100
        retries_count = 0
        errind_OidNotIncreasing = False

        MAX_RETRIES = 2
        DIFF_THRESHOLD = 10
        TIME_TO_WAIT_BETWEEN_RETRIES = 5

        while walk_data_len + DIFF_THRESHOLD < up_to_len and retries_count <= MAX_RETRIES and not errind_OidNotIncreasing:
            if retries_count > 0:
                logger.warning("[SNMP] _get_walk_data_up_to_len (%s) upto=%d, but only=%d (retries=%d)" % (oid, up_to_len, walk_data_len, retries_count))
                time.sleep(TIME_TO_WAIT_BETWEEN_RETRIES)

            try:
                # print 'TFLK-WALK1', oid, subindex, timeout, retries, kwargs, '...'
                walk_data = snmp_client.walk(oid, subindex, timeout, retries, **kwargs)
                # print 'TFLK-WALK2 ...', len(walk_data)
            except errind.OidNotIncreasing:
                errind_OidNotIncreasing = True
                walk_data = []
            except Exception, exc:
                print 'Exception', exc
                logger.warning("[SNMP] _get_walk_data_up_to_len Exception: %s", exc)
                raise exc
            # except SnmpRuntimeError, exc:
            #     walk_data = []

            walk_data_len = len(walk_data)
            retries_count += 1

        if walk_data_len + DIFF_THRESHOLD < up_to_len and not errind_OidNotIncreasing:
            logger.warning("[SNMP] _get_walk_data_up_to_len (%s) upto=%d, but only=%d -> SKIP" % (oid, up_to_len, walk_data_len))
        return walk_data


    snmp_objects = []
    cls_properties = getattr(cls, 'properties')
    data_len = 0
    for field, field_property in cls_properties.iteritems():
        # logger.info("[SNMP] field----->%s", field)
        if not field_property.oid:
            continue

        try:
            timeout = getattr(cls, 'timeout', 3)
            retries = getattr(cls, 'retries', 1)
            walk_data_list = _get_walk_data_up_to_len(len(snmp_objects), field_property.oid, timeout, retries, **field_property.kwargs)

            for walk_index, walk_data in walk_data_list:

                current_index = None
                current_subindex = None
                for index, _ in snmp_objects:
                    if walk_index == index:
                        current_index = index
                    elif walk_index[0:len(index)] == index:
                        current_index = index
                        current_subindex = walk_index[len(index):]

                if current_index:
                    o, = [o for i,o in snmp_objects if i == current_index]
                else:
                    o = cls()
                    snmp_objects.append((walk_index, o))

                data_to_set = walk_data.itervalues().next()
                if field_property.method == 'get':
                    o.setattr(field, data_to_set)
                else:
                    o.appendattr(field, (tuple(current_subindex), data_to_set))

        except SnmpRuntimeError, exc:
            # print 'SnmpRuntimeError', exc
            pass


    return snmp_objects


class SnmpObject(object):

    properties = {}
    perf_data_properties = []
    perf_properties = []

    timeout = 3
    retries = 1


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
            # print 'setattr1', field, data, subindex, data_to_assign
            data_to_assign['%s' % (','.join(subindex))] = data
        else:
            # print 'setattr2', field, data
            data_to_assign = data

        #setattr(self, field, data_to_assign)
        self.data[field] = data_to_assign


    def appendattr(self, field, data):
        # print 'appendattr', self, field, data
        self.data[field].append(data)


    def getattr(self, field, default=None):
        return self.data.get(field, default)


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


    def new_perf(self, perf, value):
        if perf not in self.perf_fields:
            self.perf_fields.append(perf)
        self.setattr(perf, value)


    @property
    def perfs(self):
        ret = {}
        for prop in self.perf_fields:
            ret[prop] = self.getattr(prop)
        return ret


class WalkObject(SnmpObject):

    def __init__(self):
        self.perf_fields = []

        self.data = dict().copy()
        for field, field_property in self.properties.iteritems():
            if field_property.method == 'get':
                
                if isinstance(field_property.default, dict):
                    self.setattr(field, field_property.default.copy())
                else:
                    self.setattr(field, field_property.default)
            else:
                self.setattr(field, list())

            # if isinstance(prop_definition.default, dict):
            #     #setattr(self, prop_key, dict().copy())
            #     self.setattr(prop_key, dict().copy())
            # else:
            #     self.setattr(prop_key, prop_definition.default)


class GetObject(SnmpObject):

    def __init__(self, community, ip, port=161):
        self.perf_fields = []

        self.community = community
        self.ip = ip
        self.port = port

        self.data = dict().copy()
        for prop_key in self.properties.keys():
            self.setattr(prop_key, None)


    def consolidate(self):
        pass
