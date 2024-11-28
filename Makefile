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
snakeviz:
	L_bash_profile analyze profile.txt --pstats profile.pstats
	snakeviz profile.pstats
