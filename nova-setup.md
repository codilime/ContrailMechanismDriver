# Installing Nova with DevStack on compute node

1. Download DevStack repository:
	```sh
	git clone https://github.com/openstack-dev/devstack.git
	cd devstack
	```
2. Checkout to version matching your OpenStack deployment, for example:
	```sh
	git checkout stable/ocata
	```

3. Create `local.conf` with following contents:
	```
	[[local|localrc]]
	# IP of compute node
	HOST_IP=xxx.xxx.xxx.xxx
	# IP of OpenStack node
	SERVICE_HOST=yyy.yyy.yyy.yyy
	MULTI_HOST=1
	LOGFILE=/opt/stack/logs/stack.sh.log
	LOGDAYS=1
	ADMIN_PASSWORD=OpenStackPassword
	DATABASE_PASSWORD=$ADMIN_PASSWORD
	RABBIT_PASSWORD=$ADMIN_PASSWORD
	SERVICE_PASSWORD=$ADMIN_PASSWORD
	
	MYSQL_HOST=$SERVICE_HOST
	RABBIT_HOST=$SERVICE_HOST
	Q_HOST=$SERVICE_HOST
	
	# Placement-api is needed for OpenStack ocata and higher 
	ENABLED_SERVICES=n-cpu,neutron,placement-api 
	```

4. Run `stack.sh`.

5. When it finish you should have working compute node connected to
	OpenStack node.
