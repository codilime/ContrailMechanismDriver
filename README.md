ContrailMechanismDriver
=======================

Contrail ML2 Mechanism Driver for [Gluon](https://wiki.openstack.org/wiki/Gluon "Gluon wiki")

Installation
============

As a devstack plugin
--------------------
Make sure that devstack is installed with ML2 enabled by adding `Q_PLUGIN=ml2` to `local.conf`.
Enable Contrail and ContrailMechanismDriver by adding
```
enable_plugin contrail https://github.com/zioc/contrail-devstack-plugin.git
enable_plugin contrail-mechanism-driver https://github.com/codilime/ContrailMechanismDriver
```
to `local.conf` file in devstack.
Then siply run `./stack.sh`.

Manual installation
-------------------

The lazy soulution is to run `install.sh` script (it handles installation of required dependencies and all the configuration).

Dependencies
------------
* https://github.com/Juniper/contrail-python-api (installed automatically by devstack plugin)
```bash
git clone https://github.com/Juniper/contrail-python-api
cd contrail-python-api
sudo python setup.py install
```

Configuring ML2 mechanism driver
--------------------
* In file `/etc/neutron/plugins/ml2/ml2_conf.ini`
	* Make sure that in section *ml2* key *mechanism_drivers* have value **contrail_driver** in list
* In file `/opt/stack/neutron/neutron.egg-info/entry_points.txt`
	* In section *neutron.ml2.mechanism_drivers* set key *contrail_driver* to **neutron.plugins.ml2.drivers.contrail_driver:ContrailMechanismDriver**

Running
-------
Neutron service need to be restarted
