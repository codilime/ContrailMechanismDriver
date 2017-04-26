#!/bin/bash

MainDir=$(dirname "${BASH_SOURCE[0]}")

append_value_colon()
{
	str="$1"
	val="$2"
	sep=''
	[ -z "$str" ] || sep=','
	echo "$str$sep$val"
}

install_dependencies()
{
	type crudini &> /dev/null || sudo apt-get -y install crudini

	python -c 'import pycontrail.client' && return # No need to install

	Dir="$PWD"
	cd /tmp
	git clone https://github.com/Juniper/contrail-python-api
	cd contrail-python-api
	sudo python setup.py install
	cd "$Dir"
}

install_plugin()
{
	[ -z "$1" ] && { echo "Missing argument for \`install_plugin' function: missing OpenStac install directory"; exit 2; }
	OpenStack="$1"
	{ date; echo "Copying plugin (whole dir: $MainDir/neutron) into $OpenStack"; ls -al "$MainDir/neutron"; } >> /tmp/congl.log; 
	
	sudo cp -dR "$MainDir/neutron" "$OpenStack"/
}

configure_plugin()
{
	ML2_conf='/etc/neutron/plugins/ml2/ml2_conf.ini'
	sudo mkdir -p "$(dirname "$ML2_conf")"
	[ ! -e "$ML2_conf" ] && { echo "Configuration file ($ML2_conf) does not exist! Can't continue :/ - You need to enable ML2 plugin first!"; exit 2; }
	m_drivers=$(sudo crudini --get "$ML2_conf" ml2 mechanism_drivers)
	echo "$m_drivers" | grep -q 'contrail_driver' || sudo crudini --set "$ML2_conf" ml2 mechanism_drivers "$(append_value_colon "$m_drivers" contrail_driver)" 
	sudo crudini --set /opt/stack/neutron/neutron.egg-info/entry_points.txt neutron.ml2.mechanism_drivers contrail_driver neutron.plugins.ml2.drivers.contrail_driver:ContrailMechanismDriver
}

