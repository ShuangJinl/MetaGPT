#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MetaGPT CLI Entry Point

Usage:
    python -m metagpt [OPTIONS] COMMAND [ARGS]...

Examples:
    python -m metagpt "write a cli blackjack game"
    python -m metagpt "search papers about machine learning"
    python -m metagpt --help
"""

from metagpt.software_company import app

if __name__ == "__main__":
    app()
