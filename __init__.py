"""
Drought Ensemble Modeling Package

A comprehensive package for drought ensemble modeling using ParFlow and related tools.

This package provides:
- Domain management and configuration
- Run execution and management
- Analysis tools for drought metrics
- Support for multiple river basins (Wolf, Potomac, Gila)

Main modules:
- classes: Core Domain and Run classes
- analysis: Analysis tools and utilities
- drought_metrics: Drought metric calculations
- domains: Domain-specific configurations
"""

# Import main classes for easy access
from .classes import Domain, Run, RunOutputReader
from .ensemble_running import run_sequence_on_domain

# Version information
__version__ = '1.0.0'
__author__ = 'Drought Ensemble Team'
__email__ = 'benjaminwest@arizona.edu'

# Main exports
__all__ = [
    'Domain',
    'Run',
    'RunOutputReader',
    'run_sequence_on_domain',
    'classes',
    'analysis', 
    'drought_metrics',
    'ensemble_running',
    'wolf',
    'potomac',
    'gila',
    'wolf_2008',
    'wolf_copy',
    'tests'
]

# Convenience imports for backward compatibility
def get_domain(config):
    """Convenience function to get domain from config"""
    from .get_domain import get_domain as _get_domain
    return _get_domain(config)

def add_pumping(*args, **kwargs):
    """Convenience function to add pumping"""
    from .add_pumping import add_pumping as _add_pumping
    return _add_pumping(*args, **kwargs)
