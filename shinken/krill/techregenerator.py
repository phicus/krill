#!/usr/bin/python
# -*- coding: utf-8 -*-

from shinken.objects.host import Host, Hosts
from shinken.util import safe_print


CPEKEY_BY_TECH = {
    'docsis': '_MAC',
    'wimax': '_MAC',
    'gpon': '_SN',
}

class TechCpe(object):
    def __init__(self, host_name, data, customs):
        self.host_name = host_name
        self.customs = {}
        for custom in customs:
            self.customs[custom] = data.get('customs', {}).get(custom)


class TechRegenerator(object):

    def __init__(self, tech, customs=[]):
        self.tech = tech
        self.customs = customs

        self.indices = {}
        self.hosts = Hosts([])

        self.inp_hosts = {}


    def load_external_queue(self, from_q):
        self.from_q = from_q


    def manage_brok(self, brok):
        manage = getattr(self, 'manage_' + brok.type + '_brok', None)
        if manage:
            return manage(brok)


    def update_element(self, e, data):
        for prop in data:
            setattr(e, prop, data[prop])


    def manage_program_status_brok(self, b):
        data = b.data
        c_id = data['instance_id']
        # print 'TECH manage_program_status_brok', b.data
        self.inp_hosts[c_id] = Hosts([])


    def manage_initial_host_status_brok(self, b):
        data = b.data
        hname = data['host_name']
        inst_id = data['instance_id']
        customs = data.get('customs', {})

        if customs.get('_TECH') == self.tech:
            key = CPEKEY_BY_TECH[self.tech]
            h = Host({})
            self.update_element(h, data)
            # safe_print("TECH Creating a host: %s/%s in instance %d" % (hname, data.get('hostgroups', 'hgs?'), inst_id))

            if key in customs:
                self.indices[customs.get(key).lower()] = TechCpe(hname, data, self.customs)

            try:
                inp_hosts = self.inp_hosts[inst_id]
            except Exception, exp:  # not good. we will cry in theprogram update
                print "Not good!", exp
                return
            # Ok, put in in the in progress hosts
            inp_hosts[h.id] = h


    def manage_host_check_result_brok(self, b):
        data = b.data
        # print 'TECH manage_host_check_result_brok', data['host_name'], data['state']
        self.manage_update_host_status_brok(b)


    def manage_update_host_status_brok(self, b):
        data = b.data
        # print 'TECH manage_update_host_status_brok', data['host_name'], data['state']
        hname = data['host_name']
        h = self.hosts.find_by_name(hname)
        if h:
            # print 'TECH manage_update_host_status_brok h!', h
            h.state = data['state']


    def manage_initial_broks_done_brok(self, b):
        inst_id = b.data['instance_id']
        print "TECH Finish the configuration of instance", inst_id
        self.all_done_linking(inst_id)


    def all_done_linking(self, inst_id):
        print "TECH all_done_linking", inst_id, self.inp_hosts
        try:
            inp_hosts = self.inp_hosts[inst_id]
        except Exception, exp:
            print "Warning all done: ", exp
            return

        for h in inp_hosts:
            # print "TECH add h", h
            self.hosts.add_item(h)

        # clean old objects
        del self.inp_hosts[inst_id]

if __name__ == '__main__':
    data = {'_LAT': 12, '_LNG':24}
    h = TechCpe('fake', data, ['_LAT', 'dummy'])
    print h._LAT, h.dummy