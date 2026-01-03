#!/usr/bin/env python3
"""Test script for list_ideas and list_bubbles with debug output."""

import sys
import logging

# Create handlers for both console and file
file_handler = logging.FileHandler('test_output.log', mode='w')
console_handler = logging.StreamHandler(sys.stdout)

logging.basicConfig(
    level=logging.INFO, 
    format='%(name)s - %(message)s',
    handlers=[file_handler, console_handler]
)

from tools.idea_tools import list_ideas
from tools.bubble_tools import list_bubbles, enter_bubble, exit_bubble

print("\n" + "="*60, flush=True)
print("TEST 1: list_bubbles (show all spaces)", flush=True)
print("="*60, flush=True)
result = list_bubbles({})
print(f"Result: {result}", flush=True)

print("\n" + "="*60, flush=True)
print("TEST 2: list_ideas (no bubble entered - should fail)", flush=True)
print("="*60, flush=True)
result = list_ideas({})
print(f"Result: {result}", flush=True)

print("\n" + "="*60, flush=True)
print("TEST 3: enter_bubble('Personal space')", flush=True)
print("="*60, flush=True)
result = enter_bubble({"bubble_name": "Personal space"})
print(f"Result: {result}", flush=True)

print("\n" + "="*60, flush=True)
print("TEST 4: list_ideas (inside bubble - should show notes)", flush=True)  
print("="*60, flush=True)
result = list_ideas({})
print(f"Result: {result}", flush=True)

print("\n" + "="*60, flush=True)
print("TEST 5: exit_bubble", flush=True)
print("="*60, flush=True)
result = exit_bubble({})
print(f"Result: {result}", flush=True)

print("\n=== All tests done ===", flush=True)