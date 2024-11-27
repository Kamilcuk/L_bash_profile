MAKEFLAGS = -rR
all:
	echo
test:
	pytest -sv
L_lib:
	L_bash_profile profile profile.txt '. ../L_lib/bin/L_lib.sh test'
xdot:
	L_bash_profile analyze profile.txt --dot profile.dot --dotlimit 3
	xdot profile.dot
snakeviz:
	L_bash_profile analyze profile.txt --pstatsfile profile.pstats
	snakeviz profile.pstats
