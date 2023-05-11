Trace the full path of Python code execution, line by line, and see exactly what is happening under the hood.

Works using `sys.settrace` to record data about each line of code which is executed. This can then be parsed to print the trace in a customizable way.

```python
from fulltracer import FullTracer

with FullTracer() as tracer:
    # Code to trace here
    pass

print(tracer)
```
