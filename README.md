# FullTracer

FullTracer is a Python library that provides a tracing mechanism to track the execution flow of Python code. It allows you to trace function calls and lines of code, generate formatted output with hyperlinks to IDEs, and customize the tracing behavior through configuration.

## Installation

FullTracer can be installed using pip:

```shell
pip install fulltracer
```

## Usage

The basic usage of FullTracer involves configuring the tracer with the desired settings, starting the tracing process, executing the code, and parsing the trace. Here's an example of how to use FullTracer:

### Python

#### Context Manager
```python
from fulltracer import FullTracer

with FullTracer() as tracer:
    # Code to be traced
    my_func()

print(tracer)
```

#### start() and stop()
```python
from fulltracer import FullTracer

tracer = FullTracer(filename_pattern=__file__)
tracer.start()
# Code to be traced
my_func()

tracer.stop()
```

#### decorator
```python
from fulltracer import FullTracer

tracer = FullTracer(filename_pattern=__file__)

@tracer
def my_func():
    # Code to be traced
    pass


my_func()
print(tracer)
```

### Command Line
Instead of 
```shell
python my_script.py
```
use
```shell
fulltrace my_script.py
```
(Still working on getting `fulltracer  -m my_script` to work)

## Configuration

FullTracer provides a `Config` class to configure the tracer's behavior. The available configuration options include:

- `anchor`: Anchor character used to pad lines.
- `line_length`: Max expected length of a line in the source code.
- `IDE`: IDE in which the code is being run.
- `not_found`: String to be used when the source code file is not found.
- `filename_pattern`: Regex pattern to match the filename.
- `func_name_pattern`: Regex pattern to match the function name.
- `line_pattern`: Regex pattern to match the line number.
- `ignore_unfound_lines`: If True, lines not found in the source code are not included in the output.
- `max_depth`: Maximum depth of the stack to be parsed.
- `trace_lines`: If True, both function calls and lines are traced.
- `parse`: Automatically parse the trace after stopping the tracer.
- `depth_tab`: String to be used to indent the lines based on the depth of the stack.
- `strip`: If True, leading and trailing whitespaces are stripped from the lines.
- `link`: Template string to generate the hyperlinks.
- `mode`: Template string to generate the output for a single line.
- `consecutive_mode`: Template string to generate the output for consecutive lines.

## Examples

For more detailed usage examples, refer to the [samples directory](https://github.com/modularizer/fulltracer/tree/master/samples) in the FullTracer GitHub repository.

## License

FullTracer is licensed under the Unlicense. See [LICENSE](https://github.com/modularizer/fulltracer/tree/master/LICENSE) for more information.
