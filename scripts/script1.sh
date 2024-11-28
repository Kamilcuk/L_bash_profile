#!/usr/bin/env bash
# line numbers synchronized with script1.py




a() {
	sleep 0.1
}




b() {
	case "$1" in
	1)
		sleep 0.2


		a ;;
	2)
		sleep 0.2



		b 1 ;;
	*)
		sleep 0.3
		;;
	esac
}


c() {
	a
	sleep 0.5



	b 2
}

c
b 0
b 1
b 2
