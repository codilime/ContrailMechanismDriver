#    Copyright 2016, Juniper Networks, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
from enum import Enum
import inspect
import netaddr
import sys
import time
import traceback

import requests
from vnc_api import vnc_api

from cfgm_common import exceptions as vnc_exc
# WARNING: Don't import from neutron_lib, it won't work!
from neutron.callbacks import registry, resources, events
from neutron.common.config import cfg
from neutron.db.db_base_plugin_v2 import NeutronDbPluginV2
from neutron.db.securitygroups_db import SecurityGroupDbMixin
from neutron.extensions.securitygroup import (
    SecurityGroupNotFound, SecurityGroupRuleNotFound
)
try:
    from neutron_lib import constants as n_const
except:
    from neutron.common import constants as n_const
try:
    from neutron_lib import context as neutron_context
except:
    from neutron import context as neutron_context
try:
    from neutron_lib.api.definitions import portbindings
except:
    from neutron.extensions import portbindings
try:
    from neutron_lib.exceptions import NeutronException, NetworkNotFound
except:
    from neutron.common.exceptions import NeutronException, NetworkNotFound
from neutron.plugins.ml2 import driver_api as api
from neutron_plugin_contrail.plugins.opencontrail.vnc_client import (
    sg_res_handler
)
from neutron_plugin_contrail.plugins.opencontrail.vnc_client import (
    sgrule_res_handler as sgrule_handler
)
from neutron_plugin_contrail.plugins.opencontrail.vnc_client import (
    subnet_res_handler
)
from neutron_plugin_contrail.plugins.opencontrail.vnc_client import (
    vmi_res_handler
)
from neutron_plugin_contrail.plugins.opencontrail.vnc_client import (
    vn_res_handler
)
from oslo_log import log
# from oslo_config import ocfg

group_contrail = cfg.OptGroup(name='ml2_driver_contrail',
                              title='Contrail controller details')
contrail_opts = [
    cfg.StrOpt('controller', default='127.0.0.1'),
    cfg.IntOpt('port', default=8082)
]

cfg.CONF.register_group(group_contrail)
cfg.CONF.register_opts(contrail_opts, group_contrail)

vnc_extra_opts = [
    cfg.BoolOpt('apply_subnet_host_routes', default=False),
    cfg.BoolOpt('multi_tenancy', default=False)
]

logger = log.getLogger(__name__)


def dump(obj):
    """Helper for logging objects."""
    objstr = ""
    for attr in dir(obj):
        objstr += ("@.%s = %s; " % (attr, getattr(obj, attr)))
    return objstr


def clear_null_keys(dic):
    """Remove all keys with None value from dict."""
    deleted_keys = []
    for key in dic.keys():
        if dic[key] is None:
            del dic[key]
            deleted_keys.append(key)
    return deleted_keys


def restore_null_keys(keys, dic):
    """ Set keys in dict to None """
    for key in keys:
        dic[key] = None


def get_dict_diff(base, update):
    """Return only dict with keys that differs from base."""
    diff = dict(update)
    for key in base.keys():
        if diff.get(key) == base[key]:
            del diff[key]
    return diff


class Hndl(Enum):
    """Enum for Contrail object handlers."""

    VirtualNetwork = 1
    Subnet = 2
    VMInterface = 3
    SecurityGroup = 4
    SGRule = 5


class ContrailSecurityGroupHook(NeutronDbPluginV2, SecurityGroupDbMixin):
    """Security Group Hook"""
    def __init__(self, sg_handler, rule_handler):
        """Setup Contrail Security Group Hook and subscribe to events related
        to security groups.

        :param sg_handler: An instance of SecurityGroupHandler.
        :param rule_handler: An instance of SecurityGroupRuleHandler.
        """
        self.sg_handler = sg_handler
        self.rule_handler = rule_handler
        self.listen()

    def listen(self):
        registry.subscribe(self.create_security_group,
                           resources.SECURITY_GROUP,
                           events.AFTER_CREATE)
        registry.subscribe(self.update_security_group,
                           resources.SECURITY_GROUP,
                           events.AFTER_UPDATE)
        registry.subscribe(self.delete_security_group,
                           resources.SECURITY_GROUP,
                           events.BEFORE_DELETE)
        registry.subscribe(self.create_security_group_rule,
                           resources.SECURITY_GROUP_RULE,
                           events.AFTER_CREATE)
        registry.subscribe(self.delete_security_group_rule,
                           resources.SECURITY_GROUP_RULE,
                           events.BEFORE_DELETE)

    def sync_group_rule(self, context, rule):
        try:
            self.delete_security_group_rule(None, None, None, context=context,
                                            security_group_rule_id=rule['id'])
        except SecurityGroupRuleNotFound:
            pass

        self.create_security_group_rule(None, None, None, context=context,
                                        security_group_rule=rule)

    def delete_group_rules(self, context, id):
        sg_obj = self.sg_handler.get_sg_obj(id)
        old_rules = self.rule_handler.security_group_rules_read(sg_obj)
        for rule in old_rules or []:
            self.rule_handler.resource_delete(context.to_dict(), rule['id'])

    def sync_group(self, context, group):
        logger.info("Syncing group: [name: %s, id: %s, tenant: %s]" % (
            group['name'], group['id'], group['tenant_id']))

        if group['tenant_id'] == '':
            return

        group['id'] = self.get_contrail_security_group_id(context,
                                                          group['id'])

        if self.does_security_group_exist(group['id']):
            self.update_security_group(None, None, None, context=context,
                                       security_group=group,
                                       security_group_id=group['id'])

            self.delete_group_rules(context, group['id'])

            for rule in group['security_group_rules']:
                self.sync_group_rule(context, rule)
        else:
            self.create_security_group(None, None, None, context=context,
                                       is_default=False, security_group=group)

    def sync_security_groups(self):
        logger.info("Syncing Security Groups with Contrail")

        context = neutron_context.get_admin_context()
        groups = self.get_security_groups(context)

        for group in groups:
            self.sync_group(context, group)

        logger.info("Finished syncing Security Groups with Contrail")

    def does_security_group_exist(self, uuid):
        try:
            self.sg_handler.resource_get(None, uuid)
            return True
        except SecurityGroupNotFound:
            return False

    def get_contrail_security_group_id(self, context, sg_id):
        if context is None:
            context = neutron_context.get_admin_context()
        group = self.get_security_group(context, sg_id)

        if group['name'] == 'default':
            project_id = group['tenant_id']
            return self.sg_handler._ensure_default_security_group_exists(project_id)

        return sg_id

    def create_security_group(self, resource, event, trigger, **kwargs):
        """Event executed when security group is created.

        :param resource: Always set to resources.SECURITY_GROUP.
        :param event: Always set to events.AFTER_CREATE.
        :param trigger: Caller which invoked hook.
        :param kwargs: Dictionary with keys: context, is_default, security_group.
        """
        context = kwargs['context']
        sg = kwargs['security_group']

        if kwargs['is_default']:
            self.sync_group(context, sg)
            return

        uuid = kwargs['security_group']['id']
        if self.does_security_group_exist(uuid):
            logger.error("Security group %s already exist, can't create" % str(uuid))
            return
        else:
            logger.debug("SecurityGroupNotFound %s" % uuid)

        # Security group have to be created manually because its uuid must
        # be the same on both OpenStack and Contrail endpoints
        contrail_sg = self.sg_handler._create_security_group(sg)
        sg_obj = self.sg_handler._security_group_neutron_to_vnc(sg, contrail_sg)
        sg_obj.uuid = uuid
        sg_uuid = self.sg_handler._resource_create(sg_obj)

        if sg_uuid != uuid:
            logger.error("Contrail UUID (%s) and Stack UUID (%s) doesn't match!" %
                (sg_uuid, uuid))
            raise ReferenceError(
                "SG _resource_create returned object withd different uuid:"
                " %s (expected was %s" % (sg_uuid, uuid))

        for rule in sg['security_group_rules']:
            self.create_security_group_rule(None, None, None, context=context,
                                            security_group_rule=rule)

    def update_security_group(self, resource, event, trigger, **kwargs):
        """Event executed when security group is updated.

        :param resource: Always set to resources.SECURITY_GROUP.
        :param event: Always set to events.AFTER_UPDATE.
        :param trigger: Caller which invoked hook.
        :param kwargs: Dictionary with keys: context, security_group,
                       security_group_id.
        """
        context = kwargs['context']
        sg = kwargs['security_group']
        self.sg_handler.resource_update(context, sg['id'], sg)

    def delete_security_group(self, resource, event, trigger, **kwargs):
        """Event executed when security group is deleted.

        :param resource: Always set to resources.SECURITY_GROUP.
        :param event: Always set to events.BEFORE_DELETE.
        :param trigger: Caller which invoked hook.
        :param kwargs: Dictionary with keys: context, security_group,
                       security_group_id.
        """
        context = kwargs['context']
        sg = kwargs['security_group_id']
        self.sg_handler.resource_delete(context, sg)

    def create_security_group_rule(self, resource, event, trigger, **kwargs):
        """Event executed when security group rule is created.

        :param resource: Always set to resources.SECURITY_GROUP_RULE.
        :param event: Always set to events.AFTER_CREATE.
        :param trigger: Caller which invoked hook.
        :param kwargs: Dictionary with keys: context, security_group_rule.
        """
        context = kwargs['context']
        rule = kwargs['security_group_rule']

        rule['security_group_id'] = self.get_contrail_security_group_id(
                                         context, rule['security_group_id'])

        if rule.get('protocol') is None:
            rule['protocol'] = 'any'

        if rule['remote_group_id'] is not None:
            rule['remote_group_id'] = self.get_contrail_security_group_id(
                                           context, rule['remote_group_id'])

        if (rule.get('remote_ip_prefix') is None
            and rule.get('remote_group_id') is None
            and rule.get('ethertype') == 'IPv4'):
            rule['remote_ip_prefix'] = '0.0.0.0/0'

        if (rule.get('remote_ip_prefix') is None
            and rule.get('remote_group_id') is None
            and rule.get('ethertype') == 'IPv6'):
            rule['remote_ip_prefix'] = '::/0'

        self.rule_handler.resource_create(context, rule)

    def delete_security_group_rule(self, resource, event, trigger, **kwargs):
        """Event executed when security group rule is deleted.

        :param resource: Always set to resources.SECURITY_GROUP_RULE.
        :param event: Always set to events.BEFORE_DELETE.
        :param trigger: Caller which invoked hook.
        :param kwargs: Dictionary with keys: context, security_group_id,
                                             security_group_rule_id.
        """
        context = kwargs['context'].to_dict()
        rule = kwargs['security_group_rule_id']

        self.rule_handler.resource_delete(context, rule)


class ContrailMechanismDriver(api.MechanismDriver):

    def initialize(self):
        logger.info("Initializing ConGl (Contrail Gluon) mechanism driver ...")

        logger.warn("Cfg is %s %d" % (cfg.CONF.ml2_driver_contrail.controller,
                                      cfg.CONF.ml2_driver_contrail.port))

        cfg.CONF.register_opts(vnc_extra_opts, 'APISERVER')
        admin_user = cfg.CONF.keystone_authtoken.admin_user
        admin_password = cfg.CONF.keystone_authtoken.admin_password
        admin_tenant_name = cfg.CONF.keystone_authtoken.admin_tenant_name
        try:
            api_srvr_ip = cfg.CONF.ml2_driver_contrail.controller
        except cfg.NoSuchOptError:
            logger.info("No controller address in config - using default")
            api_srvr_ip = "127.0.0.1"

        try:
            api_srvr_port = cfg.CONF.ml2_driver_contrail.port
        except cfg.NoSuchOptError:
            logger.info("No controller port in config - using default")
            api_srvr_port = 8082

        try:
            auth_host = cfg.CONF.keystone_authtoken.auth_host
        except cfg.NoSuchOptError:
            auth_host = "127.0.0.1"

        try:
            auth_protocol = cfg.CONF.keystone_authtoken.auth_protocol
        except cfg.NoSuchOptError:
            auth_protocol = "http"

        try:
            auth_port = cfg.CONF.keystone_authtoken.auth_port
        except cfg.NoSuchOptError:
            auth_port = "35357"

        try:
            auth_url = cfg.CONF.keystone_authtoken.auth_url
        except cfg.NoSuchOptError:
            auth_url = "/v2.0/tokens"

        try:
            auth_type = cfg.CONF.auth_strategy
        except cfg.NoSuchOptError:
            auth_type = "keystone"

        try:
            api_server_url = cfg.CONF.APISERVER.api_server_url
        except cfg.NoSuchOptError:
            api_server_url = "/"

        logger.info("Connecting to Contrail server %s : %s" %
                    (api_srvr_ip, api_srvr_port))

        connected = False
        while not connected:
            try:
                self._vnc_lib = vnc_api.VncApi(
                    admin_user,
                    admin_password,
                    admin_tenant_name,
                    api_srvr_ip,
                    api_srvr_port,
                    api_server_url,
                    auth_host=auth_host,
                    auth_port=auth_port,
                    auth_protocol=auth_protocol,
                    auth_url=auth_url,
                    auth_type=auth_type)
                connected = True
            except requests.exceptions.RequestException:
                time.sleep(3)

        self.handlers = {
            Hndl.VirtualNetwork: vn_res_handler.VNetworkHandler(self._vnc_lib),
            Hndl.Subnet: subnet_res_handler.SubnetHandler(self._vnc_lib),
            Hndl.VMInterface:
            vmi_res_handler.VMInterfaceHandler(self._vnc_lib),
            Hndl.SecurityGroup:
            sg_res_handler.SecurityGroupHandler(self._vnc_lib),
            Hndl.SGRule: sgrule_handler.SecurityGroupRuleHandler(self._vnc_lib)
        }

        self.security_hook = ContrailSecurityGroupHook(
            self.handlers[Hndl.SecurityGroup],
            self.handlers[Hndl.SGRule])
        self.security_hook.sync_security_groups()

    def create_network_precommit(self, context):
        """Allocate resources for a new network.

        :param context: NetworkContext instance describing the new
        network.

        Create a new network, allocating resources as necessary in the
        database. Called inside transaction context on session. Call
        cannot block.  Raising an exception will result in a rollback
        of the current transaction.
        """
        vnh = self.handlers[Hndl.VirtualNetwork]
        logger.info("Function '%s' context is: %s" %
                    (sys._getframe().f_code.co_name, dump(context)))
        vn_obj = vnh.neutron_dict_to_vn(vnh.create_vn_obj(context.current),
                                        context.current)
        # Force contrail to use same uuid as neutron (easier update/delete)
        vn_obj.uuid = context.current['id']
        net = self._vnc_lib.virtual_network_create(vn_obj)
        if vn_obj.router_external:
            fip_pool_obj = vnc_api.FloatingIpPool('floating-ip-pool', vn_obj)
            self._vnc_lib.floating_ip_pool_create(fip_pool_obj)
        logger.info("New network returned by contrail: %s" % dump(net))
        logger.info("Net object (%s) ((current is: %s)) is: %s" %
                    (type(vn_obj), type(context.current), dump(vn_obj)))

    def create_network_postcommit(self, context):
        """Create a network.

        :param context: NetworkContext instance describing the new
        network.

        Called after the transaction commits. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Raising an exception will
        cause the deletion of the resource.
        """
        logger.info("Function '%s' context is: %s" %
                    (sys._getframe().f_code.co_name, dump(context)))
        pass

    def update_network_precommit(self, context):
        """Update resources of a network.

        :param context: NetworkContext instance describing the new
        state of the network, as well as the original state prior
        to the update_network call.

        Update values of a network, updating the associated resources
        in the database. Called inside transaction context on session.
        Raising an exception will result in rollback of the
        transaction.

        update_network_precommit is called for all changes to the
        network state. It is up to the mechanism driver to ignore
        state or state changes that it does not know or care about.
        """
        logger.info("Function '%s' context is: %s" %
                    (sys._getframe().f_code.co_name, dump(context)))

        vnh = self.handlers[Hndl.VirtualNetwork]
        try:
            vn_obj = vnh.neutron_dict_to_vn(
                vnh._get_vn_obj_from_net_q(context.current), context.current)
        except NetworkNotFound:
            return
        except NeutronException:
            # Very ugly hack for bug in Contrail library which incorrectly
            # reports exceptions. The bug occurs in vn_res_handler.py placed
            # inside neutron_plugin_contrail library. Incorrect exception
            # is thrown in function _get_vn_obj_from_net_q, in file
            # neutron_plugin_contrail/plugins/opencontrail/vnc_client/vn_res_handler.py,
            # line 238. If we haven't caught this exception, it's reraised.
            # We traverse stack trace to see if mentioned error happened
            # and check for specific keywords indicating where exception
            # was thrown
            trace = inspect.trace()
            for line in trace:
                if "vn_res_handler.py" in line[1] and line[3] == "_get_vn_obj_from_net_q":
                    return
            raise
        vnh._resource_update(vn_obj)

    def update_network_postcommit(self, context):
        """Update a network.

        :param context: NetworkContext instance describing the new
        state of the network, as well as the original state prior
        to the update_network call.

        Called after the transaction commits. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Raising an exception will
        cause the deletion of the resource.

        update_network_postcommit is called for all changes to the
        network state.  It is up to the mechanism driver to ignore
        state or state changes that it does not know or care about.
        """
        logger.info("Function '%s' context is: %s" %
                    (sys._getframe().f_code.co_name, dump(context)))
        pass

    def delete_network_precommit(self, context):
        """Delete resources for a network.

        :param context: NetworkContext instance describing the current
        state of the network, prior to the call to delete it.

        Delete network resources previously allocated by this
        mechanism driver for a network. Called inside transaction
        context on session. Runtime errors are not expected, but
        raising an exception will result in rollback of the
        transaction.

        This code is literally resource_delete method from
        VNetworkDeleteHandler class of contrail neutron plugin
        """
        logger.info("Function '%s' context is: %s" %
                    (sys._getframe().f_code.co_name, dump(context)))
        vnh = self.handlers[Hndl.VirtualNetwork]
        net_id = context.current['id']
        try:
            vn_obj = vn_res_handler.VNetworkGetHandler._resource_get(vnh,
                                                                     id=net_id)
        except vnc_api.NoIdError:
            return

        try:
            fip_pools = vn_obj.get_floating_ip_pools()
            for fip_pool in fip_pools or []:
                vnh._vnc_lib.floating_ip_pool_delete(id=fip_pool['uuid'])
            vn_res_handler.VNetworkDeleteHandler._resource_delete(vnh,
                                                                  id=net_id)
        except vnc_api.RefsExistError:
            vnh._raise_contrail_exception('NetworkInUse',
                                          net_id=net_id, resource='network')

    def delete_network_postcommit(self, context):
        """Delete a network.

        :param context: NetworkContext instance describing the current
        state of the network, prior to the call to delete it.

        Called after the transaction commits. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Runtime errors are not
        expected, and will not prevent the resource from being
        deleted.
        """
        logger.info("Function '%s' context is: %s" %
                    (sys._getframe().f_code.co_name, dump(context)))
        pass

    def subnet_resource_create(self, subnet_q):
        """Modified copy of SubnetCreateHandler.resource_create method.

        This modified version preserves subnet_uuid given from neutron
        """
        net_id = subnet_q['network_id']
        vn_obj = self.handlers[Hndl.Subnet]._resource_get(id=net_id)
        ipam_fq_name = subnet_q.get('contrail:ipam_fq_name')
        netipam_obj = self.handlers[Hndl.Subnet]._get_netipam_obj(ipam_fq_name,
                                                                  vn_obj)
        if not ipam_fq_name:
            ipam_fq_name = netipam_obj.get_fq_name()

        subnet_vnc = (
            subnet_res_handler.SubnetCreateHandler
            ._subnet_neutron_to_vnc(subnet_q)
        )
        logger.info("Changing subnet id from %s ==to==> %s" %
                    (subnet_vnc.subnet_uuid, subnet_q['id']))
        subnet_vnc.subnet_uuid = subnet_q['id']
        subnet_key = (
            subnet_res_handler.SubnetCreateHandler
            ._subnet_vnc_get_key(subnet_vnc, net_id)
        )

        # Locate list of subnets to which this subnet has to be appended
        net_ipam_ref = None
        ipam_refs = vn_obj.get_network_ipam_refs()
        for ipam_ref in ipam_refs or []:
            if ipam_ref['to'] == ipam_fq_name:
                net_ipam_ref = ipam_ref
                break

        if not net_ipam_ref:
            # First link from net to this ipam
            vnsn_data = vnc_api.VnSubnetsType([subnet_vnc])
            vn_obj.add_network_ipam(netipam_obj, vnsn_data)
        else:  # virtual-network already linked to this ipam
            for subnet in net_ipam_ref['attr'].get_ipam_subnets():
                if self.handlers[Hndl.Subnet].subnet_cidr_overlaps(subnet_vnc,
                                                                   subnet):
                    existing_sn_id = (
                        self.handlers[Hndl.Subnet]
                        ._subnet_vnc_read_mapping(
                            key=self.handlers[Hndl.Subnet]
                            ._subnet_vnc_get_key(subnet, net_id))
                    )
                    # duplicate !!
                    msg = (
                        ("Cidr %s overlaps with another subnet of subnet %s")
                        % (subnet_q['cidr'], existing_sn_id)
                    )
                    self._raise_contrail_exception('BadRequest',
                                                   resource='subnet', msg=msg)
            vnsn_data = net_ipam_ref['attr']
            vnsn_data.ipam_subnets.append(subnet_vnc)
            # TODO(): Add 'ref_update' API that will set this field
            vn_obj._pending_field_updates.add('network_ipam_refs')
        self.handlers[Hndl.Subnet]._resource_update(vn_obj)

        # Read in subnet from server to get updated values for gw etc.
        subnet_vnc = self.handlers[Hndl.Subnet]._subnet_read(subnet_key)
        subnet_info = self.handlers[Hndl.Subnet]._subnet_vnc_to_neutron(
            subnet_vnc, vn_obj, ipam_fq_name)
        return subnet_info

    def create_subnet_precommit(self, context):
        """Allocate resources for a new subnet.

        :param context: SubnetContext instance describing the new
        subnet.

        Create a new subnet, allocating resources as necessary in the
        database. Called inside transaction context on session. Call
        cannot block.  Raising an exception will result in a rollback
        of the current transaction.
        """
        logger.info("Function '%s' context is: %s" %
                    (sys._getframe().f_code.co_name, dump(context)))
        data = context.current
        # This is required because Contrail does not check if value for given
        # key is None, it checks only if key exists (eg. ipv6_address_mode key
        # exists when creating subnet)
        null_keys = clear_null_keys(data)
        self.subnet_resource_create(data)
        # Null keys must be restored, otherwise other plugins may fail and
        # will prevent network creation
        restore_null_keys(null_keys, data)

    def create_subnet_postcommit(self, context):
        """Create a subnet.

        :param context: SubnetContext instance describing the new
        subnet.

        Called after the transaction commits. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Raising an exception will
        cause the deletion of the resource.
        """
        logger.info("Function '%s' context is: %s" %
                    (sys._getframe().f_code.co_name, dump(context)))
        pass

    def update_subnet_precommit(self, context):
        """Update resources of a subnet.

        :param context: SubnetContext instance describing the new
        state of the subnet, as well as the original state prior
        to the update_subnet call.

        Update values of a subnet, updating the associated resources
        in the database. Called inside transaction context on session.
        Raising an exception will result in rollback of the
        transaction.

        update_subnet_precommit is called for all changes to the
        subnet state. It is up to the mechanism driver to ignore
        state or state changes that it does not know or care about.
        """
        logger.info("Function '%s' context is: %s" %
                    (sys._getframe().f_code.co_name, dump(context)))
        self.handlers[Hndl.Subnet].resource_update(
            None, context.current['id'],
            get_dict_diff(context.original, context.current))
        pass

    def update_subnet_postcommit(self, context):
        """Update a subnet.

        :param context: SubnetContext instance describing the new
        state of the subnet, as well as the original state prior
        to the update_subnet call.

        Called after the transaction commits. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Raising an exception will
        cause the deletion of the resource.

        update_subnet_postcommit is called for all changes to the
        subnet state.  It is up to the mechanism driver to ignore
        state or state changes that it does not know or care about.
        """
        logger.info("Function '%s' context is: %s" %
                    (sys._getframe().f_code.co_name, dump(context)))
        pass

    def delete_subnet_precommit(self, context):
        """Delete resources for a subnet.

        :param context: SubnetContext instance describing the current
        state of the subnet, prior to the call to delete it.

        Delete subnet resources previously allocated by this
        mechanism driver for a subnet. Called inside transaction
        context on session. Runtime errors are not expected, but
        raising an exception will result in rollback of the
        transaction.
        """
        logger.info("Function '%s' context is: %s" %
                    (sys._getframe().f_code.co_name, dump(context)))

        self.handlers[Hndl.Subnet].resource_delete(None, context.current['id'])

    def delete_subnet_postcommit(self, context):
        """Delete a subnet.

        :param context: SubnetContext instance describing the current
        state of the subnet, prior to the call to delete it.

        Called after the transaction commits. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Runtime errors are not
        expected, and will not prevent the resource from being
        deleted.
        """
        logger.info("Function '%s' context is: %s" %
                    (sys._getframe().f_code.co_name, dump(context)))
        pass

    def clean_port_dict(self, port_q):
        keys = ['binding:profile', 'binding:vif_details']
        for key in keys:
            if key in port_q:
                if not port_q[key]:
                    del port_q[key]
        return port_q

    def port_resource_create(self, port_q):
        port_q = port_q.copy()
        port_q = self.clean_port_dict(port_q)
        if 'network_id' not in port_q or 'tenant_id' not in port_q:
            raise self._raise_contrail_exception(
                'BadRequest', resource='port',
                msg="'tenant_id' and 'network_id' are mandatory")

        net_id = port_q['network_id']
        try:
            vn_obj = self.handlers[Hndl.VirtualNetwork].get_vn_obj(id=net_id)
        except vnc_exc.NoIdError:
            self.handlers[Hndl.VirtualNetwork]._raise_contrail_exception(
                'NetworkNotFound', net_id=net_id, resource='port')

        vmih = self.handlers[Hndl.VMInterface]

        # DIRTY TEMPORARY HACKS - XXX
        # DIRTY TEMPORARY HACKS - XXX
        neutron_context = {'is_admin': False, 'tenant': port_q['tenant_id']}
        # DIRTY TEMPORARY HACKS - XXX
        # DIRTY TEMPORARY HACKS - XXX
        tenant_id = vmih._get_tenant_id_for_create(neutron_context, port_q)
        proj_id = vmih._project_id_neutron_to_vnc(tenant_id)

        # if mac-address is specified, check against the exisitng ports
        # to see if there exists a port with the same mac-address
        if 'mac_address' in port_q:
            vmih._validate_mac_address(proj_id, net_id, port_q['mac_address'])

        # Check and translate security group
        sec_group_list = port_q.get('security_groups', [])
        logger.info("All needed SG %s" % sec_group_list)
        sec_group_list = [
            self.security_hook.get_contrail_security_group_id(None, group)
            for group in sec_group_list
        ]
        port_q['security_groups'] = sec_group_list
        logger.info("Translated SG %s" % sec_group_list)

        for sg_id in sec_group_list:
            logger.info("Checking SG: %s" % (sg_id))
            try:
                self.handlers[Hndl.SecurityGroup].resource_get(None, sg_id)
                logger.info("SG: %s checked" % (sg_id))
            except Exception as e:
                logger.info("Exception caught during SG (%s) read: %s" %
                            (sg_id, e))
                raise

        logger.info("All SG: OK")

        # initialize port object
        vmi_obj = vmih._create_vmi_obj(port_q, vn_obj)
        vmi_obj = vmih._neutron_port_to_vmi(port_q, vmi_obj=vmi_obj)
        vmi_obj.uuid = port_q['id']

        # determine creation of v4 and v6 ip object
        ip_obj_v4_create = False
        ip_obj_v6_create = False
        fixed_ips = []
        ipam_refs = vn_obj.get_network_ipam_refs() or []
        for ipam_ref in ipam_refs:
            subnet_vncs = ipam_ref['attr'].get_ipam_subnets()
            for subnet_vnc in subnet_vncs:
                cidr = '%s/%s' % (subnet_vnc.subnet.get_ip_prefix(),
                                  subnet_vnc.subnet.get_ip_prefix_len())
                if not ip_obj_v4_create and (
                        netaddr.IPNetwork(cidr).version == 4):
                    ip_obj_v4_create = True
                    fixed_ips.append(
                        {'subnet_id': subnet_vnc.subnet_uuid,
                         'ip_family': 'v4'})
                if not ip_obj_v6_create and (
                        netaddr.IPNetwork(cidr).version == 6):
                    ip_obj_v6_create = True
                    fixed_ips.append({'subnet_id': subnet_vnc.subnet_uuid,
                                      'ip_family': 'v6'})

        # create the object
        port_id = self.handlers[Hndl.VMInterface]._resource_create(vmi_obj)
        try:
            if 'fixed_ips' in port_q:
                self.handlers[Hndl.VMInterface]._create_instance_ips(
                    vn_obj, vmi_obj, port_q['fixed_ips'])
            elif vn_obj.get_network_ipam_refs():
                self.handlers[Hndl.VMInterface]._create_instance_ips(
                    vn_obj, vmi_obj, fixed_ips)
        except Exception as e:
            logger.error(
                "Got exception from contrail: %s  ---> %s" %
                (e, traceback.format_exception(*sys.exc_info())))
            # failure in creating the instance ip. Roll back
            self.handlers[Hndl.VMInterface]._resource_delete(id=port_id)
            raise e

        # TODO() below reads back default parent name, fix it
        vmi_obj = self.handlers[Hndl.VMInterface]._resource_get(
            id=port_id, fields=['instance_ip_back_refs'])
        self.handlers[Hndl.VMInterface]._vmi_to_neutron_port(vmi_obj)

    def create_port_precommit(self, context):
        """Allocate resources for a new port.

        :param context: PortContext instance describing the port.

        Create a new port, allocating resources as necessary in the
        database. Called inside transaction context on session. Call
        cannot block.  Raising an exception will result in a rollback
        of the current transaction.
        """
        logger.info(
            "Function '%s' context is: %s" %
            (sys._getframe().f_code.co_name, dump(context)))

        # DIRTY TEMPORARY HACKS - XXX:
        # There is a bug in neutron which causes port creation failure:
        # https://bugs.launchpad.net/neutron/+bug/1464806
        # Contrail expects tenant_id to be non-empty because it's used
        # to get a project UUID. We applied workaround proposed here:
        # https://bugs.launchpad.net/networking-odl/+bug/1464807
        # We set port's tenant_id to tenant_id of network present in context
        if context.current['tenant_id'] == '':
            logger.debug('create_port_precommit: tenant_id is empty')
            context.current['tenant_id'] = context._network_context._network['tenant_id']

        self.port_resource_create(context.current)

    def create_port_postcommit(self, context):
        """Create a port.

        :param context: PortContext instance describing the port.

        Called after the transaction completes. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance.  Raising an exception will
        result in the deletion of the resource.
        """
        logger.info(
            "Function '%s' context is: %s" %
            (sys._getframe().f_code.co_name, dump(context)))
        pass

    def update_port_precommit(self, context):
        """Update resources of a port.

        :param context: PortContext instance describing the new
        state of the port, as well as the original state prior
        to the update_port call.

        Called inside transaction context on session to complete a
        port update as defined by this mechanism driver. Raising an
        exception will result in rollback of the transaction.

        update_port_precommit is called for all changes to the port
        state. It is up to the mechanism driver to ignore state or
        state changes that it does not know or care about.
        """
        logger.info(
            "Function '%s' context is: %s" %
            (sys._getframe().f_code.co_name, dump(context)))
        vmih = self.handlers[Hndl.VMInterface]
        vmih.resource_update(
            None,
            context.current['id'],
            get_dict_diff(context.original,
                          context.current))
        pass

    def update_port_postcommit(self, context):
        """Update a port.

        :param context: PortContext instance describing the new
        state of the port, as well as the original state prior
        to the update_port call.

        Called after the transaction completes. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance.  Raising an exception will
        result in the deletion of the resource.

        update_port_postcommit is called for all changes to the port
        state. It is up to the mechanism driver to ignore state or
        state changes that it does not know or care about.
        """
        logger.info(
            "Function '%s' context is: %s" %
            (sys._getframe().f_code.co_name, dump(context)))
        pass

    def delete_port_precommit(self, context):
        """Delete resources of a port.

        :param context: PortContext instance describing the current
        state of the port, prior to the call to delete it.

        Called inside transaction context on session. Runtime errors
        are not expected, but raising an exception will result in
        rollback of the transaction.
        """
        logger.info(
            "Function '%s' context is: %s" %
            (sys._getframe().f_code.co_name, dump(context)))
        self.handlers[Hndl.VMInterface].resource_delete(
            None, context.current['id'])
        pass

    def delete_port_postcommit(self, context):
        """Delete a port.

        :param context: PortContext instance describing the current
        state of the port, prior to the call to delete it.

        Called after the transaction completes. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance.  Runtime errors are not
        expected, and will not prevent the resource from being
        deleted.
        """
        logger.info(
            "Function '%s' context is: %s" %
            (sys._getframe().f_code.co_name, dump(context)))
        pass

    def bind_port(self, context):
        """Attempt to bind a port.

        :param context: PortContext instance describing the port

        Called inside transaction context on session, prior to
        create_port_precommit or update_port_precommit, to
        attempt to establish a port binding. If the driver is able to
        bind the port, it calls context.set_binding with the binding
        details.
        """
        logger.info(
            "Function '%s' context [%s] is: %s" %
            (sys._getframe().f_code.co_name, context.__class__.__name__,
             dump(context)))
        logger.info("Network is: %s" % (dump(context.network)))
        port_id = context.current['id']
        vmih = self.handlers[Hndl.VMInterface]
        vmi_obj = vmih._resource_get(id=port_id)
        vmih._set_vm_instance_for_vmi(vmi_obj, context.current['device_id'])

        vif_details = {portbindings.CAP_PORT_FILTER: True}

        for segment in context.segments_to_bind:
            context.set_binding(
                segment['id'],
                'vrouter',
                vif_details,
                n_const.PORT_STATUS_ACTIVE)
        pass
