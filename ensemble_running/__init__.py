"""
Ensemble Running Package

This package contains utilities for running ensemble simulations.
"""

try:
    from .run_sequence_on_domain import run_sequence_on_domain
except ImportError:
    # Handle case where dependencies are not available
    def run_sequence_on_domain(*args, **kwargs):
        raise ImportError("Required dependencies (numpy, etc.) are not installed")

__all__ = ['run_sequence_on_domain']
__version__ = '1.0.0'
