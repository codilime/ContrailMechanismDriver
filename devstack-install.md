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

3. Run `./stack.sh`

Now you should have running OpenStack environment and *no further configuration
is needed*.
