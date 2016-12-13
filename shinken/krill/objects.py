#!/usr/bin/python

import sys

from shinken.krill import auth

from collections import namedtuple
pots_data = namedtuple('pots_data', ['cpeid', 'cli', 'order', 'username', 'password', 'pbx_extension'])

# Cpe = namedtuple('Cpe', ['host_name'], verbose=True)


class Cpe(object):

    host_attributes_to_get = ('host_name', 'state', 'address', 'hostgroups', 'cpe_address', 'cpe_registration_host', 'cpe_registration_id', 'cpe_registration_state', 'cpe_registration_tags', 'cpe_connection_request_url', 'cpe_ipleases')

    bool_attribute_names = ('access', 'external_voip')
    int_attribute_names = ('cpe_id', 'customer_id')
    float_attribute_names = ('loc_lat', 'loc_lon')


    def __init__(self, data):

        for attr in self.host_attributes_to_get:
            setattr(self, attr, data[attr])

        self.potses = []
        num_voice_lines = int(data['customs'].get('_VOICESERVICENUMBEROFENTRIES', 0))
        for order in range(1, num_voice_lines+1):
            cli = data['customs'].get('_VOICE%d_CLI' % order)
            cli = int(cli) if cli and cli.isdigit() else 0
            # print 'data['customs'].get _CPE_ID', data['customs'].get('_CPE_ID')
            cpeid = data['customs'].get('_CPE_ID')
            cpeid = int(cpeid) if cpeid else 0
            pd = pots_data(
                cpeid=cpeid,
                cli=cli,
                order=order,
                username=data['customs'].get('_VOICE%d_USERNAME' % order),
                password=data['customs'].get('_VOICE%d_PASSWORD' % order),
                pbx_extension=bool(data['customs'].get('_VOICE%d_PBX_EXTENSION' % order)),
            )
            self.potses.append(pd)

        for k,v in data['customs'].iteritems():
            if not k.startswith('_VOICE'):
                trans_key = k[1:].lower()
                if trans_key in self.bool_attribute_names:
                    v = bool(int(v) if v else 0)
                if trans_key in self.int_attribute_names:
                    v = int(v) if v else 0
                if trans_key in self.float_attribute_names:
                    v = float(v) if v else 0
                setattr(self, trans_key, v)


    def get_groupnames(self):
        return self.hostgroups


    @property
    def cpekeys(self):
        ret = []
        if hasattr(self, 'mac') and self.mac:
            ret.append('mac')
        if hasattr(self, 'sn') and self.sn:
            ret.append('sn')
        if hasattr(self, 'dsn') and self.dsn:
            ret.append('dsn')
        return ret


    def __str__(self):
        return '%s %s %s (%s)' % (self.host_name, self.tech if hasattr(self, 'tech') else '??', self.state, self.hostgroups)


if __name__ == '__main__':
    host_data = {'last_time_unreachable': 0, 'childs': [], 'labels': [], 'action_url': '', 'last_problem_id': 0, 'cpe_address': '', 'comments': [], 'low_flap_threshold': 25, 'process_perf_data': True, 'icon_image': '', 'check_flapping_recovery_notification': True, 'last_state': 'DOWN', 'topology_change': False, 'my_own_business_impact': -1, 'display_name': u'olt', 'notification_interval': 1440, 'last_hard_state_change': 1480333018, 
        'failure_prediction_enabled': False, 'retry_interval': 1, 'event_handler_enabled': False, '3d_coords': '', 'parents': [], 'cpe_registration_id': '', 'last_state_update': 1480816389.931539, 'execution_time': 1.7434890270233154, 'start_time': 0, 'notifications_enabled': True, 'freshness_threshold': 0, 'alias': u'SnmpBooster-Host template', 'flapping_comment_id': 0, 'early_timeout': 0, 'in_scheduled_downtime': False, 'time_to_orphanage': 300, 'notes': '', 'flap_detection_enabled': True, 'instance_id': 0, 'long_output': u'', 'host_name': u'olt', 'timeout': 0, 'output': u'CRITICAL - Host Unreachable (10.42.10.10)', 'custom_views': [],
        'check_type': 0, 'source_problems': {'services': [], 'hosts': []}, 'last_event_id': 28, 
        'hostgroups': u'olt', 'problem_has_been_acknowledged': False, 'notes_url': '', 'last_state_type': 'HARD', 
        'contacts': [], 'notification_period': u'24x7', 'last_hard_state': 'DOWN', 'processed_business_rule': '', 'retain_status_information': True, 'business_rule_downtime_as_ack': False, 
        'stalking_options': [''], 'state': 'DOWN', 'business_rule_host_notification_options': [], 'end_time': 0, 'tags': [u'generic-host', u'SnmpBooster-host'], 'snapshot_criteria': ['d', 'u'], 'retain_nonstatus_information': True, 'contact_groups': [u'noc', u'ispadmin'], 'vrml_image': '', 'address': u'10.42.10.10', '2d_coords': '', 'acknowledgement_type': 1, 'icon_set': '', 'business_impact': 4, 'max_check_attempts': 3, 'business_rule_service_notification_options': [], 
        'child_dependencies': {'services': [u'olt/cpu GTGO', u'olt/uplink', u'olt/onug-olt', u'olt/cpu SMXA'], 'hosts': []}, 'flapping_changes': [False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False], 
        'statusmap_image': '', 'percent_state_change': 0.0, 'current_notification_number': 0, 'escalations': [], 'cpe_registration_host': '', 'last_notification': 0.0, 'active_checks_enabled': True, 'check_period': u'24x7', 'parent_dependencies': {'services': [], 'hosts': []}, 'flap_detection_options': ['o', 'd', 'u'], 'last_state_id': 0, 'initial_state': '', 'first_notification_delay': 0, 'notification_options': [u'd', u'u', u'r', u'f'], 
        'has_been_checked': 1, 'pending_flex_downtime': 0, 'event_handler': None, 'obsess_over_host': False, 'state_type': 'HARD', 'cpe_registration_tags': '', 'state_type_id': 1, 'scheduled_downtime_depth': 0, 'in_checking': True, 'last_state_change': 1480332903.409573, 'is_problem': False, 'duration_sec': 483486.52196598053, 'high_flap_threshold': 50, 'check_interval': 5, 'state_id': 1, 'perf_data': u'', 'check_freshness': False, 'is_impact': False, 'impacts': {'services': [], 'hosts': []}, 'icon_image_alt': '', 
        'checkmodulations': [], 'should_be_scheduled': 1, 'id': '6a654d68b9c411e6843d5254000d0ebe', 'maintenance_period': '', 'realm': u'All', 'current_event_id': 38, 'passive_checks_enabled': True, 'trending_policies': [], 'next_chk': 1480816451, 'last_chk': 1480816387, 'current_notification_id': 0, 'last_snapshot': 0, 'cpe_connection_request_url': '', 'initial_output': '', 'latency': 1.354917049407959, 'return_code': 2, 
        'customs': {u'_MODEL': u'C320', u'_SYS_LOCATION': u'default', u'_SNMPCOMMUNITYREAD': u'krillrw', u'_TECH': u'gpon', u'_NOCONCURRENCY': u'0', u'_SNMPVERSION': u'2',         u'_USEBULK': u'0', u'_MAXOIDREQUEST': u'20', u'_SNMPCOMMUNITYWRITE': u'krillrw'}, 
        'in_maintenance': None, 'is_flapping': False, 
        'business_rule_smart_notifications': False, 'attempt': 3, 'downtimes': [], 'last_time_down': 1480816389, 'modified_attributes': 0L, 
        'last_time_up': 1480332597, 'current_problem_id': 19, 'cpe_registration_state': '', 
        'got_business_rule': False, 'last_hard_state_id': 1, 'business_rule_output_template': ''}

    cpe = Cpe(host_data)
    print cpe
