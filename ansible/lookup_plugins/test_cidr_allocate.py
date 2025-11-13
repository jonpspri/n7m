#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script for the CIDR allocator module.
This script tests the CIDRAllocator class directly without needing Ansible.
"""

import sys
import os

# Add the current directory to the path so we can import the module
sys.path.insert(0, os.path.dirname(__file__))

# Mock AnsibleError for testing
class AnsibleError(Exception):
    pass

# Inject mock into sys.modules before importing
if 'ansible' not in sys.modules:
    from types import ModuleType
    ansible_module = ModuleType('ansible')
    ansible_errors = ModuleType('ansible.errors')
    ansible_errors.AnsibleError = AnsibleError
    ansible_module.errors = ansible_errors
    sys.modules['ansible'] = ansible_module
    sys.modules['ansible.errors'] = ansible_errors

# Mock LookupBase for testing
class LookupBase:
    pass

if 'ansible.plugins' not in sys.modules:
    ansible_plugins = ModuleType('ansible.plugins')
    ansible_plugins_lookup = ModuleType('ansible.plugins.lookup')
    ansible_plugins_lookup.LookupBase = LookupBase
    ansible_plugins.lookup = ansible_plugins_lookup
    sys.modules['ansible.plugins'] = ansible_plugins
    sys.modules['ansible.plugins.lookup'] = ansible_plugins_lookup

from cidr_allocate import CIDRAllocator


def test_basic_allocation():
    """Test basic allocation with no used CIDRs."""
    print("Test 1: Basic allocation with no used CIDRs")
    allocator = CIDRAllocator("172.16.0.0/12", [], 24)
    result = allocator.allocate()
    print(f"  Master: 172.16.0.0/12")
    print(f"  Used: []")
    print(f"  Prefix: /24")
    print(f"  Result: {result}")
    assert result == "172.16.0.0/24", f"Expected 172.16.0.0/24, got {result}"
    print("  PASS\n")


def test_allocation_with_used_blocks():
    """Test allocation avoiding used blocks."""
    print("Test 2: Allocation with used blocks")
    used = ["172.16.0.0/16", "172.17.0.0/16"]
    allocator = CIDRAllocator("172.16.0.0/12", used, 24)
    result = allocator.allocate()
    print(f"  Master: 172.16.0.0/12")
    print(f"  Used: {used}")
    print(f"  Prefix: /24")
    print(f"  Result: {result}")
    # Should allocate in the gap after 172.17.0.0/16
    assert result == "172.18.0.0/24", f"Expected 172.18.0.0/24, got {result}"
    print("  PASS\n")


def test_best_fit_algorithm():
    """Test that best-fit algorithm chooses smallest gap."""
    print("Test 3: Best-fit algorithm (smallest gap selection)")
    # Create gaps of different sizes
    # Master: 172.16.0.0/12 covers 172.16.0.0 - 172.31.255.255
    # Gap 1: 172.16.0.0/16 to 172.17.255.255 (131072 addresses) - Used
    # Gap 2: 172.18.0.0/24 to 172.18.0.255 (256 addresses) - Available (small gap)
    # Gap 3: 172.19.0.0/16 to 172.31.255.255 (remaining) - Available (large gap)
    used = ["172.16.0.0/15", "172.18.1.0/24"]  # Leaves small gap at 172.18.0.0/24
    allocator = CIDRAllocator("172.16.0.0/12", used, 24)
    result = allocator.allocate()
    print(f"  Master: 172.16.0.0/12")
    print(f"  Used: {used}")
    print(f"  Prefix: /24")
    print(f"  Result: {result}")
    print(f"  Expected: 172.18.0.0/24 (fits in smallest available gap)")
    assert result == "172.18.0.0/24", f"Expected 172.18.0.0/24, got {result}"
    print("  PASS\n")


def test_alignment_requirements():
    """Test that allocations respect CIDR alignment."""
    print("Test 4: CIDR alignment requirements")
    # If 172.16.0.0/24 is used, and we want a /23,
    # it should align to /23 boundaries
    used = ["172.16.0.0/24"]
    allocator = CIDRAllocator("172.16.0.0/16", used, 23)
    result = allocator.allocate()
    print(f"  Master: 172.16.0.0/16")
    print(f"  Used: {used}")
    print(f"  Prefix: /23")
    print(f"  Result: {result}")
    # A /23 needs to be aligned to 512-address boundaries
    # 172.16.0.0/24 uses 172.16.0.0-172.16.0.255
    # Next /23 boundary is 172.16.2.0/23
    assert result == "172.16.2.0/23", f"Expected 172.16.2.0/23, got {result}"
    print("  PASS\n")


def test_various_prefix_sizes():
    """Test allocation of various prefix sizes."""
    print("Test 5: Various prefix sizes")
    test_cases = [
        ("10.0.0.0/8", [], 16, "10.0.0.0/16"),
        ("10.0.0.0/8", ["10.0.0.0/16"], 16, "10.1.0.0/16"),
        ("192.168.0.0/16", [], 20, "192.168.0.0/20"),
        # Note: 192.168.0.0/20 covers 192.168.0.0-192.168.15.255, so /24 goes after
        ("192.168.0.0/16", ["192.168.0.0/20"], 24, "192.168.16.0/24"),
    ]

    for master, used, prefix, expected in test_cases:
        allocator = CIDRAllocator(master, used, prefix)
        result = allocator.allocate()
        print(f"  Master: {master}, Used: {used}, Prefix: /{prefix}")
        print(f"  Result: {result}, Expected: {expected}")
        assert result == expected, f"Expected {expected}, got {result}"
        print("  PASS")
    print()


def test_overlapping_used_ranges():
    """Test handling of overlapping used ranges."""
    print("Test 6: Overlapping used ranges")
    # These ranges overlap and should be merged
    used = ["172.16.0.0/20", "172.16.8.0/21", "172.16.4.0/22"]
    allocator = CIDRAllocator("172.16.0.0/12", used, 24)
    result = allocator.allocate()
    print(f"  Master: 172.16.0.0/12")
    print(f"  Used: {used} (overlapping ranges)")
    print(f"  Prefix: /24")
    print(f"  Result: {result}")
    # Should allocate after the merged range
    assert result == "172.16.16.0/24", f"Expected 172.16.16.0/24, got {result}"
    print("  PASS\n")


def test_error_cases():
    """Test error handling."""
    print("Test 7: Error handling")

    # Test 7a: Invalid master CIDR
    print("  7a: Invalid master CIDR")
    try:
        allocator = CIDRAllocator("invalid", [], 24)
        print("  FAIL: Should have raised error")
        sys.exit(1)
    except Exception as e:
        print(f"  Correctly raised error: {e}")
        print("  PASS")

    # Test 7b: Prefix length larger than master
    print("  7b: Prefix length smaller than master")
    try:
        allocator = CIDRAllocator("172.16.0.0/24", [], 16)
        print("  FAIL: Should have raised error")
        sys.exit(1)
    except Exception as e:
        print(f"  Correctly raised error: {e}")
        print("  PASS")

    # Test 7c: No space available
    print("  7c: No space available")
    try:
        allocator = CIDRAllocator("172.16.0.0/24", ["172.16.0.0/24"], 24)
        result = allocator.allocate()
        print("  FAIL: Should have raised error")
        sys.exit(1)
    except Exception as e:
        print(f"  Correctly raised error: {e}")
        print("  PASS")

    print()


def test_small_gaps():
    """Test handling of gaps too small for requested size."""
    print("Test 8: Gaps too small for requested size")
    # Create a situation where there are small gaps but we need a larger block
    used = [
        "172.16.0.0/25",  # Uses 172.16.0.0-172.16.0.127
        "172.16.0.192/26",  # Uses 172.16.0.192-172.16.0.255
        # Gap: 172.16.0.128-172.16.0.191 (64 addresses) - too small for /24
    ]
    allocator = CIDRAllocator("172.16.0.0/16", used, 24)
    result = allocator.allocate()
    print(f"  Master: 172.16.0.0/16")
    print(f"  Used: {used}")
    print(f"  Prefix: /24")
    print(f"  Result: {result}")
    # Should skip the small gap and allocate after
    assert result == "172.16.1.0/24", f"Expected 172.16.1.0/24, got {result}"
    print("  PASS\n")


if __name__ == "__main__":
    print("=" * 70)
    print("CIDR Allocator Test Suite")
    print("=" * 70)
    print()

    try:
        test_basic_allocation()
        test_allocation_with_used_blocks()
        test_best_fit_algorithm()
        test_alignment_requirements()
        test_various_prefix_sizes()
        test_overlapping_used_ranges()
        test_error_cases()
        test_small_gaps()

        print("=" * 70)
        print("ALL TESTS PASSED!")
        print("=" * 70)
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
