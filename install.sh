#!/bin/bash

Functions="$(dirname "${BASH_SOURCE[0]}")/install_functions.sh"
[ ! -r "$Functions" ] && { echo "Cant read functions library : $Functions!"; exit 2; }
. "$Functions"

DEST=${DEST:-"/opt/stack"}
BakSuffix="-bak-$(date +%Y%m%d-%H%M%S)"
ThisIP=$(ip route get 8.8.8.8 | sed '1 ! d; s/ *$//; s/.* //')
NeutronMl2PluginConf="/etc/neutron/plugins/ml2/ml2_conf.ini"

CreateDefaultML2conf()
{
	cat > /tmp/ml2_conf.ini <<-heredoc-EOF
	[DEFAULT]

	debug = true
	verbose = true

	[ml2]
	extension_drivers = port_security
	path_mtu = 1500

	#
	# From neutron.ml2
	#

	# List of network type driver entrypoints to be loaded from the
	# neutron.ml2.type_drivers namespace. (list value)
	type_drivers = local,flat,vlan,gre,vxlan

	# Ordered list of network_types to allocate as tenant networks. The default
	# value 'local' is useful for single-box testing but provides no connectivity
	# between hosts. (list value)
	tenant_network_types = vlan

	# An ordered list of networking mechanism driver entrypoints to be loaded from
	# the neutron.ml2.mechanism_drivers namespace. (list value)
	mechanism_drivers = openvswitch,linuxbridge,l2population

	[ml2_type_flat]

	[ml2_type_geneve]

	[ml2_type_gre]
	tunnel_id_ranges = 1:1000

	[ml2_type_vlan]
	network_vlan_ranges = mynetwork:100:200

	[ml2_type_vxlan]
	vni_ranges = 1001:2000

	[securitygroup]
	firewall_driver = neutron.agent.linux.iptables_firewall.OVSHybridIptablesFirewallDriver

	[agent]
	tunnel_types = gre
	root_helper_daemon = sudo /usr/local/bin/neutron-rootwrap-daemon /etc/neutron/rootwrap.conf
	root_helper = sudo /usr/local/bin/neutron-rootwrap /etc/neutron/rootwrap.conf

	[ovs]
	datapath_type = system
	tunnel_bridge = br-tun
	local_ip = $ThisIP
heredoc-EOF

	dir=$(dirname "$NeutronMl2PluginConf")
	[ ! -e "$dir" ] && sudo mkdir -p "$dir"
	sudo cp /tmp/ml2_conf.ini "$dir"
}

install_dependencies
install_plugin "$DEST"

NeutronConf="/etc/neutron/neutron.conf"
sudo cp "$NeutronConf" "$NeutronConf$BakSuffix"
crudini --del "$NeutronConf" DEFAULT api_extensions_path
crudini --set "$NeutronConf" DEFAULT service_plugins neutron.services.l3_router.l3_router_plugin.L3RouterPlugin
crudini --set --existing "$NeutronConf" DEFAULT core_plugin neutron.plugins.ml2.plugin.Ml2Plugin
crudini --del --existing "$NeutronConf" quotas quota_driver

if [ ! -e "$NeutronMl2PluginConf" ]; then
	CreateDefaultML2conf
else
	sudo cp "$NeutronMl2PluginConf" "$NeutronMl2PluginConf$BakSuffix"
fi


configure_plugin

