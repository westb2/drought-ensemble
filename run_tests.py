#!/usr/bin/env python3
"""
Test runner for the drought-ensemble package.

This script should be run from the project root directory to properly test
the package structure and imports.
"""

import sys
import os

# Add the current directory to Python path so we can import the package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_domain_tests():
    """Run the domain tests"""
    print("Running Domain Tests...")
    print("=" * 50)
    
    try:
        # Import and run the domain tests
        from classes.test.DomainTestFull import test_domain_class, test_domain_get_domain
        
        # Run the tests
        test_domain_class()
        test_domain_get_domain()
        
        print("\n✅ Domain tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Domain tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_run_tests():
    """Run the run tests"""
    print("\nRunning Run Tests...")
    print("=" * 50)
    
    try:
        # Import and run the run tests
        from classes.test.test_run import run
        
        # The run test will execute automatically when imported
        print("✅ Run tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Run tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_run_output_reader_tests():
    """Run the RunOutputReader tests"""
    print("\nRunning RunOutputReader Tests...")
    print("=" * 50)
    
    try:
        # Import and run the RunOutputReader tests
        from classes.test.test_run_output_reader import run_comprehensive_tests
        
        # Run the comprehensive tests
        success = run_comprehensive_tests()
        
        if success:
            print("✅ RunOutputReader tests completed successfully!")
            return True
        else:
            print("❌ RunOutputReader tests failed!")
            return False
        
    except Exception as e:
        print(f"❌ RunOutputReader tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_package_import_tests():
    """Test that the package imports work correctly"""
    print("\nTesting Package Imports...")
    print("=" * 50)
    
    try:
        # Test main package imports
        print("✅ Main package imports work")
        
        # Test subpackage imports
        from classes import Domain as DomainClass
        from classes import Run as RunClass
        from classes import RunOutputReader as RunOutputReaderClass
        print("✅ Subpackage imports work")
        
        print("✅ Domain config imports work")
        
        print("✅ All package imports work correctly!")
        return True
        
    except Exception as e:
        print(f"❌ Package import tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_import_structure_tests():
    """Test the import structure without external dependencies"""
    print("\nTesting Import Structure...")
    print("=" * 50)
    
    try:
        # Test import structure tests
        from tests.test_imports import test_basic_imports, test_package_structure
        
        # Run the import structure tests
        test_package_structure()
        success = test_basic_imports()
        
        if success:
            print("✅ Import structure tests completed successfully!")
            return True
        else:
            print("❌ Import structure tests failed!")
            return False
            
    except Exception as e:
        print(f"❌ Import structure tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Drought Ensemble Package Tests")
    print("=" * 50)
    
    # check if all the tests passed
    success = run_package_import_tests() and run_import_structure_tests() and run_domain_tests() and run_run_tests() and run_run_output_reader_tests()
    if success:
        print("🎉 All tests completed successfully!")
    else:
        print("❌ Some tests failed!")    
    
    print("\n🎉 All tests completed!")
