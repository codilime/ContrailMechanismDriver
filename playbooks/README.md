Setup development VMs using Ansible playbooks
=============================================

Variables used by configuration templates are stored in *group_vars* directory so be sure to adjust it according to your setup before running *site.yml* playbook.


Prerequisite
-------------
* If Devstack VM is installed on Ubuntu 16.04 be sure to take this steps before running VM init playbook:

```
ansible openstack -i hosts --sudo -m raw -a 'sed -i_bak "s/\(nameserver\) .*/\1 8\.8\.8\.8/" /etc/resolv.conf'
ansible openstack -i hosts --sudo -m raw -a "apt install -y python-minimal"
```


Initial steps required by both VMs
----------------------------------

* Add ssh keys to *known\_hosts* for both VMs:

```
ssh-keyscan <VM IP address> >> ~/.ssh/known_hosts
```


Setup OpenContrail & Devstack VMs
---------------------------------

Run *site.yml* playbook (it could take few hours to finish):

```
ansible-playbook site.yml
```
