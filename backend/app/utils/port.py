# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Port utility functions for Owlangs.

This module contains utilities for port management and network operations.
"""

import socket
from contextlib import closing


def find_free_port(start_port: int) -> int:
    """
    Find a free port starting from the given port number.
    
    Args:
        start_port: The port number to start searching from
        
    Returns:
        The first available port number
    """
    port = start_port
    while True:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            if sock.connect_ex(('127.0.0.1', port)) != 0:
                return port
            port += 1
