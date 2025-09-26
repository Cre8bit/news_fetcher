#!/usr/bin/env python3
"""
Simple test runner for utils functions.
Run this script to test the clean_text, normalize_url, and extract_domain functions.
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def main():
    """Run the tests and show results."""
    print("Testing Utils Functions")
    print("=" * 50)
    
    # Import and run the tests
    from test_utils import TestCleanText, TestNormalizeUrl, TestExtractDomain
    import unittest
    
    # Create a test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestCleanText))
    suite.addTests(loader.loadTestsFromTestCase(TestNormalizeUrl))  
    suite.addTests(loader.loadTestsFromTestCase(TestExtractDomain))
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    if result.wasSuccessful():
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)