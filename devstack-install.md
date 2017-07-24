# Installation guide - devstack scenario

## Scenario

This Installation and Configuration instruction will lead to working two-node
OpenStack+Contrail environment (with ContrailMechanismDriver enabled).

## Steps on devstack node

1. Install all dependencies listed in [README](./README.md)

2. Download devstack and put the following settings to `local.conf` (feel free to tune them):
	```
	[[local|localrc]]

	...

	Q_PLUGIN=ml2
	
	# Options below are optional
	CONTRAIL_DRIVER_CONTROLLER='127.0.0.1'
	CONTRAIL_DRIVER_PORT=8082
	NEUTRON_ENTRY_POINTS='/opt/stack/neutron/neutron.egg-info/entry_points.txt'
	
	# Obviously, You should include this:
	enable_plugin contrail-mechanism-driver https://github.com/zhtk/ContrailMechanismDriver.git
	```

3. Run `./stack.sh`

## Steps on contrail node

1. Install all dependencies listed in [README](./README.md)

2. Do everything listed in readme in section `Manual installation - (Separate Contrail node)`.
