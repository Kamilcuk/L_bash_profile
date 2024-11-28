# L_bash_profile

L_bash_profile provides deterministic profiling of Bash programs. A _profile_ is contains the whole trace of execution of a particular bash script with timestamp of each executed command. Such _profile_ can be formatted into reports to find code hot-spots.

<!-- vim-markdown-toc GFM -->

* [Example](#example)
* [Features](#features)
* [Installation](#installation)
* [Subcommands](#subcommands)
  * [profile](#profile)
  * [analyze](#analyze)
* [LICENSE](#license)

<!-- vim-markdown-toc -->

# Example

```
$ L_bash_profile profile -o ./profile.txt 'i=0; while ((i < 100)); do ((i++)); done'
PROFILING: i=0; while ((i < 100)); do ((i++)); done to ./profile.txt
PROFING ENDED, output in /dev/stdout
$ L_bash_profile analyze ./profile.txt
Top 3 cummulatively longest commands:
  percent    spent_us  cmd            calls    spentPerCall    topCaller1  topCaller2    topCaller3    example
---------  ----------  -----------  -------  --------------  ------------  ------------  ------------  ---------
50.1513         3_148  ((i < 100))      101         31.1683           101                              ~:13
49.4504         3_104  ((i++))          100         31.04             100                              ~:13
 0.955871          60  i=0                1         60                  1                              ~:13

Script executed in 0:00:00.006277us, 202 instructions, 0 functions.
```

# Features

- generate dot callgraph
- print longest commands
- print longest functions
- generate python profile file

# Installation

```
pipx install L_bash_profile
```

# Subcommands

## profile

Executes a given script under profiling.

Profiling just executes a `bash -c` script that spcifies `DEBUG` trap that executes a command that prints timestamp, current command, and context to the given file. After setup, the script executes the commands given on command line.

To profile a script, you have to execute it in current shell context `source ./yourscript args`.

## analyze

Analyses the prifiling information, printing commands and function hotspots.

Additionally it can generate a dot graph from the calls, for example:

```
$ L_bash_profile profile 'f() { sleep 0.1; }; g() { sleep 0.1; f; f; }; b() { f; g; }; b' | L_bash_profile analyze --dot profile.dot
PROFILING: f() { sleep 0.1; }; g() { sleep 0.1; f; f; }; b() { f; g; }; b to /dev/stdout
PROFING ENDED, output in /dev/stdout
Top 4 cummulatively longest commands:
    percent    spent_us  cmd          calls    spentPerCall  topCaller1    topCaller2    topCaller3    example
-----------  ----------  ---------  -------  --------------  ------------  ------------  ------------  --------------
133.307         405_612  sleep 0.1        4     101403       f 3           g 1                         environment:13
  0.132777          404  f                6         67.3333  f 3           g 2           b 1           environment:13
  0.0374667         114  g                2         57       b 1           g 1                         environment:13
  0.0348375         106  b                2         53       1             b 1                         ~:13

Top 3 cummulatively longest functions:
    percent    spent_us  funcname      calls    spentPerCall    instructions    instructionsPerCall  example
-----------  ----------  ----------  -------  --------------  --------------  ---------------------  --------------
100.093         304_552  f                 3          101517               6                      2  environment:13
 33.3493        101_472  g                 1          101472               4                      4  environment:13
  0.0492983         150  b                 1             150               3                      3  environment:13

Script executed in 0:00:00.304270us, 14 instructions, 3 functions.
```

Generates a `profile.dot` file that can be viewed:

![exampledot](./doc/exampledot.png)

# Example output

```
Top 20 cummulatively longest commands:
  percent    spent_us  cmd                                                   calls    spentPerCall  topCaller1                          topCaller2                               topCaller3                 example
---------  ----------  --------------------------------------------------  -------  --------------  ----------------------------------  ---------------------------------------  -------------------------  --------------------------
 5.47741      115_763  "${@:2}"                                               1794         64.5279  L_assert2 1025                      L_is_valid_variable_name 293             L_regex_match 293          ../L_lib/bin/L_lib.sh:406
 4.45483       94_151  declare -p _L_optspec                                   174        541.098   _L_argparse_split 159               _L_argparse_parse_args_short_option 15                              ../L_lib/bin/L_lib.sh:2819
 3.70534       78_311  (($#))                                                 1292         60.6122  _L_abbreviation_v 368               L_args_contain 356                       _L_argparse_split 292      ../L_lib/bin/L_lib.sh:3772
 3.23247       68_317  shift                                                  1180         57.8958  _L_abbreviation_v 368               L_args_contain 356                       _L_argparse_split 200      ../L_lib/bin/L_lib.sh:662
 2.54289       53_743  L_assert2 "$(declare -p _L_optspec)" L_var_is_se..      134        401.067   _L_argparse_split 67                L_assert2 67                                                        ../L_lib/bin/L_lib.sh:2728
 1.75324       37_054  L_assert2  L_regex_match "${!3}" "^[^=]*=[(].*[)..      586         63.2321  L_nestedasa_get 293                 L_assert2 293                                                       ../L_lib/bin/L_lib.sh:1828
 1.62293       34_300  L_assert2  L_is_valid_variable_name "$1"                586         58.5324  L_nestedasa_get 293                 L_assert2 293                                                       ../L_lib/bin/L_lib.sh:1827
 1.59913       33_797  [[ "$1" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]                  311        108.672   L_is_valid_variable_name 311                                                                            ../L_lib/bin/L_lib.sh:583
 1.43783       30_388  [[ "$1" =~ $2 ]]                                        293        103.713   L_regex_match 293                                                                                       ../L_lib/bin/L_lib.sh:311
 1.33175       28_146  _L_optspec_declare_p=$(declare -p _L_optspec)            44        639.682   _L_argparse_split 44                                                                                    ../L_lib/bin/L_lib.sh:2826
 1.23456       26_092  declare -n _L_asa="$1"                                  435         59.9816  L_asa_has 375                       L_asa_is_empty 50                        _L_asa_get_v 5             ../L_lib/bin/L_lib.sh:1734
 1.15995       24_515  _L_argparse_parser_next_option _L_i _L_optspec          428         57.278   _L_argparse_parser_next_option 214  _L_argparse_parse_args_set_defaults 108  _L_argparse_parse_args 77  ../L_lib/bin/L_lib.sh:3104
 1.14149       24_125  L_asa_has _L_parser "option$_L_i"                       428         56.3668  _L_argparse_parser_next_option 214  L_asa_has 214                                                       ../L_lib/bin/L_lib.sh:2909
 1.1379        24_049  [[ -n "${_L_asa["$2"]+yes}" ]]                          375         64.1307  L_asa_has 375                                                                                           ../L_lib/bin/L_lib.sh:1735
 1.13501       23_988  eval "$1=${!3#*=}"                                      293         81.8703  L_nestedasa_get 293                                                                                     ../L_lib/bin/L_lib.sh:1829
 1.11774       23_623  [[ $1 != _L_asa ]]                                      435         54.3057  L_asa_has 375                       L_asa_is_empty 50                        _L_asa_get_v 5             ../L_lib/bin/L_lib.sh:1734
 1.03428       21_859  [[ "$1" = "$needle" ]]                                  343         63.7289  L_args_contain 343                                                                                      ../L_lib/bin/L_lib.sh:664
 0.950999      20_099  jq -r .v                                                  6       3349.83    t 6                                                                                                     ../L_lib/bin/L_lib.sh:949
 0.924124      19_531  _L_handle_v "$@"                                        310         63.0032  _L_handle_v 155                     L_abbreviation 74                        L_max 18                   ../L_lib/bin/L_lib.sh:556
 0.910781      19_249  _"${FUNCNAME[1]}"_v "${@:3}"                            288         66.8368  _L_handle_v 144                     _L_abbreviation_v 74                     _L_max_v 18                ../L_lib/bin/L_lib.sh:341

Top 20 cummulatively longest functions:
  percent    spent_us  funcname                               calls    spentPerCall    instructions    instructionsPerCall  example
---------  ----------  -----------------------------------  -------  --------------  --------------  ---------------------  --------------------------
 21.1877      447_794  _L_argparse_split                         92        4867.33             4071               44.25     ../L_lib/bin/L_lib.sh:2685
  6.31623     133_491  L_assert2                               1025         130.235            2050                2        ../L_lib/bin/L_lib.sh:406
  5.26407     111_254  _L_unittest_internal                     175         635.737            1762               10.0686   ../L_lib/bin/L_lib.sh:1910
  4.99153     105_494  L_nestedasa_get                          293         360.048            1465                5        ../L_lib/bin/L_lib.sh:1827
  4.17789      88_298  L_args_contain                           117         754.684            1406               12.0171   ../L_lib/bin/L_lib.sh:662
  4.11675      87_006  L_asa_has                                375         232.016            1500                4        ../L_lib/bin/L_lib.sh:1734
  3.86934      81_777  _L_abbreviation_v                         74        1105.09             1379               18.6351   ../L_lib/bin/L_lib.sh:835
  3.73776      78_996  _L_argparse_parse_args                    27        2925.78             1326               49.1111   ../L_lib/bin/L_lib.sh:3324
  2.82215      59_645  L_argparse                                24        2485.21              880               36.6667   ../L_lib/bin/L_lib.sh:3354
  2.808        59_346  _L_handle_v                              154         385.364             929                6.03247  ../L_lib/bin/L_lib.sh:335
  2.39025      50_517  L_is_valid_variable_name                 311         162.434             622                2        ../L_lib/bin/L_lib.sh:583
  2.34809      49_626  _L_argparse_parser_next_option           214         231.897             856                4        ../L_lib/bin/L_lib.sh:2907
  2.26155      47_797  L_argparse_print_help                     12        3983.08              836               69.6667   ../L_lib/bin/L_lib.sh:2563
  2.1893       46_270  L_regex_match                            293         157.918             586                2        ../L_lib/bin/L_lib.sh:310
  1.62719      34_390  _L_argparse_parser_next_argument         123         279.593             588                4.78049  ../L_lib/bin/L_lib.sh:2920
  1.52002      32_125  L_var_is_set                             163         197.086             489                3        ../L_lib/bin/L_lib.sh:508
  1.41668      29_941  _L_argparse_parse_args_short_option       10        2994.1               260               26        ../L_lib/bin/L_lib.sh:3167
  1.30435      27_567  t                                          5        5513.4                41                8.2      ../L_lib/bin/L_lib.sh:946
  1.23073      26_011  _L_argparse_parse_args_set_defaults       27         963.37              389               14.4074   ../L_lib/bin/L_lib.sh:3104
  1.13184      23_921  _L_list_functions_with_prefix_v            1       23921                 455              455        ../L_lib/bin/L_lib.sh:560

Script executed in 0:00:02.113461us, 28867 instructions, 123 functions.
```

# LICENSE

Licensed under GPLv3.
Written by Kamil Cukrowski 2024.
