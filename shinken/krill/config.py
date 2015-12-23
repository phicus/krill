#!/usr/bin/python

from shinken.objects.config import Config
from shinken.daemons.arbiterdaemon import Arbiter

class ConfigParser(object):

    def __init__(self):
        self.conf = Config()
        buf = self.conf.read_config(['/etc/shinken/shinken.cfg'])
        self.raw_objects = self.conf.read_config_buf(buf)

        self.conf.create_objects_for_type(self.raw_objects, 'arbiter')
        self.conf.create_objects_for_type(self.raw_objects, 'module')
        self.conf.early_arbiter_linking()

        if len(self.conf.arbiters) == 1:
            self.arbdaemon = Arbiter(
                config_files=[''],
                is_daemon=[''],
                do_replace=False,
                verify_only=False,
                debug=None,
                debug_file=None,
                arb_name='arbtest'
            )
            self.arbdaemon.modules_dir = '/var/lib/shinken/modules/'
            self.arbdaemon.load_modules_manager()

            me = None
            for arb in self.conf.arbiters:
                me = arb
                self.arbdaemon.modules_manager.set_modules(arb.modules)
                self.arbdaemon.do_load_modules()
                self.arbdaemon.load_modules_configuration_objects(self.raw_objects)

        self.conf.create_objects(self.raw_objects)
        self.conf.instance_id = 0
        self.conf.instance_name = 'test'


        # Hack push_flavor, that is set by the dispatcher
        self.conf.push_flavor = 0
        self.conf.load_triggers()
        #import pdb;pdb.set_trace()
        self.conf.linkify_templates()
        #import pdb;pdb.set_trace()
        self.conf.apply_inheritance()
        #import pdb;pdb.set_trace()
        self.conf.explode()
        #print "Aconf.services has %d elements" % len(self.conf.services)
        self.conf.apply_implicit_inheritance()
        self.conf.fill_default()
        self.conf.remove_templates()
        self.conf.compute_hash()
        #print "conf.services has %d elements" % len(self.conf.services)
        self.conf.override_properties()
        self.conf.linkify()
        self.conf.apply_dependencies()
        self.conf.set_initial_state()
        self.conf.explode_global_conf()
        self.conf.propagate_timezone_option()
        self.conf.create_business_rules()
        self.conf.create_business_rules_dependencies()
        self.conf.is_correct()
        if not self.conf.conf_is_correct:
            print "The conf is not correct, I stop here"
            self.conf.dump()
            return
        self.conf.clean()

        self.arbdaemon.conf = self.conf


    def get_module_conf(self, module_type):
        for i in self.raw_objects['module']:
            if module_type in i['module_type']:
                return i
