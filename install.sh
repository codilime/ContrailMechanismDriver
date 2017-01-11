#!/bin/sh

type crudini &> /dev/null || { echo "Missing 'crudini' command!"; exit 2; }

install_contrail_api()
{
	echo "Installing contrail-python-api ..."
	cd /tmp
	git clone https://github.com/Juniper/contrail-python-api
	cd contrail-python-api
	sudo python setup.py install
}

append_value()
{
	str="$1"
	val="$2"
	sep=''
	[ -z $str ] || sep=','
	echo $str$sep$val
}

ML2_conf='/etc/neutron/plugins/ml2/ml2_conf.ini'
sudo mkdir -p "`dirname $ML2_conf`"
[ ! -e "$ML2_conf" ] && { echo "Configuration file ($ML2_conf) does not exist! Can't continue :/ - You need to enable ML2 plugin first!"; exit 2; }
m_drivers=`sudo crudini --get "$ML2_conf" ml2 mechanism_drivers`
echo "$m_drivers" | grep -q 'contrail_dirver' || sudo crudini --set "$ML2_conf" ml2 mechanism_drivers "`append_value $m_drivers contrail_dirver`" 
sudo crudini --set /opt/stack/neutron/neutron.egg-info/entry_points.txt neutron.ml2.mechanism_drivers contrail_dirver neutron.plugins.ml2.drivers.contrail_dirver:ConglMechanismDriver

python -c 'import pycontrail.client' || install_contrail_api

