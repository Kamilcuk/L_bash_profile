# pstats

My documentation of python pstats objects.

# docs

`pstats` has type `dict[tuple[str, int, str], tuple[int, int, int, int, list[tuple[int, int, int, int]]]]`.

The `pstats` object is marshal-ed dictionary object with tuple of `(filename, lineno, funcname)` of keys and tuple of `(cc, nc, tt, ct, callers)` as values.

The tuple elements of `pstats[func]` hold:
- `cc` is the number of primitive calls to the function. Primitive calls are all calls minus recursive calls.
- `nc` is the number of all calls to the function.
- `tt` is the time spent in the function excluding the time spent in subfunctions.
   - If a function calls itself recursively, then this time is summed.
- `ct` is the time spent in the function.
   - If a function calls itself recursively, then this time is effectively ignored.
- `callers` is a list of a nested tuple of `(cc, nc, tt, ct)`. The tuple elements `pstats[func].callers[func2]` hold:
   - `cc` - the the number of calls `func2` made to `func`
   - `nc` - always equal to `cc`, just ignore
   - `tt` - the time spent in such `func2` calls that at least one called `func` excluding the time spent in subfunction 
   - `ct` - the time spent in such `func2` calls that at least one called `func`

The following properties hold:
- `pstats.keys()` holds __all__ functions that were executed in the script
- `set(c for s in pstats.values() for c in s.callers).issubset(stats.keys())`
- `all(s.nc >= s.cc for s in pstats.values())`
- `all(f.nc == sum(c.nc for s in stats.values() for c in stats.callers.values()))`

# links

 - https://github.com/python/cpython/blob/main/Lib/cProfile.py#L63
 - https://github.com/python/cpython/blob/main/Modules/_lsprof.c#L31
 - https://github.com/python/cpython/blob/main/Lib/pstats.py#L160
 - https://docs.python.org/3/library/profile.html
 - https://zameermanji.com/blog/2012/6/30/undocumented-cprofile-features/
 - https://stackoverflow.com/questions/15816415/in-python-cprofile-what-is-the-difference-between-calls-count-and-primitive-cal

