"""
Entry point for python -m color_tools

This is the "doorman" - when you run the package as a module, Python
looks for this file and executes it. Our job: call cli.main() and get
out of the way!
"""

from .cli import main

if __name__ == "__main__":
    main()