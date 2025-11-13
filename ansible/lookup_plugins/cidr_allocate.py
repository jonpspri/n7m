#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2025
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
lookup: cidr_allocate
author: Ansible
version_added: "1.0.0"
short_description: Allocate an available CIDR block from a master range
description:
    - Finds and allocates an available CIDR block of a specified size within a master CIDR range.
    - Avoids conflicts with already-allocated CIDR blocks.
    - Uses a best-fit algorithm to efficiently utilize the address space by preferring the smallest available gap.
options:
    _terms:
        description: Not used, but kept for lookup plugin compatibility
        required: false
    master_cidr:
        description:
            - The master CIDR range from which to allocate (e.g., '172.16.0.0/12').
        required: true
        type: str
    used_cidrs:
        description:
            - List of CIDR blocks that are already in use and should be avoided.
            - Can be of varying prefix lengths.
        required: false
        type: list
        elements: str
        default: []
    prefix_length:
        description:
            - The desired prefix length for the new CIDR block (e.g., 24 for a /24 network).
            - Must be >= the master CIDR's prefix length and <= 32.
        required: true
        type: int
notes:
    - This lookup plugin uses a best-fit algorithm to find the smallest available gap that can accommodate the requested CIDR block.
    - The allocated CIDR block will be properly aligned on network boundaries.
    - If no suitable block is found, the plugin will fail with an error message.
"""

EXAMPLES = r"""
# Allocate a /24 network from a master /12 range
- name: Allocate CIDR block
  debug:
    msg: "{{ lookup('cidr_allocate', master_cidr='172.16.0.0/12', prefix_length=24, used_cidrs=[]) }}"

# Allocate a /24 avoiding already-used blocks
- name: Allocate CIDR block with exclusions
  debug:
    msg: "{{ lookup('cidr_allocate', master_cidr='172.16.0.0/12', prefix_length=24,
         used_cidrs=['172.16.0.0/16', '172.17.0.0/16', '172.18.5.0/24']) }}"

# Use the allocated CIDR in a variable
- name: Get new VPC CIDR
  set_fact:
    new_vpc_cidr: "{{ lookup('cidr_allocate',
                      master_cidr='10.0.0.0/8',
                      prefix_length=16,
                      used_cidrs=existing_cidrs) }}"
"""

RETURN = r"""
_raw:
    description:
        - The allocated CIDR block in standard notation (e.g., '172.16.5.0/24')
    type: str
"""

import ipaddress
from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase


class CIDRAllocator:
    """
    Handles the logic for finding and allocating available CIDR blocks.
    Uses a best-fit algorithm to minimize address space fragmentation.
    """

    def __init__(self, master_cidr, used_cidrs, prefix_length):
        """
        Initialize the CIDR allocator.

        Args:
            master_cidr: String representation of the master CIDR (e.g., '172.16.0.0/12')
            used_cidrs: List of already-allocated CIDR strings
            prefix_length: Desired prefix length for the new allocation (e.g., 24)
        """
        try:
            self.master_network = ipaddress.ip_network(master_cidr, strict=False)
        except (ValueError, TypeError) as e:
            raise AnsibleError(f"Invalid master CIDR '{master_cidr}': {str(e)}")

        self.prefix_length = prefix_length
        self.used_networks = []

        # Validate prefix length
        if not isinstance(prefix_length, int):
            raise AnsibleError(f"prefix_length must be an integer, got {type(prefix_length).__name__}")

        if prefix_length < self.master_network.prefixlen:
            raise AnsibleError(
                f"Requested prefix length ({prefix_length}) is smaller than master CIDR "
                f"prefix length ({self.master_network.prefixlen})"
            )

        if prefix_length > 32:
            raise AnsibleError(f"Requested prefix length ({prefix_length}) must be <= 32")

        # Parse and validate used CIDRs
        for cidr in used_cidrs:
            try:
                network = ipaddress.ip_network(cidr, strict=False)
                # Only include networks that overlap with master range
                if self._networks_overlap(network, self.master_network):
                    self.used_networks.append(network)
            except (ValueError, TypeError) as e:
                raise AnsibleError(f"Invalid CIDR in used_cidrs '{cidr}': {str(e)}")

        # Sort used networks by starting address for easier gap finding
        self.used_networks.sort(key=lambda net: net.network_address)

    def _networks_overlap(self, net1, net2):
        """Check if two networks overlap."""
        return net1.overlaps(net2)

    def _merge_overlapping_ranges(self):
        """
        Merge overlapping or adjacent used networks into contiguous ranges.
        Returns a list of (start_int, end_int) tuples representing used IP ranges.
        """
        if not self.used_networks:
            return []

        # Convert networks to integer ranges
        ranges = []
        for network in self.used_networks:
            start = int(network.network_address)
            end = int(network.broadcast_address)
            ranges.append((start, end))

        # Merge overlapping ranges
        merged = []
        current_start, current_end = ranges[0]

        for start, end in ranges[1:]:
            if start <= current_end + 1:  # Overlapping or adjacent
                current_end = max(current_end, end)
            else:
                merged.append((current_start, current_end))
                current_start, current_end = start, end

        merged.append((current_start, current_end))
        return merged

    def _find_available_gaps(self):
        """
        Find all gaps (unused ranges) in the master CIDR.
        Returns a list of (start_int, end_int) tuples.
        """
        master_start = int(self.master_network.network_address)
        master_end = int(self.master_network.broadcast_address)

        used_ranges = self._merge_overlapping_ranges()
        gaps = []

        # Check for gap before first used range
        if not used_ranges:
            gaps.append((master_start, master_end))
            return gaps

        if used_ranges[0][0] > master_start:
            gaps.append((master_start, used_ranges[0][0] - 1))

        # Check for gaps between used ranges
        for i in range(len(used_ranges) - 1):
            gap_start = used_ranges[i][1] + 1
            gap_end = used_ranges[i + 1][0] - 1
            if gap_start <= gap_end:
                gaps.append((gap_start, gap_end))

        # Check for gap after last used range
        if used_ranges[-1][1] < master_end:
            gaps.append((used_ranges[-1][1] + 1, master_end))

        return gaps

    def _find_aligned_cidr_in_gap(self, gap_start, gap_end):
        """
        Find a properly-aligned CIDR block of the desired prefix length within a gap.

        Args:
            gap_start: Starting IP address (as integer) of the gap
            gap_end: Ending IP address (as integer) of the gap

        Returns:
            ipaddress.IPv4Network object if found, None otherwise
        """
        # Calculate the size of the network we want to allocate
        network_size = 2 ** (32 - self.prefix_length)

        # Find the alignment requirement (CIDR blocks must start on specific boundaries)
        alignment = network_size

        # Find the first aligned address >= gap_start
        aligned_start = gap_start
        if gap_start % alignment != 0:
            aligned_start = ((gap_start // alignment) + 1) * alignment

        # Check if the aligned network fits in the gap
        aligned_end = aligned_start + network_size - 1

        if aligned_end <= gap_end:
            # Create and return the network
            network_addr = ipaddress.IPv4Address(aligned_start)
            return ipaddress.ip_network(f"{network_addr}/{self.prefix_length}", strict=False)

        return None

    def allocate(self):
        """
        Find and return an available CIDR block using best-fit algorithm.

        Returns:
            String representation of the allocated CIDR block

        Raises:
            AnsibleError if no suitable block can be found
        """
        gaps = self._find_available_gaps()

        if not gaps:
            raise AnsibleError(
                f"No available address space in master CIDR {self.master_network}. "
                f"All addresses are allocated."
            )

        # For each gap, try to find a valid CIDR allocation
        # Store tuples of (gap_size, cidr_network, gap_info) for best-fit selection
        candidates = []

        for gap_start, gap_end in gaps:
            cidr = self._find_aligned_cidr_in_gap(gap_start, gap_end)
            if cidr:
                gap_size = gap_end - gap_start + 1
                candidates.append((gap_size, cidr, (gap_start, gap_end)))

        if not candidates:
            # Calculate how much space we need
            needed_size = 2 ** (32 - self.prefix_length)
            raise AnsibleError(
                f"Cannot allocate /{self.prefix_length} network in {self.master_network}. "
                f"No suitable gaps found. Need {needed_size} contiguous addresses. "
                f"Available gaps: {[f'{ipaddress.IPv4Address(s)}-{ipaddress.IPv4Address(e)} '
                f'({e-s+1} addresses)' for s, e in gaps]}"
            )

        # Sort by gap size (smallest first) for best-fit algorithm
        candidates.sort(key=lambda x: x[0])

        # Return the CIDR from the smallest gap
        _, best_cidr, _ = candidates[0]
        return str(best_cidr)


class LookupModule(LookupBase):
    """
    Ansible lookup plugin for CIDR allocation.
    """

    def run(self, terms, variables=None, **kwargs):
        """
        Main entry point for the lookup plugin.

        Args:
            terms: Positional arguments (not used)
            variables: Ansible variables in scope
            **kwargs: Keyword arguments (master_cidr, used_cidrs, prefix_length)

        Returns:
            List containing a single CIDR string
        """
        # Get parameters
        master_cidr = kwargs.get("master_cidr")
        used_cidrs = kwargs.get("used_cidrs", [])
        prefix_length = kwargs.get("prefix_length")

        # Validate required parameters
        if not master_cidr:
            raise AnsibleError("master_cidr parameter is required")

        if prefix_length is None:
            raise AnsibleError("prefix_length parameter is required")

        # Ensure used_cidrs is a list
        if not isinstance(used_cidrs, list):
            raise AnsibleError(f"used_cidrs must be a list, got {type(used_cidrs).__name__}")

        # Create allocator and find available CIDR
        allocator = CIDRAllocator(master_cidr, used_cidrs, prefix_length)
        allocated_cidr = allocator.allocate()

        # Return as a list (lookup plugins must return lists)
        return [allocated_cidr]
