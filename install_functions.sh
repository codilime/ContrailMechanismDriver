#!/bin/bash

MainDir=$(dirname "${BASH_SOURCE[0]}")

append_value_colon()
{
	local str="$1"
	local val="$2"
	local sep=''
	[ -z "$str" ] || sep=','
	echo "$str$sep$val"
}

ini_add_if_not_exist()
{
	local IniFile="$1"
	local IniSection="$2"
	local IniKey="$3"
	local IniVal="$4"
	sudo crudini --get "$IniFile" "$IniSection" "$IniKey" || sudo crudini --set "$IniFile" "$IniSection" "$IniKey" "$IniVal"
}

locate_entry_points()
{
	local SearchDir='/usr/lib/python2.7/dist-packages'
	local LastVer=$(find "$SearchDir" -name 'neutron-*.egg-info' | sed 's@^.*/neutron-@@; s/\.egg-info$//;' | sort -n | tail -1)
	local EntryFile="$SearchDir/neutron-$LastVer.egg-info/entry_points.txt"
	echo "$EntryFile"
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
	[ -z "$1" ] && { echo "Missing argument for \`install_plugin' function: missing OpenStack install directory"; exit 2; }
	OpenStack="$1"
	{ date; echo "Copying plugin (whole dir: $MainDir/neutron) into $OpenStack"; ls -al "$MainDir/neutron"; } >> /tmp/congl.log;

	sudo cp -dR "$MainDir/neutron" "$OpenStack"/
	sudo cp -dR "$MainDir/neutron" "$OpenStack"/neutron
}

configure_plugin()
{
	ML2_conf='/etc/neutron/plugins/ml2/ml2_conf.ini'
	sudo mkdir -p "$(dirname "$ML2_conf")"
	[ ! -e "$ML2_conf" ] && { echo "Configuration file ($ML2_conf) does not exist! Can't continue :/ - You need to enable ML2 plugin first!"; exit 2; }
	m_drivers=$(sudo crudini --get "$ML2_conf" ml2 mechanism_drivers)
	echo "$m_drivers" | grep -q 'contrail_driver' || sudo crudini --set "$ML2_conf" ml2 mechanism_drivers "$(append_value_colon "$m_drivers" contrail_driver)" 
	ini_add_if_not_exist "$ML2_conf" ml2_driver_contrail controller '127.0.0.1'
	ini_add_if_not_exist "$ML2_conf" ml2_driver_contrail port 8082

	EntryPoints='/opt/stack/neutron/neutron.egg-info/entry_points.txt'
	[ ! -e "$EntryPoints" ] && EntryPoints=$(locate_entry_points)
	[ ! -e "$EntryPoints" ] && { echo "Can't find entry_points file: $EntryPoints - Aborting!"; exit 2; }
	[ ! -z "$BakSuffix" ] && sudo cp "$EntryPoints" "$EntryPoints$BakSuffix"
	sudo crudini --set "$EntryPoints" neutron.ml2.mechanism_drivers contrail_driver neutron.plugins.ml2.drivers.contrail_driver:ContrailMechanismDriver
}

