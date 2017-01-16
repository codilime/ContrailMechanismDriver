#!/bin/sh

Dir=`dirname $0`

exec $Dir/deployment_scripts/install.sh "$@"
