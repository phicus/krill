#!/usr/bin/python
# -*- coding: utf-8 -*-

from shinken.objects.host import Host, Hosts
from shinken.objects.hostgroup import Hostgroup, Hostgroups

from shinken.util import safe_print
from shinken.log import logger


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
        self.hostgroups = Hostgroups([])

        self.inp_hosts = {}
        self.inp_hostgroups = {}


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
        self.inp_hostgroups[c_id] = Hostgroups([])


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


    def manage_initial_hostgroup_status_brok(self, b):
        data = b.data
        hgname = data['hostgroup_name']
        inst_id = data['instance_id']

        # Try to get the inp progress Hostgroups
        try:
            inp_hostgroups = self.inp_hostgroups[inst_id]
        except Exception, exp:  # not good. we will cry in theprogram update
            logger.error("[regen] host_check_result:: Not good!   %s" % exp)
            return

        logger.debug("Creating a hostgroup: %s in instance %d" % (hgname, inst_id))

        # With void members
        hg = Hostgroup([])

        # populate data
        self.update_element(hg, data)

        # We will link hosts into hostgroups later
        # so now only save it
        inp_hostgroups[hg.id] = hg


    def manage_initial_broks_done_brok(self, b):
        inst_id = b.data['instance_id']
        print "TECH Finish the configuration of instance", inst_id
        self.all_done_linking(inst_id)


    def all_done_linking(self, inst_id):
        print "TECH all_done_linking", inst_id, self.inp_hosts
        try:
            inp_hosts = self.inp_hosts[inst_id]
            inp_hostgroups = self.inp_hostgroups[inst_id]
        except Exception, exp:
            print "Warning all done: ", exp
            return

        # Link HOSTGROUPS with hosts
        for hg in inp_hostgroups:
            new_members = []
            for (i, hname) in hg.members:
                h = inp_hosts.find_by_name(hname)
                if h:
                    new_members.append(h)
            hg.members = new_members

        # Merge HOSTGROUPS with real ones
        for inphg in inp_hostgroups:
            hgname = inphg.hostgroup_name
            hg = self.hostgroups.find_by_name(hgname)
            # If hte hostgroup already exist, just add the new
            # hosts into it
            if hg:
                hg.members.extend(inphg.members)
            else:  # else take the new one
                self.hostgroups.add_item(inphg)

        # Now link HOSTS with hostgroups, and commands
        print "TECH HOSTS?"
        for h in inp_hosts:
            print "TECH add h", h
            new_hostgroups = []
            for hgname in h.hostgroups.split(','):
                hgname = hgname.strip()
                hg = self.hostgroups.find_by_name(hgname)
                if hg:
                    new_hostgroups.append(hg)
            h.hostgroups = new_hostgroups

            self.hosts.add_item(h)

        # clean old objects
        del self.inp_hosts[inst_id]
        del self.inp_hostgroups[inst_id]
