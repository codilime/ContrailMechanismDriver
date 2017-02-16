#!/bin/sh

Functions="`dirname ${BASH_SOURCE[0]}`/../install_functions.sh"
[ ! -r "$Functions" ] && { echo "Cant read functions library : $Functions!"; exit 2; }
. "$Functions"

DEST=${DEST:-"/opt/stack"}

install_dependencies
install_plugin "$DEST"
configure_plugin
