#!/bin/bash
set -euo pipefail

_trap_DEBUG() {
	local txt i
	for i in ${!BASH_SOURCE[@]}; do
		txt+=$'\t'"$i:${BASH_SOURCE[i]}:${BASH_LINENO[i]}:${FUNCNAME[i]}"
	done
	echo "# ${BASH_COMMAND@Q}$txt"
}
# trap 'echo "# ${BASH_COMMAND@Q} ${#BASH_SOURCE[@]} ${BASH_SOURCE[0]@Q} $LINENO ${FUNCNAME[0]:-}"' DEBUG
trap '_trap_DEBUG' DEBUG
set -T
"$@"
: END
