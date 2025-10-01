# Cisco Switch Configuration Tool v6.0

A comprehensive GUI application for managing and configuring Cisco switches with an intuitive interface. This tool streamlines the process of configuring multiple switch ports while enforcing best practices and maintaining consistency across your network infrastructure.

## 🚀 What's New in v6.0

- **Automatic VLAN Detection**: Intelligently detects and adds VLANs referenced in port configurations
- **Smart VLAN Naming**: Automatic meaningful VLAN names (Data, Voice, Wireless, Guest, Management)
- **Enhanced Security Features**: Port security, DHCP snooping, DAI, IP source guard
- **Advanced Switching**: STP/RSTP/MSTP, VTP management, EtherChannel support
- **Professional Configuration**: Clean startup, comprehensive CLI generation
- **Network Management**: SNMP, NTP, PoE management, QoS configuration

## Features

- **Intuitive Port Management**
  - Visual port selection interface
  - Bulk port configuration
  - Support for both Access and Trunk ports

- **Access Port Configuration**
  - Data VLAN assignment
  - Voice VLAN support
  - PortFast configuration
  - QoS trust settings for voice traffic

- **Trunk Port Configuration**
  - Native VLAN configuration
  - Allowed VLANs management
  - Direct VLAN updates

- **Advanced Port Features**
  - Port Security (MAC address limiting, violation actions)
  - EtherChannel/LACP/PAGP configuration
  - Storm Control (broadcast, multicast, unicast)
  - PoE management and power limits
  - ACL assignment (inbound/outbound)

- **Global Configuration**
  - STP/RSTP/MSTP configuration
  - VTP domain management
  - SNMP configuration
  - NTP time synchronization
  - Security features (DHCP Snooping, DAI, IP Source Guard)

- **Security Features**
  - Port Security with sticky learning
  - DHCP Snooping
  - Dynamic ARP Inspection (DAI)
  - IP Source Guard
  - Storm Control

- **QoS Configuration**
  - Trust settings (CoS, DSCP)
  - Access Control Lists (Standard and Extended)
  - EtherChannel load balancing

- **Configuration Management**
  - Save and load port configurations
  - Port description management
  - Configuration validation
  - Template system for reusable configurations

## Installation

1. Ensure you have Python installed on your system
2. Clone this repository:
   ```bash
   git clone https://github.com/diyarit/cisco-switch-config-tool.git
   ```
3. Install required dependencies:
   ```bash
   pip install tkinter json re os
   ```

## Usage

1. Run the application:
   ```bash
   python CiscoConfigTool_v6.py
   ```

2. **Port Configuration:**
   - Select one or multiple ports in the interface
   - Choose between Access or Trunk mode
   - Configure port-specific settings:
     - For Access ports: Data VLAN, Voice VLAN, PortFast, QoS
     - For Trunk ports: Native VLAN, Allowed VLANs

3. **Bulk Operations:**
   - Select multiple ports for simultaneous configuration
   - Apply common settings across selected ports
   - Update trunk settings for multiple ports at once

## Configuration Examples

### Access Port Configuration
```
# Example Access Port Settings
- Mode: Access
- Data VLAN: 10
- Voice VLAN: 100
- PortFast: Enabled
- QoS Trust: Enabled for voice
```

### Trunk Port Configuration
```
# Example Trunk Port Settings
- Mode: Trunk
- Native VLAN: 1
- Allowed VLANs: ALL or "1,10-20,30"
```

### Advanced Port Features
```
# Port Security Example
- Enable Port Security: Yes
- Max MAC Addresses: 2
- Violation Action: Shutdown
- Sticky Learning: Enabled

# EtherChannel Example
- Enable EtherChannel: Yes
- Mode: LACP
- Group Number: 1
- Load Balance: src-dst-ip

# Storm Control Example
- Broadcast Storm Control: Enabled
- Threshold: 80%
```

### Global Configuration Examples
```
# STP Configuration
- STP Mode: Rapid-PVST
- Priority: 4096

# VTP Configuration
- VTP Mode: Transparent
- Domain: COMPANY
- Password: secure123

# Security Features
- DHCP Snooping: Enabled
- Dynamic ARP Inspection: Enabled
- IP Source Guard: Enabled

# Network Management
- SNMP Community: public
- NTP Server: time.nist.gov
- PoE Management: Enabled
```

## 🎯 Advanced Features

### **Automatic VLAN Management**
- **Smart Detection**: Automatically detects VLANs from port configurations
- **Intelligent Naming**: 
  - VLAN 1 → "Default"
  - VLAN 10 → "Data" 
  - VLAN 100 → "Voice"
  - VLAN 20 → "Wireless"
  - VLAN 30 → "Guest"
  - VLAN 1000 → "Management"

### **Security Configuration**
- **Port Security**: MAC address limiting, violation actions, sticky learning
- **DHCP Snooping**: Prevents rogue DHCP servers
- **Dynamic ARP Inspection**: Protects against ARP spoofing
- **IP Source Guard**: Validates source IP addresses
- **Storm Control**: Broadcast, multicast, unicast protection

### **Professional Configuration Generation**
- **Clean Startup**: No unwanted configuration output on launch
- **Comprehensive CLI**: Complete Cisco switch configuration
- **Best Practices**: Industry-standard security and performance settings
- **Error Prevention**: Automatic VLAN detection prevents missing VLANs

## Best Practices

- Always verify port selections before applying changes
- Use descriptive port descriptions for easier management
- Regularly save port configurations
- Follow your organization's VLAN numbering scheme
- Enable PortFast only on end-device facing ports
- Use meaningful VLAN names for better network documentation
- Enable security features (port security, DHCP snooping) on access ports
- Configure STP properly to prevent network loops

## 📋 Changelog

### v6.0.0 (Latest)
- ✨ **NEW**: Automatic VLAN detection and smart naming
- ✨ **NEW**: Enhanced security features (port security, DAI, IP source guard)
- ✨ **NEW**: Advanced switching protocols (STP/RSTP/MSTP, VTP)
- ✨ **NEW**: Network management (SNMP, NTP, PoE)
- ✨ **NEW**: Professional configuration generation
- 🔧 **IMPROVED**: Clean application startup
- 🔧 **IMPROVED**: Comprehensive CLI command generation
- 🔧 **IMPROVED**: Better error handling and validation

### v5.1.0
- Basic port configuration (access/trunk)
- VLAN management
- Template system
- Global configuration settings

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📞 Support

For issues, feature requests, or questions, please open an issue on GitHub.
