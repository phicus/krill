#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys

from shinken.util import safe_print
from shinken.log import logger

# from shinken.objects.host import Host, Hosts
from objects import Cpe
from utils import total_size

CPEKEY_BY_TECH = {
    'docsis': '_MAC',
    'wimax': '_MAC',
    'gpon': '_SN',
}

class TechRegenerator(object):

    def __init__(self, filter_by_techs=None, filter_by_fields=None, customs=[]):
        self.filter_by_techs = filter_by_techs
        self.filter_by_fields = filter_by_fields
        self.customs = customs

        self.index_hosts = {}
        self.index_hostgroups = {}
        self.hosts = {}
        # self.hosts = Hosts([])
        self.inp_hosts = {}


    def load_external_queue(self, from_q):
        self.from_q = from_q


    def manage_brok(self, brok):
        manage = getattr(self, 'manage_' + brok.type + '_brok', None)
        if manage:
            return manage(brok)


    def manage_program_status_brok(self, b):
        data = b.data
        c_id = data['instance_id']
        print 'TECH manage_program_status_brok'
        logger.info("[TECHRG] manage_program_status_brok")
        self.inp_hosts[c_id] = {}


    def manage_initial_host_status_brok(self, b):
        data = b.data
        hname = data['host_name']
        inst_id = data['instance_id']
        customs = data.get('customs', {})

        # print 'TECH manage_initial_host_status_brok', data
        if not self._want_host(data):
            return

        try:
            inp_hosts = self.inp_hosts[inst_id]
        except Exception, exp:  # not good. we will cry in theprogram update
            print "Not good!", exp
            return

        
        # print 'TECH h', h, data['id']
        inp_hosts[data['id']] = h

        h = Cpe(data)
        self.index_hosts[data['host_name']] = h
        if 'cpe' in data['hostgroups']:
            for k in h.cpekeys:
                self.index_hosts[getattr(h, k)] = h
            if self.filter_by_fields:
                for k in self.filter_by_fields:
                    # print 'TECH k', getattr(h, k), h
                    self.index_hosts[getattr(h, k)] = h



    def _want_host(self, data):
        if self.filter_by_techs:
            return '_TECH' in data['customs'] and data['customs'].get('_TECH') in self.filter_by_techs

        elif self.filter_by_fields:
            for f in self.filter_by_fields:
                if 'customs' in data and '_'+f.upper() in data['customs']:
                    return True
            return False

        return True


    def manage_initial_service_status_brok(self, b):
        data = b.data
        hname = data['host_name']
        sdesc = data['service_description']
        soutput = data['output']

        print 'TECH manage_initial_service_status_brok', hname, sdesc, soutput
        # if hname.startswith('cmts'):
        #     print 'TECH manage_initial_service_status_brok', hname, sdesc, soutput


    def manage_initial_broks_done_brok(self, b):
        inst_id = b.data['instance_id']
        print "TECH manage_initial_broks_done_brok of instance", inst_id, len(self.index_hosts)
        logger.info("[TECHRG] LEAK manage_initial_broks_done_brok inst_id=%s total_size=%s", inst_id, total_size(self.index_hosts))

        try:
            inp_hosts = self.inp_hosts[inst_id]
        except Exception, exp:
            logger.error("[TECHRG] Warning all done: %s" % exp)
            return

        # for hid in inp_hosts:
        #     print 'h', hid, inp_hosts[hid]

        del self.inp_hosts[inst_id]


    def manage_update_program_status_brok(self, b):
        print 'TECH manage_update_program_status_brok'


    def manage_update_host_status_brok(self, b):
        data = b.data
        logger.info("[TECHRG] LEAK manage_update_host_status_brok %s %s", data['host_name'], data['state'])
        hname = data['host_name']
        h = self.index_hosts.get(hname)
        if h:
            h.state = data['state']


    def manage_update_service_status_brok(self, b):
        data = b.data
        hname = data['host_name']
        sdesc = data['service_description']
        soutput = data['output']
        logger.info("[TECHRG] LEAK manage_update_service_status_brok %s %s %s", hname, sdesc, soutput)


    def get_host(self, key):
        return self.index_hosts.get(key)



if __name__ == '__main__':
    rg = TechRegenerator(filter_by_fields=('pppoe_username',))
    rg._want_host({_})