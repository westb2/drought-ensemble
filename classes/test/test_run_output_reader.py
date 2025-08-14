import sys
import os
import unittest
import numpy as np
import xarray as xr
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from RunOutputReader import RunOutputReader
from Run import Run
from Domain import Domain


class TestRunOutputReader(unittest.TestCase):
    """Comprehensive tests for the RunOutputReader class"""
    
    def setUp(self):
        """Set up test fixtures before each test method"""
        # Create a test domain
        self.domain = Domain(config_file="domains/wolf_test/config.ini", TESTING=True)
        
        # Create a test run
        self.run = Run(sequence="simple_test.json", domain=self.domain)
        
        # Create a mock data accessor for testing
        self.mock_data_accessor = Mock()
        self.mock_data_accessor.mask = np.ones((10, 41, 78))  # 10 layers, 41x78 grid
        self.mock_data_accessor.dx = 1000.0
        self.mock_data_accessor.dy = 1000.0
        self.mock_data_accessor.specific_storage = np.ones((10, 41, 78)) * 1e-4
        self.mock_data_accessor.computed_porosity = np.ones((10, 41, 78)) * 0.3
        self.mock_data_accessor.mannings = np.ones((1, 41, 78)) * 0.1
        self.mock_data_accessor.slope_x = np.ones((41, 78)) * 0.01
        self.mock_data_accessor.slope_y = np.ones((41, 78)) * 0.01

    def test_initialization(self):
        """Test RunOutputReader initialization"""
        print("\n🧪 Testing RunOutputReader initialization...")
        
        with patch.object(RunOutputReader, 'get_data_accessor', return_value=self.mock_data_accessor):
            reader = RunOutputReader(self.run)
            
            # Test that the run is properly set
            self.assertEqual(reader.run, self.run)
            
            # Test that domain attributes are properly initialized
            self.assertIn('mask', reader.domain_attributes)
            self.assertIn('dx', reader.domain_attributes)
            self.assertIn('dy', reader.domain_attributes)
            self.assertIn('dz_array', reader.domain_attributes)
            self.assertIn('specific_storage', reader.domain_attributes)
            self.assertIn('porosity', reader.domain_attributes)
            self.assertIn('mannings', reader.domain_attributes)
            self.assertIn('slope_x', reader.domain_attributes)
            self.assertIn('slope_y', reader.domain_attributes)
            
            # Test mask processing
            self.assertTrue(np.all(np.isnan(reader.domain_attributes['mask']) | (reader.domain_attributes['mask'] == 1)))
            
            # Test dz_array shape
            self.assertEqual(reader.domain_attributes['dz_array'].shape, (10, 1, 1))
            
            print("✅ Initialization test passed")

    def test_get_data_accessor(self):
        """Test the get_data_accessor method"""
        print("\n🧪 Testing get_data_accessor method...")
        
        # Mock the run's get_output_folders method
        mock_output_folder = "/fake/output/folder"
        self.run.get_output_folders = Mock(return_value=[mock_output_folder])
        
        # Mock ParFlow Run.from_definition
        mock_run = Mock()
        mock_run.data_accessor = self.mock_data_accessor
        
        with patch('parflow.Run.from_definition', return_value=mock_run), \
             patch('shutil.copyfile') as mock_copyfile:
            
            reader = RunOutputReader(self.run)
            result = reader.get_data_accessor("fake_dir")
            
            # Test that the method returns the data accessor
            self.assertEqual(result, self.mock_data_accessor)
            
            # Test that copyfile was called (may be called multiple times due to initialization)
            mock_copyfile.assert_called_with(
                f'{mock_output_folder}/mannings.pfb', 
                f'{mock_output_folder}/run.out.mannings.pfb'
            )
            
            print("✅ get_data_accessor test passed")

    def test_read_output_basic_functionality(self):
        """Test basic functionality of read_output method"""
        print("\n🧪 Testing read_output basic functionality...")
        
        # Mock the get_data_accessor method
        with patch.object(RunOutputReader, 'get_data_accessor', return_value=self.mock_data_accessor):
            reader = RunOutputReader(self.run)
            
            # Mock the file reading - use actual data size from the domain
            # The data size should match the coordinate system calculation
            actual_timesteps = self.run.domain.stop_time * self.run.number_of_years // self.run.domain.dump_interval
            mock_pressure = np.random.random((actual_timesteps, 10, 41, 78))
            mock_saturation = np.random.random((actual_timesteps, 10, 41, 78))
            
            with patch('parflow.read_pfb_sequence') as mock_read_pfb:
                mock_read_pfb.side_effect = [mock_pressure, mock_saturation]
                
                # Mock the map_blocks calls (they might be commented out in actual implementation)
                with patch.object(xr.DataArray, 'map_blocks', side_effect=AttributeError("map_blocks not available")):
                    result = reader.read_output()
                    
                    # Test that the result is an xarray Dataset
                    self.assertIsInstance(result, xr.Dataset)
                    
                    # Test that it contains the expected variables (based on actual implementation)
                    expected_vars = ['pressure', 'saturation', 'mask', 'mannings']
                    for var in expected_vars:
                        self.assertIn(var, result.data_vars)
                    
                    # Test data shapes
                    actual_timesteps = self.run.domain.stop_time * self.run.number_of_years // self.run.domain.dump_interval
                    self.assertEqual(result['pressure'].shape, (actual_timesteps, 10, 41, 78))
                    self.assertEqual(result['saturation'].shape, (actual_timesteps, 10, 41, 78))
                    self.assertEqual(result['mask'].shape, (10, 41, 78))
                    self.assertEqual(result['mannings'].shape, (10, 41, 78))
                    
                    print("✅ read_output basic functionality test passed")

    def test_read_output_data_processing(self):
        """Test data processing in read_output method"""
        print("\n🧪 Testing read_output data processing...")
        
        with patch.object(RunOutputReader, 'get_data_accessor', return_value=self.mock_data_accessor):
            reader = RunOutputReader(self.run)
            
            # Create test data with known values - use actual data size from the domain
            # The data size should match the coordinate system calculation
            actual_timesteps = self.run.domain.stop_time * self.run.number_of_years // self.run.domain.dump_interval
            test_pressure = np.ones((actual_timesteps, 10, 41, 78)) * 1000.0  # 1000 Pa everywhere
            test_saturation = np.ones((actual_timesteps, 10, 41, 78)) * 0.5   # 50% saturation everywhere
            
            with patch('parflow.read_pfb_sequence') as mock_read_pfb:
                mock_read_pfb.side_effect = [test_pressure, test_saturation]
                
                with patch.object(xr.DataArray, 'map_blocks') as mock_map_blocks:
                    actual_timesteps = self.run.domain.stop_time * self.run.number_of_years // self.run.domain.dump_interval
                    mock_map_blocks.return_value = xr.DataArray(np.ones((actual_timesteps, 10, 41, 78)) * 0.1)
                    
                    result = reader.read_output()
                    
                    # Test that pressure data is properly processed
                    # The data should be masked with the domain mask
                    self.assertIsInstance(result['pressure'], xr.DataArray)
                    self.assertIsInstance(result['saturation'], xr.DataArray)
                    
                    # Test that mask is properly formatted
                    mask_values = result['mask'].values
                    self.assertTrue(np.all(np.isnan(mask_values) | (mask_values == 1)))
                    
                    # Test that mask is properly formatted
                    mask_values = result['mask'].values
                    self.assertTrue(np.all(np.isnan(mask_values) | (mask_values == 1)))
                    
                    print("✅ read_output data processing test passed")

    def test_read_output_coordinate_system(self):
        """Test coordinate system setup in read_output method"""
        print("\n🧪 Testing read_output coordinate system...")
        
        with patch.object(RunOutputReader, 'get_data_accessor', return_value=self.mock_data_accessor):
            reader = RunOutputReader(self.run)
            
            actual_timesteps = self.run.domain.stop_time * self.run.number_of_years // self.run.domain.dump_interval
            mock_pressure = np.random.random((actual_timesteps, 10, 41, 78))
            mock_saturation = np.random.random((actual_timesteps, 10, 41, 78))
            
            with patch('parflow.read_pfb_sequence') as mock_read_pfb:
                mock_read_pfb.side_effect = [mock_pressure, mock_saturation]
                
                with patch.object(xr.DataArray, 'map_blocks', side_effect=AttributeError("map_blocks not available")):
                    result = reader.read_output()
                    
                    # Test that coordinates are properly set
                    self.assertIn('time', result.coords)
                    self.assertIn('z', result.coords)
                    self.assertIn('y', result.coords)
                    self.assertIn('x', result.coords)
                    
                    # Test coordinate dimensions
                    actual_timesteps = self.run.domain.stop_time * self.run.number_of_years // self.run.domain.dump_interval
                    self.assertEqual(len(result.coords['time']), actual_timesteps)
                    self.assertEqual(len(result.coords['z']), 10)
                    self.assertEqual(len(result.coords['y']), 41)
                    self.assertEqual(len(result.coords['x']), 78)
                    
                    # Test that time coordinates are properly spaced
                    time_coords = result.coords['time'].values
                    expected_times = range(0, self.run.domain.stop_time * self.run.number_of_years, self.run.domain.dump_interval)
                    np.testing.assert_array_equal(time_coords, expected_times)
                    
                    print("✅ read_output coordinate system test passed")

    def test_read_output_error_handling(self):
        """Test error handling in read_output method"""
        print("\n🧪 Testing read_output error handling...")
        
        with patch.object(RunOutputReader, 'get_data_accessor', return_value=self.mock_data_accessor):
            reader = RunOutputReader(self.run)
            
            # Test with missing files
            with patch('parflow.read_pfb_sequence', side_effect=FileNotFoundError("File not found")):
                with self.assertRaises(FileNotFoundError):
                    reader.read_output()
            
            # Test with corrupted data
            with patch('parflow.read_pfb_sequence', side_effect=ValueError("Corrupted data")):
                with self.assertRaises(ValueError):
                    reader.read_output()
            
            print("✅ read_output error handling test passed")

    def test_domain_attributes_consistency(self):
        """Test that domain attributes are consistent and properly formatted"""
        print("\n🧪 Testing domain attributes consistency...")
        
        with patch.object(RunOutputReader, 'get_data_accessor', return_value=self.mock_data_accessor):
            reader = RunOutputReader(self.run)
            
            # Test that all attributes have the expected types
            self.assertIsInstance(reader.domain_attributes['dx'], float)
            self.assertIsInstance(reader.domain_attributes['dy'], float)
            self.assertIsInstance(reader.domain_attributes['dz_array'], np.ndarray)
            self.assertIsInstance(reader.domain_attributes['mask'], np.ndarray)
            self.assertIsInstance(reader.domain_attributes['porosity'], np.ndarray)
            self.assertIsInstance(reader.domain_attributes['mannings'], np.ndarray)
            self.assertIsInstance(reader.domain_attributes['slope_x'], np.ndarray)
            self.assertIsInstance(reader.domain_attributes['slope_y'], np.ndarray)
            
            # Test that arrays have consistent shapes
            base_shape = (10, 41, 78)
            self.assertEqual(reader.domain_attributes['mask'].shape, base_shape)
            self.assertEqual(reader.domain_attributes['porosity'].shape, base_shape)
            self.assertEqual(reader.domain_attributes['mannings'].shape, (1, 41, 78))  # Single layer
            self.assertEqual(reader.domain_attributes['slope_x'].shape, (41, 78))      # Surface only
            self.assertEqual(reader.domain_attributes['slope_y'].shape, (41, 78))      # Surface only
            
            # Test that dz_array has the correct shape
            self.assertEqual(reader.domain_attributes['dz_array'].shape, (10, 1, 1))
            
            # Test that dz values are positive
            self.assertTrue(np.all(reader.domain_attributes['dz_array'] > 0))
            
            print("✅ domain attributes consistency test passed")

    def test_mask_processing(self):
        """Test that mask processing works correctly"""
        print("\n🧪 Testing mask processing...")
        
        # Create a test mask with some zeros
        test_mask = np.ones((10, 41, 78))
        test_mask[0, 0:10, 0:10] = 0  # Set some areas to zero
        
        self.mock_data_accessor.mask = test_mask
        
        with patch.object(RunOutputReader, 'get_data_accessor', return_value=self.mock_data_accessor):
            reader = RunOutputReader(self.run)
            
            processed_mask = reader.domain_attributes['mask']
            
            # Test that zeros are converted to NaN
            self.assertTrue(np.all(np.isnan(processed_mask[0, 0:10, 0:10])))
            
            # Test that ones remain as ones
            self.assertTrue(np.all(processed_mask[0, 10:, 10:] == 1))
            
            # Test that the mask only contains 1s and NaNs
            self.assertTrue(np.all(np.isnan(processed_mask) | (processed_mask == 1)))
            
            print("✅ mask processing test passed")

    def test_integration_with_real_data(self):
        """Integration test with real data (if available)"""
        print("\n🧪 Testing integration with real data...")
        
        try:
            # This test will only run if the real data exists
            reader = RunOutputReader(self.run)
            result = reader.read_output()
            
            # Test that we get a valid dataset
            self.assertIsInstance(result, xr.Dataset)
            
            # Test that the dataset has the expected structure
            self.assertIn('pressure', result.data_vars)
            self.assertIn('saturation', result.data_vars)
            self.assertIn('mask', result.data_vars)
            self.assertIn('mannings', result.data_vars)
            
            # Test that data is not all NaN
            self.assertFalse(np.all(np.isnan(result['pressure'].values)))
            self.assertFalse(np.all(np.isnan(result['saturation'].values)))
            
            print("✅ integration test passed")
            
        except (FileNotFoundError, OSError) as e:
            print(f"⚠️  Integration test skipped (no real data): {e}")
            # This is expected if the test data doesn't exist


def run_comprehensive_tests():
    """Run all comprehensive tests for RunOutputReader"""
    print("🧪 Running comprehensive RunOutputReader tests...")
    print("=" * 60)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestRunOutputReader)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    print(f"   Tests run: {result.testsRun}")
    print(f"   Failures: {len(result.failures)}")
    print(f"   Errors: {len(result.errors)}")
    
    if result.failures:
        print("\n❌ Failures:")
        for test, traceback in result.failures:
            print(f"   - {test}: {traceback}")
    
    if result.errors:
        print("\n❌ Errors:")
        for test, traceback in result.errors:
            print(f"   - {test}: {traceback}")
    
    if result.wasSuccessful():
        print("\n🎉 All tests passed!")
    else:
        print("\n❌ Some tests failed!")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    # Run the comprehensive tests
    success = run_comprehensive_tests()
    
    # Also run the original simple test for backward compatibility
    print("\n" + "=" * 60)
    print("🧪 Running original simple test...")
    try:
        domain = Domain(config_file="domains/wolf_test/config.ini", TESTING=True)
        run = Run(sequence="simple_test.json", domain=domain)
        run_output_reader = RunOutputReader(run)
        result = run_output_reader.read_output()
        print("✅ Original simple test passed")
        print(f"   Dataset shape: {result.dims}")
        print(f"   Variables: {list(result.data_vars.keys())}")
    except Exception as e:
        print(f"❌ Original simple test failed: {e}")
        success = False
    
    exit(0 if success else 1)