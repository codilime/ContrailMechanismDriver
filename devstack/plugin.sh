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
			source "$NEUTRON_DIR/devstack/lib/ml2" contrail_driver
			enable_ml2_extension_driver
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

