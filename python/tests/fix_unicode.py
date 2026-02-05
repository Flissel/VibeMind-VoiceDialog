"""
Fix Unicode Characters in Test Files

This script replaces Unicode characters with ASCII characters in test files
to avoid UnicodeEncodeError on Windows with cp1252 encoding.
"""

import os
import re

# Define Unicode to ASCII mappings
UNICODE_TO_ASCII = {
    '✓': '[PASS]',
    '✗': '[FAIL]',
}

def fix_unicode_in_file(file_path):
    """Fix Unicode characters in a file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace Unicode characters with ASCII
    for unicode_char, ascii_char in UNICODE_TO_ASCII.items():
        content = content.replace(unicode_char, ascii_char)
    
    # Write back to file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Fixed Unicode characters in {file_path}")

def main():
    """Main function."""
    # Define test files to fix
    test_files = [
        'test_shuttle_orchestrator_agent.py',
        'test_shuttle_workers.py',
        'test_shuttle_integration.py',
    ]
    
    # Fix Unicode characters in each file
    for test_file in test_files:
        if os.path.exists(test_file):
            fix_unicode_in_file(test_file)
        else:
            print(f"File not found: {test_file}")
    
    print("\nUnicode characters fixed successfully!")

if __name__ == "__main__":
    main()
