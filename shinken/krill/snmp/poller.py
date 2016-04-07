#!/usr/bin/python
# -*- coding: utf-8 -*-

from Queue import Queue
import threading
from threading import Thread

from pysnmp.smi import builder, view
from pysnmp.entity.rfc3413.oneliner import cmdgen

from pyasn1.type import univ

import utils

from shinken.log import logger

CHUNK_SIZE = 5000
HOSTS_PER_THREAD = 100

class Worker(Thread):

    def __init__(self, requests, responses, name):
        Thread.__init__(self, name=name, args=(), kwargs=None, verbose=True)
        self.requests = requests
        self.responses = responses
        self.cmdGen = cmdgen.CommandGenerator()
        self.setDaemon(True)
        self.start()


    def run(self):
        banned_transportAddr = []

        while not self.requests.empty():
            authData, transportTarget, varNames, method = self.requests.get()
            cbCtx = (authData, transportTarget)
 
            if transportTarget.transportAddr not in banned_transportAddr:
                if method == 'get':
                    errorIndication, errorStatus, errorIndex, varBinds = self.cmdGen.getCmd(
                        authData, transportTarget, *varNames,
                        lookupNames=True, lookupValues=True
                    )
                    self.responses.append(
                        (errorIndication, errorStatus, errorIndex, varBinds, cbCtx)
                    )
                else:
                    errorIndication, errorStatus, errorIndex, varBinds = self.cmdGen.nextCmd(
                        authData, transportTarget, *varNames,
                        lookupNames=True, lookupValues=True
                    )
                    self.responses.append(
                        (errorIndication, errorStatus, errorIndex, [x[0] for x in varBinds], cbCtx)
                    )
            if errorIndication:
                banned_transportAddr.append(transportTarget.transportAddr)

            self.requests.task_done()


class ThreadPool:

    def __init__(self, num_threads):
        self.requests = Queue(num_threads)
        self.responses = []
        self.threads = []
        for thread_id in range(num_threads):
            th = Worker(self.requests, self.responses, name='th#%d'%thread_id)
            self.threads.append(th)


    def add_get_request(self, authData, transportTarget, varBinds):
        self.requests.put((authData, transportTarget, varBinds, 'get'))


    def add_walk_request(self, authData, transportTarget, varBinds):
        self.requests.put((authData, transportTarget, varBinds, 'walk'))


    def getResponses(self):
        return self.responses


    def waitCompletion(self):
        self.requests.join()


class SnmpPoller(object):

    def __init__(self, mibs=[], mibSources=[], max_threads=5):
        self.mibs = mibs
        self.mibSources = mibSources
        self.max_threads = max_threads

        self.mibBuilder = builder.MibBuilder()

        extraMibSources = tuple([builder.DirMibSource(d) for d in self.mibSources])
        totalMibSources = extraMibSources + self.mibBuilder.getMibSources()
        self.mibBuilder.setMibSources( *totalMibSources )
        if self.mibs:
            self.mibBuilder.loadModules( *self.mibs )
        self.mibViewController = view.MibViewController(self.mibBuilder)

        self.get_targets = []
        self.walk_targets = []
        self.objects_to_poll = []


    # def _get_mib_variables(self, args):
    #     mib_variables = []
    #     for arg in args:
    #         mv = cmdgen.MibVariable(*arg)
    #         mv.resolveWithMib(self.mibViewController)
    #         mib_variables.append(mv)
    #     return mib_variables


    def set_objects_to_poll(self, objects_to_poll):

        self.get_targets = []
        self.walk_targets = []
        self.objects_to_poll = objects_to_poll

        # print 'set_objects_to_poll', objects_to_poll
        for object_to_poll in self.objects_to_poll:
            get_mib_variables = []
            for field, field_property in object_to_poll.properties.iteritems():

                mibVariable = cmdgen.MibVariable(*field_property.oid)
                mibVariable.resolveWithMib(self.mibViewController)
                modName, symName, indices = mibVariable.getMibSymbol()
                # print 'modName, symName, indices', modName, symName, indices
                
                if field_property.method == 'get':
                    get_mib_variables.append(mibVariable)
                else:
                    object_to_poll.setattr(field, [])

                    self.walk_targets.append((
                        cmdgen.CommunityData(object_to_poll.community, mpModel=0),
                        cmdgen.UdpTransportTarget((object_to_poll.ip, object_to_poll.port),
                            timeout=object_to_poll.timeout,
                            retries=object_to_poll.retries
                        ),
                        [mibVariable],
                    ))


            # properties = object_to_poll.properties
            # mib_variables = self._get_mib_variables(properties.values())

            # logger.info("[SnmpPoller] set_objects_to_poll addr=%s", object_to_poll.ip)
            if get_mib_variables:
                self.get_targets.append((
                    cmdgen.CommunityData(object_to_poll.community, mpModel=0),
                    cmdgen.UdpTransportTarget((object_to_poll.ip, object_to_poll.port),
                        timeout=object_to_poll.timeout,
                        retries=object_to_poll.retries
                    ),
                    get_mib_variables,
                ))
        

    def async(self):
        '''
        http://pysnmp.sourceforge.net/examples/current/v3arch/oneliner/manager/cmdgen/get-async-multiple-transports-and-protocols.html
        '''

        def chunks(l, n):
            for i in range(0, len(l), n):
                yield l[i:i+n]

        cmdGen  = cmdgen.AsynCommandGenerator()

        # print 'chunks:', len(self.targets)
        chunk_i = 1
        for chunk in chunks(self.targets, CHUNK_SIZE):
            # print 'chunk...', chunk_i, len(chunk)
            for authData, transportTarget, varNames in chunk:
                cmdGen.getCmd(
                    authData, transportTarget, varNames,
                    # User-space callback function and its context
                    (self.callback, (authData, transportTarget)),
                    lookupNames=True, lookupValues=True
                )

            cmdGen.snmpEngine.transportDispatcher.runDispatcher()
            # print 'chunk!!!', chunk_i
            chunk_i += 1


    def sync(self):
        '''
        http://pysnmp.sourceforge.net/examples/current/v3arch/oneliner/manager/cmdgen/get-threaded-multiple-transports-and-protocols.html
        '''
        threads = int((len(self.get_targets) + len(self.walk_targets)) / HOSTS_PER_THREAD) + 1
        threads = min([threads, self.max_threads])
        # logger.warning("[SnmpPoller] sync threads %d", threads)
        # logger.warning("[SnmpPoller] self.get_targets %s", self.get_targets)
        pool = ThreadPool(threads)

        for authData, transportTarget, varNames in self.get_targets:
            pool.add_get_request(authData, transportTarget, varNames)
        for authData, transportTarget, varNames in self.walk_targets:
            pool.add_walk_request(authData, transportTarget, varNames)
        
        pool.waitCompletion()

        for errorIndication, errorStatus, errorIndex, varBinds, cbCtx in pool.getResponses():
            sendRequestHandle = None
            self.callback(sendRequestHandle, errorIndication, errorStatus, errorIndex, varBinds, cbCtx)

        for object_to_poll in self.objects_to_poll:
            object_to_poll.consolidate()


    def callback(self, sendRequestHandle, errorIndication, errorStatus, errorIndex,
              varBinds, cbCtx):
        (authData, transportTarget) = cbCtx
        # logger.warning("[SnmpPoller] callback %s", varBinds)
        if errorIndication:
            logger.warning("[SnmpPoller] errorIndication %s %s %s",
                transportTarget,
                varBinds,
                errorIndication
            )
            return 
        if errorStatus:
            logger.warning("[SnmpPoller] errorStatus %s %s %s %s",
                transportTarget,
                varBinds,
                errorStatus.prettyPrint(),
                errorIndex and varBinds[int(errorIndex)-1] or '?'
            )
            return
        
        addr = transportTarget.transportAddr[0]
        # logger.warning("[SnmpPoller] addr %s", addr)
        try:
            this_object, = [o for o in self.objects_to_poll if o.ip == addr]
        except Exception, exc:
            logger.warning("[SnmpPoller] this_object? addr=%s", addr)
            return

        for oid_val in varBinds:
            oid, val = oid_val
            # oid, val = oid_val[0]
            # logger.warning("[SnmpPoller] oid_val, oid, val %s %s %s", oid_val, oid, val)
            mv = cmdgen.MibVariable(oid)
            mv.resolveWithMib(self.mibViewController)
            modName, symName, indices = mv.getMibSymbol()
            index_string = tuple([x.prettyPrint() for x in indices])
            # logger.warning("[SnmpPoller] INDICES %s %s %s %s %s", oid, val, modName, symName, index_string)

            if val is None:
                logger.warning("[SnmpPoller] val none oid=%s", oid.prettyPrint())
            else:
                # logger.warning("[SnmpPoller] this_object %s", this_object.properties)
                for field, field_property in this_object.properties.iteritems():
                    # logger.warning("[SnmpPoller] field, field_property %s %s", field, field_property.oid)
                    
                    try:
                        mib, symbol, index = field_property.oid
                    except:
                        mib, symbol = field_property.oid
                        index = None

                    # logger.warning("[SnmpPoller] callback mib, symbol %s %s / %s %s", mib, symbol, modName, symName)
                    if modName == mib and symName == symbol:
                        value = mv.getMibNode().syntax.clone(val).prettyPrint()                        
                        # logger.warning("[SnmpPoller] callback addr=%s %s(index=%s)->%s", addr, field, index, value)
                        if index is not None:
                            # logger.warning("[SnmpPoller] callback field:value %s<-%s", field, value)
                            this_object.setattr(field, value)
                        else:
                            buf = this_object.getattr(field)
                            # logger.warning("[SnmpPoller] callback buf1=%s", buf)
                            buf.append((index_string, value))
                            this_object.setattr(field, buf)
                            # logger.warning("[SnmpPoller] callback buf2=%s", buf)
                        


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
