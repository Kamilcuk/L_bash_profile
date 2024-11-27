import cProfile
import marshal
import tempfile
import pprint
import time
nums = range(1000)
def a():
    stop = time.time() + 0.1
    while stop > time.time():
        for i in nums:
            i=i+1
def b(i):
    if i == 1:
        stop = time.time() + 0.2
        while stop > time.time():
            for i in nums:
                i=i+1
        a()
    elif i == 2:
        stop = time.time() + 0.2
        while stop > time.time():
            for i in nums:
                i=i+1
        b(1)
    else:
        stop = time.time() + 0.3
        while stop > time.time():
            for i in nums:
                i=i+1
def c():
    time.sleep(0.3)
    a()
    b()

    print("c")
with tempfile.NamedTemporaryFile() as statsfile:
    cProfile.run("(b(0),b(0),b(1),b(1))", statsfile.name)
    stats = marshal.load(statsfile.file)
for key, val in stats.items():
    print(f"{key[0]}:{key[1]}:{key[2]}\tnc={val[0]} cc={val[1]} tt={val[2]:f} ct={val[3]:f}")
    for key, val in (val[4] or {}).items():
        print(f" ^ {key[0]}:{key[1]}:{key[2]}\tnc={val[0]} cc={val[1]} tt={val[2]:f} ct={val[3]:f}")
