Setup development VMs using Ansible playbooks
=============================================


Initial steps required by both VMs
----------------------------------

1. Add ssh keys to *known\_hosts* for both VMs:

```
ssh-keyscan <VM IP address> >> ~/.ssh/known_hosts
```


2. Setup ssh trust communication and install basic dependencies using *init\_vms* playbook

```
ansible-playbook -i inventory/hosts init_vms.yml --extra-vars “group=<host_group>”
```

* for OpenContrail VM use group *contrail*
* for Devstack VM use group *openstack*


**Notice:**
If Devstack VM is installed on Ubuntu 16.04 be sure to take this steps before running VM init playbook:

```
ansible openstack -i inventory/hosts --sudo -m raw -a 'sed -i_bak "s/\(nameserver\) .*/\1 8\.8\.8\.8/" /etc/resolv.conf'
ansible openstack -i inventory/hosts --sudo -m raw -a "apt install -y python-minimal"
```


Setup OpenContrail VM
---------------------

Run *contrail\_vm* playbook (it could take few hours to finish):

```
ansible-playbook -i inventory/hosts contrail_vm.yml
```


Setup Devstack VM
-----------------

Run *openstack\_vm* playbook as follows (it will also take a while):

```
ansible-playbook -i inventory/hosts openstack_vm.yml
```

