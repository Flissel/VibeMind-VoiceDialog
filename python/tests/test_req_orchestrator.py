#!/usr/bin/env python3
"""Test req-orchestrator integration with e-ticketing bubble."""
import sys
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv('../.env', override=True)

from tools.summary_tools import submit_to_req_orchestrator, get_requirement_clarifications

print('=== Testing submit_to_req_orchestrator ===')
result = submit_to_req_orchestrator({
    'bubble_name': 'e-ticketing',
    'output_dir': '../test_output/requirements'
})
print(result)
print()

print('=== Testing get_requirement_clarifications ===')
clarifications = get_requirement_clarifications({})
print(clarifications)
