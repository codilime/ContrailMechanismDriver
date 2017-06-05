#!/bin/bash

#IP of Keystone host 
AUTH_HOST=${AUTH_HOST:-192.168.0.6}
#Keystone endpoint url
AUTH_URL=http://$AUTH_HOST:5000/v2.0
ADMIN_USER=admin
ADMIN_PASSWORD=admin
ADMIN_TENANT_NAME=admin
CONTRAIL_SRC_DIR=/opt/stack/contrail


function replace_ContrailPlugin_ini_conf()
{
	file="/etc/contrail/ContrailPlugin.ini"
	check_replace_value $file KEYSTONE auth_host $AUTH_HOST
	check_replace_value $file KEYSTONE auth_url $AUTH_URL
	check_replace_value $file KEYSTONE admin_password $ADMIN_PASSWORD
}


function replace_contrail_plugin_ini_conf()
{
	file="/etc/contrail/contrail_plugin.ini"
	check_replace_value $file KEYSTONE auth_host $AUTH_HOST
	check_replace_value $file KEYSTONE auth_url $AUTH_URL
	check_replace_value $file KEYSTONE admin_password $ADMIN_PASSWORD
}


function replace_contrail_api_conf_conf()
{
	file="/etc/contrail/contrail-api.conf"
	check_replace_value $file KEYSTONE auth_host $AUTH_HOST
	check_replace_value $file KEYSTONE admin_password $ADMIN_PASSWORD
}


function replace_contrail_schema_conf_conf()
{
	file="/etc/contrail/contrail-schema.conf"
	check_replace_value $file KEYSTONE admin_password $ADMIN_PASSWORD
	}


function replace_svc_monitor_conf_conf()
{
	file="/etc/contrail/svc-monitor.conf"
	check_replace_value $file KEYSTONE admin_password $ADMIN_PASSWORD
	}


function replace_contrail_snmp_collector_conf_conf()
{
	file="/etc/contrail/contrail-snmp-collector.conf"
	check_replace_value $file KEYSTONE admin_user $ADMIN_USER
	check_replace_value $file KEYSTONE admin_tenant_name $ADMIN_TENANT_NAME
	check_replace_value $file KEYSTONE admin_password $ADMIN_PASSWORD
}

function replace_vnc_api_lib_ini()
{
	file="/etc/contrail/vnc_api_lib.ini"
	check_replace_value "$file" auth AUTHN_SERVER "$AUTH_HOST"
}

function patch_contrail_web_core_config_global_js()
{
	sed -i -e "s/config\.identityManager\.ip.*$/config\.identityManager\.ip = '$AUTH_HOST';/" $CONTRAIL_SRC_DIR/contrail-web-core/config/config.global.js
	sed -i -e "s+config\.featurePkg\.webController\.path.*$+config\.featurePkg\.webController\.path = '$CONTRAIL_SRC_DIR/contrail-web-controller';+" $CONTRAIL_SRC_DIR/contrail-web-core/config/config.global.js

}

function patch_openstackrc()
{
	file='/etc/contrail/openstackrc'
	#export OS_AUTH_URL=http://127.0.0.1:5000/v2.0/
	sed -i -e "s!^\(export OS_AUTH_URL=\).*!\1$AUTH_URL!" "$file"
}

#############Helper Functions###################

function ini_has_option() {
    local file=$1
    local section=$2
    local option=$3
    local line
    line=$(sed -ne "/^\[$section\]/,/^\[.*\]/ { /^$option[ \t]*=/ p; }" "$file")
    [ -n "$line" ]
}

function iniset() {
    local file=$1
    local section=$2
    local option=$3
    local value=$4

    [[ -z $section || -z $option ]] && return

    if ! grep -q "^\[$section\]" "$file" 2>/dev/null; then
        # Add section at the end
        echo -e "\n[$section]" >>"$file"
    fi
    if ! ini_has_option "$file" "$section" "$option"; then
        # Add it
        sed -i -e "/^\[$section\]/ a\\
$option = $value
" "$file"
    else
        local sep=$(echo -ne "\x01")
        # Replace it
        sed -i -e '/^\['${section}'\]/,/^\[.*\]/ s'${sep}'^\('${option}'[ \t]*=[ \t]*\).*$'${sep}'\1'"${value}"${sep} "$file"
    fi
}


function check_replace_value()
{
	file=$1
	section=$2
	key=$3
	value=$4
	if [[ -n "$value" ]]; then
	if [[ -n "$section" ]]; then
		iniset $file $section $key $value
	else
		iniset $file "DEFAULTS" $key $value
	fi
	fi
}



##########Function Calls##############

replace_ContrailPlugin_ini_conf
replace_contrail_plugin_ini_conf
replace_contrail_api_conf_conf
replace_contrail_schema_conf_conf
replace_svc_monitor_conf_conf
replace_contrail_snmp_collector_conf_conf
replace_vnc_api_lib_ini

patch_contrail_web_core_config_global_js
patch_openstackrc


##########Tips##############

#http://fosshelp.blogspot.in/2015/02/opencontrail-ui-error-install-feature.html


########################



########################




