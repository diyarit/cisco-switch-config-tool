# Cisco Switch Configuration Tool

A powerful GUI application for managing and configuring Cisco switches with an intuitive interface. This tool streamlines the process of configuring multiple switch ports while enforcing best practices and maintaining consistency across your network infrastructure.

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

- **Configuration Management**
  - Save and load port configurations
  - Port description management
  - Configuration validation

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
   python CiscoConfigTool_v5.py
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

## Best Practices

- Always verify port selections before applying changes
- Use descriptive port descriptions for easier management
- Regularly save port configurations
- Follow your organization's VLAN numbering scheme
- Enable PortFast only on end-device facing ports

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
