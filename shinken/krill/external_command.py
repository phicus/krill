#!/usr/bin/python
# -*- coding: utf-8 -*-

import time
import collections

from shinken.log import logger
from shinken.external_command import ExternalCommand


class KrillExternalCommands(object):

    SERVICESTATES = {'OK':'0', 'WARNING':'1', 'CRITICAL':'2', 'UNKNOWN':'3'}
    #HOSTSTATES = {'UP':'0', 'DOWN':'1', 'UNREACHABLE':'????'}
    HOSTSTATES = {'UP':'0', 'DOWN':'2'}

    def __init__(self):
        self.reset()
        self.from_q = None


    def load_external_queue(self, from_q):
        logger.info("[EC] load_external_queue %s" % from_q)
        self.from_q = from_q


    def reset(self):
        self.host_services = collections.defaultdict(dict)
        self.extcmds = []


    def process_host_check_result(self, host_name, state_string, output, force=False):
        logger.info("[EC] process_host_check_result ?? %s %s %s %s", host_name, state_string, output, force)
        if force or not self._yet(host_name, '__HOST__'):
            logger.info("[EC] process_host_check_result !!")
            self._set(host_name, '__HOST__', self.HOSTSTATES[state_string], output)


    def push_change_host_var(self, host, varname, varvalue):
        logger.info("[EC] push_change_host_var... %s %s %s", host, varname, varvalue)
        if host and getattr(host, varname) != varvalue:
            extcmd = '[%d] %s;%s;%s;%s' % (int(time.time()), 'CHANGE_HOST_VAR', host.host_name, varname, varvalue)
            self.push_extcmd(extcmd)


    def push_process_host_check_result(self, host_name, state_string, output):
        ts = int(time.time())
        state = self.HOSTSTATES[state_string]
        extcmd = '[%d] %s;%s;%s;%s' % (ts, 'PROCESS_HOST_CHECK_RESULT', host_name, state, output)
        self.push_extcmd(extcmd)


    def process_service_check_result(self, host_name, service, state_string, output, force=False):
        if force or not self._yet(host_name, service):
            self._set(host_name, service, self.SERVICESTATES[state_string], output)


    def push_process_service_check_result(self, host_name, service, state_string, output):
        ts = int(time.time())
        state = self.SERVICESTATES[state_string]
        extcmd = '[%d] %s;%s;%s;%s;%s' % (ts, 'PROCESS_SERVICE_CHECK_RESULT', host_name, service, state, output)
        self.push_extcmd(extcmd)


    def _yet(self, host_name, service):
        return host_name in self.host_services and service in self.host_services[host_name]


    def _set(self, host_name, service, state, output):
        self.host_services[host_name][service] = (int(time.time()), state, output)


    def add_simple_host_dependency(self, son, father):
        extcmd = '[%d] ADD_SIMPLE_HOST_DEPENDENCY;%s;%s' % (int(time.time()), son, father)
        extcmd = extcmd.decode('utf8', 'replace')
        self.extcmds.append(extcmd)


    # def _print_host_services(self, label):
    #     print '_print_host_services INI', label
    #     for host, checks in self.host_services.iteritems():
    #         print '_print_host_services', host, checks.keys()
    #     print '_print_host_services END', label


    def all(self):
        extcmds = self.extcmds

        for host, checks in self.host_services.iteritems():
            for service, ts__state__output in checks.iteritems():
                ts, state, output = ts__state__output
                if service == '__HOST__':
                    extcmd = '[%d] %s;%s;%s;%s' % (ts, 'PROCESS_HOST_CHECK_RESULT', host, state, output)
                else:
                    extcmd = '[%d] %s;%s;%s;%s;%s' % (ts, 'PROCESS_SERVICE_CHECK_RESULT', host, service, state, output)

                extcmd = extcmd.decode('utf8', 'replace')
                extcmds.append(extcmd)
        return extcmds


    def get_process_host_check_result_extcmd(self, host, state_string, output):
        ts = int(time.time())
        # host = 'cpe%d' % cpe.id
        state = self.HOSTSTATES[state_string]
        extcmd = '[%d] %s;%s;%s;%s' % (ts, 'PROCESS_HOST_CHECK_RESULT', host, state, output)
        return extcmd


    def send_all(self):
        def chunks(l, n):
            for i in range(0, len(l), n):
                yield l[i:i+n]

        logger.info("[EC] send_all...")
        COMMAND_CHUNK_SIZE = 500
        self_all = self.all()
        for chunk in chunks(self_all, COMMAND_CHUNK_SIZE):
            for extcmd in chunk:
                logger.debug("[EC] send_all extcmd=%s" % extcmd)
                self.push_extcmd(extcmd)
            time.sleep(1)
            logger.debug("[EC] sleep")
        logger.info("[EC] send_all len=%d!!!", len(self_all))


    def push_extcmd(self, extcmd):
        e = ExternalCommand(extcmd)
        if self.from_q:
            # logger.info("[EC] push_extcmd!!")
            self.from_q.put(e)
        else:
            logger.info("[EC] push_extcmd e=%s" % e)

if __name__ == '__main__':
    host_name = 'fake'
    ec = KrillExternalCommands()
    ec.process_host_check_result(host_name, 'UP', 'bla bla', force=True)
    print 'HS1', ec.host_services
    ec.process_host_check_result(host_name, 'DOWN', 'nasti', force=True)
    print 'HS2', ec.host_services
