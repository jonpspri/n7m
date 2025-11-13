# CIDR Allocate Lookup Plugin

A sophisticated Ansible lookup plugin for intelligent CIDR block allocation with best-fit algorithm support.

## Features

- **Smart Allocation**: Automatically finds available CIDR blocks within a master range
- **Best-Fit Algorithm**: Minimizes address space fragmentation by selecting the smallest suitable gap
- **Conflict Avoidance**: Respects already-allocated CIDR blocks of any size
- **Proper Alignment**: Ensures allocated blocks are properly aligned on CIDR boundaries
- **Overlap Handling**: Intelligently merges overlapping used ranges
- **Comprehensive Validation**: Validates all inputs and provides clear error messages

## Installation

### Option 1: Lookup Plugin Directory (Recommended)
```bash
# Create lookup_plugins directory in your playbook directory
mkdir -p lookup_plugins

# Move the plugin
mv library/cidr_allocate.py lookup_plugins/
```

### Option 2: Environment Variable
```bash
# Set the lookup plugins path to include the library directory
export ANSIBLE_LOOKUP_PLUGINS=./library:$ANSIBLE_LOOKUP_PLUGINS
```

### Option 3: Ansible Configuration
Add to `ansible.cfg`:
```ini
[defaults]
lookup_plugins = ./library:~/.ansible/plugins/lookup:/usr/share/ansible/plugins/lookup
```

## Usage

### Basic Syntax

```yaml
"{{ lookup('cidr_allocate',
    master_cidr='172.16.0.0/12',
    prefix_length=24,
    used_cidrs=[]) }}"
```

### Parameters

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `master_cidr` | Yes | String | The master CIDR range to allocate from (e.g., '172.16.0.0/12') |
| `prefix_length` | Yes | Integer | Desired prefix length for the allocation (e.g., 24 for /24) |
| `used_cidrs` | No | List | List of already-allocated CIDR blocks to avoid (default: []) |

## Examples

### Example 1: Simple Allocation
Allocate a /24 network from a /12 master range with no existing allocations:

```yaml
- name: Allocate a /24 network
  set_fact:
    new_network: "{{ lookup('cidr_allocate',
                     master_cidr='172.16.0.0/12',
                     prefix_length=24,
                     used_cidrs=[]) }}"
  # Result: 172.16.0.0/24
```

### Example 2: Avoiding Existing Allocations
Allocate a /24 network while avoiding already-used blocks:

```yaml
- name: Allocate avoiding existing networks
  set_fact:
    new_network: "{{ lookup('cidr_allocate',
                     master_cidr='172.16.0.0/12',
                     prefix_length=24,
                     used_cidrs=['172.16.0.0/16', '172.17.0.0/16']) }}"
  # Result: 172.18.0.0/24 (best-fit in smallest available gap)
```

### Example 3: VPC CIDR Allocation
Allocate a /16 VPC CIDR block:

```yaml
- name: Get existing VPC CIDRs
  set_fact:
    existing_vpcs:
      - "172.16.0.0/16"
      - "172.17.0.0/16"

- name: Allocate new VPC CIDR
  set_fact:
    new_vpc_cidr: "{{ lookup('cidr_allocate',
                      master_cidr='172.16.0.0/12',
                      prefix_length=16,
                      used_cidrs=existing_vpcs) }}"
  # Result: 172.18.0.0/16
```

### Example 4: Multiple Sequential Allocations
Allocate multiple subnets in sequence:

```yaml
- name: Allocate multiple subnets
  set_fact:
    allocated_subnets: "{{ allocated_subnets | default([]) +
                          [lookup('cidr_allocate',
                           master_cidr='10.0.0.0/8',
                           prefix_length=24,
                           used_cidrs=(existing_networks + allocated_subnets | default([])))] }}"
  loop: "{{ range(0, 5) | list }}"
  loop_control:
    label: "Subnet {{ item + 1 }}"
```

### Example 5: Error Handling
Handle allocation failures gracefully:

```yaml
- name: Try to allocate
  block:
    - set_fact:
        new_cidr: "{{ lookup('cidr_allocate',
                     master_cidr='192.168.1.0/24',
                     prefix_length=24,
                     used_cidrs=['192.168.1.0/24']) }}"
  rescue:
    - debug:
        msg: "No available CIDR blocks in the specified range"
```

## Algorithm Details

### Best-Fit Allocation

The plugin implements a best-fit algorithm that:

1. **Identifies Gaps**: Finds all unused contiguous address ranges within the master CIDR
2. **Merges Overlaps**: Intelligently merges overlapping or adjacent used ranges
3. **Validates Alignment**: Ensures CIDR blocks are properly aligned (e.g., /24 on 256-byte boundaries)
4. **Selects Smallest Gap**: Chooses the smallest available gap that fits the requested size
5. **Minimizes Fragmentation**: Preserves larger gaps for future larger allocations

### Example Behavior

Given:
- Master CIDR: `172.16.0.0/12` (covers 172.16.0.0 - 172.31.255.255)
- Used blocks: `['172.16.0.0/15', '172.18.1.0/24']`
- Requested: `/24`

The plugin will:
1. Find gaps:
   - Gap 1: `172.18.0.0/24` (256 addresses) - small gap
   - Gap 2: `172.18.2.0 - 172.31.255.255` - large gap
2. Select the smallest suitable gap (Gap 1)
3. Return: `172.18.0.0/24`

This approach maximizes address space efficiency.

## Testing

A comprehensive test suite is included:

```bash
# Run the test suite
cd library
python3 test_cidr_allocate.py
```

The test suite covers:
- Basic allocation with no conflicts
- Allocation with existing used blocks
- Best-fit algorithm verification
- CIDR alignment requirements
- Various prefix sizes
- Overlapping range handling
- Error conditions
- Edge cases

## Error Handling

The plugin will fail with descriptive errors for:

- Invalid CIDR notation
- Prefix length smaller than master CIDR prefix
- Prefix length > 32
- No available address space
- Gaps too small for requested allocation

Example error messages:
```
Invalid master CIDR '172.16.0.0/40': netmask is > 32
Requested prefix length (16) is smaller than master CIDR prefix length (24)
Cannot allocate /16 network in 172.16.0.0/12. No suitable gaps found.
```

## Technical Notes

### CIDR Alignment

CIDR blocks must be aligned on specific boundaries:
- `/24` must start where the last 8 bits are zero (e.g., x.x.0.0, x.x.1.0, x.x.2.0)
- `/23` must start on 512-address boundaries (e.g., x.x.0.0, x.x.2.0, x.x.4.0)
- `/16` must start where the last 16 bits are zero (e.g., x.0.0.0)

The plugin automatically handles this alignment.

### Performance

The plugin is optimized for typical enterprise use cases:
- Handles hundreds of existing allocations efficiently
- O(n log n) complexity for sorting and merging
- Minimal memory footprint
- Fast execution (typically < 100ms)

## Use Cases

1. **Dynamic VPC Creation**: Automatically allocate VPC CIDRs without manual tracking
2. **Subnet Management**: Allocate subnets within VPCs dynamically
3. **Network Automation**: Integrate with cloud provisioning workflows
4. **IPAM Integration**: Use as part of IP Address Management workflows
5. **Testing**: Generate non-conflicting test networks

## Requirements

- Python 3.6+
- Ansible 2.9+
- Python `ipaddress` module (standard library)

## License

GNU General Public License v3.0+

## Support

For issues or questions:
1. Check the test suite for usage examples
2. Review the example playbook
3. Examine error messages carefully (they're designed to be helpful)
