#!/usr/bin/python
# -*- coding: utf-8 -*-

from Queue import Queue
from threading import Thread

from pysnmp.smi import builder, view
from pysnmp.entity.rfc3413.oneliner import cmdgen

from pyasn1.type import univ

import utils


class Worker(Thread):

    def __init__(self, requests, responses):
        Thread.__init__(self)
        self.requests = requests
        self.responses = responses
        self.cmdGen = cmdgen.CommandGenerator()
        self.setDaemon(True)
        self.start()
    

    def run(self):
        while True:
            authData, transportTarget, varNames = self.requests.get()
            self.responses.append(
                self.cmdGen.getCmd(
                    authData, transportTarget, *varNames,
                    lookupNames=True, lookupValues=True
                )
            )
            self.requests.task_done()


class ThreadPool:

    def __init__(self, num_threads):
        self.requests = Queue(num_threads)
        self.responses = []
        for _ in range(num_threads):
            Worker(self.requests, self.responses)


    def addRequest(self, authData, transportTarget, varBinds):
        self.requests.put((authData, transportTarget, varBinds))


    def getResponses(self):
        return self.responses


    def waitCompletion(self):
        self.requests.join()


class SnmpPoller(object):

    def __init__(self, mibs=[], mibSources=[]):
        self.mibs = mibs
        self.mibSources = mibSources


        self.mibBuilder = builder.MibBuilder()

        extraMibSources = tuple([builder.DirMibSource(d) for d in self.mibSources])
        totalMibSources = self.mibBuilder.getMibSources() + extraMibSources
        self.mibBuilder.setMibSources( *totalMibSources )
        if self.mibs:
            self.mibBuilder.loadModules( *self.mibs )
        self.mibViewController = view.MibViewController(self.mibBuilder)

        self.targets = []
        self.objects_to_poll = []


    def _get_mib_variables(self, args):
        mib_variables = []
        for arg in args:
            mv = cmdgen.MibVariable(*arg)
            mv.resolveWithMib(self.mibViewController)
            mib_variables.append(mv)
        return mib_variables


    def set_objects_to_poll(self, objects_to_poll):
        self.targets = []
        self.objects_to_poll = objects_to_poll
        for object_to_poll in self.objects_to_poll:
            properties = object_to_poll.properties
            mib_variables = self._get_mib_variables(properties.values())
            self.targets.append((
                cmdgen.CommunityData(object_to_poll.community, mpModel=0),
                cmdgen.UdpTransportTarget((object_to_poll.ip, object_to_poll.port)), mib_variables,
            ))
    

    def async(self):
        '''
        http://pysnmp.sourceforge.net/examples/current/v3arch/oneliner/manager/cmdgen/get-async-multiple-transports-and-protocols.html
        '''

        cmdGen  = cmdgen.AsynCommandGenerator()

        for authData, transportTarget, varNames in self.targets:
            cmdGen.getCmd(
                authData, transportTarget, varNames,
                # User-space callback function and its context
                (self.callback, (authData, transportTarget)),
                lookupNames=True, lookupValues=True
            )

        if self.targets:
            cmdGen.snmpEngine.transportDispatcher.runDispatcher()


    def sync(self):
        '''
        http://pysnmp.sourceforge.net/examples/current/v3arch/oneliner/manager/cmdgen/get-threaded-multiple-transports-and-protocols.html
        '''
        pool = ThreadPool(3)

        for authData, transportTarget, varNames in self.targets:
            pool.addRequest(authData, transportTarget, varNames)
        
        pool.waitCompletion()

        for errorIndication, errorStatus, errorIndex, varBinds in pool.getResponses():
            print('Response for %s from %s:' % (authData, transportTarget))
            if errorIndication:
                print(errorIndication)
            if errorStatus:
                print('%s at %s' % (
                    errorStatus.prettyPrint(),
                    errorIndex and varBinds[int(errorIndex)-1][0] or '?'
                    )
                )
            
            for oid, val in varBinds:
                if val is None:
                    print(oid.prettyPrint())
                else:
                    print('%s = %s' % (oid.prettyPrint(), val.prettyPrint()))


    def callback(self, sendRequestHandle, errorIndication, errorStatus, errorIndex,
              varBinds, cbCtx):
        (authData, transportTarget) = cbCtx
        # print('%s via %s' % (authData, transportTarget))

        if errorIndication:
            print(errorIndication)
            return 1
        if errorStatus:
            print('%s at %s' % (
                errorStatus.prettyPrint(),
                errorIndex and varBinds[int(errorIndex)-1] or '?'
                )
            )
            return 1
        
        addr = transportTarget.transportAddr[0]
        try:
            this_object, = [o for o in self.objects_to_poll if o.ip == addr]
        except Exception, exc:
            return

        for oid, val in varBinds:
            mv = cmdgen.MibVariable(oid)
            mv.resolveWithMib(self.mibViewController)
            modName, symName, indices = mv.getMibSymbol()
            index_string = tuple([x.prettyPrint() for x in indices])
            index_string = indices

            if val is None:
                print(oid.prettyPrint())
            else:
                # print(' --> %s = %s' % (oid.prettyPrint(), val.prettyPrint()))
                for field, field_def in this_object.properties.iteritems():
                    mib, symbol, _ = field_def
                    # print '??', modName, mib, symName, symbol
                    if modName == mib and symName == symbol:
                        # print 'syntax1', type(mv.getMibNode().syntax.clone(val))
                        value = mv.getMibNode().syntax.clone(val).prettyPrint()
                        # print 'syntax2', value, type(value)
                        # value = utils.to_native(val)
                        # print 'syntax3', value, type(value)
                        this_object.setattr(field, value)


if __name__ == '__main__':

    import objects

    class Docsis2xCm(objects.GetObject):

        properties = {
            'configfile': ('DOCS-CABLE-DEVICE-MIB', 'docsDevServerConfigFile', 0),
            # 'dnfreq': ('DOCS-IF-MIB', 'docsIfDownChannelFrequency', 3),
            'dnpower': ('DOCS-IF-MIB', 'docsIfDownChannelPower', 3),
        }

    p = SnmpPoller(
        mibs=['DOCS-CABLE-DEVICE-MIB'],
        mibSources=['/home/irojo/dev/krill-modules/krill-docsis/module/snmpcmts/pymibs']
    )
    o = Docsis2xCm(community='pubsl', ip='10.105.15.10')
    p.set_objects_to_poll([o])
    p.async()
    print '!!', o.configfile, o.dnpower
