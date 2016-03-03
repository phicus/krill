#!/usr/bin/python
# -*- coding: utf-8 -*-

import socket

from pysnmp.entity import engine, config
from pysnmp.carrier.asynsock.dgram import udp
from pysnmp.smi import builder, view
import pysnmp.entity.rfc3413.oneliner.cmdgen as cmdgen
from pysnmp.proto import errind

import utils

from shinken.log import logger


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


class SnmpClient(object):
    def __init__(self, host, port, community, mibs=[], mibSources=[]):
        self.host = host
        self.port = port
        self.community = community
        self.mibs = mibs
        self.mibSources = mibSources

        self._snmpEngine = engine.SnmpEngine()

        ## SecurityName <-> CommunityName mapping
        config.addV1System(self._snmpEngine, 'my-area', self.community)
        
        ## Specify security settings per SecurityName (SNMPv1 - 0, SNMPv2c - 1)
        config.addTargetParams(self._snmpEngine, 'my-creds', 'my-area', 'noAuthNoPriv', 1)
        
        #
        # Setup transport endpoint and bind it with security settings yielding
        # a target name (choose one entry depending of the transport needed).
        #
        
        # UDP/IPv4
        config.addSocketTransport(
            self._snmpEngine,
            udp.domainName,
            udp.UdpSocketTransport().openClientMode()
        )
        config.addTargetAddr(
            self._snmpEngine, 'my-router',
            udp.domainName, (host, port),
            'my-creds'
        )
        self.mibBuilder = builder.MibBuilder()

        extraMibSources = tuple([builder.DirMibSource(d) for d in self.mibSources])
        totalMibSources = self.mibBuilder.getMibSources() + extraMibSources
        self.mibBuilder.setMibSources( *totalMibSources )
        if self.mibs:
            self.mibBuilder.loadModules( *self.mibs )
        self.mibViewController = view.MibViewController(self.mibBuilder)

        V2C = 1
        self.auth_data = cmdgen.CommunityData('krill', self.community, V2C)
        self.udp_transport_target = cmdgen.UdpTransportTarget((self.host, self.port), timeout=20, retries=1)

    def __str__(self):
        return '%s:%s:%s' % (self.host, self.port, self.community)

    def set_named(self, mib, index, oid2value):
        varBinds = []
        for symbol,value in oid2value:
            mv_arg = (mib, symbol) + index
            mv = cmdgen.MibVariable(*mv_arg)
            mv.resolveWithMib(self.mibViewController)
            varBinds.append((mv, value))
        self.set(varBinds)

    def set(self, varBinds):
        cmdGen = cmdgen.CommandGenerator()

        #logger.info("SNMP::set (%r)" % (varBinds))
        errorIndication, errorStatus, errorIndex, varBinds = cmdGen.setCmd(
            self.auth_data,
            self.udp_transport_target,
            *varBinds,
            lookupNames=True
            #lookupValues=True,
        )
        error = self.handle_snmp_error(errorIndication, errorStatus, errorIndex, varBinds)
        if error:
            raise SnmpSetError(error['msg'])
        else:
            for oid, val in varBinds:
                pass
                #print('%s = %s' % (oid.prettyPrint(), val.prettyPrint()))

    def handle_snmp_error(self, errorIndication, errorStatus, errorIndex, varBinds):
        #logger.info("SNMP::handle_snmp_error (%r, %r, %r, %r)" % (errorIndication, errorStatus, errorIndex, varBinds))
        error = False
        if errorIndication:
            error = 'ei:%s' % errorIndication
        elif errorStatus and errorIndex:
            error = 'es:%s at ei:%s' % (errorStatus.prettyPrint(), varBinds[int(errorIndex)-1])
        elif errorStatus:
            error = 'es:%s' % errorStatus.prettyPrint()

        if error:
            return {
                'errorIndication':errorIndication,
                'errorStatus':errorStatus,
                'errorIndex':errorIndex,
                'msg':error,
            }


    def snmptable(self, mib, table, prefixlen=0):
        mibtable, = self.mibBuilder.importSymbols(mib, table)
        assert mibtable.__class__.__name__ == 'MibTable'

        try:
            tabledata = self._next_cmd_data(mibtable.getName())
        except RuntimeError, exc:
            print exc
            return []

        raw = []
        for oid, value in tabledata:
            mv = self.get_resolved_mib_variable(oid)
            modName, symName, indices = mv.getMibSymbol()
            symName = CamelCase2_(symName[prefixlen:])
            index_string = '.'.join([x.prettyPrint() for x in indices])
            index_string = tuple([x.prettyPrint() for x in indices])
            #print 'TFLK1', oid, modName, symName, indices, value, mv.getMibNode().syntax.__class__, index_string
            #print 'TFLK2 [%s]' % value
            try:
                value_string = mv.getMibNode().syntax.clone(value).prettyPrint()
                #value_string = str(value)
            except AttributeError:
                #print 'AttributeError!!', indices
                symName += '.'.join([x.prettyPrint() for x in indices])
                value_string = "ERROR: %s -> %s" % (index_string, value.prettyPrint())
                #print 'value_string: symName', symName, value_string, indices, index_string

            #value_string = value.prettyPrint()
            try:
                i = [i for i,d in raw].index(index_string)
                ti, td = raw[i]
                td[symName] = value_string
            except Exception as exc:
                raw.append((index_string, {symName: value_string}, ))
                #raw.append((indices, {symName: value_string}, ))

        # return [(ti, info_container.InfoContainer(td, return_none=True)) for ti, td in raw]
        return [(ti, AttrDict(td)) for ti, td in raw]

    def get_resolved_mib_variable(self, oid):
        mv = cmdgen.MibVariable(oid)
        mv.resolveWithMib(self.mibViewController)
        return mv

    def _next_cmd_data(self, oid, **kwargs):
        try:
            (errorIndication, errorStatus, errorIndex, varBinds) = \
                cmdgen.CommandGenerator().nextCmd(
                    self.auth_data, 
                    cmdgen.UdpTransportTarget((self.host, self.port)),
                    oid,
                    #lookupNames=True, lookupValues=True
                    #ignoreNonIncreasingOid=True,
                    **kwargs
                )
            error = self.handle_snmp_error(errorIndication, errorStatus, errorIndex, varBinds)
            if error:
                if str(error['errorIndication']) == "OIDs are not increasing":
                    r = errind.OidNotIncreasing(error['errorIndication'])
                else:
                    r = SnmpRuntimeError(error['errorIndication'])
                raise r
            else:
                return [x[0] for x in varBinds]
        except socket.error, exc:
            raise exceptions.SNMPExceptionError(exc)


    def walk(self, oid, subindex=None, **kwargs):
        if len(oid) == 2:
            mib, symbol = oid
            mibVariable = cmdgen.MibVariable(mib, symbol).loadMibs(mib)
            mibVariable.resolveWithMib(self.mibViewController)
            oid_to_walk = mibVariable.asTuple()
        else:
            oid_to_walk = oid

        if subindex:
            oid_to_walk += subindex

        data = self._next_cmd_data(oid_to_walk, **kwargs)

        raw = []
        for oid, value in data:
            # print 'walk oid', mib, symbol, oid, value
            mv = self.get_resolved_mib_variable(oid)
            modName, symName, indices = mv.getMibSymbol()
            index_string = tuple([x.prettyPrint() for x in indices])
            try:
                #print 'value %s %s %r --> %s' % (type(value), value, mv.getMibNode().syntax, mv.getMibNode().syntax.clone(value).prettyPrint())
                final_value = mv.getMibNode().syntax.clone(value).prettyPrint()
            except AttributeError:
                symName += index_string
                final_value = "ERROR: %s -> %s" % (index_string, value.prettyPrint())

            try:
                i = [i for i,d in raw].index(index_string)
                ti, td = raw[i]
                td[symName] = utils.to_native(value)
            except Exception as exc:
                raw.append((index_string, {symName: final_value}, ))

        return raw

class SnmpSetError(Exception):
    pass

class SnmpRuntimeError(Exception):
    pass
