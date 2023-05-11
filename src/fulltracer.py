import argparse
import os
import re
import runpy
import sys
from typing import TypedDict
import logging
from functools import wraps

from dataclasses import dataclass

logger = logging.getLogger(__file__)


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

    start_line_pattern: str | None = None
    start_func_pattern: str | None = None
    start_file_pattern: str | None = None

    def __post_init__(self):
        if self.link == self.DEFAULT:
            self.link = HyperLinks.VSCODE_LINK if self.IDE == "vscode" else HyperLinks.PYCHARM_LINK
        if self.mode == self.DEFAULT:
            self.mode = f"(%depth)%depth_indent{self.anchor}10{self.anchor}%line{self.anchor}{self.line_length + 10}{self.anchor}{Colors.GREEN}{self.link} (%func){Colors.RESET_FMT}"
        if self.consecutive_mode == self.DEFAULT:
            self.consecutive_mode = f" {self.anchor}10{self.anchor}%line{self.anchor}{self.line_length + 10}{self.anchor}{Colors.GREEN}{self.link} (%func){Colors.RESET_FMT}"

    def replace(self, **kw):
        d = self.__dict__.copy()
        d.update({k: v for k, v in kw.items() if v != Config.DEFAULT})
        return type(self)(**d)


@dataclass(slots=True)
class FrameInfo:
    filename: str
    """filename of the source code"""

    func_name: str
    """name of the function"""

    line_no: int
    """line number of the source code"""

    depth: int
    """depth of the stack"""

    event: str
    """event which triggered the trace"""


class ParsingState(TypedDict):
    started: bool

    ignoring: int
    """if True, the lines are being ignored"""

    lines: dict[str, list[str]]
    """dict containing the lines of code for each filename"""

    last_file_func_line: tuple[str, str, int]
    """tuple containing the last filename, function name and line number"""

    parsed_trace: list[str]
    """list of strings containing the parsed output of the trace"""


class FullTracer:
    DEFAULT_CONFIG = Config()

    def __init__(self, **kw):
        self.configuration = Config(**kw)
        """current configuration of the tracer"""

        self.trace: list[FrameInfo] = []
        """list of tuples containing info about each line of code called"""

        self.parsing_state: ParsingState = {
            "started": False,
            "ignoring": 0,
            "last_file_func_line": ("", "", -2),
            "lines": {},
            "parsed_trace": [],
        }

        self.depth = 0
        """current depth of the stack"""

        self.last_frame = None
        """last frame which was traced"""

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
        self._tracer(frame, event)
        self.last_frame = frame
        if self.trace_lines:
            return self.tracer

    def _tracer(self, frame, event):
        """Tracer function which is called by sys.settrace().

                If self.trace_lines is True, the function calls and the lines are traced.
                If self.trace_lines is False, only the function calls are traced.
                """
        if event == "call":
            self.depth += 1
        elif event == "line":
            pass
        elif event == "return":
            self.depth -= 1
        self.trace.append(self._get_frame_info(frame, event, self.depth))

    def _get_frame_info(self, frame, event, depth) -> FrameInfo:
        """Get the info about the frame"""
        co = frame.f_code
        func_name = co.co_name
        line_no = frame.f_lineno
        filename = co.co_filename
        return FrameInfo(filename, func_name, line_no, depth, event)

    def clear(self):
        """Clear the trace and the parsed trace"""
        self.trace = []
        self.parsing_state["parsed_trace"] = []
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

    def parse(self, *a, **kw) -> str:
        # Get values for all the parameters
        config = self._get_config(*a, **kw)

        self.parsed_string = "parsing"
        for frame_info in self.trace:
            # Parse the current line
            self._parse_frame_info(frame_info, config)
        self.parsed_string = "\n\t".join(self.parsing_state["parsed_trace"])
        return self.parsed_string

    def _parse_frame_info(self, frame_info: FrameInfo, config: Config):
        """Parse the current line"""

        # Check if the current line should unignored
        if self.parsing_state["ignoring"] and frame_info.depth < self.parsing_state["ignoring"]:
            self.parsing_state["ignoring"] = 0

        if not self.parsing_state["ignoring"]:
            # check if we are ignoring the current line due to a regexp pattern of filename or function name
            if (not self.parsing_state["started"]) or self._should_trace_line(frame_info, config):
                # Get the line of code from the source code file
                line, line_found = self._get_line(frame_info, self.parsing_state["lines"], config)

                if (not self.parsing_state["started"]) and line_found:
                    self.parsing_state["started"] = self._check_start(frame_info, config, line)

                # Check if we are ignoring the current line due to a regexp pattern of the line of code
                if self.parsing_state["started"] and self._should_include_line(line, config):

                    # Check if we are in consecutive mode (meaning the line immediately follows the previous line)
                    if self._is_consecutive_line(frame_info, self.parsing_state["last_file_func_line"]):
                        mode = config.consecutive_mode
                    else:
                        mode = config.mode

                    # Format the line of code
                    formatted_line = self._format_line(line, config)

                    # Parse the line of code into the output line
                    parsed_line = self._parse_line(mode, frame_info, formatted_line, self.parsing_state["last_file_func_line"], config)

                    # Append the parsed line to the parsed trace
                    if not (config.ignore_unfound_lines and not line_found):
                        self.parsing_state["parsed_trace"].append(parsed_line)

                    # Update the last file, function, and line
                    self.parsing_state["last_file_func_line"] = (frame_info.filename, frame_info.func_name, frame_info.line_no)
            else:
                # Ignore all lines in the current block and below
                self.parsing_state["ignoring"] = frame_info.depth
        else:
            # logger.debug("ignoring", parsing_state["ignoring"], frame_info)
            pass

    def _get_config(self, *a, **kw) -> Config:
        """Get the configuration object based on the provided keyword arguments"""
        config = a[0] if len(a) else self.configuration
        return config.replace(**kw)

    @staticmethod
    def _check_start(frame_info: FrameInfo, config: Config, line: str) -> bool:
        return (config.start_line_pattern is None or re.match(config.start_line_pattern, line)) and \
        (config.start_func_pattern is None or re.match(config.start_func_pattern, frame_info.func_name)) and \
        (config.start_file_pattern is None or re.match(config.start_file_pattern, frame_info.filename))

    @staticmethod
    def _should_trace_line(frame_info: FrameInfo, config: Config) -> bool:
        """Check if the line should be traced based on the event, depth, and configuration"""
        trace_lines = config.trace_lines
        max_depth = config.max_depth

        if not trace_lines and frame_info.event != "call":
            logger.debug("not tracing line because event is not call")
            return False
        if max_depth and frame_info.depth > max_depth:
            logger.debug("not tracing line because depth is too high")
            return False
        if config.filename_pattern is not None and not re.match(config.filename_pattern, frame_info.filename):
            logger.debug(f"not tracing line because filename ({frame_info.filename}) does not match pattern ({config.filename_pattern})")
            return False
        if config.func_name_pattern is not None and not re.match(config.func_name_pattern, frame_info.func_name):
            logger.debug("not tracing line because function name does not match pattern")
            return False
        return True

    @staticmethod
    def _get_line(frame_info: FrameInfo, lines: dict[str, list[str]], config: Config):
        """Get the line of code from the file or use the 'not_found' string"""
        line_found = True
        try:
            if frame_info.filename not in lines:
                with open(frame_info.filename) as f:
                    lines[frame_info.filename] = f.readlines()
            line = lines[frame_info.filename][frame_info.line_no - 1][:-1]
        except FileNotFoundError:
            line = config.not_found
            line_found = False
            logger.debug(f"{frame_info.filename} not found")
        return line, line_found

    @staticmethod
    def _should_include_line(line: str, config: Config):
        """Check if the line should be included in the output based on the line pattern"""
        line_pattern = config.line_pattern
        return line_pattern is None or re.search(line_pattern, line)

    @staticmethod
    def _is_consecutive_line(frame_info: FrameInfo, last_file_func_line: tuple[str, str, int]):
        """Check if the line is consecutive to the previous line"""
        return (frame_info.filename, frame_info.func_name) == tuple(last_file_func_line[:2]) and frame_info.line_no == (last_file_func_line[2] + 1)

    @staticmethod
    def _format_line(line, config):
        """Format the line of code by replacing quotation marks and stripping whitespace"""
        formatted_line = line.replace('"', config.quotation_replacement)
        if config.strip:
            formatted_line = formatted_line.strip()
        return formatted_line

    @staticmethod
    def _parse_line(mode, frame_info, line_formatted, last_file_func_line, config):
        """Parse the line using the provided mode and replace placeholders with actual values"""
        same_line = frame_info.filename == last_file_func_line[0] and frame_info.line_no == last_file_func_line[-1]
        formatted_func_name = frame_info.func_name if not same_line else f"{last_file_func_line[1]}=>{frame_info.func_name}"

        linked = config.link in mode
        mode = mode.replace("%file", frame_info.filename)
        mode = mode.replace("%func", formatted_func_name)
        mode = mode.replace("%lineno", str(frame_info.line_no))
        mode = mode.replace("%event", frame_info.event)

        depth_indent = config.depth_tab * frame_info.depth
        mode = mode.replace("%depth_indent", depth_indent)
        mode = mode.replace("%depth", str(frame_info.depth))

        formatted_line = line_formatted.replace('"', config.quotation_replacement) if linked and (config.quotation_replacement is not None) else line_formatted
        if config.strip:
            formatted_line = formatted_line.strip()

        mode = mode.replace("%line", formatted_line)

        parts = mode.split(config.anchor)
        parsed_line = ""
        for i, v in enumerate(parts):
            if i % 2 == 0:
                parsed_line += v
            else:
                n = len(re.findall("\033", parsed_line))
                parsed_line += " " * (int(v) - len(parsed_line) + n * 4 + int(n > 0))

        return parsed_line

    def wrap(self, f):
        """Wrap a function with the tracer"""
        @wraps(f)
        def wrapped(*args, **kwargs):
            self.start()
            try:
                return f(*args, **kwargs)
            finally:
                self.stop()
        return wrapped

    def __call__(self, f):
        """Wrap a function with the tracer"""
        return self.wrap(f)

    def __iter__(self):
        return iter(self.parsing_state["parsed_trace"])

    def __repr__(self):
        return f"{self.__class__.__name__}({len(self.parsing_state['parsed_trace'])}/{len(self.trace)})\n\t{self.parsed_string}"


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
    parser.add_argument('--link', type=str, default=Config.DEFAULT, help='String to be used to link consecutive lines')
    parser.add_argument("--start_line_pattern", type=str, default='^if __name__ == "__main__":\s*', help="Regex pattern to match the initial line at which to start trace")
    parser.add_argument("--start_file_pattern", type=str, default=Config.DEFAULT, help="Regex pattern to match the initial file at which to start trace")
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='If set, debug messages are printed to the console')

    args = parser.parse_args()

    if args.start_file_pattern == Config.DEFAULT:
        args.start_file_pattern = ".*" + args.script
    config_args = {k: v for k, v in vars(args).items() if v != Config.DEFAULT and k not in ["script", "verbose"]}
    config = Config(**config_args)

    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.addHandler(logging.StreamHandler(sys.stdout))
    with FullTracer(**config.__dict__) as ft:
        # This will run the script as if it were the "__main__" module
        runpy.run_path(args.script, run_name="__main__")
    print(ft)


if __name__ == '__main__':
    main()