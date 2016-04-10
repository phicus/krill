#!/usr/bin/python
# -*- coding: utf-8 -*-

from Queue import Queue
import threading
from threading import Thread
import time

from pysnmp.smi import builder, view
from pysnmp.entity.rfc3413.oneliner import cmdgen

from pyasn1.type import univ

import utils

from shinken.log import logger

CHUNK_SIZE = 5000
HOSTS_PER_THREAD = 40


class SnmpPollerException(Exception):
    pass


class TimeoutQueue(Queue):

    def __init__(self, *args, **kwargs):
        Queue.__init__(self, *args, **kwargs)
        self.failed_loops = -1
        self.last_unfinished_tasks = None


    def tasks_are_working(self):
        MAX_FAILED_LOOPS = 3

        # print 'tasks_are_working IN'
        if self.failed_loops == -1:
            # print 'tasks_are_working FIRST!'
            self.failed_loops = 0
            return True

        unfinished_tasks = self.unfinished_tasks
        # print 'tasks_are_working', self.last_unfinished_tasks, unfinished_tasks
        if self.last_unfinished_tasks > unfinished_tasks:
            # print 'tasks_are_working last_unfinished_tasks <- unfinished_tasks', self.last_unfinished_tasks, unfinished_tasks
            self.last_unfinished_tasks = unfinished_tasks
            return True
        else:
            # print 'tasks_are_working failed_loops', self.failed_loops, MAX_FAILED_LOOPS, type(self.failed_loops), type(MAX_FAILED_LOOPS)
            self.failed_loops += 1
            if self.failed_loops >= MAX_FAILED_LOOPS:
                # print 'tasks_are_working FALSE!!'
                return False
            else:
                return True


    def join_with_timeout(self, timeout):
        self.last_unfinished_tasks = self.unfinished_tasks
        self.all_tasks_done.acquire()
        try:
            endtime = time.time() + timeout
            while self.unfinished_tasks:
                remaining = endtime - time.time()
                logger.debug("[SnmpPoller] time remaining: %s unfinished tasks: %d", remaining, self.unfinished_tasks)
                if not self.tasks_are_working():
                    raise SnmpPollerException("[SnmpPoller] tasks are not working!")

                if remaining <= 0.0:
                    logger.debug("[SnmpPoller] timeout!")
                    raise SnmpPollerException("[SnmpPoller] polling timeout!")
                self.all_tasks_done.wait(10)
        finally:
            logger.debug("[SnmpPoller] join_with_timeout finally!")
            self.all_tasks_done.release()


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
        # self.requests = Queue()
        self.requests = TimeoutQueue()
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
        # self.requests.join()
        self.requests.join_with_timeout(timeout=1800)


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
        logger.warning("[SnmpPoller] sync threads %d", threads)
        pool = ThreadPool(threads)

        for authData, transportTarget, varNames in self.get_targets:
            pool.add_get_request(authData, transportTarget, varNames)
        logger.warning("[SnmpPoller] sync 2")
        for authData, transportTarget, varNames in self.walk_targets:
            pool.add_walk_request(authData, transportTarget, varNames)
        
        # logger.warning("[SnmpPoller] sync >> waitCompletion...")
        pool.waitCompletion()
        # logger.warning("[SnmpPoller] sync << waitCompletion...")

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
    from property import Property

    class docsis2xCm(objects.GetObject):
        timeout = 3
        retries = 0

        properties = {
            'uptime': Property(oid=('SNMPv2-MIB', 'sysUpTime', 0)),

            '_ethinoctets': Property(oid=('IF-MIB', 'ifInOctets', 1)),
            '_ethoutoctets': Property(oid=('IF-MIB', 'ifOutOctets', 1)),

            'configfile': Property(oid=('DOCS-CABLE-DEVICE-MIB', 'docsDevServerConfigFile', 0)),
            'sn': Property(oid=('DOCS-CABLE-DEVICE-MIB', 'docsDevSerialNumber', 0)),

            '_dnfreqlist': Property(oid=('DOCS-IF-MIB', 'docsIfDownChannelFrequency'), method='walk'),
            '_dnrxlist': Property(oid=('DOCS-IF-MIB', 'docsIfDownChannelPower'), method='walk'),
            '_dnsnrlist': Property(oid=('DOCS-IF-MIB', 'docsIfSigQSignalNoise'), method='walk'),
            '_dnunerroredslist': Property(oid=('DOCS-IF-MIB', 'docsIfSigQUnerroreds'), method='walk'),
            '_dncorrectedslist': Property(oid=('DOCS-IF-MIB', 'docsIfSigQCorrecteds'), method='walk'),
            '_dnuncorrectableslist': Property(oid=('DOCS-IF-MIB', 'docsIfSigQUncorrectables'), method='walk'),
            '_upfreq': Property(oid=('DOCS-IF-MIB', 'docsIfUpChannelFrequency', 4)),
            '_upmodulationprofilelist': Property(oid=('DOCS-IF-MIB', 'docsIfUpChannelModulationProfile'), method='walk'),

            '_uptxlist': Property(oid=('DOCS-IF-MIB', 'docsIfCmStatusTxPower'), method='walk'),
        }

    p = SnmpPoller(
        mibs=['DOCS-CABLE-DEVICE-MIB'],
        mibSources=['/var/lib/shinken/modules/krill-docsis/module/snmpcmts/pymibs']
    )
    o = docsis2xCm(community='public', ip='10.60.37.218')
    p.set_objects_to_poll([o, o])

    snmp_polling_attempts = 0
    snmp_polling_succeded = False
    while not snmp_polling_succeded and snmp_polling_attempts < 3:
        try:
            p.sync()
            snmp_polling_succeded = True
        except SnmpPollerException, exc:
            print 'SnmpPollerException ', exc
            snmp_polling_attempts += 1

    print '!!', o.configfile, o._dnrxlist
