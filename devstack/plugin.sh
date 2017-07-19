#bin/sh

Functions="`dirname ${BASH_SOURCE[0]}`/../install_functions.sh"
[ ! -r "$Functions" ] && { echo "Cant read functions library : $Functions!"; exit 2; }
. "$Functions"

MODE="$1"
PHASE="$2"

setup_stack()
{
	case "$PHASE" in
		"pre-install")
			install_dependencies
			;;

		"install")
			install_plugin "$DEST"
			;;

		"post-config")
			source "$NEUTRON_DIR/devstack/plugin.sh"

			# Configuring driver
			neutron_ml2_extension_driver_add "contrail_driver"
			iniset $NEUTRON_CORE_PLUGIN_CONF ml2_driver_contrail controller $CONTRAIL_DRIVER_CONTROLLER
			iniset $NEUTRON_CORE_PLUGIN_CONF ml2_driver_contrail port $CONTRAIL_DRIVER_PORT

			# Adding driver to runtime
			iniset $NEUTRON_ENTRY_POINTS 'neutron.ml2.mechanism_drivers' 'contrail_driver' 'neutron.plugins.ml2.drivers.contrail_driver:ContrailMechanismDriver'
			;;

		"extra")
			# nothing to do
			;;

		"test-config")
			# nothing to do
			;;

		*)
			echo "Unhandled option: $PHASE in mode $MODE";
			exit 0
			;;
	esac
}

case "$MODE" in
	"stack")
		setup_stack
		;;

	"unstack")
		# nothing to do
		;;

	"clean")
		# nothing to do
		;;

	*)
		echo "Unhandled option: $MODE";
		exit 0
		;;
esac

