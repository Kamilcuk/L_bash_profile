MAKEFLAGS = -rR --warn-undefined-variables --no-show-directories
SHELL = bash
$(shell mkdir -vp build)

compare_script1: build/a build/b
	paste -d'@' build/a build/b | column -t -s '@'
build/script1.py.prof: ./script1.py
	python -m cProfile -o $@ script1.py
build/script1.sh.txt: ../src/L_bash_profile.py ./script1.py
	L_bash_profile profile -o $@ '. ./script1.sh'
build/script1.sh.prof: build/script1.sh.txt
	L_bash_profile analyze --pstats $@ $<
build/a: build/script1.sh.prof ../src/L_bash_profile.py
	L_bash_profile showpstats -r $< > $@
build/b: build/script1.py.prof ../src/L_bash_profile.py
	L_bash_profile showpstats -r $< > $@
