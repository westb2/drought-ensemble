The below content was AI generated

# Drought Ensemble Modeling Package

A comprehensive Python package for drought ensemble modeling using ParFlow and related tools.

## Overview

This package provides tools for:
- **Domain Management**: Creating and configuring modeling domains for different river basins
- **Run Execution**: Managing ParFlow model runs with various scenarios
- **Analysis Tools**: Processing and analyzing drought metrics and model outputs
- **Multi-Basin Support**: Wolf, Potomac, and Gila River domains

## Project Structure

```
drought-ensemble/
├── __init__.py                 # Main package initialization
├── classes/                    # Core classes
│   ├── __init__.py            # Classes package
│   ├── Domain.py              # Domain management class
│   ├── Run.py                 # Run execution class
│   └── test/                  # Class-specific tests
│       ├── __init__.py        # Test package
│       ├── DomainTestFull.py  # Domain class tests
│       └── test_run.py        # Run class tests
├── analysis/                   # Analysis tools
│   ├── __init__.py            # Analysis package
│   ├── utils.py               # Utility functions
│   ├── pumping_analysis.ipynb # Pumping analysis notebook
│   ├── recovery_analysis.ipynb # Recovery analysis notebook
│   └── poster_figures.ipynb   # Poster figure generation
├── drought_metrics/           # Drought metric calculations
│   ├── __init__.py            # Metrics package
│   ├── pdsi.ipynb            # PDSI calculations
│   └── data/                  # Data files
├── domains/                   # Domain configurations
│   ├── wolf_test/            # Wolf River test domain
│   ├── inputs/               # Domain inputs
│   └── outputs/              # Domain outputs
├── wolf/                      # Wolf River domain
│   ├── __init__.py           # Wolf package
│   ├── config.py             # Wolf configuration
│   ├── do_run.ipynb          # Run execution notebook
│   └── get_domain.ipynb      # Domain setup notebook
├── potomac/                   # Potomac River domain
│   ├── __init__.py           # Potomac package
│   ├── config.py             # Potomac configuration
│   └── ...                   # Similar structure
├── gila/                      # Gila River domain
│   ├── __init__.py           # Gila package
│   ├── config.py             # Gila configuration
│   └── ...                   # Similar structure
├── tests/                     # Test infrastructure
│   ├── __init__.py           # Tests package
│   └── test_imports.py       # Import structure tests
├── run_tests.py               # Test runner script
├── example_usage.py           # Usage examples
└── README.md                  # This file
```

## Installation

### Prerequisites

1. **Python Environment**: Python 3.7+ with conda or pip
2. **External Dependencies**:
   - `parflow`: ParFlow modeling framework
   - `subsettools`: Domain subsetting tools
   - `hf_hydrodata`: Hydro data access tools
   - `numpy`, `pandas`: Data processing

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd drought-ensemble

# Create and activate conda environment
conda create -n drought-env python=3.9
conda activate drought-env

# Install external dependencies (if available via conda/pip)
conda install -c conda-forge parflow
pip install subsettools hf_hydrodata

# The package is now ready to use
```

## Usage

### Basic Usage

```python
# Import main classes
from drought_ensemble import Domain, Run

# Create a domain
domain = Domain(
    config_file="domains/wolf_test/config.ini",
    TESTING=True
)

# Create and run a simulation
run = Run(
    domain=domain,
    sequence_file="domains/wolf_test/run_sequences/simple_test.json"
)
run.run()
```

### Domain-Specific Usage

```python
# Import domain configurations
from drought_ensemble.wolf import config as wolf_config
from drought_ensemble.potomac import config as potomac_config

# Access domain parameters
print(f"Wolf HUC ID: {wolf_config.CURRENT_HUC_ID}")
print(f"Potomac HUC ID: {potomac_config.CURRENT_HUC_ID}")
```

### Analysis Tools

```python
# Import analysis utilities
from drought_ensemble.analysis import utils

# Use utility functions
# (specific functions depend on utils.py implementation)
```

## Testing Infrastructure

### Test Organization

The project has a comprehensive testing infrastructure organized into several layers:

1. **Unit Tests** (`classes/test/`): Test individual classes and methods
2. **Integration Tests** (`tests/`): Test package structure and imports
3. **Notebook Tests**: Jupyter notebooks with example workflows

### Running Tests

#### Method 1: Test Runner (Recommended)

```bash
# Run all tests from project root
python run_tests.py
```

This runs:
- Package import tests
- Domain class tests
- Run class tests

#### Method 2: Individual Test Files

```bash
# Test import structure
python tests/test_imports.py

# Test domain functionality
python classes/test/DomainTestFull.py

# Test run functionality
python classes/test/test_run.py
```

#### Method 3: Module Execution

```bash
# Run tests as modules (most proper)
python -m classes.test.DomainTestFull
python -m classes.test.test_run
python -m tests.test_imports
```

#### Method 4: Domain-Specific Tests

```bash
# Test individual domains
python wolf/test.py
python potomac/test.py
python gila/test.py
```

### Test Categories

#### Import Structure Tests (`tests/test_imports.py`)
- Verifies package structure is correct
- Tests that all `__init__.py` files exist
- Validates import paths work without external dependencies

#### Domain Tests (`classes/test/DomainTestFull.py`)
- Tests Domain class functionality
- Validates configuration loading
- Tests domain creation and management

#### Run Tests (`classes/test/test_run.py`)
- Tests Run class functionality
- Validates run execution workflows
- Tests sequence management

### Test Dependencies

- **Core Tests**: No external dependencies required
- **Domain Tests**: Require `subsettools`, `hf_hydrodata`
- **Run Tests**: Require `parflow`, `subsettools`

### Adding New Tests

1. **Unit Tests**: Add to `classes/test/` directory
2. **Integration Tests**: Add to `tests/` directory
3. **Update `__init__.py`**: Add new test modules to `__all__`
4. **Update Test Runner**: Add new tests to `run_tests.py`

## Development

### Adding New Domains

1. Create domain directory (e.g., `new_river/`)
2. Add `__init__.py` with domain description
3. Create `config.py` with domain parameters
4. Add domain to main package `__init__.py`

### Adding New Classes

1. Create class file in `classes/`
2. Update `classes/__init__.py` to export the class
3. Update main package `__init__.py`
4. Add tests in `classes/test/`

### Code Style

- Follow PEP 8 for Python code
- Use descriptive docstrings
- Include type hints where possible
- Write tests for new functionality

## Troubleshooting

### Common Issues

#### Import Errors
```bash
# If you get "No module named 'drought_ensemble'"
# Make sure you're in the project root directory
cd /path/to/drought-ensemble
python tests/test_imports.py
```

#### Missing Dependencies
```bash
# Install required packages
conda install -c conda-forge parflow
pip install subsettools hf_hydrodata
```

#### Test Failures
```bash
# Run import tests first to verify structure
python tests/test_imports.py

# Check specific test failures
python -m classes.test.DomainTestFull
```

### Getting Help

1. **Check Test Output**: Run `python tests/test_imports.py` first
2. **Verify Dependencies**: Ensure all required packages are installed
3. **Check Paths**: Make sure you're running from the project root
4. **Review Logs**: Check error messages for specific import issues

## Contributing

1. **Fork the repository**
2. **Create a feature branch**
3. **Add tests for new functionality**
4. **Ensure all tests pass**
5. **Submit a pull request**

## License

[Add your license information here]

## Contact

- **Team**: Drought Ensemble Team
- **Email**: benjaminwest@arizona.edu
- **Project**: [Add project URL]
