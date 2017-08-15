Setup development VMs using Ansible playbooks
=============================================

Variables used by configuration templates are stored in *group_vars* directory so be sure to adjust it according to your setup before running *site.yml* playbook. It uses also *hosts* for VMs definition so be sure to reedit this as well.


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


NOTICE
------
Use Ubuntu 14.04 and 16.04 for VMs. If you are installing Openstack Ocata after succesfull deployment be sure to issue command listed below on OpenStack node, otherwise scheduling VM using Nova won't work.

```
$ nova-manage cell_v2 simple_cell_setup

```
