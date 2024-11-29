MAKEFLAGS = -rR
all:
	echo
test:
	pytest -sv
pyright:
	basedpyright src
L_lib:
	L_bash_profile profile -o profile.txt '. ../L_lib/bin/L_lib.sh test'
xdot:
	L_bash_profile analyze profile.txt --dot profile.dot --dotlimit 3
	xdot profile.dot
xdot2 xdot_L_argparse:
	L_bash_profile analyze profile.txt --dot profile.dot --dotfunction L_argparse --dotcmds --dotlimit 6
	xdot profile.dot
xdot_L_asa_has:
	L_bash_profile analyze profile.txt --dot profile.dot --dotcmds --dotfunction L_asa_has
	xdot profile.do
snakeviz:
	L_bash_profile analyze profile.txt --pstats profile.pstats
	snakeviz profile.pstats
