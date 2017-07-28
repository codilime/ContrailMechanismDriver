# Installation guide - installing OpenStack using DevStack

## Scenario

This Installation and Configuration instruction will lead to working
OpenStack environment (with ContrailMechanismDriver enabled).

## Steps on OpenStack node

1. Install all dependencies listed in [README](./README.md)

2. Download [DevStack](https://github.com/openstack-dev/devstack) and put
	the following settings to `local.conf` (feel free to tune them):
	```
	[[local|localrc]]

	...

	Q_PLUGIN=ml2
	
	# Options below are optional
	CONTRAIL_DRIVER_CONTROLLER='127.0.0.1'
	CONTRAIL_DRIVER_PORT=8082
	
	# Obviously, You should include this:
	enable_plugin contrail-mechanism-driver https://github.com/zhtk/ContrailMechanismDriver.git
	```

3. If You have defined your own `Q_ML2_PLUGIN_MECHANISM_DRIVERS` variable
	in `local.conf` then make sure, that `contrail_driver` doesn't appear
	inside. Otherwise you **will** face very strange errors and you will have to
	perform configuration manually.
	All configuration related to this mechanism driver will be done automatically
	during installation phase.

4. Run `./stack.sh`

5. Check if `contrail_driver` is loaded and no errors are visible.
	`cat /opt/stack/logs/q-svc.log | grep contrail_driver` should be
	sufficient.

Now you should have running OpenStack environment and **no further configuration
should be needed**.
