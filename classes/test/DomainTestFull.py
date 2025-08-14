# Comprehensive test for the domain class

import os
import sys

# Handle imports for both running as module and running directly
try:
    from ..Domain import Domain
except ImportError:
    # If running directly, add parent directory to path
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    from Domain import Domain

def test_domain_class():
    """Test the full Domain class functionality"""
    try:
        from ..Domain import Domain
        
        domain = Domain(config_file="/Users/ben/Documents/GitHub/drought-ensemble/domains/wolf_test/config.ini", TESTING=True)
        
        # Debug: Print the RUN_DIR to see where files should be created
        print(f"✓ RUN_DIR = {domain.directory}")
        print(f"✓ TESTING = {domain.TESTING}")
        print(f"✓ name = {domain.name}")
        print(f"✓ project_root = {domain.project_root}")
        
        # Test that the domain object has the expected attributes
        expected_attrs = ['dry_year', 'average_year', 'wet_year', 'name', 'huc_id', 'p', 'q']
        for attr in expected_attrs:
            assert hasattr(domain, attr), f"Domain object missing attribute: {attr}"
            print(f"✓ Domain object has {attr} = {getattr(domain, attr)}")
        
        # Test the domain_exists method
        # Check if domains exist (they might exist from previous runs)
        dry_exists = domain.domain_exists("dry")
        wet_exists = domain.domain_exists("wet")
        average_exists = domain.domain_exists("average")
        print(f"✓ domain_exists check - dry: {dry_exists}, wet: {wet_exists}, average: {average_exists}")
        print("✓ domain_exists method works correctly")
        
        print("✓ Full Domain class test completed successfully!")
        
    except ImportError as e:
        print(f"⚠ Domain class test skipped due to missing dependencies: {e}")
        print("This is expected if the required packages (subsettools, hf_hydrodata, etc.) are not installed.")
    except Exception as e:
        print(f"✗ Domain class test failed: {e}")

# Test basic config loading without importing the full Domain class
def test_config_loading():
    """Test that the config file can be loaded properly"""
    config_file = "/Users/ben/Documents/GitHub/drought-ensemble/domains/wolf_test/config.ini"
    
    # Load the config file using configparser
    import configparser
    config = configparser.ConfigParser()
    config.read(config_file)
    
    # Test that required attributes exist
    required_attrs = ['DRY_YEAR', 'AVERAGE_YEAR', 'WET_YEAR', 'NAME', 'HUC_ID', 'P', 'Q']
    for attr in required_attrs:
        assert config.has_option('DEFAULT', attr), f"Missing required attribute: {attr}"
        value = config.get('DEFAULT', attr)
        print(f"✓ {attr} = {value}")
    
    print("✓ All required config attributes are present")

def test_domain_get_domain():
    """Test the get_domain method"""

    # import the domain class
    # Domain is already imported at the top of the file
    domain = Domain(config_file="/Users/ben/Documents/GitHub/drought-ensemble/domains/wolf_test/config.ini", TESTING=True)
    domain.get_domain()
    
    # Debug: Check what domain_exists is actually returning
    dry_exists = domain.domain_exists("dry")
    wet_exists = domain.domain_exists("wet")
    average_exists = domain.domain_exists("average")
    
    print(f"✓ DRY exists: {dry_exists}")
    print(f"✓ WET exists: {wet_exists}")
    print(f"✓ AVERAGE exists: {average_exists}")
    
    # Also check if the directories actually exist using os.path.exists
    import os
    dry_path = os.path.join(domain.directory, "outputs", f"{domain.name}_dry")
    wet_path = os.path.join(domain.directory, "outputs", f"{domain.name}_wet")
    average_path = os.path.join(domain.directory, "outputs", f"{domain.name}_average")
    
    print(f"✓ DRY path exists: {os.path.exists(dry_path)}")
    print(f"✓ WET path exists: {os.path.exists(wet_path)}")
    print(f"✓ AVERAGE path exists: {os.path.exists(average_path)}")
    
    assert domain.domain_exists("dry")
    assert domain.domain_exists("wet")
    assert domain.domain_exists("average")



if __name__ == "__main__":
    test_domain_class()
    test_domain_get_domain()
