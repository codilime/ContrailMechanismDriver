#!/bin/bash

ThisDir=$(dirname "${BASH_SOURCE[0]}")

INSTALL_OPTIONAL=${INSTALL_OPTIONAL:-1}

check_crudini()
{
	type crudini &> /dev/null 
	return $?
}

assure_crudini()
{
	check_crudini || sudo apt-get install -y crudini || echo Warning! "Failed to install crudini :/"
	check_crudini || { echo "crudini is not avaliable - exitting!"; exit 2; }
}

update_sources()
{
	local update=0
	local Stamp=$(stat -c %Z /var/lib/apt/periodic/update-success-stamp) || update=1
	local Time=$(( ($(date +%s) - Stamp) /60 /60))
	[ $Time -gt 72 ] && update=1
	[ $update -eq 1 ] && sudo apt-get update
}

find_iface()
{
	# echo is to truncate any whitespace here
	# shellcheck disable=SC2046,SC2005
	echo $(ip addr | grep -E '(^[0-9]*:|inet )' | grep -B 1 "inet $1" | head -1 | cut -f 2 -d :)
}

FoundThisIP=$(ip route get 8.8.8.8 | sed '1 ! d; s/ *$//; s/.* //')
FoundIface=$(find_iface "$FoundThisIP")

ThisIp=${THIS_IP:-$FoundThisIP}
Iface=${IFACE:-$FoundIface}
KeystoneIP=${KEYSTONE_IP:-127.0.1.1}

echo "Will use:"
echo "Iface: $Iface"
echo "IP: $ThisIp"
echo "KeystoneIP: $KeystoneIP"
echo "Hit RETURN to continue (Ctrl+C - abort)"
read xxx || exit 1

gpg --keyserver pgp.mit.edu --recv-keys 749D6EEC0353B12C
gpg --export --armor 749D6EEC0353B12C | sudo apt-key add -
sudo add-apt-repository -y ppa:webupd8team/java
cd /tmp
update_sources
echo 'bad9a731639655118740bee119139c1ed019737ec802a630dd7ad7aab4309623 jdk-7u80-linux-x64.tar.gz' > jdk-7u80-linux-x64.tar.gz.sha256
NeedJavaTarball=0
[ ! -e /tmp/jdk-7u80-linux-x64.tar.gz ] && NeedJavaTarball=1
[ sha256sum -c jdk-7u80-linux-x64.tar.gz.sha256 ] || NeedJavaTarball=1
[ 1 -eq "$NeedJavaTarball" ] && wget http://ftp.osuosl.org/pub/funtoo/distfiles/oracle-java/jdk-7u80-linux-x64.tar.gz
echo oracle-java7-installer oracle-java7-installer/local select /tmp | sudo /usr/bin/debconf-set-selections
echo oracle-java7-installer shared/accepted-oracle-license-v1-1 select true | sudo /usr/bin/debconf-set-selections
sudo apt-get -y install oracle-java7-installer

UPDATE_KERNEL=0
uname -a | grep '3.13' || UPDATE_KERNEL=1
if [ $UPDATE_KERNEL -eq 1 ]; then
	echo "Hit RETURN to continue with updating kernel to 3.13-xxx"
	read xxx || exit 1
	sudo apt-get -y install linux-cloud-tools-3.13.0-116 linux-cloud-tools-3.13.0-116-generic linux-cloud-tools-common linux-headers-3.13.0-116 linux-headers-3.13.0-116-generic linux-image-3.13.0-116-generic linux-image-extra-3.13.0-116-generic linux-libc-dev:amd64 linux-tools-3.13.0-116 linux-tools-3.13.0-116-generic linux-tools-common
	sed -ibak -e 's/^GRUB_DEFAULT=0$/GRUB_DEFAULT="Advanced options for Ubuntu>Ubuntu, with Linux 3.13.0-116-generic"/' /etc/default/grub
	sudo update-grub
fi

sudo apt-get -y install git libcrypto++-dev libev4 libev-dev libffi-dev
sudo apt-get -y install python-pyparsing python-pip
[ "$INSTALL_OPTIONAL" = "1" ] && sudo apt-get -y install lnav
sudo apt-get -f -y install
sudo python -m pip install 'setuptools==33.1.0'
sudo pip install 'setuptools==33.1.0' fixtures 'bitarray>=0.8.0' 'pycassa>=1.7.2' 'MarkupSafe>=1.0' kazoo

cd
[ ! -d 'contrail-installer' ] && git clone https://github.com/Juniper/contrail-installer
cd contrail-installer/

if [ ! -e localrc ]; then
	cat > localrc <<-heredoc-EOF
	STACK_DIR=\$(cd \$(dirname \$0) && pwd)

	LOG_DIR=\$STACK_DIR/log/screens
	LOG=True
	DEBUG=True
	LOGFILE=\$STACK_DIR/log/contrail.log
	LOGDAYS=1
	USE_SCREEN=True

	KEYSTONE_IP=$KeystoneIP

	DATABASE_PASSWORD=admin
	RABBIT_PASSWORD=admin
	SERVICE_TOKEN=admin
	SERVICE_PASSWORD=admin
	ADMIN_PASSWORD=admin

	#set loglevel to 1/2/3 . Always stderr into logfile,console.
	#For LOG_LEVEL 1 stdout into logfile.
	#For LOG_LEVEL 2 stdout into logfile and xtrace commands into console.
	#For LOG_LEVEL 3 stdout and xtrace into logfile,console.

	LOG_LEVEL=3

	SERVICE_TIMEOUT=180
	SERVICE_HOST=localhost

	#use only when INSTALL_PROFILE=COMPUTE, provide IP of compute node
	#COMPUTE_HOST_IP=<IP of compute-node>

	INSTALL_PROFILE=ALL
	PHYSICAL_INTERFACE=$Iface

	# to get source code make it as False
	CONTRAIL_DEFAULT_INSTALL=False

	# default branch is master
	CONTRAIL_BRANCH=R3.0.3.x

	# to get the ppa packages uncomment
	LAUNCHPAD_BRANCH=r2.20

	# repo proto is https or (default) ssh. Leave commented for ssh
	CONTRAIL_REPO_PROTO=https

	# proto for openstack bits. Use HTTPS if git is firewalled
	GIT_BASE=https://github.com

	CASS_MAX_HEAP_SIZE=500M
	CASS_HEAP_NEWSIZE=100M

	# number of jobs used to build
	NB_JOBS=`cat /proc/cpuinfo | grep '^processor' | wc -l`

	# target of the build debug/production
	# TARGET=production

	CONTRAIL_VGW_INTERFACE=vgw
	CONTRAIL_VGW_PUBLIC_SUBNET=11.0.0.0/24
	CONTRAIL_VGW_PUBLIC_NETWORK=default-domain:demo:net:net
	heredoc-EOF
fi

./contrail.sh build
if [ $? -ne 0 ]; then
	[ -e /opt/stack/contrail/controller/src/analytics/SConscript ] && sed -i "s/AnalyticsEnv\.Prepend(LIBS=\['cpuinfo', *$/\0 'crypto', 'ssl',/" /opt/stack/contrail/controller/src/analytics/SConscript
	sudo python -m pip install 'setuptools==33.1.0'
	set -e
	./contrail.sh build;
	set +e
fi

set -e
./contrail.sh install
./contrail.sh configure
set +e

sudo apt-get -f -y install
assure_crudini
crudini --del /etc/contrail/contrail-control.conf CONFIGDB rabbitmq_password
crudini --del /etc/contrail/contrail-control.conf CONFIGDB rabbitmq_user
crudini --del /etc/contrail/contrail-control.conf CONFIGDB rabbitmq_server_list
crudini --del /etc/contrail/contrail-control.conf CONFIGDB config_db_server_list
crudini --del /etc/contrail/contrail-dns.conf CONFIGDB rabbitmq_password
crudini --del /etc/contrail/contrail-dns.conf CONFIGDB rabbitmq_user
crudini --del /etc/contrail/contrail-dns.conf CONFIGDB rabbitmq_server_list
crudini --del /etc/contrail/contrail-dns.conf CONFIGDB config_db_server_list
for i in testrepository python-neutronclient neutron-lib; do sudo pip install "$i"; done

if [ ! -d /opt/stack/neutron ]; then
	# For some reason neutron needs latest pip and simple "pip install -U pip" is not enugh
	python -m pip uninstall -y setuptools
	python -m pip uninstall -y distribute
	# the next command should FAIL now because the above should be uninstalled
	python -c "import pkg_resources"
	# reinstall stuff now
	python -m pip install -U --force-reinstall setuptools
	python -m pip install -U --force-reinstall pip
	# now check things work and are the same
	set -e
	python -m pip --version
	pip --version
	set +e

	cd /opt/stack
	sudo git clone https://github.com/openstack/neutron
	sudo pip install ./neutron
fi

cd
cd contrail-installer/
[ -x "$ThisDir/contrail-reconfig.sh" ] && AUTH_HOST="$KeystoneIP" sudo "$ThisDir/contrail-reconfig.sh"
./contrail.sh start

