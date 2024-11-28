#!/usr/bin/env python
import time

nums = range(1000)


def a():
    stop = time.time() + 0.1
    while stop > time.time():
        for i in nums:
            i = i + 1


def b(i):
    if i == 1:
        stop = time.time() + 0.2
        while stop > time.time():
            for i in nums:
                i = i + 1
        a()
    elif i == 2:
        stop = time.time() + 0.2
        while stop > time.time():
            for i in nums:
                i = i + 1
        b(1)
    else:
        stop = time.time() + 0.3
        while stop > time.time():
            for i in nums:
                i = i + 1


def c():
    a()
    stop = time.time() + 0.5
    while stop > time.time():
        for i in nums:
            i = i + 1
    b(2)


c()
b(0)
b(1)
b(2)
