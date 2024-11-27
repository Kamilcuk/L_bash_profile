#!/bin/bash
set -euo pipefail

f() {
	sleep 0.1
	sleep 0.1
	sleep 0.1
}

g() {
	sleep 0.1
	f 2
}

g 1
sleep 0.1
