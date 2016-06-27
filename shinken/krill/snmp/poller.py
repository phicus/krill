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
import syslog


CHUNK_SIZE = 5000
# HOSTS_PER_THREAD = 2


class SnmpPollerException(Exception):
    pass

class GoodEnoughSnmpPollerException(Exception):
    pass


class TimeoutQueue(Queue):

    def __init__(self, *args, **kwargs):
        Queue.__init__(self, *args, **kwargs)
        self.failed_loops = -2
        self.last_unfinished_tasks = None
        self.init_unfinished_tasks = None
        self.reset()


    def reset(self):
        print 'TFLK reset1'
        while not self.empty():
            print 'TFLK reset2', self.get()
        print 'TFLK reset3'
        self.failed_loops = -1


    def tasks_are_working(self):
        MAX_FAILED_LOOPS = 3
        GOOD_ENOUGH_FINISHED_TASKS_PERCENTAGE = 0.5

        logger.info('[SnmpPoller] tasks_are_working self.failed_loops=%d', self.failed_loops)
        if self.failed_loops == -1:
            self.failed_loops = 0
            return True

        logger.info('[SnmpPoller] tasks_are_working self.unfinished_tasks=%d self.last_unfinished_tasks=%d', self.unfinished_tasks, self.last_unfinished_tasks)
        if self.last_unfinished_tasks > self.unfinished_tasks:
            logger.info('[SnmpPoller] tasks_are_working last=%d <- unfinished=%d', self.last_unfinished_tasks, self.unfinished_tasks)
            self.last_unfinished_tasks = self.unfinished_tasks
            return True
        else:
            self.failed_loops += 1
            if self.failed_loops >= MAX_FAILED_LOOPS:
                logger.info("[SnmpPoller] tasks_are_working (self.failed_loops >= MAX_FAILED_LOOPS!!) unfinished_tasks=%d init_unfinished_tasks=%d", self.unfinished_tasks, self.init_unfinished_tasks)
                try:
                    pct_unfinished_tasks = 100 * self.unfinished_tasks/float(self.init_unfinished_tasks)
                except:
                    logger.warning("[SnmpPoller] tasks_are_working: unfinished_tasks=%d init_unfinished_tasks=%d", self.unfinished_tasks, self.init_unfinished_tasks)
                    pct_unfinished_tasks = 0

                if pct_unfinished_tasks < GOOD_ENOUGH_FINISHED_TASKS_PERCENTAGE:
                    raise GoodEnoughSnmpPollerException()
                else:
                    return False
            else:
                return True


    def join_with_timeout(self, timeout):
        self.last_unfinished_tasks = self.init_unfinished_tasks
        self.init_unfinished_tasks = self.unfinished_tasks
        self.all_tasks_done.acquire()
        try:
            endtime = time.time() + timeout
            while self.unfinished_tasks:
                self.all_tasks_done.wait(1) #let task start
                remaining = endtime - time.time()
                logger.info("[SnmpPoller] time remaining: %s unfinished tasks: %d", remaining, self.unfinished_tasks)
                syslog.syslog(syslog.LOG_DEBUG, "[SnmpPoller] time remaining: %s unfinished tasks: %d" % (remaining, self.unfinished_tasks))
                if not self.tasks_are_working():
                    raise SnmpPollerException("[SnmpPoller] tasks are not working!")

                if remaining <= 0.0:
                    logger.info("[SnmpPoller] timeout!")
                    raise SnmpPollerException("[SnmpPoller] polling timeout!")
                self.all_tasks_done.wait(5)
        except GoodEnoughSnmpPollerException:
            logger.warning("[SnmpPoller] join_with_timeout GoodEnoughSnmpPollerException!")
            self.all_tasks_done.release()
        finally:
            logger.info("[SnmpPoller] join_with_timeout finally!")
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

        while True:
            authData, transportTarget, getVarNames, walkVarNames = self.requests.get()
            cbCtx = (authData, transportTarget)

            logger.debug('RUN-1 %s %s', self, transportTarget.transportAddr) 
            syslog.syslog(syslog.LOG_DEBUG, 'RUN-1 %s %s' % (self, transportTarget.transportAddr))

            errorIndication = 0

            if getVarNames:
                errorIndication, errorStatus, errorIndex, varBinds = self.cmdGen.getCmd(
                    authData, transportTarget, *getVarNames,
                    lookupNames=True, lookupValues=True
                )
                # logger.info('RUN-1 %s getVarNames=%s', self, getVarNames)
                self.responses.append(
                    (errorIndication, errorStatus, errorIndex, varBinds, cbCtx)
                )

            for walkVarName in walkVarNames:
                if errorIndication:
                    break
                # logger.info('RUN-1 %s walkVarName=%s', self, walkVarName)
                errorIndication, errorStatus, errorIndex, varBinds = self.cmdGen.nextCmd(
                    authData, transportTarget, *[walkVarName],
                    lookupNames=True, lookupValues=True
                )
                self.responses.append(
                    (errorIndication, errorStatus, errorIndex, [x[0] for x in varBinds], cbCtx)
                )

            self.requests.task_done()


    def run____(self):
        banned_transportAddr = []

        while True:
        # while not self.requests.empty():
            authData, transportTarget, varNames, method = self.requests.get()
            cbCtx = (authData, transportTarget)
            
            logger.debug('RUN-1 %s %s %s m=%s', self, transportTarget.transportAddr, banned_transportAddr, method) 
            syslog.syslog(syslog.LOG_DEBUG, 'RUN-1 %s %s %s m=%s' % (self, transportTarget.transportAddr, banned_transportAddr, method))
            if transportTarget.transportAddr[0] not in banned_transportAddr:
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
                banned_transportAddr.append(transportTarget.transportAddr[0])

            self.requests.task_done()


class ThreadPool:

    def __init__(self, num_threads):
        # self.requests = Queue(num_threads)
        self.requests = TimeoutQueue(num_threads)
        # self.workers = []
        self.responses = []
        for thread_id in range(num_threads):
            # self.workers.append(Worker(self.requests, self.responses, name='th#%d'%thread_id))
            Worker(self.requests, self.responses, name='th#%d'%thread_id)

        self.reset()


    def reset(self):
        del self.responses[:]
        self.requests.reset()


    def add_request(self, authData, transportTarget, getVarNames, walkVarNames):
        self.requests.put((authData, transportTarget, getVarNames, walkVarNames))


    def add_get_request(self, authData, transportTarget, varBinds):
        self.requests.put((authData, transportTarget, varBinds, 'get'))


    def add_walk_request(self, authData, transportTarget, varBinds):
        self.requests.put((authData, transportTarget, varBinds, 'walk'))


    def getResponses(self):
        return self.responses


    def waitCompletion(self, timeout):
        # self.requests.join()
        self.requests.join_with_timeout(timeout)


class SnmpPoller(object):

    def __init__(self, mibs=[], mibSources=[], threads=40, timeout=3600):
        self.threads = threads
        self.timeout = timeout
        # threads = int((len(self.get_targets) + len(self.walk_targets)) / HOSTS_PER_THREAD) + 1
        # threads = min([threads, self.max_threads])
        logger.debug("[SnmpPoller] sync threads %d", threads)

        # self.pool = ThreadPool(threads)
        self.pool = None
        self.set_mib_mibsources(mibs, mibSources)

        self.targets = []
        self.get_targets = []
        self.walk_targets = []
        self.objects_to_poll = []


    def init(self):
        if self.pool == None:
            self.pool = ThreadPool(self.threads)


    def set_mib_mibsources(self, mibs, mibSources):
        # logger.warning("[SnmpPoller] set_mib_mibsources %s %s", mibs, mibSources)
        self.mibs = mibs
        self.mibSources = mibSources

        self.mibBuilder = builder.MibBuilder()
        extraMibSources = tuple([builder.DirMibSource(d) for d in self.mibSources])
        totalMibSources = extraMibSources + self.mibBuilder.getMibSources()
        self.mibBuilder.setMibSources( *totalMibSources )
        if self.mibs:
            self.mibBuilder.loadModules( *self.mibs )
        self.mibViewController = view.MibViewController(self.mibBuilder)


    # def _get_mib_variables(self, args):
    #     mib_variables = []
    #     for arg in args:
    #         mv = cmdgen.MibVariable(*arg)
    #         mv.resolveWithMib(self.mibViewController)
    #         mib_variables.append(mv)
    #     return mib_variables


    def set_objects_to_poll(self, objects_to_poll):

        self.targets = []
        self.get_targets = []
        self.walk_targets = []
        self.objects_to_poll = objects_to_poll

        for object_to_poll in self.objects_to_poll:
            target_gets_def = []
            target_walks_def = []
            get_mib_variables = []
            for field, field_property in object_to_poll.properties.iteritems():

                mibVariable = cmdgen.MibVariable(*field_property.oid)
                mibVariable.resolveWithMib(self.mibViewController)
                modName, symName, indices = mibVariable.getMibSymbol()
                
                if field_property.method == 'get':
                    # get_mib_variables.append(mibVariable)
                    target_gets_def.append(mibVariable)
                else:
                    object_to_poll.setattr(field, [])

                    # self.walk_targets.append((
                    #     cmdgen.CommunityData(object_to_poll.community, mpModel=0),
                    #     cmdgen.UdpTransportTarget((object_to_poll.ip, object_to_poll.port),
                    #         timeout=object_to_poll.timeout,
                    #         retries=object_to_poll.retries
                    #     ),
                    #     [mibVariable],
                    # ))
                    target_walks_def.append(mibVariable)


            self.targets.append((
                cmdgen.CommunityData(object_to_poll.community, mpModel=0),
                cmdgen.UdpTransportTarget((object_to_poll.ip, object_to_poll.port),
                    timeout=object_to_poll.timeout,
                    retries=object_to_poll.retries
                ),
                target_gets_def,
                target_walks_def
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

        chunk_i = 1
        for chunk in chunks(self.targets, CHUNK_SIZE):
            for authData, transportTarget, varNames in chunk:
                cmdGen.getCmd(
                    authData, transportTarget, varNames,
                    # User-space callback function and its context
                    (self.callback, (authData, transportTarget)),
                    lookupNames=True, lookupValues=True
                )

            cmdGen.snmpEngine.transportDispatcher.runDispatcher()
            chunk_i += 1


    def sync(self):
        '''
        http://pysnmp.sourceforge.net/examples/current/v3arch/oneliner/manager/cmdgen/get-threaded-multiple-transports-and-protocols.html
        '''
        logger.warning("[SnmpPoller] sync 1")
        if not self.targets:
            return
        elif len(self.targets) == 1:
            responses = self._get_responses_by_myself()
        else:
            responses = self._get_responses_by_pool()
        logger.warning("[SnmpPoller] sync 2")

        for errorIndication, errorStatus, errorIndex, varBinds, cbCtx in responses:
            sendRequestHandle = None
            self.callback(sendRequestHandle, errorIndication, errorStatus, errorIndex, varBinds, cbCtx)

        logger.warning("[SnmpPoller] sync 3")
        for object_to_poll in self.objects_to_poll:
            object_to_poll.consolidate()
        logger.warning("[SnmpPoller] sync 4")

    def _get_responses_by_myself(self):
        authData, transportTarget, getVarNames, walkVarNames = self.targets[0]
        cbCtx = (authData, transportTarget)

        errorIndication = 0

        cmdGen = cmdgen.CommandGenerator()
        responses = []

        if getVarNames:
            errorIndication, errorStatus, errorIndex, varBinds = cmdGen.getCmd(
                authData, transportTarget, *getVarNames,
                lookupNames=True, lookupValues=True
            )
            responses.append(
                    (errorIndication, errorStatus, errorIndex, varBinds, cbCtx)
                )

        for walkVarName in walkVarNames:
            if errorIndication:
                break
            # logger.info('RUN-1 %s walkVarName=%s', self, walkVarName)
            errorIndication, errorStatus, errorIndex, varBinds = cmdGen.nextCmd(
                authData, transportTarget, *[walkVarName],
                lookupNames=True, lookupValues=True
            )
            responses.append(
                (errorIndication, errorStatus, errorIndex, [x[0] for x in varBinds], cbCtx)
            )
        return responses


    def _get_responses_by_pool(self):
        self.init()
        self.pool.reset()

        for authData, transportTarget, getVarNames, walkVarNames in self.targets:
            self.pool.add_request(authData, transportTarget, getVarNames, walkVarNames)

        self.pool.waitCompletion(self.timeout)

        return self.pool.getResponses()




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
            # print 'oid, val', addr, oid, val
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

                    # logger.warning("[SnmpPoller] callback mib, symbol %s %s / %s %s (val=%s)", mib, symbol, modName, symName, val)
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
                        


def test_rod():
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
            # 'sn': Property(oid=('DOCS-CABLE-DEVICE-MIB', 'docsDevSerialNumber', 0)),

            '_dnfreq': Property(oid=('DOCS-IF-MIB', 'docsIfDownChannelFrequency', 3)),
            '_dnrx': Property(oid=('DOCS-IF-MIB', 'docsIfDownChannelPower', 3)),
            '_dnsnr': Property(oid=('DOCS-IF-MIB', 'docsIfSigQSignalNoise', 3)),
            '_dnunerroreds': Property(oid=('DOCS-IF-MIB', 'docsIfSigQUnerroreds', 3)),
            '_dncorrecteds': Property(oid=('DOCS-IF-MIB', 'docsIfSigQCorrecteds', 3)),
            '_dnuncorrectables': Property(oid=('DOCS-IF-MIB', 'docsIfSigQUncorrectables', 3)),
            '_upfreq': Property(oid=('DOCS-IF-MIB', 'docsIfUpChannelFrequency', 4)),
            '_upmodulationprofile': Property(oid=('DOCS-IF-MIB', 'docsIfUpChannelModulationProfile', 4)),

            '_uptx': Property(oid=('DOCS-IF-MIB', 'docsIfCmStatusTxPower', 2)),

            # 'cpeipmax': (('DOCS-CABLE-DEVICE-MIB', 'docsDevCpeIpMax', 0),
        }

    p = SnmpPoller(threads=6,timeout=10)
    os = [
        # docsis2xCm(community='public', ip='10.6.93.139'),
        # docsis2xCm(community='public', ip='10.6.69.37'),
        docsis2xCm(community='public', ip='10.4.85.101'),
        docsis2xCm(community='public', ip='10.4.85.246'),
        docsis2xCm(community='public', ip='10.4.85.109'),
        docsis2xCm(community='public', ip='10.4.85.130'),
        docsis2xCm(community='public', ip='10.4.84.39'),
        docsis2xCm(community='public', ip='10.4.77.28'),
        docsis2xCm(community='public', ip='10.4.81.195'),
        docsis2xCm(community='public', ip='10.4.80.147'),
        docsis2xCm(community='public', ip='10.4.89.76'),
        docsis2xCm(community='public', ip='10.4.85.113'),
        docsis2xCm(community='public', ip='10.4.90.109'),
        docsis2xCm(community='public', ip='10.4.87.148'),
        docsis2xCm(community='public', ip='10.4.79.142'),
        docsis2xCm(community='public', ip='10.4.81.213'),
        docsis2xCm(community='public', ip='10.4.85.29'),
        docsis2xCm(community='public', ip='10.4.81.99'),
        docsis2xCm(community='public', ip='10.4.87.189'),
        docsis2xCm(community='public', ip='10.4.80.254'),
        docsis2xCm(community='public', ip='10.4.85.222'),
        docsis2xCm(community='public', ip='10.4.83.35'),
        docsis2xCm(community='public', ip='10.4.90.211'),
        docsis2xCm(community='public', ip='10.4.78.101'),
        docsis2xCm(community='public', ip='10.4.93.188'),
        docsis2xCm(community='public', ip='10.4.88.153'),
        docsis2xCm(community='public', ip='10.4.81.48'),
        docsis2xCm(community='public', ip='10.4.80.130'),
    ]

    p.set_mib_mibsources(mibs=['DOCS-CABLE-DEVICE-MIB'], mibSources=['/var/lib/shinken/modules/krill-docsis/module/snmpcmts/pymibs'])
    p.set_objects_to_poll(os)

    import logging
    logger.setLevel(logging.DEBUG)

    while True:
        snmp_polling_attempts = 0
        snmp_polling_succeded = False
        while not snmp_polling_succeded and snmp_polling_attempts < 3:
            try:
                p.sync()
                snmp_polling_succeded = True
            except SnmpPollerException, exc:
                print 'SnmpPollerException ', exc
                snmp_polling_attempts += 1

        for o in os:
            print 'cm:', o.configfile, o._dnrx

        logger.warning('[TEST] sleep...')
        time.sleep(1)


def main():
    import mplog

def test_lenovo():
    import objects
    from property import Property

    class linux(objects.GetObject):
        timeout = 3
        retries = 0

        properties = {
            'name': Property(oid=('SNMPv2-MIB', 'sysName', 0)),
            'uptime': Property(oid=('SNMPv2-MIB', 'sysUpTime', 0)),
            # 'or_id': Property(oid=('SNMPv2-MIB', 'sysORID'), method='walk'),
            'or_descr': Property(oid=('SNMPv2-MIB', 'sysORDescr'), method='walk'),
            # 'or_uptime': Property(oid=('SNMPv2-MIB', 'sysORUpTime'), method='walk'),
        }

    p = SnmpPoller(threads=6,timeout=10)    
    # p.set_mib_mibsources(mibs=['DOCS-CABLE-DEVICE-MIB'], mibSources=['/var/lib/shinken/modules/krill-docsis/module/snmpcmts/pymibs'])
    import logging
    logger.setLevel(logging.DEBUG)

    while True:
        os = [
            linux(community='public', ip='127.0.0.1'),
            linux(community='public', ip='127.0.0.1')
        ]
        p.set_objects_to_poll(os)

        snmp_polling_attempts = 0
        snmp_polling_succeded = False
        while not snmp_polling_succeded and snmp_polling_attempts < 3:
            try:
                p.sync()
                snmp_polling_succeded = True
            except SnmpPollerException, exc:
                print 'SnmpPollerException ', exc
                snmp_polling_attempts += 1

        for o in os:
            print 'linux:', o.name, o.uptime, o.or_descr

        logger.warning('[TEST] sleep...')
        time.sleep(1)

if __name__ == '__main__':
    test_lenovo()
