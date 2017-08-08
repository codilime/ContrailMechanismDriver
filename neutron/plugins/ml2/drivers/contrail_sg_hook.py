from neutron.callbacks import registry, resources, events
from neutron.db.db_base_plugin_v2 import NeutronDbPluginV2
from neutron.db.securitygroups_db import SecurityGroupDbMixin
from neutron.extensions.securitygroup import (
    SecurityGroupNotFound, SecurityGroupRuleNotFound
)
try:
    from neutron_lib import context as neutron_context
except:
    from neutron import context as neutron_context
from oslo_log import log

logger = log.getLogger(__name__)


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
