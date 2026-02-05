"""
End-to-End Test Runner for Shuttle Agent System

This script runs all tests for the Shuttle Agent System, including:
- Unit tests for Shuttle Orchestrator Agent
- Unit tests for Shuttle Worker Agents
- Integration tests for the entire system

Usage:
    python tests/run_all_shuttle_tests.py
"""

import sys
import os
import subprocess
import time
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, '.')

logger = None
try:
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
except ImportError:
    logger = None


class TestRunner:
    """Test runner for Shuttle Agent System."""
    
    def __init__(self):
        """Initialize test runner."""
        self.test_results: List[Dict[str, Any]] = []
        self.total_tests = 0
        self.total_successes = 0
        self.total_failures = 0
        self.total_errors = 0
        self.total_time = 0.0
    
    def run_test(self, test_file: str, test_name: str) -> Dict[str, Any]:
        """Run a single test file."""
        if logger:
            logger.info(f"Running {test_name}...")
        
        start_time = time.time()
        
        try:
            # Run test file
            result = subprocess.run(
                [sys.executable, test_file],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            execution_time = time.time() - start_time
            
            # Parse output
            output = result.stdout + result.stderr
            
            # Extract test statistics
            tests_run = 0
            successes = 0
            failures = 0
            errors = 0
            
            for line in output.split('\n'):
                if 'Tests run:' in line:
                    try:
                        tests_run = int(line.split('Tests run:')[1].strip().split()[0])
                    except (IndexError, ValueError):
                        pass
                elif 'Successes:' in line:
                    try:
                        successes = int(line.split('Successes:')[1].strip().split()[0])
                    except (IndexError, ValueError):
                        pass
                elif 'Failures:' in line:
                    try:
                        failures = int(line.split('Failures:')[1].strip().split()[0])
                    except (IndexError, ValueError):
                        pass
                elif 'Errors:' in line:
                    try:
                        errors = int(line.split('Errors:')[1].strip().split()[0])
                    except (IndexError, ValueError):
                        pass
            
            # Determine if test passed
            passed = result.returncode == 0
            
            # Store result
            test_result = {
                "test_name": test_name,
                "test_file": test_file,
                "passed": passed,
                "tests_run": tests_run,
                "successes": successes,
                "failures": failures,
                "errors": errors,
                "execution_time": execution_time,
                "output": output,
            }
            
            self.test_results.append(test_result)
            
            # Update totals
            self.total_tests += tests_run
            self.total_successes += successes
            self.total_failures += failures
            self.total_errors += errors
            self.total_time += execution_time
            
            if logger:
                if passed:
                    logger.info(f"[PASS] {test_name} passed ({execution_time:.2f}s)")
                else:
                    logger.error(f"[FAIL] {test_name} failed ({execution_time:.2f}s)")
            
            return test_result
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            
            test_result = {
                "test_name": test_name,
                "test_file": test_file,
                "passed": False,
                "tests_run": 0,
                "successes": 0,
                "failures": 0,
                "errors": 1,
                "execution_time": execution_time,
                "output": "Test timed out after 5 minutes",
            }
            
            self.test_results.append(test_result)
            self.total_errors += 1
            self.total_time += execution_time
            
            if logger:
                logger.error(f"[TIMEOUT] {test_name} timed out ({execution_time:.2f}s)")
            
            return test_result
        
        except Exception as e:
            execution_time = time.time() - start_time
            
            test_result = {
                "test_name": test_name,
                "test_file": test_file,
                "passed": False,
                "tests_run": 0,
                "successes": 0,
                "failures": 0,
                "errors": 1,
                "execution_time": execution_time,
                "output": str(e),
            }
            
            self.test_results.append(test_result)
            self.total_errors += 1
            self.total_time += execution_time
            
            if logger:
                logger.error(f"[ERROR] {test_name} failed with exception: {e}")
            
            return test_result
    
    def run_all_tests(self) -> bool:
        """Run all tests."""
        if logger:
            logger.info("="*70)
            logger.info("SHUTTLE AGENT SYSTEM END-TO-END TESTS")
            logger.info("="*70)
            logger.info("")
        
        # Define tests to run
        tests = [
            {
                "file": "python/tests/test_shuttle_orchestrator_agent.py",
                "name": "Shuttle Orchestrator Agent Unit Tests"
            },
            {
                "file": "python/tests/test_shuttle_workers.py",
                "name": "Shuttle Worker Agents Unit Tests"
            },
            {
                "file": "python/tests/test_shuttle_integration.py",
                "name": "Shuttle Agent System Integration Tests"
            },
        ]
        
        # Run all tests
        for test in tests:
            self.run_test(test["file"], test["name"])
        
        # Print summary
        self.print_summary()
        
        # Return overall success
        return all(result["passed"] for result in self.test_results)
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*70)
        print("SHUTTLE AGENT SYSTEM END-TO-END TESTS - SUMMARY")
        print("="*70)
        print(f"\nTotal tests run: {self.total_tests}")
        print(f"Total successes: {self.total_successes}")
        print(f"Total failures: {self.total_failures}")
        print(f"Total errors: {self.total_errors}")
        print(f"Total time: {self.total_time:.2f}s")
        print("\n" + "="*70)
        print("DETAILED RESULTS")
        print("="*70 + "\n")
        
        for result in self.test_results:
            status = "[PASS]" if result["passed"] else "[FAIL]"
            print(f"{status}: {result['test_name']}")
            print(f"  Tests run: {result['tests_run']}")
            print(f"  Successes: {result['successes']}")
            print(f"  Failures: {result['failures']}")
            print(f"  Errors: {result['errors']}")
            print(f"  Time: {result['execution_time']:.2f}s")
            print()
        
        print("="*70)
        
        if logger:
            logger.info(f"\nTotal tests run: {self.total_tests}")
            logger.info(f"Total successes: {self.total_successes}")
            logger.info(f"Total failures: {self.total_failures}")
            logger.info(f"Total errors: {self.total_errors}")
            logger.info(f"Total time: {self.total_time:.2f}s")


def main():
    """Main function."""
    # Create test runner
    runner = TestRunner()
    
    # Run all tests
    success = runner.run_all_tests()
    
    # Return exit code
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
