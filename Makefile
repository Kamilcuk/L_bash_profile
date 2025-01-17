MAKEFLAGS = -rR --warn-undefined-variables --no-print-directories
SHELL = bash
ARGS ?=

.PHONY: all test pyright L_lib analyze dump 2L_lib 2analyze 2dump 12compare xdot xdot2 xdot_L_argparse xdot_L_asa_has snakeviz

all:
	echo
test:
	pytest -sv
pyright:
	basedpyright src
clean:
	rm -vf profile*

MODE ?= XTRACE
L_lib:
	L_bash_profile profile -o profile.$(MODE).txt 'export L_UNITTEST_UNSET_X=0; . ../L_lib/bin/L_lib.sh test $(ARGS)' -m $(MODE)
analyze:
	L_bash_profile analyze profile.$(MODE).txt \
		--dumprecords profile.$(MODE).records.txt \
		--callgraph profile.$(MODE).callgraph.dot \
		--callstats profile.$(MODE).callstats.dot \
		--pstats profile.$(MODE).pstats $(ARGS)
xdot: analyze
	xdot profile.$(MODE).callstats.dot
xdot_L_argparse: ARGS += --filterfunction L_argparse --dotlimit 6
xdot_L_argparse: analyze xdot
xdot_L_asa_has: ARGS += --filterfunction L_asa_has
xdot_L_asa_has: analyze xdot
snakeviz: analyze
	snakeviz profile.$(MODE).pstats

_compare:
	set -x; \
		COLUMNS=$$(tput cols <&2); \
		f() { cat -vte "$$@" | cut -c-$$(( $${COLUMNS:-80} /2-2)); }; \
		paste -d$$'\x01' <(f profile.$(A).records.txt) <(f profile.$(B).records.txt) | \
		column -ts$$'\x01' | less


2L_lib: MODE=DEBUG
2L_lib: L_lib
2analyze: MODE=DEBUG
2analyze: L_lib
2xdot: MODE=DEBUG
2xdot: xdot
12compare: A=XTRACE B=DEBUG
12compare: compare


3L_lib: MODE=VAR
3L_lib: L_lib
3analyze: MODE=VAR
3analyze: L_lib
3xdot: MODE=VAR
3xdot: xdot
13compare: A=XTRACE B=VAR
13compare: compare

