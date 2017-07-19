ContrailMechanismDriver
=======================

Contrail ML2 Mechanism Driver for [Gluon](https://wiki.openstack.org/wiki/Gluon "Gluon wiki")

Dependencies
============

Contrail node
-------------

* https://github.com/Juniper/contrail-python-api
	```sh
	git clone https://github.com/Juniper/contrail-python-api
	cd contrail-python-api
	sudo python setup.py install
	```

* https://github.com/openstack/neutron
	```sh
	git clone https://github.com/openstack/neutron
	sudo pip install ./neutron
	```
* https://github.com/openstack/nova - for launching VMs on Contrail node
	```sh
	git clone https://github.com/openstack/nova
	sudo pip install ./nova
	```

OpenStack node
--------------

* `vnc_api` and `cfgm_common`. They are not available as standalone packages, so the best idea is to search for
	`api-lib/dist/vnc_api-0.1.dev0.tar.gz` and `config/common/dist/cfgm_common-0.1.dev0.tar.gz` in
	your Contrail build directory and then copy these files to OpenStack server. Then issue
	```sh
	sudo pip install vnc_api-0.1.dev0.tar.gz
	sudo pip install cfgm_common-0.1.dev0.tar.gz
	```

* https://github.com/Juniper/contrail-neutron-plugin
	```sh
	git clone https://github.com/Juniper/contrail-neutron-plugin.git
	sudo pip install ./contrail-neutron-plugin
	```

Installation
============

Prerequisites
-------------
In order to ContrailMechanismDriver to work correctly, you will need operational **OpenStack** node with Gluon installed.

There are two possible use cases.
* All-in-one installation - Contrail is on same node as OpenStack
* Contrail on separate node (this is preferred option)

Manual installation - (Separate Contrail node)
----------------------------------------------
_Note:_ `CONTRAIL_SRC_DIR` _is_ `/opt/stack/contrail` _when using_ **Contrail-installer**

1. Install Contrail
	If you don't have Contrail binary packages you can compile it from sources. Probably the easiest way is to use [Contrail-installer](https://github.com/Juniper/contrail-installer)

	_Please note that it is not guaranteed that contrail-installer install all needed dependant libraries. Below list presents libraries neede by Contrail and not installed by contrail-installer._
	
	Libraries (via apt-get install):
	* libcrypto++-dev
	* libev4
	* libev-dev
	* libffi-dev
	
	Python modules (pip install):
	* fixtures
	* 'bitarray>=0.8.0'
	* 'pycassa>=1.7.2'
	* 'MarkupSafe>=1.0'
	* kazoo
2. Install neutron-libraries - use: https://github.com/openstack/neutron
	Those libraries are not distributed separately so best way to have them is to install neutron itself.
3. Configure contrail to use **keystone** from **OpenStack node**
	* In Contrail configuration files replace all occurences of `auth_host` and `auth_url` to refer **keystone** service running on **OpenStack node**.
	* In file `$CONTRAIL_SRC_DIR/contrail-web-core/config/config.global.js` replace entry `config.identityManager.ip` to point to **OpenStack node**
	* In file `$CONTRAIL_SRC_DIR/contrail-web-core/config/config.global.js` replace entry `config.featurePkg.webController.path` to `'$CONTRAIL_SRC_DIR/contrail-web-controller';`
4. Verify that Contrail is working correctly
5. Install [contrail-python-api](https://github.com/Juniper/contrail-python-api)

_Note:_ There is experimental script that tries to install Contrail as a standalone node. Script is located in [contrail-install.sh](./util/contrail-install.sh).

As a devstack plugin - (All-in-one installation)
------------------------------------------------
_Please note that installing Contrail as a devstack plugin means that Contrail will be Core plugin for OpenStack which will prevent Gluon from working correctly._
Devstack is avaliable here: https://github.com/openstack-dev/devstack
Dependencies will be installed automatically.
Make sure that devstack is installed with ML2 enabled by adding `Q_PLUGIN=ml2` to `local.conf`.
Enable Contrail and ContrailMechanismDriver by adding
```
enable_plugin contrail https://github.com/zioc/contrail-devstack-plugin.git
enable_plugin contrail-mechanism-driver https://github.com/codilime/ContrailMechanismDriver
```
to `local.conf` file in devstack.
Then siply run `./stack.sh`.

Manual installation - (All-in-one installation)
-----------------------------------------------

The lazy soulution is to run `install.sh` script (it handles installation of required dependencies and all the configuration).

Configuration
=============

Configuring ML2 mechanism driver
--------------------
**On OpenStack node**
* In file `/etc/neutron/plugins/ml2/ml2_conf.ini`
	* Make sure that in section *ml2* key *mechanism_drivers* have value **contrail_driver** in list
	* Add section `ml2_driver_contrail` and point to contrail controller node:
		- key *controller* should contain Contrail controller address (default: 127.0.0.1)
		- key *port* should point to Contrail controller listen port (default: 8082)
* Make sure that neutron-server reads `ml2_conf.ini` file during startup (this might require to modify `/etc/init.d/neutron-server` file and add `--config-file=/etc/neutron/plugins/ml2/ml2_conf.ini` to **DAEMON_ARGS** variable
* In file `entry_points.txt` (location depends on neutron version and OpenStack installation method) in section *neutron.ml2.mechanism_drivers* set key *contrail_driver* to **neutron.plugins.ml2.drivers.contrail_driver:ContrailMechanismDriver**
	* For Fuel based installations: /usr/lib/python2.7/dist-packages/neutron-<version>.egg-info/entry_points.txt
	* For devstack based installations: /opt/stack/neutron/neutron.egg-info/entry_points.txt

Running
=======

Neutron service need to be restarted

* For **devstack** another config file must be supplied to neutron by adding `--config-file /etc/neutron/plugins/ml2/ml2_conf.ini` to commandline
