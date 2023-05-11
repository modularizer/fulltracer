import argparse
import os
import re
import runpy
import sys

from dataclasses import dataclass


class Colors:
    """ANSI color codes for printing colored text in terminal"""
    GREEN = "\033[32m"
    GRAY = "\033[90m"
    RED = "\033[31m"
    ORANGE = "\033[33m"
    YELLOW = "\033[93m"
    RESET_FMT = "\033[0m"


class HyperLinks:
    """Hyperlinks which can be used to open the file in IDE at the line number"""
    PYCHARM_LINK = 'File "%file", line %lineno'
    VSCODE_LINK = f"[{PYCHARM_LINK}](command:workbench.action.files.openFile?path=%file&line=%line_no)"


@dataclass(kw_only=True)
class Config:
    """Configuration for the FullTracer"""
    anchor: str = "⚓"
    """Anchor character used to pad lines"""

    quotation_replacement: str = "\u201D"
    """Character used to replace quotation marks in the output to make the IDE hyperlinks work"""

    line_length: int = 80
    """Max expected length of a line in the source code. Used to pad the lines with anchor characters"""

    IDE: str = "vscode" if os.environ.get("TERM_PROGRAM") == "vscode" else "pycharm" if os.environ.get(
        "PYCHARM_HOSTED") else "unknown"
    """IDE in which the code is being run. Used to generate the hyperlinks"""

    not_found: str = f"{Colors.YELLOW}Not found{Colors.RESET_FMT}"
    """String to be used when the source code file is not found"""

    filename_pattern: str | None = None
    """Regex pattern to match the filename. If not provided, the filename is not matched"""

    func_name_pattern: str | None = None
    """Regex pattern to match the function name. If not provided, the function name is not matched"""

    line_pattern: str | None = None
    """Regex pattern to match the line number. If not provided, the line number is not matched"""

    ignore_unfound_lines: bool = True
    """If True, the lines which are not found in the source code are not included in the output"""

    max_depth: int | None = None
    """Maximum depth of the stack to be parsed. If not provided, the stack is parsed till the end"""

    trace_lines: bool = True
    """If True, the lines are traced. If False, only the function calls are traced"""

    parse: bool = True
    """Automatically parse the trace after stopping the tracer"""

    depth_tab: str = ""
    """String to be used to indent the lines based on the depth of the stack"""

    strip: bool = False
    """If True, the leading and trailing whitespaces are stripped from the lines"""

    DEFAULT: str = "%DEFAULT%"
    """Placeholder indicating that the default value should be used"""

    link: str = DEFAULT
    """Template string to generate the hyperlinks"""

    mode: str = DEFAULT
    """Template string to generate the output for a single line"""

    consecutive_mode: str | None = DEFAULT
    """Template string to generate the output for consecutive lines"""

    def __post_init__(self):
        if self.link == self.DEFAULT:
            self.link = HyperLinks.VSCODE_LINK if self.IDE == "vscode" else HyperLinks.PYCHARM_LINK
        if self.mode == self.DEFAULT:
            self.mode = f"(%depth)%depth_indent{self.anchor}10{self.anchor}%line{self.anchor}{self.line_length + 10}{self.anchor}{Colors.GREEN}{self.link} (%func){Colors.RESET_FMT}"
        if self.consecutive_mode == self.DEFAULT:
            self.consecutive_mode = f" {self.anchor}10{self.anchor}%line{self.anchor}{self.line_length + 10}{self.anchor}{Colors.GREEN}{self.link} (%func){Colors.RESET_FMT}"


class FullTracer:
    DEFAULT_CONFIG = Config()

    def __init__(self, **kw):
        self.configuration = Config(**kw)
        """current configuration of the tracer"""

        self.trace = []
        """list of tuples containing info about each line of code called"""

        self.parsed_trace = []
        """list of strings containing the parsed output of the trace"""

        self.depth = 0
        """current depth of the stack"""

        self.last_frame = None
        """last frame which was traced"""

        self.current_stack = []
        """current stack of frames"""

        self.parsed_string = "unparsed"
        """string containing the parsed output of the trace"""

        self.trace_lines = self.configuration.trace_lines
        """if True, the lines are traced. If False, only the function calls are traced"""

    def configure(self, *a, **kw):
        """Configure the tracer with the given configuration"""
        if len(a):
            if kw or len(a) > 1:
                raise ValueError("Either pass a single Config object or pass the configuration as keyword arguments")
            self.configuration = a[0]
        else:
            self.configuration = Config(**kw)

    def tracer(self, frame, event, arg):
        """Tracer function which is called by sys.settrace().

        If self.trace_lines is True, the function calls and the lines are traced.
        If self.trace_lines is False, only the function calls are traced.
        """
        if event == "call":
            co = frame.f_code
            func_name = co.co_name
            line_no = frame.f_lineno
            filename = co.co_filename

            self.depth += 1
            self.last_frame = frame
            self.current_stack.append((frame, func_name, line_no, event, self.depth))

            self.trace.append((filename, func_name, line_no, event, self.depth))
        elif event == "line":
            co = frame.f_code
            func_name = co.co_name
            line_no = frame.f_lineno
            filename = co.co_filename
            self.trace.append((filename, func_name, line_no, event, self.depth))
        elif event == "return":
            self.depth -= 1
            self.last_frame = frame
            self.current_stack.pop()

        if self.trace_lines:
            return self.tracer

    def clear(self):
        """Clear the trace and the parsed trace"""
        self.trace = []
        self.parsed_trace = []
        self.current_stack = []
        self.parsed_string = "unparsed"

    def start(self, trace_lines=Config.DEFAULT):
        """Start tracing the code"""
        self.trace_lines = trace_lines if trace_lines != Config.DEFAULT else self.configuration.trace_lines
        sys.settrace(self.tracer)

    def stop(self, *a, parse=Config.DEFAULT, num_pop=0, **kw):
        """Stop tracing the code and parse the trace if parse is True"""
        sys.settrace(None)
        for _ in range(num_pop):
            self.trace.pop()
        if parse == Config.DEFAULT:
            parse = self.configuration.parse
        if parse:
            self.parse(*a, **kw)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, type, value, traceback):
        self.stop(num_pop=4)

    def parse(self,
               mode = Config.DEFAULT,
               consective_mode=Config.DEFAULT,
               trace_lines=Config.DEFAULT,
               filename_pattern=Config.DEFAULT,
               func_name_pattern=Config.DEFAULT,
               line_pattern=Config.DEFAULT,
               ignore_unfound_lines=Config.DEFAULT,
               max_depth=Config.DEFAULT,
               not_found=Config.DEFAULT,
               link=Config.DEFAULT,
               quotation_replacement=Config.DEFAULT,
               anchor=Config.DEFAULT,
               depth_tab=Config.DEFAULT,
               strip = Config.DEFAULT,
              ) -> str:

        # get values for all the parameters
        if mode == Config.DEFAULT:
            mode = self.configuration.mode
        if consective_mode == Config.DEFAULT:
            consective_mode = self.configuration.consecutive_mode
        if trace_lines == Config.DEFAULT:
            trace_lines = self.configuration.trace_lines
        if filename_pattern == Config.DEFAULT:
            filename_pattern = self.configuration.filename_pattern
        if func_name_pattern == Config.DEFAULT:
            func_name_pattern = self.configuration.func_name_pattern
        if line_pattern == Config.DEFAULT:
            line_pattern = self.configuration.line_pattern
        if ignore_unfound_lines == Config.DEFAULT:
            ignore_unfound_lines = self.configuration.ignore_unfound_lines
        if max_depth == Config.DEFAULT:
            max_depth = self.configuration.max_depth
        if not_found == Config.DEFAULT:
            not_found = self.configuration.not_found
        if link == Config.DEFAULT:
            link = self.configuration.link
        if quotation_replacement == Config.DEFAULT:
            quotation_replacement = self.configuration.quotation_replacement
        if anchor == Config.DEFAULT:
            anchor = self.configuration.anchor
        if depth_tab == Config.DEFAULT:
            depth_tab = self.configuration.depth_tab
        if strip == Config.DEFAULT:
            strip = self.configuration.strip

        lines = {}
        self.parsed_trace = []
        self.parsed_string = ""
        ignoring = False
        last_file_func_line = (None, None, -2)
        for filename, func_name, line_no, event, depth in self.trace:
            if ignoring and depth <= ignoring:
                ignoring = False

            if (not ignoring) and\
                    (trace_lines or event == "call") and \
                    ((not max_depth) or depth <= max_depth) and \
                    (filename_pattern is None or re.match(filename_pattern, filename)) and \
                    (func_name_pattern is None or re.match(func_name_pattern, func_name)):
                try:
                    if filename not in lines:
                        with open(filename) as f:
                            lines[filename] = f.readlines()
                    line = lines[filename][line_no - 1][:-1]
                    line_found = True
                except FileNotFoundError:
                    line = not_found
                    line_found = False
                if line_pattern is None or re.search(line_pattern, line):
                    consective = (filename, func_name) == tuple(last_file_func_line[:2]) and line_no == (last_file_func_line[2] + 1)
                    s = consective_mode if consective_mode and consective else mode

                    same_line = filename == last_file_func_line[0] and line_no == last_file_func_line[-1]
                    formatted_func_name = func_name if not same_line else f"{last_file_func_line[1]}=>{func_name}"

                    linked = link in s
                    s = s.replace("%file", filename)
                    s = s.replace("%func", formatted_func_name)
                    s = s.replace("%lineno", str(line_no))
                    s = s.replace("%event", event)

                    depth_indent = depth_tab * depth
                    s = s.replace("%depth_indent", depth_indent)
                    s = s.replace("%depth", str(depth))

                    formatted_line = line.replace('"', quotation_replacement) if linked and (quotation_replacement is not None) else line
                    if strip:
                        formatted_line =  formatted_line.strip()

                    s = s.replace("%line", formatted_line)

                    parts = s.split(anchor)
                    x = ""
                    for i, v in enumerate(parts):
                        if i % 2 == 0:
                            x += v
                        else:
                            n = len(re.findall("\033", x))
                            x += " "*(int(v) - len(x) + n*4 + int(n>0))

                    file_func_line = (filename, formatted_func_name, line_no)

                    if not (ignore_unfound_lines and not line_found):
                        if same_line:
                            self.parsed_trace.pop()
                        self.parsed_trace.append(x)
                        last_file_func_line = file_func_line
            else:
                ignoring = depth
        self.parsed_string = "\n\t".join(self.parsed_trace)
        return self.parsed_string

    def __iter__(self):
        return iter(self.parsed_trace)

    def __repr__(self):
        return f"{self.__class__.__name__}({len(self.parsed_trace)}/{len(self.trace)})\n\t{self.parsed_string}"


def main():
    parser = argparse.ArgumentParser(description='Python CLI that wraps scripts with FullTracer')
    parser.add_argument('script', type=str, help='Python script to execute')
    parser.add_argument('--anchor', type=str, default=Config.DEFAULT, help='Anchor character used to pad lines')
    parser.add_argument('--quotation-replacement', type=str, default=Config.DEFAULT, help='Character used to replace quotation marks in the output')
    parser.add_argument('--line-length', type=int, default=Config.line_length, help='Max expected length of a line in the source code')
    parser.add_argument('--IDE', type=str, default=Config.DEFAULT, help='IDE in which the code is being run')
    parser.add_argument('--not-found', type=str, default=Config.DEFAULT, help='String to be used when the source code file is not found')
    parser.add_argument('--filename-pattern', type=str, default=Config.DEFAULT, help='Regex pattern to match the filename')
    parser.add_argument('--func-name-pattern', type=str, default=Config.DEFAULT, help='Regex pattern to match the function name')
    parser.add_argument('--line-pattern', type=str, default=Config.DEFAULT, help='Regex pattern to match the line number')
    parser.add_argument('--ignore-unfound-lines', action='store_true', default=Config.ignore_unfound_lines, help='If set, lines not found in the source code are not included in the output')
    parser.add_argument('--max-depth', type=int, default=0, help='Maximum depth of the stack to be parsed')
    parser.add_argument('--trace-lines', action='store_true', default=Config.trace_lines, help='If set, both function calls and lines are traced')
    parser.add_argument('--parse', action='store_true', default=Config.parse, help='Automatically parse the trace after stopping the tracer')
    parser.add_argument('--depth-tab', type=str, default=Config.DEFAULT, help='String to be used to indent the lines based on the depth of the stack')
    parser.add_argument('--strip', action='store_true', default=Config.strip, help='If set, leading and trailing whitespaces are stripped from the lines')

    args = parser.parse_args()

    config_args = {k: v for k, v in vars(args).items() if v != Config.DEFAULT and k != "script"}
    config = Config(**config_args)

    with FullTracer(**config.__dict__) as ft:
        # This will run the script as if it were the "__main__" module
        runpy.run_path(args.script, run_name="__main__")
    print(ft)



if __name__ == '__main__':
    main()