#!/usr/bin/env python3
"""
Example usage of the drought-ensemble package with proper imports.

This script demonstrates how to use the package without sys.path.append.
"""

# Method 1: Import from the main package
from drought_ensemble import Domain, Run, get_domain, add_pumping

# Method 2: Import from specific subpackages
from drought_ensemble.classes import Domain as DomainClass
from drought_ensemble.classes import Run as RunClass

# Method 3: Import domain-specific configs
from drought_ensemble.wolf import config as wolf_config
from drought_ensemble.potomac import config as potomac_config

def example_domain_usage():
    """Example of using the Domain class"""
    print("=== Domain Usage Example ===")
    
    # Create a domain with testing enabled
    domain = Domain(
        config_file="/Users/ben/Documents/GitHub/drought-ensemble/domains/wolf_test/config.ini", 
        TESTING=True
    )
    
    print(f"Domain name: {domain.name}")
    print(f"Domain HUC ID: {domain.huc_id}")
    print(f"Run directory: {domain.RUN_DIR}")
    print(f"Testing mode: {domain.TESTING}")
    
    return domain

def example_run_usage():
    """Example of using the Run class"""
    print("\n=== Run Usage Example ===")
    
    # First create a domain
    domain = Domain(
        config_file="/Users/ben/Documents/GitHub/drought-ensemble/domains/wolf_test/config.ini", 
        TESTING=True
    )
    
    # Create a run
    run = Run(
        domain=domain, 
        sequence_file="domains/wolf_test/run_sequences/simple_test.json"
    )
    
    print(f"Run directory: {run.run_dir}")
    print(f"Testing mode: {run.TESTING}")
    
    return run

def example_config_usage():
    """Example of using domain configs"""
    print("\n=== Config Usage Example ===")
    
    # Access wolf domain config
    print(f"Wolf domain config: {wolf_config.DOMAIN_NAME}")
    print(f"Wolf HUC ID: {wolf_config.CURRENT_HUC_ID}")
    
    # Access potomac domain config
    print(f"Potomac domain config: {potomac_config.DOMAIN_NAME}")
    print(f"Potomac HUC ID: {potomac_config.CURRENT_HUC_ID}")

if __name__ == "__main__":
    print("Drought Ensemble Package Example")
    print("=" * 40)
    
    try:
        # Example 1: Domain usage
        domain = example_domain_usage()
        
        # Example 2: Run usage
        run = example_run_usage()
        
        # Example 3: Config usage
        example_config_usage()
        
        print("\n✅ All examples completed successfully!")
        print("\nKey benefits of the new package structure:")
        print("- No more sys.path.append needed")
        print("- Clean, explicit imports")
        print("- Better organization and maintainability")
        print("- Easy to import from anywhere in the project")
        
    except Exception as e:
        print(f"❌ Error running examples: {e}")
        print("Make sure you're running this from the project root directory")

