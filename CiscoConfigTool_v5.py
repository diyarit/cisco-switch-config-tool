import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog, font as tkFont
import platform
import math
import json
import os
from datetime import datetime
import re

# --- Constants ---
APP_VERSION = "5.1.0"
APP_COPYRIGHT = "© 2025 Network Solutions"

PORT_SIZE = 40
PORT_PAD_X = 10
PORT_PAD_Y = 10
PORTS_PER_ROW = 12
DEFAULT_PORT_COLOR = "#d9d9d9"
SELECTED_PORT_COLOR = "#add8e6"
CONFIGURED_PORT_COLOR = "#90ee90"

# Interface type definitions
INTERFACE_TYPES = {
    "FastEthernet": {"prefix": "FastEthernet", "abbrev": "Fa", "speed": "10/100 Mbps"},
    "GigabitEthernet": {"prefix": "GigabitEthernet", "abbrev": "Gi", "speed": "10/100/1000 Mbps"},
    "TenGigabitEthernet": {"prefix": "TenGigabitEthernet", "abbrev": "Te", "speed": "10 Gbps"}
}
DEFAULT_INTERFACE_TYPE = "GigabitEthernet"
DEFAULT_SLOT = "0"
DEFAULT_SUBSLOT = "0"

# --- Tooltip Helper Class ---
class ToolTip:
    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(500, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def showtip(self, event=None):
        x = y = 0
        try:
            x, y, cx, cy = self.widget.bbox("insert")
            x += self.widget.winfo_rootx() + 20
            y += self.widget.winfo_rooty() + 20
        except tk.TclError:
            try:
                x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
                y = self.widget.winfo_rooty() + self.widget.winfo_height() // 2
            except tk.TclError:
                return

        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{max(0, x)}+{max(0, y)}")
        label = tk.Label(self.tw, text=self.text, justify='left',
                       background="#ffffe0", relief='solid', borderwidth=1,
                       wraplength=300)
        label.pack(ipadx=2, ipady=1)

    def hidetip(self):
        tw = self.tw
        self.tw = None
        if tw:
            try:
                if tw.winfo_exists():
                    tw.destroy()
            except tk.TclError:
                pass

# --- Main Application Class ---
class CiscoConfigTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Cisco Configuration Tool v5.1")

        # Make the window responsive
        self.root.minsize(800, 600)  # Set minimum window size

        # Configure root grid weights
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # --- Style and Font Setup ---
        self._setup_styles_and_fonts()

        # --- State Variables ---
        self.config_commands = []
        self.port_items = {}
        self.port_configs = {}
        self.selected_ports = set()
        self.last_clicked_port = None
        self.config_history = []  # Track states for undo/redo
        self.current_step = -1  # History pointer

        # File paths for saving/loading configurations
        self.port_configs_file = "port_configs.json"
        self.global_configs_file = "global_configs.json"

        # Track configured VLANs
        self.configured_vlans = set()  # Track configured VLAN IDs

        # Global configuration storage
        self.global_configs = {
            "hostname": "",
            "enable_secret": "",
            "line_password": "",
            "vty_ssh": True,
            "vty_telnet": True,
            "pwd_encrypt": True,
            "no_domain_lookup": True,
            "vlans": {},  # {vlan_id: vlan_name}
            "svi_interface": "Vlan1",
            "svi_ip": "",
            "svi_mask": "255.255.255.0",
            "svi_desc": "",
            "gateway_ip": ""
        }

        # --- Configurable Settings ---
        self.total_ports_var = tk.IntVar(value=24)
        self.interface_prefix_var = tk.StringVar(value=INTERFACE_TYPES[DEFAULT_INTERFACE_TYPE]['prefix'])
        self.ports_per_row_var = tk.IntVar(value=PORTS_PER_ROW)

        # Add template configurations
        self.port_templates = {
            "Access Port": {
                "mode": "access",
                "description": "Standard Access Port",
                "access_vlan": "10",
                "portfast": True,
                "qos_trust": False
            },
            "Phone Port": {
                "mode": "access",
                "description": "Voice + Data Port",
                "access_vlan": "10",
                "voice_vlan": "100",
                "portfast": True,
                "qos_trust": True
            },
            "AP Port": {
                "mode": "trunk",
                "description": "Access Point Port",
                "native_vlan": "10",
                "trunk_vlans": "10,20,30,100",
                "portfast": True,
                "qos_trust": True
            },
            "Trunk Port": {
                "mode": "trunk",
                "description": "Trunk to Switch",
                "native_vlan": "10",
                "trunk_vlans": "ALL",
                "portfast": False,
                "qos_trust": True
            }
        }

        # Add validation patterns
        self.validation_patterns = {
            "vlan": r"^([1-9]|[1-9][0-9]|[1-9][0-9][0-9]|[1-3][0-9][0-9][0-9]|40[0-9][0-4])$",
            "hostname": r"^[a-zA-Z0-9\-\_\.]+$",
            "ip_address": r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$"
        }

        # --- Create Main Layout ---
        self._create_main_layout()

        # --- Initial Drawing ---
        self._draw_switch()

        # Load configurations if they exist
        self._load_port_configs()
        self._load_global_configs()

        # Initialize the VLAN list
        self._refresh_vlan_list()

    def _setup_styles_and_fonts(self):
        style = ttk.Style()
        available_themes = style.theme_names()
        if 'vista' in available_themes and platform.system() == "Windows":
            style.theme_use('vista')
        elif 'clam' in available_themes:
            style.theme_use('clam')
        elif 'aqua' in available_themes and platform.system() == "Darwin":
            style.theme_use('aqua')
        elif 'alt' in available_themes:
            style.theme_use('alt')

        # Configure Accent button style
        style.configure("Accent.TButton",
                      font=('TkDefaultFont', 10, 'bold'),
                      padding=5)

        self.default_font = tkFont.nametofont("TkDefaultFont")
        self.default_font.configure(size=10)
        self.root.option_add("*Font", self.default_font)
        self.mono_font = ("Courier New", 9)
        self.port_label_font = (self.default_font.actual()['family'], 8)
        self.small_font_tuple = (self.default_font.actual()['family'], 8)

    def _create_main_layout(self):
        # Main container frame
        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Configure weights for main_frame
        main_frame.grid_rowconfigure(0, weight=1)  # Top section (switch and config)
        main_frame.grid_rowconfigure(1, weight=0)  # Bottom section (output and controls)
        main_frame.grid_columnconfigure(0, weight=3)  # Switch view gets more space
        main_frame.grid_columnconfigure(1, weight=2)  # Config panel gets less space

        # Left side (Switch view and settings)
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left_frame.grid_rowconfigure(1, weight=1)  # Switch canvas gets all extra space
        left_frame.grid_columnconfigure(0, weight=1)

        # Settings at the top
        self._create_settings_widgets(left_frame)

        # Switch canvas area
        self._setup_canvas_area(left_frame)

        # Right side (Configuration panels)
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        # Create a notebook for configuration panels
        self.config_notebook = ttk.Notebook(right_frame)
        self.config_notebook.grid(row=0, column=0, sticky="nsew")

        # Port Configuration Tab
        port_config_tab = ttk.Frame(self.config_notebook)
        self.config_notebook.add(port_config_tab, text="Port Config")
        self._create_port_config_panel_widgets(port_config_tab)

        # Global Configuration Tab
        global_config_tab = ttk.Frame(self.config_notebook)
        self.config_notebook.add(global_config_tab, text="Global Config")
        self._create_global_config_panel_widgets(global_config_tab)

        # Add Template Editor Tab
        template_editor_tab = ttk.Frame(self.config_notebook)
        self.config_notebook.add(template_editor_tab, text="Template Editor")
        self._create_template_editor_widgets(template_editor_tab)

        # Bind tab change event
        self.config_notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Bottom frame (Output and controls)
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(5, 0))
        self._create_bottom_frame_layout(bottom_frame)

    def _setup_canvas_area(self, parent_frame):
        # Create a frame to hold the canvas and scrollbars
        canvas_frame = ttk.Frame(parent_frame)
        canvas_frame.grid(row=1, column=0, sticky="nsew")
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)

        # Create canvas and scrollbars
        self.switch_canvas = tk.Canvas(canvas_frame, bg="white")
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.switch_canvas.xview)
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.switch_canvas.yview)

        # Configure canvas scrolling
        self.switch_canvas.configure(xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)

        # Grid layout for canvas and scrollbars
        self.switch_canvas.grid(row=0, column=0, sticky="nsew")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")

        # Bind canvas events
        self.switch_canvas.bind("<Button-1>", self.on_port_click)
        self.switch_canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_canvas_configure(self, event):
        # Update the scrollregion when the canvas is resized
        self.switch_canvas.configure(scrollregion=self.switch_canvas.bbox("all"))

    def _create_settings_widgets(self, parent_frame):
        settings_frame = ttk.Frame(parent_frame, padding=(0, 0, 0, 10))
        settings_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))

        # Port Count
        ttk.Label(settings_frame, text="Port Count:").pack(side=tk.LEFT, padx=(0, 5))
        port_count_spin = ttk.Spinbox(settings_frame, from_=1, to=96,
                                    textvariable=self.total_ports_var, width=5)
        port_count_spin.pack(side=tk.LEFT, padx=5)
        ToolTip(port_count_spin, "Total number of ports to display (1-96).")

        # Interface Type Selection
        ttk.Label(settings_frame, text="Interface Type:").pack(side=tk.LEFT, padx=(15, 5))
        self.interface_type_var = tk.StringVar(value=DEFAULT_INTERFACE_TYPE)
        interface_type_combo = ttk.Combobox(settings_frame, textvariable=self.interface_type_var,
                                         values=list(INTERFACE_TYPES.keys()), state="readonly", width=15)
        interface_type_combo.pack(side=tk.LEFT, padx=5)
        ToolTip(interface_type_combo, "Select interface type (FastEthernet, GigabitEthernet, TenGigabitEthernet)")

        # Slot Number
        ttk.Label(settings_frame, text="Slot:").pack(side=tk.LEFT, padx=(15, 5))
        self.slot_var = tk.StringVar(value=DEFAULT_SLOT)
        slot_entry = ttk.Entry(settings_frame, textvariable=self.slot_var, width=3)
        slot_entry.pack(side=tk.LEFT, padx=5)
        ToolTip(slot_entry, "Slot number (0-9)")

        # Subslot Number
        ttk.Label(settings_frame, text="Subslot:").pack(side=tk.LEFT, padx=(15, 5))
        self.subslot_var = tk.StringVar(value=DEFAULT_SUBSLOT)
        subslot_entry = ttk.Entry(settings_frame, textvariable=self.subslot_var, width=3)
        subslot_entry.pack(side=tk.LEFT, padx=5)
        ToolTip(subslot_entry, "Subslot number (0-9)")

        # Update Button
        update_btn = ttk.Button(settings_frame, text="Update Layout", command=self._draw_switch)
        update_btn.pack(side=tk.LEFT, padx=15)
        ToolTip(update_btn, "Redraw the switch diagram with the specified port count.")

        # Bind events to update interface prefix
        interface_type_combo.bind("<<ComboboxSelected>>", self._update_interface_prefix)
        slot_entry.bind("<KeyRelease>", self._update_interface_prefix)
        subslot_entry.bind("<KeyRelease>", self._update_interface_prefix)

    def _update_interface_prefix(self, event=None):
        """Update the interface prefix based on selected interface type and slot/subslot values."""
        interface_type = self.interface_type_var.get()
        slot = self.slot_var.get().strip()
        subslot = self.subslot_var.get().strip()

        # Validate slot and subslot are numeric
        if not slot.isdigit() or not subslot.isdigit():
            return

        # Update the interface prefix
        prefix = INTERFACE_TYPES[interface_type]['prefix']
        self.interface_prefix_var.set(f"{prefix}{slot}/{subslot}/")
        self.update_status(f"Interface prefix updated to {self.interface_prefix_var.get()}")

    def _calculate_canvas_size(self):
        ports_per_row = self.ports_per_row_var.get()
        total_ports = self.total_ports_var.get()
        if ports_per_row <= 0:
            ports_per_row = 1
        if total_ports <= 0:
            total_ports = 1

        num_rows = math.ceil(total_ports / ports_per_row)
        canvas_width = ports_per_row * (PORT_SIZE + PORT_PAD_X) + PORT_PAD_X
        canvas_height = num_rows * (PORT_SIZE + PORT_PAD_Y) + PORT_PAD_Y
        return canvas_width, canvas_height

    def _draw_switch(self):
        self.switch_canvas.delete("all")
        self.port_items.clear()
        self.last_clicked_port = None

        total_ports = self.total_ports_var.get()
        ports_per_row = self.ports_per_row_var.get()
        if ports_per_row <= 0:
            ports_per_row = 1
        if total_ports <= 0:
            messagebox.showwarning("Invalid Setting",
                                 "Port count must be greater than 0.",
                                 parent=self.root)
            self.total_ports_var.set(1)
            total_ports = 1

        canvas_width, canvas_height = self._calculate_canvas_size()
        self.switch_canvas.config(scrollregion=(0, 0, canvas_width, canvas_height))

        start_x = PORT_PAD_X
        start_y = PORT_PAD_Y

        for i in range(total_ports):
            port_num = i + 1
            row = i // ports_per_row
            col = i % ports_per_row

            x1 = start_x + col * (PORT_SIZE + PORT_PAD_X)
            y1 = start_y + row * (PORT_SIZE + PORT_PAD_Y)
            x2 = x1 + PORT_SIZE
            y2 = y1 + PORT_SIZE

            rect_id = self.switch_canvas.create_rectangle(
                x1, y1, x2, y2, fill=DEFAULT_PORT_COLOR, outline="black",
                tags=("port", f"port_{port_num}"))
            text_id = self.switch_canvas.create_text(
                x1 + PORT_SIZE / 2, y1 + PORT_SIZE / 2, text=str(port_num),
                font=self.port_label_font, tags=("port_text", f"port_{port_num}"))
            self.port_items[port_num] = {'rect': rect_id, 'text': text_id}

        # Remove selections/configs for ports that no longer exist
        ports_to_remove = {p for p in self.selected_ports if p > total_ports}
        self.selected_ports -= ports_to_remove
        keys_to_remove = [p for p in self.port_configs if p > total_ports]
        for key in keys_to_remove:
            del self.port_configs[key]

        self._update_port_visuals()
        self.update_status(f"Switch layout updated for {total_ports} ports.")

    def _clear_port_selection(self):
        """Clear all port selections."""
        # Debug output
        print("Clearing all port selections")
        print(f"Before clear - Selected ports: {sorted(list(self.selected_ports))}")

        # Clear the selection
        self.selected_ports = set()
        self.last_clicked_port = None

        # Debug output
        print(f"After clear - Selected ports: {sorted(list(self.selected_ports))}")

        # Update the UI
        self._update_port_visuals()
        self._reset_port_config_panel()

        # Update status
        self.update_status("All port selections cleared")

    def _show_all_configurations(self):
        """Show all configurations including global settings and port configurations."""
        # Debug output
        print("Showing all configurations")
        print(f"Configured ports: {sorted(list(self.port_configs.keys()))}")

        # Clear the output
        self.output_text.delete("1.0", tk.END)
        self.config_commands = []

        # First, show global configurations
        self._show_global_configurations()

        # Then show port configurations
        if not self.port_configs:
            if self.output_text.get("1.0", tk.END).strip() == "":
                self.output_text.insert(tk.END, "No ports are currently configured.\n")
            return

        # Generate commands for all configured ports
        configured_ports = sorted(list(self.port_configs.keys()))
        for port_num in configured_ports:
            port_config = self.port_configs[port_num]
            self.output_text.insert(tk.END, f"\n! --- Configuration for port(s) {port_num} ---\n")
            interface_name = f"{self.interface_prefix_var.get()}{port_num}"

            # Generate configuration lines
            config_lines = [f"interface {interface_name}"]
            if "description" in port_config:
                config_lines.append(f" description {port_config['description']}")

            mode = port_config.get("mode", "")
            if mode == "access":
                config_lines.append(" switchport mode access")
                if "data_vlan" in port_config:
                    config_lines.append(f" switchport access vlan {port_config['data_vlan']}")
                if "voice_vlan" in port_config:
                    config_lines.append(f" switchport voice vlan {port_config['voice_vlan']}")
            elif mode == "trunk":
                config_lines.extend([" switchport mode trunk", " switchport nonegotiate"])
                if "native_vlan" in port_config:
                    config_lines.append(f" switchport trunk native vlan {port_config['native_vlan']}")
                if "allowed_vlans" in port_config:
                    allowed_vlans = port_config['allowed_vlans']
                    if allowed_vlans.lower() == "all":
                        config_lines.append(" switchport trunk allowed vlan all")
                    else:
                        config_lines.append(f" switchport trunk allowed vlan {allowed_vlans}")

            if port_config.get("qos_trust", False):
                config_lines.append(" mls qos trust cos")
            if port_config.get("portfast", False):
                config_lines.append(" spanning-tree portfast")

            config_lines.extend([" no shutdown", " exit"])

            # Add configuration to output
            self.output_text.insert(tk.END, "\n".join(config_lines) + "\n")

        # Update status
        self.update_status(f"Showing all configurations")

    def _show_global_configurations(self):
        """Show global configurations from the global_configs dictionary."""
        # Hostname
        hostname = self.global_configs.get("hostname", "")
        if hostname:
            self.output_text.insert(tk.END, f"! --- Hostname '{hostname}' ---\n")
            self.output_text.insert(tk.END, f"hostname {hostname}\n")

        # Passwords
        enable_secret = self.global_configs.get("enable_secret", "")
        line_password = self.global_configs.get("line_password", "")
        vty_ssh = self.global_configs.get("vty_ssh", True)
        vty_telnet = self.global_configs.get("vty_telnet", True)

        if enable_secret or line_password:
            desc = "Enable Secret & Line Password(s)" if enable_secret and line_password else "Enable Secret" if enable_secret else "Line Password(s)"
            self.output_text.insert(tk.END, f"\n! --- {desc} ---\n")

            if enable_secret:
                self.output_text.insert(tk.END, f"enable secret {enable_secret}\n")

            if line_password:
                self.output_text.insert(tk.END, "line console 0\n")
                self.output_text.insert(tk.END, f"password {line_password}\n")
                self.output_text.insert(tk.END, "login\n")
                self.output_text.insert(tk.END, "exit\n")
                self.output_text.insert(tk.END, "line vty 0 4\n")
                self.output_text.insert(tk.END, f"password {line_password}\n")
                self.output_text.insert(tk.END, "login\n")

                transport_cmd = "transport input"
                if vty_ssh and vty_telnet:
                    transport_cmd += " ssh telnet"
                elif vty_ssh:
                    transport_cmd += " ssh"
                elif vty_telnet:
                    transport_cmd += " telnet"
                else:
                    transport_cmd += " none"

                self.output_text.insert(tk.END, f"{transport_cmd}\n")
                self.output_text.insert(tk.END, "exit\n")

        # Basic settings
        pwd_encrypt = self.global_configs.get("pwd_encrypt", True)
        no_domain_lookup = self.global_configs.get("no_domain_lookup", True)

        if pwd_encrypt or no_domain_lookup:
            self.output_text.insert(tk.END, "\n! --- Basic settings ---\n")
            if pwd_encrypt:
                self.output_text.insert(tk.END, "service password-encryption\n")
            if no_domain_lookup:
                self.output_text.insert(tk.END, "no ip domain-lookup\n")

        # VLANs
        if "vlans" in self.global_configs and self.global_configs["vlans"]:
            for vlan_id, vlan_name in sorted(self.global_configs["vlans"].items(), key=lambda x: int(x[0])):
                self.output_text.insert(tk.END, f"\n! --- VLAN {vlan_id} ---\n")
                self.output_text.insert(tk.END, f"vlan {vlan_id}\n")
                if vlan_name:
                    self.output_text.insert(tk.END, f" name {vlan_name}\n")
                self.output_text.insert(tk.END, " exit\n")

        # SVI Interface
        svi_interface = self.global_configs.get("svi_interface", "")
        svi_ip = self.global_configs.get("svi_ip", "")
        svi_mask = self.global_configs.get("svi_mask", "")
        svi_desc = self.global_configs.get("svi_desc", "")

        if svi_interface and svi_ip and svi_mask:
            self.output_text.insert(tk.END, f"\n! --- IP for {svi_interface} ---\n")
            self.output_text.insert(tk.END, f"interface {svi_interface}\n")
            if svi_desc:
                self.output_text.insert(tk.END, f" description {svi_desc}\n")
            if not svi_interface.lower().startswith("vlan"):
                self.output_text.insert(tk.END, " no switchport\n")
            self.output_text.insert(tk.END, f" ip address {svi_ip} {svi_mask}\n")
            self.output_text.insert(tk.END, " no shutdown\n")
            self.output_text.insert(tk.END, " exit\n")

        # Default Gateway
        gateway_ip = self.global_configs.get("gateway_ip", "")
        if gateway_ip:
            self.output_text.insert(tk.END, f"\n! --- Default Gateway via {gateway_ip} ---\n")
            self.output_text.insert(tk.END, f"ip route 0.0.0.0 0.0.0.0 {gateway_ip}\n")


    def _update_port_visuals(self):
        """Update the visual appearance of ports based on their state and show configurations.

        This method sets the color of each port based on its state and updates the configuration display:
        - Selected ports are shown in blue (SELECTED_PORT_COLOR)
        - Configured but not selected ports are shown in green (CONFIGURED_PORT_COLOR)
        - Unconfigured and not selected ports are shown in gray (DEFAULT_PORT_COLOR)
        """
        # Debug output
        print(f"Updating port visuals")
        print(f"Selected ports: {sorted(list(self.selected_ports))}")
        print(f"Configured ports: {sorted(list(self.port_configs.keys()))}")

        total_ports = self.total_ports_var.get()
        for port_num in range(1, total_ports + 1):
            if port_num in self.port_items:
                items = self.port_items[port_num]
                rect_id = items['rect']
                # Determine port state and apply appropriate color
                # Priority: Selected > Configured > Default
                if port_num in self.selected_ports:
                    fill_color = SELECTED_PORT_COLOR
                    print(f"Port {port_num}: Selected (Blue)")
                elif port_num in self.port_configs:
                    fill_color = CONFIGURED_PORT_COLOR
                    print(f"Port {port_num}: Configured (Green)")
                else:
                    fill_color = DEFAULT_PORT_COLOR
                    print(f"Port {port_num}: Default (Gray)")
                self.switch_canvas.itemconfig(rect_id, fill=fill_color)

        # Automatically show all configurations
        self._show_all_configurations()

    def undo_config(self):
        if self.current_step >= 0:
            self.current_step -= 1
            import copy
            self.port_configs = copy.deepcopy(self.config_history[self.current_step])
            self._update_port_visuals()
            self.update_status("Undo applied.")
        else:
            self.update_status("Nothing to undo.")

    def redo_config(self):
        if self.current_step < len(self.config_history)-1:
            self.current_step += 1
            import copy
            self.port_configs = copy.deepcopy(self.config_history[self.current_step])
            self._update_port_visuals()
            self.update_status("Redo applied.")
        else:
            self.update_status("Nothing to redo.")

    def on_port_click(self, event):
        """Handle port click events with multiple selection support.

        This method implements an advanced selection model:
        - Regular click: Selects ONLY the clicked port, deselecting all others
        - Ctrl+click: Toggles the selection state of the clicked port without affecting others
        - Shift+click: Selects a range of ports from the last clicked port to the current one
        """
        canvas = event.widget
        x = canvas.canvasx(event.x)
        y = canvas.canvasy(event.y)
        item_ids = canvas.find_overlapping(x, y, x, y)

        clicked_port_num = None
        for item_id in item_ids:
            tags = canvas.gettags(item_id)
            if "port" in tags and "port_text" not in tags:
                for tag in tags:
                    if tag.startswith("port_"):
                        try:
                            clicked_port_num = int(tag.split("_")[1])
                            break
                        except (ValueError, IndexError):
                            continue
            if clicked_port_num:
                break

        if not clicked_port_num:
            return

        # Debug output
        print(f"Port {clicked_port_num} clicked")
        print(f"Before click - Selected ports: {sorted(list(self.selected_ports))}")
        print(f"Ctrl: {event.state & 0x0004}, Shift: {event.state & 0x0001}")

        # Check for modifier keys
        ctrl_pressed = (event.state & 0x0004) != 0  # Control key
        shift_pressed = (event.state & 0x0001) != 0  # Shift key

        if ctrl_pressed:
            # CTRL+CLICK: Toggle selection of the clicked port
            if clicked_port_num in self.selected_ports:
                self.selected_ports.remove(clicked_port_num)
                print(f"Removed port {clicked_port_num} from selection (Ctrl+click)")
            else:
                self.selected_ports.add(clicked_port_num)
                print(f"Added port {clicked_port_num} to selection (Ctrl+click)")

            # Update last clicked port
            self.last_clicked_port = clicked_port_num

        elif shift_pressed and self.last_clicked_port is not None:
            # SHIFT+CLICK: Select range from last clicked port to current port
            start_port = min(self.last_clicked_port, clicked_port_num)
            end_port = max(self.last_clicked_port, clicked_port_num)

            # Create a range of ports to select
            port_range = set(range(start_port, end_port + 1))

            # Add the range to the current selection
            self.selected_ports.update(port_range)
            print(f"Selected port range {start_port}-{end_port} (Shift+click)")

            # Don't update last_clicked_port to maintain the anchor point for future shift+clicks

        else:
            # REGULAR CLICK: Select only the clicked port
            if self.selected_ports == {clicked_port_num}:
                print(f"Port {clicked_port_num} already selected")
                return

            # Clear the current selection and select only the clicked port
            self.selected_ports = {clicked_port_num}
            self.last_clicked_port = clicked_port_num
            print(f"Selected only port {clicked_port_num} (regular click)")

        # Debug output
        print(f"After click - Selected ports: {sorted(list(self.selected_ports))}")

        # Update the status bar with the number of selected ports
        num_selected = len(self.selected_ports)
        if num_selected > 1:
            self.update_status(f"{num_selected} ports selected")
        elif num_selected == 1:
            port_num = list(self.selected_ports)[0]
            self.update_status(f"Port {port_num} selected")

        # Update the UI
        self._update_port_visuals()
        self._update_port_config_panel_from_selection()

    def _update_interface_prefix(self, event=None):
        """Update the interface prefix based on the selected type and slot numbers"""
        interface_type = self.interface_type_var.get()
        slot = self.slot_var.get().strip() or DEFAULT_SLOT
        subslot = self.subslot_var.get().strip() or DEFAULT_SUBSLOT

        # Validate slot and subslot numbers
        if not slot.isdigit() or not subslot.isdigit():
            return

        # Generate the interface prefix
        prefix = f"{INTERFACE_TYPES[interface_type]['prefix']}{slot}/{subslot}/"
        self.interface_prefix_var.set(prefix)

    def _generate_interface_ranges(self, port_set):
        if not port_set:
            return []

        prefix = self.interface_prefix_var.get()
        ports = sorted(list(port_set))
        ranges = []
        if not ports:
            return ranges

        start_range = ports[0]
        end_range = ports[0]

        for i in range(1, len(ports)):
            if ports[i] == end_range + 1:
                end_range = ports[i]
            else:
                if start_range == end_range:
                    ranges.append(f"{prefix}{start_range}")
                else:
                    ranges.append(f"{prefix}{start_range}-{end_range}")
                start_range = ports[i]
                end_range = ports[i]

        if start_range == end_range:
            ranges.append(f"{prefix}{start_range}")
        else:
            ranges.append(f"{prefix}{start_range}-{end_range}")

        return ranges

    def _create_port_config_panel_widgets(self, parent_frame):
        # Create a canvas with scrollbar for the configuration panel
        canvas = tk.Canvas(parent_frame)
        scrollbar = ttk.Scrollbar(parent_frame, orient="vertical", command=canvas.yview)

        # Create the main content frame
        content_frame = ttk.Frame(canvas)
        content_frame.grid_columnconfigure(0, weight=1)

        # Create a frame for the Apply button that will stay at the bottom
        button_frame = ttk.Frame(parent_frame)

        # Configure the canvas
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas_frame = canvas.create_window((0, 0), window=content_frame, anchor="nw")

        # Pack the scrollbar and canvas
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        button_frame.pack(side="bottom", fill="x", padx=5, pady=5)

        # Update the scroll region when the frame changes size
        def _configure_canvas(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Update the canvas frame width to match the canvas
            canvas.itemconfig(canvas_frame, width=canvas.winfo_width())

        content_frame.bind("<Configure>", _configure_canvas)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_frame, width=canvas.winfo_width()))

        # Add Template Selection
        template_frame = ttk.LabelFrame(content_frame, text="Quick Templates", padding=(5, 5))
        template_frame.pack(fill=tk.X, padx=5, pady=5)

        self.template_var = tk.StringVar()
        self.template_combo = ttk.Combobox(template_frame, textvariable=self.template_var,
                                    values=list(self.port_templates.keys()))
        self.template_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.template_combo.bind('<<ComboboxSelected>>', self._on_template_selected)

        apply_template_btn = ttk.Button(template_frame, text="Apply Template",
                                      command=lambda: self._apply_template(self.template_var.get()))
        apply_template_btn.pack(side=tk.LEFT, padx=5)

        ToolTip(self.template_combo, "Select a pre-configured template for common port types")
        ToolTip(apply_template_btn, "Apply the selected template to selected ports")

        # Add configuration widgets to the content frame
        self._create_port_config_content(content_frame)


        # Add the Show All Configurations button
        show_all_btn = ttk.Button(button_frame, text="Show All Configurations",
                                command=self._show_all_configurations)
        show_all_btn.pack(fill="x", padx=5, pady=5)
        ToolTip(show_all_btn, "Show configurations for all configured ports")

        # Add the Apply button to the button frame
        apply_btn = ttk.Button(button_frame, text="Apply Configuration",
                             command=self._update_vlan_from_port_config,
                             style="Accent.TButton")
        apply_btn.pack(fill="x", padx=5, pady=5)
        ToolTip(apply_btn, "Apply the configuration to all selected ports")

        # Add Help Button
        help_btn = ttk.Button(parent_frame, text="Port Configuration Help",
                            command=self._show_help_window)
        help_btn.pack(side=tk.BOTTOM, pady=5)

    def _create_port_config_content(self, parent_frame):
        # Mode Selection
        mode_frame = ttk.LabelFrame(parent_frame, text="Port Mode", padding=5)
        mode_frame.pack(fill="x", padx=5, pady=5)

        self.port_mode_var = tk.StringVar(value="Access")
        self.port_mode_combo = ttk.Combobox(mode_frame, textvariable=self.port_mode_var,
                                          values=["Access", "Trunk"], state="readonly")
        self.port_mode_combo.pack(fill="x", padx=5, pady=5)
        self.port_mode_combo.bind("<<ComboboxSelected>>", self._on_port_mode_change)

        # Description
        desc_frame = ttk.LabelFrame(parent_frame, text="Description", padding=5)
        desc_frame.pack(fill="x", padx=5, pady=5)

        self.port_desc_entry = ttk.Entry(desc_frame)
        self.port_desc_entry.pack(fill="x", padx=5, pady=5)

        # Access Settings
        self.port_access_frame = ttk.LabelFrame(parent_frame, text="Access Settings", padding=5)
        self.port_access_frame.pack(fill="x", padx=5, pady=5)

        # Data VLAN Entry with validation
        data_vlan_frame = ttk.Frame(self.port_access_frame)
        data_vlan_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(data_vlan_frame, text="Data VLAN ID:").pack(side="left")

        def vlan_validator(P):
            if P == "" or re.match(self.validation_patterns["vlan"], P):
                return True
            else:
                return False

        reg = self.root.register(vlan_validator)
        self.port_data_vlan_entry = ttk.Entry(data_vlan_frame, width=10, validate="key",
                                           validatecommand=(reg, "%P"))
        self.port_data_vlan_entry.pack(side="left", padx=(5, 0))

        # Voice VLAN with validation
        voice_vlan_frame = ttk.Frame(self.port_access_frame)
        voice_vlan_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(voice_vlan_frame, text="Voice VLAN ID:").pack(side="left")
        self.port_voice_vlan_entry = ttk.Entry(voice_vlan_frame, width=10, validate="key",
                                            validatecommand=(reg, "%P"))
        self.port_voice_vlan_entry.pack(side="left", padx=(5, 0))

        # PortFast
        portfast_frame = ttk.Frame(self.port_access_frame)
        portfast_frame.pack(fill="x", padx=5, pady=2)
        self.port_portfast_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(portfast_frame, text="Enable PortFast",
                       variable=self.port_portfast_var).pack(side="left")

        # QoS Trust
        qos_frame = ttk.Frame(self.port_access_frame)
        qos_frame.pack(fill="x", padx=5, pady=2)
        self.port_qos_trust_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(qos_frame, text="Apply Voice QoS Trust (cos)",
                       variable=self.port_qos_trust_var).pack(side="left")

        # Trunk Settings
        self.port_trunk_frame = ttk.LabelFrame(parent_frame, text="Trunk Settings", padding=5)
        self.port_trunk_frame.pack(fill="x", padx=5, pady=5)

        # Native VLAN with validation
        native_vlan_frame = ttk.Frame(self.port_trunk_frame)
        native_vlan_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(native_vlan_frame, text="Native VLAN ID:").pack(side="left")
        self.port_native_vlan_entry = ttk.Entry(native_vlan_frame, width=10, validate="key",
                                             validatecommand=(reg, "%P"))
        self.port_native_vlan_entry.pack(side="left", padx=(5, 0))

        # Direct update button for native VLAN
        update_native_btn = ttk.Button(native_vlan_frame, text="Update",
                                    command=self._direct_update_native_vlan)
        update_native_btn.pack(side="left", padx=(5, 0))
        ToolTip(update_native_btn, "Directly update the native VLAN for selected ports")

        # Allowed VLANs
        allowed_vlan_frame = ttk.Frame(self.port_trunk_frame)
        allowed_vlan_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(allowed_vlan_frame, text="Allowed VLANs:").pack(side="left")

        self.port_allowed_vlan_entry = ttk.Entry(allowed_vlan_frame)
        self.port_allowed_vlan_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))

        # Direct update button for allowed VLANs
        update_allowed_btn = ttk.Button(allowed_vlan_frame, text="Update",
                                     command=self._direct_update_allowed_vlans)
        update_allowed_btn.pack(side="left", padx=(5, 0))
        ToolTip(update_allowed_btn, "Directly update the allowed VLANs for selected ports")

        ToolTip(self.port_allowed_vlan_entry, "Enter 'all' or a comma-separated list of VLANs or ranges (e.g., '1,10-20,30')")

        # Add action buttons
        action_frame = ttk.Frame(parent_frame)
        action_frame.pack(fill="x", padx=5, pady=10)

        # Apply Changes Button
        apply_btn = ttk.Button(action_frame, text="Apply Changes", command=self._update_vlan_from_port_config,
                            style="Accent.TButton")
        apply_btn.pack(side=tk.LEFT, padx=5)
        ToolTip(apply_btn, "Apply the current VLAN settings to selected ports")

        # Reset Button
        reset_btn = ttk.Button(action_frame, text="Reset", command=self._reset_port_config_panel)
        reset_btn.pack(side=tk.LEFT, padx=5)
        ToolTip(reset_btn, "Reset the port configuration panel to default values")

        # Initial state
        self._on_port_mode_change()

    def _on_port_mode_change(self, event=None):
        mode = self.port_mode_var.get().lower()

        if len(self.selected_ports) == 1:
            port_num = list(self.selected_ports)[0]
            if port_num in self.port_configs:
                current_config = self.port_configs[port_num]
                current_mode = current_config.get("mode", "").lower()

                if current_mode != mode and current_mode in ["access", "trunk"]:
                    if mode == "access":
                        self.port_data_vlan_entry.delete(0, tk.END)
                        self.port_voice_vlan_entry.delete(0, tk.END)
                    elif mode == "trunk":
                        self.port_native_vlan_entry.delete(0, tk.END)
                        self.port_allowed_vlan_entry.delete(0, tk.END)
                        self.port_allowed_vlan_entry.insert(0, "ALL")

        if mode == "access":
            self.port_access_frame.pack()
            self.port_trunk_frame.pack_forget()
        elif mode == "trunk":
            self.port_access_frame.pack_forget()
            self.port_trunk_frame.pack()
        else:
            self.port_access_frame.pack_forget()
            self.port_trunk_frame.pack_forget()

    def _reset_port_config_panel(self):
        current_mode = self.port_mode_var.get().lower()
        self.port_mode_combo.set("")
        self.port_desc_entry.delete(0, tk.END)
        self.port_data_vlan_entry.delete(0, tk.END)
        self.port_voice_vlan_entry.delete(0, tk.END)
        self.port_native_vlan_entry.delete(0, tk.END)
        self.port_allowed_vlan_entry.delete(0, tk.END)
        self.port_portfast_var.set(True)
        self.port_qos_trust_var.set(False)
        if current_mode in ["access", "trunk"]:
            self.port_mode_combo.set(current_mode.capitalize())
        self._on_port_mode_change()

    def _update_vlan_from_port_config(self):
        """Update VLAN configuration for the currently selected ports only.
        This method ensures that only the selected ports are affected.
        """
        if not self.selected_ports:
            messagebox.showwarning("No Selection", "Please select one or more ports first.", parent=self.root)
            return

        # Make a completely new copy of the selected ports to avoid any reference issues
        # This is critical to ensure we only modify the ports that were selected
        ports_to_configure = set(port for port in self.selected_ports)

        # Debug output
        print(f"Updating VLAN for ports: {sorted(list(ports_to_configure))}")
        print(f"Selected ports before updating: {sorted(list(self.selected_ports))}")

        import copy
        prev_state = copy.deepcopy(self.port_configs)
        self.config_history = self.config_history[:self.current_step+1]
        self.config_history.append(prev_state)
        self.current_step += 1

        mode = self.port_mode_var.get().lower()
        description = self.port_desc_entry.get().strip()
        portfast = self.port_portfast_var.get()
        qos_trust = self.port_qos_trust_var.get()
        native_vlan = self.port_native_vlan_entry.get().strip()
        allowed_vlans = self.port_allowed_vlan_entry.get().strip()

        if not allowed_vlans and mode == "trunk":
            allowed_vlans = "ALL"

        # Track new VLANs
        new_vlans = set()
        if native_vlan:
            new_vlans.add(native_vlan)
        if mode == "access":
            data_vlan = self.port_data_vlan_entry.get().strip()
            voice_vlan = self.port_voice_vlan_entry.get().strip()
            if data_vlan:
                new_vlans.add(data_vlan)
            if voice_vlan:
                new_vlans.add(voice_vlan)
        elif mode == "trunk" and allowed_vlans.lower() != "all":
            for vlan in allowed_vlans.split(","):
                if "-" in vlan:
                    start, end = map(str.strip, vlan.split("-"))
                    new_vlans.update(str(v) for v in range(int(start), int(end) + 1))
                else:
                    new_vlans.add(vlan.strip())

        # Show alert for new VLANs and update tracking
        for vlan in new_vlans:
            try:
                # Convert to integer for consistent type
                vlan_id = int(vlan)
                if vlan_id not in self.configured_vlans:
                    self.configured_vlans.add(vlan_id)
                    messagebox.showinfo("New VLAN", f"New VLAN {vlan_id} has been added to the configuration.")
            except ValueError:
                # Skip any values that can't be converted to integers
                pass

        # Refresh the VLAN list in the global config tab
        self._refresh_vlan_list()

        if mode == "trunk":
            if native_vlan:
                try:
                    native_vlan_int = int(native_vlan)
                    if not 1 <= native_vlan_int <= 4094:
                        raise ValueError("Native VLAN ID must be between 1 and 4094.")
                except ValueError as e:
                    messagebox.showwarning("Invalid Input", str(e), parent=self.root)
                    return

            if allowed_vlans.lower() != "all" and not self._validate_vlan_range(allowed_vlans):
                messagebox.showwarning("Invalid Input",
                                    f"Invalid VLAN range in allowed VLANs: {allowed_vlans}",
                                    parent=self.root)
                return

        for port_num in ports_to_configure:
            if port_num not in self.port_configs:
                self.port_configs[port_num] = {
                    "mode": mode,
                    "description": description,
                    "portfast": portfast,
                    "qos_trust": qos_trust
                }

            self.port_configs[port_num]["mode"] = mode
            self.port_configs[port_num]["description"] = description
            self.port_configs[port_num]["portfast"] = portfast
            self.port_configs[port_num]["qos_trust"] = qos_trust

            if mode == "access":
                if "native_vlan" in self.port_configs[port_num]:
                    del self.port_configs[port_num]["native_vlan"]
                if "allowed_vlans" in self.port_configs[port_num]:
                    del self.port_configs[port_num]["allowed_vlans"]

                data_vlan = self.port_data_vlan_entry.get().strip()
                if data_vlan:
                    try:
                        data_vlan_int = int(data_vlan)
                        if not 1 <= data_vlan_int <= 4094:
                            raise ValueError("Data VLAN ID must be between 1 and 4094.")
                        self.port_configs[port_num]["data_vlan"] = data_vlan
                    except ValueError as e:
                        messagebox.showwarning("Invalid Input", str(e), parent=self.root)
                        return

                voice_vlan = self.port_voice_vlan_entry.get().strip()
                if voice_vlan:
                    try:
                        voice_vlan_int = int(voice_vlan)
                        if not 1 <= voice_vlan_int <= 4094:
                            raise ValueError("Voice VLAN ID must be between 1 and 4094.")
                        self.port_configs[port_num]["voice_vlan"] = voice_vlan
                    except ValueError as e:
                        messagebox.showwarning("Invalid Input", str(e), parent=self.root)
                        return
                elif "voice_vlan" in self.port_configs[port_num]:
                    del self.port_configs[port_num]["voice_vlan"]

            elif mode == "trunk":
                if "data_vlan" in self.port_configs[port_num]:
                    del self.port_configs[port_num]["data_vlan"]
                if "voice_vlan" in self.port_configs[port_num]:
                    del self.port_configs[port_num]["voice_vlan"]

                if native_vlan:
                    self.port_configs[port_num]["native_vlan"] = native_vlan
                elif "native_vlan" in self.port_configs[port_num]:
                    del self.port_configs[port_num]["native_vlan"]

                self.port_configs[port_num]["allowed_vlans"] = allowed_vlans

        # Debug output
        print(f"Configured ports: {sorted(list(ports_to_configure))}")
        print(f"Selected ports after configuring: {sorted(list(self.selected_ports))}")

        # Update visuals and save configurations
        self._update_port_visuals()
        self._save_port_configs()

        # Clear output and generate commands only for the ports that were selected
        self.output_text.delete("1.0", tk.END)
        self.config_commands = []

        # IMPORTANT: Use ports_to_configure, not self.selected_ports
        configured_ports = self._generate_port_config_commands(specific_ports=ports_to_configure)

        # Update status with the number of ports that were actually configured
        num_configured = len(configured_ports) if configured_ports else 0
        self.update_status(f"Updated VLAN values for {num_configured} port(s)")

    def _direct_update_native_vlan(self):
        """Update native VLAN for the currently selected ports only.
        This method ensures that only the selected ports are affected.
        """
        if not self.selected_ports:
            messagebox.showwarning("No Selection", "Please select one or more ports first.", parent=self.root)
            return

        # Make a completely new copy of the selected ports to avoid any reference issues
        # This is critical to ensure we only modify the ports that were selected
        ports_to_configure = set(port for port in self.selected_ports)
        focused_ports = list(ports_to_configure)

        # Debug output
        print(f"Updating native VLAN for ports: {sorted(list(ports_to_configure))}")
        print(f"Selected ports before updating: {sorted(list(self.selected_ports))}")
        native_vlan = self.port_native_vlan_entry.get().strip()

        if native_vlan:
            try:
                native_vlan_int = int(native_vlan)
                if not 1 <= native_vlan_int <= 4094:
                    raise ValueError("Native VLAN ID must be between 1 and 4094.")
            except ValueError as e:
                messagebox.showwarning("Invalid Input", str(e), parent=self.root)
                return
        else:
            native_vlan = "1"

        import copy
        prev_state = copy.deepcopy(self.port_configs)
        self.config_history = self.config_history[:self.current_step+1]
        self.config_history.append(prev_state)
        self.current_step += 1

        updated_ports = []
        for port_num in focused_ports:
            if port_num in self.port_configs:
                if self.port_configs[port_num].get("mode", "").lower() == "trunk":
                    self.port_configs[port_num]["native_vlan"] = native_vlan
                    updated_ports.append(port_num)

        # Debug output
        print(f"Updated ports: {sorted(list(updated_ports))}")
        print(f"Selected ports after updating: {sorted(list(self.selected_ports))}")

        # Update visuals and save configurations
        self._update_port_visuals()
        self._save_port_configs()

        # Clear output and generate commands only for the updated ports
        self.output_text.delete("1.0", tk.END)
        self.config_commands = []
        if updated_ports:
            # IMPORTANT: Use updated_ports, not self.selected_ports
            self._generate_port_config_commands(specific_ports=updated_ports)
            self.update_status(f"Updated native VLAN for port(s): {', '.join(map(str, updated_ports))}")
        else:
            self.update_status("No ports were updated.")

    def _direct_update_allowed_vlans(self):
        """Update allowed VLANs for the currently selected ports only.
        This method ensures that only the selected ports are affected.
        """
        if not self.selected_ports:
            messagebox.showwarning("No Selection", "Please select one or more ports first.", parent=self.root)
            return

        # Make a completely new copy of the selected ports to avoid any reference issues
        # This is critical to ensure we only modify the ports that were selected
        ports_to_configure = set(port for port in self.selected_ports)
        focused_ports = list(ports_to_configure)

        # Debug output
        print(f"Updating allowed VLANs for ports: {sorted(list(ports_to_configure))}")
        print(f"Selected ports before updating: {sorted(list(self.selected_ports))}")
        allowed_vlans = self.port_allowed_vlan_entry.get().strip()

        if not allowed_vlans:
            allowed_vlans = "ALL"

        if allowed_vlans.lower() != "all":
            if not any(c.isdigit() for c in allowed_vlans):
                messagebox.showwarning("Invalid Input",
                                    f"Invalid VLAN range in allowed VLANs: {allowed_vlans}. Must contain at least one digit.",
                                    parent=self.root)
                return

        import copy
        prev_state = copy.deepcopy(self.port_configs)
        self.config_history = self.config_history[:self.current_step+1]
        self.config_history.append(prev_state)
        self.current_step += 1

        updated_ports = []
        for port_num in focused_ports:
            if port_num in self.port_configs:
                if self.port_configs[port_num].get("mode", "").lower() == "trunk":
                    self.port_configs[port_num]["allowed_vlans"] = allowed_vlans
                    updated_ports.append(port_num)

        # Debug output
        print(f"Updated ports: {sorted(list(updated_ports))}")
        print(f"Selected ports after updating: {sorted(list(self.selected_ports))}")

        # Update visuals and save configurations
        self._update_port_visuals()
        self._save_port_configs()

        # Clear output and generate commands only for the updated ports
        self.output_text.delete("1.0", tk.END)
        self.config_commands = []
        if updated_ports:
            # IMPORTANT: Use updated_ports, not self.selected_ports
            self._generate_port_config_commands(specific_ports=updated_ports)
            self.update_status(f"Updated allowed VLANs for port(s): {', '.join(map(str, updated_ports))}")
        else:
            self.update_status("No ports were updated.")

    def _update_port_config_panel_from_selection(self):
        """Update the port configuration panel based on the selected ports.

        This method handles both single and multiple port selections:
        - For a single port, it shows that port's configuration
        - For multiple ports with the same configuration, it shows their common configuration
        - For multiple ports with different configurations, it shows a mixed state
        """
        # Start with a clean slate
        self._reset_port_config_panel()

        if not self.selected_ports:
            return

        # Debug output
        print(f"Updating config panel for ports: {sorted(list(self.selected_ports))}")

        # Show the number of selected ports in the status bar
        num_selected = len(self.selected_ports)
        if num_selected > 1:
            self.update_status(f"{num_selected} ports selected")

        # Check if any selected ports are configured
        configured_ports = [p for p in self.selected_ports if p in self.port_configs]
        if not configured_ports:
            print("No configured ports in selection")
            return

        print(f"Configured ports in selection: {configured_ports}")

        # Get configurations for all selected ports
        selected_configs = [self.port_configs.get(port_num, {}) for port_num in self.selected_ports]
        if not any(selected_configs):
            return

        # Find common mode across selected ports
        modes = {config.get('mode', '').lower() for config in selected_configs if config}
        if len(modes) == 1:
            common_mode = modes.pop()
            self.port_mode_combo.set(common_mode.capitalize())
            print(f"Common mode: {common_mode}")

            # Now that we know the mode, update mode-specific fields
            if common_mode == "access":
                # Find common data VLAN - check both 'data_vlan' and 'access_vlan' keys for compatibility
                data_vlans = set()
                for config in selected_configs:
                    if config:
                        if 'data_vlan' in config:
                            data_vlans.add(config.get('data_vlan', ''))
                        elif 'access_vlan' in config:
                            data_vlans.add(config.get('access_vlan', ''))

                if len(data_vlans) == 1:
                    data_vlan = data_vlans.pop()
                    self.port_data_vlan_entry.delete(0, tk.END)
                    self.port_data_vlan_entry.insert(0, data_vlan)
                    print(f"Common data VLAN: {data_vlan}")

                # Find common voice VLAN
                voice_vlans = {config.get('voice_vlan', '') for config in selected_configs if config}
                if len(voice_vlans) == 1:
                    voice_vlan = voice_vlans.pop()
                    self.port_voice_vlan_entry.delete(0, tk.END)
                    self.port_voice_vlan_entry.insert(0, voice_vlan)
                    print(f"Common voice VLAN: {voice_vlan}")

            elif common_mode == "trunk":
                # Find common native VLAN
                native_vlans = {config.get('native_vlan', '') for config in selected_configs if config}
                if len(native_vlans) == 1:
                    native_vlan = native_vlans.pop()
                    self.port_native_vlan_entry.delete(0, tk.END)
                    self.port_native_vlan_entry.insert(0, native_vlan)
                    print(f"Common native VLAN: {native_vlan}")

                # Find common allowed VLANs
                allowed_vlans = {config.get('allowed_vlans', 'ALL') for config in selected_configs if config}
                if len(allowed_vlans) == 1:
                    allowed_vlan = allowed_vlans.pop()
                    self.port_allowed_vlan_entry.delete(0, tk.END)
                    self.port_allowed_vlan_entry.insert(0, allowed_vlan)
                    print(f"Common allowed VLANs: {allowed_vlan}")
        else:
            print(f"Mixed modes: {modes}")
            # If there are mixed modes, we can't show mode-specific settings
            # Just leave the mode dropdown empty
            self.port_mode_combo.set("")

        # Find common description
        descriptions = {config.get('description', '') for config in selected_configs if config}
        if len(descriptions) == 1:
            common_desc = descriptions.pop()
            self.port_desc_entry.delete(0, tk.END)
            self.port_desc_entry.insert(0, common_desc)
            print(f"Common description: {common_desc}")
        else:
            print(f"Mixed descriptions: {descriptions}")

        # Find common portfast and qos_trust settings
        portfast_values = {config.get('portfast', False) for config in selected_configs if config}
        if len(portfast_values) == 1:
            self.port_portfast_var.set(portfast_values.pop())

        qos_trust_values = {config.get('qos_trust', False) for config in selected_configs if config}
        if len(qos_trust_values) == 1:
            self.port_qos_trust_var.set(qos_trust_values.pop())

        # Update the UI based on the mode
        self._on_port_mode_change()

    def apply_port_config_to_selected(self):
        if not self.selected_ports:
            messagebox.showwarning("No Selection", "Please select one or more ports first.",
                                 parent=self.root)
            return

        import copy
        prev_state = copy.deepcopy(self.port_configs)
        self.config_history = self.config_history[:self.current_step+1]
        self.config_history.append(prev_state)
        self.current_step += 1

        mode = self.port_mode_var.get().lower()
        description = self.port_desc_entry.get().strip()
        portfast = self.port_portfast_var.get()
        qos_trust = self.port_qos_trust_var.get()

        if not mode:
            messagebox.showwarning("Missing Mode", "Please select a port mode.", parent=self.root)
            return

        config_to_apply = {"mode": mode, "description": description}
        mode_cmds = []

        try:
            if mode == "access":
                data_vlan_str = self.port_data_vlan_entry.get().strip()
                voice_vlan_str = self.port_voice_vlan_entry.get().strip()

                if not data_vlan_str:
                    raise ValueError("Data VLAN ID is required for access ports.")
                try:
                    data_vlan = int(data_vlan_str)
                    if not 1 <= data_vlan <= 4094:
                        raise ValueError("Data VLAN ID must be between 1 and 4094.")
                    config_to_apply["data_vlan"] = str(data_vlan)
                except ValueError:
                    raise ValueError(f"Invalid Data VLAN ID: {data_vlan_str}")

                mode_cmds.extend([
                    " switchport mode access",
                    f" switchport access vlan {data_vlan}"
                ])

                if voice_vlan_str:
                    try:
                        voice_vlan = int(voice_vlan_str)
                        if not 1 <= voice_vlan <= 4094:
                            raise ValueError("Voice VLAN ID must be between 1 and 4094.")
                        if voice_vlan == data_vlan:
                            raise ValueError("Voice VLAN must be different from Data VLAN.")
                        config_to_apply["voice_vlan"] = str(voice_vlan)
                        mode_cmds.append(f" switchport voice vlan {voice_vlan}")
                    except ValueError as e:
                        if "must be different" in str(e):
                            raise e
                        raise ValueError(f"Invalid Voice VLAN ID: {voice_vlan_str}")

            elif mode == "trunk":
                native_vlan_str = self.port_native_vlan_entry.get().strip()
                allowed_vlans = self.port_allowed_vlan_entry.get().strip()

                if native_vlan_str:
                    try:
                        native_vlan = int(native_vlan_str)
                        if not 1 <= native_vlan <= 4094:
                            raise ValueError("Native VLAN ID must be between 1 and 4094.")
                        config_to_apply["native_vlan"] = str(native_vlan)
                    except ValueError:
                        raise ValueError(f"Invalid Native VLAN ID: {native_vlan_str}")
                else:
                    config_to_apply["native_vlan"] = "1"

                if not allowed_vlans:
                    allowed_vlans = "ALL"

                if allowed_vlans.upper() != "ALL":
                    vlan_ranges = allowed_vlans.split(",")
                    validated_ranges = []

                    for vrange in vlan_ranges:
                        try:
                            if "-" in vrange:
                                start, end = map(int, vrange.split("-"))
                                if not (1 <= start <= 4094 and 1 <= end <= 4094 and start <= end):
                                    raise ValueError(f"Invalid VLAN range: {vrange}")
                                validated_ranges.append(f"{start}-{end}")
                            else:
                                vlan = int(vrange)
                                if not 1 <= vlan <= 4094:
                                    raise ValueError(f"Invalid VLAN ID: {vlan}")
                                validated_ranges.append(str(vlan))
                        except ValueError:
                            raise ValueError(f"Invalid VLAN specification: {vrange}")

                    allowed_vlans = ",".join(validated_ranges)

                config_to_apply["allowed_vlans"] = allowed_vlans

                mode_cmds.extend([
                    " switchport mode trunk",
                    " switchport nonegotiate"
                ])

                if native_vlan_str:
                    mode_cmds.append(f" switchport trunk native vlan {native_vlan}")

                if allowed_vlans:
                    if allowed_vlans.lower() == "all":
                        mode_cmds.append(f" switchport trunk allowed vlan all")
                    else:
                        mode_cmds.append(f" switchport trunk allowed vlan {allowed_vlans}")

            config_to_apply["portfast"] = portfast
            config_to_apply["qos_trust"] = qos_trust

            if portfast:
                mode_cmds.append(" spanning-tree portfast")
            if qos_trust:
                mode_cmds.append(" mls qos trust cos")

        except ValueError as e:
            messagebox.showwarning("Invalid Input", str(e), parent=self.root)
            return

        generated_config_lines = []
        interface_list = self._generate_interface_ranges(self.selected_ports)

        for intf_specifier in interface_list:
            command_prefix = "interface range" if "-" in intf_specifier else "interface"
            generated_config_lines.append(f"{command_prefix} {intf_specifier}")

            if description:
                generated_config_lines.append(f" description {description}")

            generated_config_lines.extend(mode_cmds)
            generated_config_lines.append(" no shutdown")
            generated_config_lines.append(" exit")

        for port_num in self.selected_ports:
            port_config = config_to_apply.copy()
            if mode == "trunk" and "allowed_vlans" in config_to_apply:
                port_config["allowed_vlans"] = config_to_apply["allowed_vlans"]
            self.port_configs[port_num] = port_config

        if generated_config_lines:
            port_list_str = ", ".join(map(str, sorted(list(self.selected_ports))))
            self.append_to_output(generated_config_lines,
                                f"{mode.capitalize()} config for port(s) {port_list_str}")
            self._update_port_visuals()

    def _create_global_config_panel_widgets(self, parent_frame):
        parent_frame.columnconfigure(1, weight=1)
        current_row = 0

        # Basic Device Settings Frame
        basic_frame = ttk.LabelFrame(parent_frame, text="Basic Device Settings", padding=5)
        basic_frame.grid(row=current_row, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        basic_frame.columnconfigure(1, weight=1)
        current_row += 1

        # Hostname
        hostname_frame = ttk.Frame(basic_frame)
        hostname_frame.pack(fill=tk.X, pady=2)
        hostname_lbl = ttk.Label(hostname_frame, text="Hostname:", width=12)
        hostname_lbl.pack(side=tk.LEFT)
        self.global_hostname_entry = ttk.Entry(hostname_frame, width=20)
        self.global_hostname_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ToolTip(self.global_hostname_entry, "Device hostname (no spaces).")

        # Passwords
        passwords_frame = ttk.Frame(basic_frame)
        passwords_frame.pack(fill=tk.X, pady=2)
        passwords_lbl = ttk.Label(passwords_frame, text="Enable Secret:", width=12)
        passwords_lbl.pack(side=tk.LEFT)
        self.global_enable_secret_entry = ttk.Entry(passwords_frame, show="*", width=20)
        self.global_enable_secret_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ToolTip(self.global_enable_secret_entry, "Enable secret password.")

        # Line Password
        line_pw_frame = ttk.Frame(basic_frame)
        line_pw_frame.pack(fill=tk.X, pady=2)
        line_pw_lbl = ttk.Label(line_pw_frame, text="Line Password:", width=12)
        line_pw_lbl.pack(side=tk.LEFT)
        self.global_line_pw_entry = ttk.Entry(line_pw_frame, show="*", width=20)
        self.global_line_pw_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ToolTip(self.global_line_pw_entry, "Console and VTY line password.")

        # VTY Access
        vty_frame = ttk.Frame(basic_frame)
        vty_frame.pack(fill=tk.X, pady=2)
        vty_lbl = ttk.Label(vty_frame, text="VTY Access:", width=12)
        vty_lbl.pack(side=tk.LEFT)
        self.global_vty_ssh_var = tk.BooleanVar(value=True)
        ssh_check = ttk.Checkbutton(vty_frame, text="SSH", variable=self.global_vty_ssh_var)
        ssh_check.pack(side=tk.LEFT)
        self.global_vty_telnet_var = tk.BooleanVar(value=True)
        telnet_check = ttk.Checkbutton(vty_frame, text="Telnet", variable=self.global_vty_telnet_var)
        telnet_check.pack(side=tk.LEFT)
        ToolTip(ssh_check, "Allow SSH access on VTY lines.")
        ToolTip(telnet_check, "Allow Telnet access on VTY lines.")

        # Basic Settings
        basic_settings_frame = ttk.Frame(basic_frame)
        basic_settings_frame.pack(fill=tk.X, pady=2)
        basic_settings_lbl = ttk.Label(basic_settings_frame, text="Basic Settings:", width=12)
        basic_settings_lbl.pack(side=tk.LEFT)
        self.global_pwd_encrypt_var = tk.BooleanVar(value=True)
        pwd_encrypt_check = ttk.Checkbutton(basic_settings_frame, text="Password Encryption", variable=self.global_pwd_encrypt_var)
        pwd_encrypt_check.pack(side=tk.LEFT)
        self.global_no_domain_lookup_var = tk.BooleanVar(value=True)
        no_domain_lookup_check = ttk.Checkbutton(basic_settings_frame, text="No Domain Lookup", variable=self.global_no_domain_lookup_var)
        no_domain_lookup_check.pack(side=tk.LEFT)
        ToolTip(pwd_encrypt_check, "Enable service password-encryption.")
        ToolTip(no_domain_lookup_check, "Disable IP domain lookup.")

        # Add Buttons
        add_btn_frame = ttk.Frame(basic_frame)
        add_btn_frame.pack(fill=tk.X, pady=5)
        hostname_add_btn = ttk.Button(add_btn_frame, text="Add Hostname", command=self.add_global_hostname)
        hostname_add_btn.pack(side=tk.LEFT, padx=5)
        passwords_add_btn = ttk.Button(add_btn_frame, text="Add Passwords", command=self.add_global_passwords)
        passwords_add_btn.pack(side=tk.LEFT, padx=5)
        basic_settings_add_btn = ttk.Button(add_btn_frame, text="Add Basic Settings", command=self.add_global_basic_settings)
        basic_settings_add_btn.pack(side=tk.LEFT, padx=5)

        # VLAN Configuration Frame
        vlan_frame = ttk.LabelFrame(parent_frame, text="VLAN Configuration", padding=5)
        vlan_frame.grid(row=current_row, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        vlan_frame.columnconfigure(1, weight=1)
        current_row += 1

        vlan_id_lbl = ttk.Label(vlan_frame, text="ID:")
        vlan_id_lbl.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.global_vlan_id_entry = ttk.Entry(vlan_frame, width=6)
        self.global_vlan_id_entry.grid(row=0, column=1, padx=5, pady=2, sticky="w")
        ToolTip(self.global_vlan_id_entry, "VLAN number (1-4094).")

        vlan_name_lbl = ttk.Label(vlan_frame, text="Name:")
        vlan_name_lbl.grid(row=0, column=2, padx=5, pady=2, sticky="w")
        self.global_vlan_name_entry = ttk.Entry(vlan_frame, width=15)
        self.global_vlan_name_entry.grid(row=0, column=3, padx=5, pady=2, sticky="ew")
        ToolTip(self.global_vlan_name_entry, "Optional VLAN name (no spaces).")

        vlan_add_btn = ttk.Button(vlan_frame, text="Add VLAN", width=10,
                                command=self.add_global_vlan)
        vlan_add_btn.grid(row=0, column=4, padx=5, pady=2)

        # VLAN List Frame
        vlan_list_frame = ttk.LabelFrame(vlan_frame, text="Configured VLANs", padding=5)
        vlan_list_frame.grid(row=1, column=0, columnspan=5, sticky="ew", padx=5, pady=10)

        self.vlan_listbox = tk.Listbox(vlan_list_frame, height=4)
        self.vlan_listbox.pack(fill=tk.BOTH, expand=True)

        # SVI / L3 Interface Frame
        svi_frame = ttk.LabelFrame(parent_frame, text="Management/Routed IP (SVI/L3 Port)",
                                 padding=5)
        svi_frame.grid(row=current_row, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        svi_frame.columnconfigure(1, weight=1)
        current_row += 1

        svi_intf_lbl = ttk.Label(svi_frame, text="Interface:")
        svi_intf_lbl.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.global_svi_intf_entry = ttk.Entry(svi_frame, width=15)
        self.global_svi_intf_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        self.global_svi_intf_entry.insert(0, "Vlan1")
        ToolTip(self.global_svi_intf_entry, "Interface name (e.g., Vlan1, GigabitEthernet0/0).")

        svi_ip_lbl = ttk.Label(svi_frame, text="IP Address:")
        svi_ip_lbl.grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.global_svi_ip_entry = ttk.Entry(svi_frame, width=15)
        self.global_svi_ip_entry.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        ToolTip(svi_ip_lbl, "IPv4 address (e.g., 192.168.1.1).")

        svi_mask_lbl = ttk.Label(svi_frame, text="Subnet Mask:")
        svi_mask_lbl.grid(row=2, column=0, padx=5, pady=2, sticky="w")
        self.global_svi_mask_entry = ttk.Entry(svi_frame, width=15)
        self.global_svi_mask_entry.grid(row=2, column=1, padx=5, pady=2, sticky="ew")
        self.global_svi_mask_entry.insert(0, "255.255.255.0")
        ToolTip(svi_mask_lbl, "Subnet mask (e.g., 255.255.255.0).")

        svi_desc_lbl = ttk.Label(svi_frame, text="Description:")
        svi_desc_lbl.grid(row=3, column=0, padx=5, pady=2, sticky="w")
        self.global_svi_desc_entry = ttk.Entry(svi_frame, width=15)
        self.global_svi_desc_entry.grid(row=3, column=1, padx=5, pady=2, sticky="ew")
        ToolTip(svi_desc_lbl, "Optional interface description.")

        svi_add_btn = ttk.Button(svi_frame, text="Add IP Interface", width=15,
                               command=self.add_global_svi)
        svi_add_btn.grid(row=1, column=2, rowspan=3, padx=5, pady=2, sticky="ns")

        # Default Gateway Frame
        gw_frame = ttk.LabelFrame(parent_frame, text="Default Gateway", padding=5)
        gw_frame.grid(row=current_row, column=0, columnspan=3, sticky="ew", padx=5, pady=10)
        gw_frame.columnconfigure(1, weight=1)
        current_row += 1

        gw_ip_lbl = ttk.Label(gw_frame, text="Gateway IP:")
        gw_ip_lbl.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.global_gw_ip_entry = ttk.Entry(gw_frame, width=20)
        self.global_gw_ip_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        ToolTip(gw_ip_lbl, "IP address of the default gateway router.")

        gw_add_btn = ttk.Button(gw_frame, text="Add Gateway", width=12,
                              command=self.add_global_gateway)
        gw_add_btn.grid(row=0, column=2, padx=5, pady=2)

    def add_global_hostname(self):
        hostname = self.global_hostname_entry.get().strip()
        if not hostname:
            messagebox.showwarning("Missing Info", "Please enter a hostname.",
                                 parent=self.root)
            return
        if " " in hostname:
            messagebox.showwarning("Invalid Input", "Hostname cannot contain spaces.",
                                 parent=self.root)
            return
        cmd = f"hostname {hostname}"
        self.append_to_output(cmd, f"Hostname '{hostname}'")

        # Save to global configs
        self.global_configs["hostname"] = hostname
        self._save_global_configs()

        # Keep the hostname in the entry field
        # self.global_hostname_entry.delete(0, tk.END)

    def add_global_passwords(self):
        enable_secret = self.global_enable_secret_entry.get()
        line_pw = self.global_line_pw_entry.get()
        allow_ssh = self.global_vty_ssh_var.get()
        allow_telnet = self.global_vty_telnet_var.get()
        cmds = []
        desc = "Password(s)"

        if enable_secret:
            cmds.append(f"enable secret {enable_secret}")
            desc = "Enable Secret & Line Password(s)"

        if line_pw:
            cmds.extend([
                "line console 0",
                f"password {line_pw}",
                "login",
                "exit",
                "line vty 0 4",
                f"password {line_pw}",
                "login"
            ])
            transport_cmd = "transport input"
            added_transport = False
            if allow_ssh:
                transport_cmd += " ssh"
                added_transport = True
            if allow_telnet:
                transport_cmd += " telnet"
                added_transport = True
            cmds.append(transport_cmd if added_transport else "transport input none")
            cmds.append("exit")
        elif enable_secret:
            desc = "Enable Secret"
        else:
            messagebox.showinfo("No Input", "No passwords entered.", parent=self.root)
            return

        self.append_to_output(cmds, desc)

        # Save to global configs
        self.global_configs["enable_secret"] = enable_secret
        self.global_configs["line_password"] = line_pw
        self.global_configs["vty_ssh"] = allow_ssh
        self.global_configs["vty_telnet"] = allow_telnet
        self._save_global_configs()

        # Keep the values in the entry fields
        # self.global_enable_secret_entry.delete(0, tk.END)
        # self.global_line_pw_entry.delete(0, tk.END)

    def add_global_basic_settings(self):
        cmds = []
        pwd_encrypt = self.global_pwd_encrypt_var.get()
        no_domain_lookup = self.global_no_domain_lookup_var.get()

        if pwd_encrypt:
            cmds.append("service password-encryption")
        if no_domain_lookup:
            cmds.append("no ip domain-lookup")
        if not cmds:
            messagebox.showinfo("No Selection", "No basic settings selected.",
                              parent=self.root)
            return

        self.append_to_output(cmds, "Basic settings")

        # Save to global configs
        self.global_configs["pwd_encrypt"] = pwd_encrypt
        self.global_configs["no_domain_lookup"] = no_domain_lookup
        self._save_global_configs()

    def add_global_vlan(self):
        vlan_id_str = self.global_vlan_id_entry.get().strip()
        vlan_name = self.global_vlan_name_entry.get().strip()
        cmds = []
        try:
            if not vlan_id_str:
                raise ValueError("VLAN ID required.")
            vlan_id = int(vlan_id_str)
            if not 1 <= vlan_id <= 4094:
                raise ValueError("VLAN ID range (1-4094).")
            if vlan_id in self.configured_vlans:
                raise ValueError(f"VLAN {vlan_id} already exists.")
            if " " in vlan_name:
                raise ValueError("VLAN Name cannot contain spaces.")
            cmds.append(f"vlan {vlan_id}")
            if vlan_name:
                cmds.append(f" name {vlan_name}")
            cmds.append(" exit")
            self.append_to_output(cmds, f"VLAN {vlan_id}")

            # Store as integer for consistent type
            self.configured_vlans.add(vlan_id)

            # Store VLAN name in global configs
            if vlan_name:
                if "vlans" not in self.global_configs:
                    self.global_configs["vlans"] = {}
                self.global_configs["vlans"][str(vlan_id)] = vlan_name

            display_name = f"VLAN {vlan_id}: {vlan_name}" if vlan_name else f"VLAN {vlan_id}"
            self.vlan_listbox.insert(tk.END, display_name)

            # Save global configs after adding a VLAN
            self._save_global_configs()

            self.global_vlan_id_entry.delete(0, tk.END)
            self.global_vlan_name_entry.delete(0, tk.END)
        except ValueError as e:
            messagebox.showwarning("Invalid Input", str(e), parent=self.root)

    def add_global_svi(self):
        interface = self.global_svi_intf_entry.get().strip()
        ip = self.global_svi_ip_entry.get().strip()
        mask = self.global_svi_mask_entry.get().strip()
        desc = self.global_svi_desc_entry.get().strip()
        cmds = []
        try:
            if not interface:
                raise ValueError("Interface name required.")
            if not ip:
                raise ValueError("IP Address required.")
            if not mask:
                raise ValueError("Subnet Mask required.")
            if " " in interface or " " in ip or " " in mask:
                raise ValueError("No spaces allowed in Interface/IP/Mask.")
            if ip.count('.') != 3 or mask.count('.') != 3:
                raise ValueError("Invalid IP/Mask format.")

            cmds.append(f"interface {interface}")
            if desc:
                cmds.append(f" description {desc}")
            if not interface.lower().startswith("vlan"):
                cmds.append(" no switchport")
            cmds.append(f" ip address {ip} {mask}")
            cmds.append(" no shutdown")
            cmds.append(" exit")

            self.append_to_output(cmds, f"IP for {interface}")

            # Save to global configs
            self.global_configs["svi_interface"] = interface
            self.global_configs["svi_ip"] = ip
            self.global_configs["svi_mask"] = mask
            self.global_configs["svi_desc"] = desc
            self._save_global_configs()

            # Keep the interface and mask in the entry fields
            # self.global_svi_ip_entry.delete(0, tk.END)
            # self.global_svi_desc_entry.delete(0, tk.END)
        except ValueError as e:
            messagebox.showwarning("Invalid Input", str(e), parent=self.root)

    def add_global_gateway(self):
        gw_ip = self.global_gw_ip_entry.get().strip()
        try:
            if not gw_ip:
                raise ValueError("Gateway IP required.")
            if " " in gw_ip or gw_ip.count('.') != 3:
                raise ValueError("Invalid Gateway IP format.")
            cmd = f"ip route 0.0.0.0 0.0.0.0 {gw_ip}"
            self.append_to_output(cmd, f"Default Gateway via {gw_ip}")

            # Save to global configs
            self.global_configs["gateway_ip"] = gw_ip
            self._save_global_configs()

            # Keep the gateway IP in the entry field
            # self.global_gw_ip_entry.delete(0, tk.END)
        except ValueError as e:
            messagebox.showwarning("Invalid Input", str(e), parent=self.root)

    def _create_bottom_frame_layout(self, parent_frame):
        parent_frame.grid_rowconfigure(0, weight=1)
        parent_frame.grid_columnconfigure(0, weight=1)

        self.output_text = scrolledtext.ScrolledText(
            parent_frame, wrap=tk.WORD, height=8,
            font=self.mono_font)
        self.output_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        control_frame = ttk.Frame(parent_frame)
        control_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))
        control_frame.grid_columnconfigure(0, weight=1)

        # Status bar with version info
        status_frame = ttk.Frame(control_frame)
        status_frame.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        status_frame.grid_columnconfigure(0, weight=1)

        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(status_frame, textvariable=self.status_var,
                                  relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.update_status("Ready. Click ports (Ctrl/Shift for multi-select). Use panels to configure.")

        # Version and copyright in status bar
        version_label = ttk.Label(status_frame, text=f"v{APP_VERSION}", relief=tk.SUNKEN, padding=(5, 0))
        version_label.pack(side=tk.RIGHT)

        copyright_label = ttk.Label(status_frame, text=APP_COPYRIGHT, relief=tk.SUNKEN, padding=(5, 0))
        copyright_label.pack(side=tk.RIGHT, padx=2)

        button_bar = ttk.Frame(control_frame)
        button_bar.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        button_bar.grid_columnconfigure(1, weight=1)

        left_buttons_frame = ttk.Frame(button_bar)
        left_buttons_frame.grid(row=0, column=0, sticky="w")

        self.generate_button = ttk.Button(left_buttons_frame, text="Generate Full Config",
                                       command=self.generate_full_config,
                                       style="Accent.TButton")
        self.generate_button.pack(side=tk.LEFT, padx=5)
        ToolTip(self.generate_button, "Wrap added commands with enable, conf t, end, etc.")

        self.copy_button = ttk.Button(left_buttons_frame, text="Copy to Clipboard",
                                   command=self.copy_to_clipboard)
        self.copy_button.pack(side=tk.LEFT, padx=5)
        ToolTip(self.copy_button, "Copy outputostomy content to clipboard.")

        self.save_button = ttk.Button(left_buttons_frame, text="Save Config File...",
                                   command=self.save_config)
        self.save_button.pack(side=tk.LEFT, padx=5)
        ToolTip(self.save_button, "Save output box content to a text file.")

        undo_btn = ttk.Button(left_buttons_frame, text="Undo", command=self.undo_config)
        undo_btn.pack(side=tk.LEFT, padx=5)
        ToolTip(undo_btn, "Undo last port configuration change")

        redo_btn = ttk.Button(left_buttons_frame, text="Redo", command=self.redo_config)
        redo_btn.pack(side=tk.LEFT, padx=5)
        ToolTip(redo_btn, "Redo previously undone port configuration change")

        right_buttons_frame = ttk.Frame(button_bar)
        right_buttons_frame.grid(row=0, column=2, sticky="e")

        self.clear_button = ttk.Button(right_buttons_frame, text="Clear All",
                                    command=self.clear_all)
        self.clear_button.pack(side=tk.RIGHT, padx=5)
        ToolTip(self.clear_button, "Clear selections, panels, output, and applied states.")

    def update_status(self, message):
        self.status_var.set(message)

    def append_to_output(self, commands, item_description="Item"):
        """Append commands to the output text box with a description.

        Args:
            commands: A string or list of strings containing the commands to append
            item_description: A description of the commands being added
        """
        if not commands:
            return
        if isinstance(commands, str):
            commands = [commands]

        # Add the new commands to the config_commands list
        self.output_text.insert(tk.END, f"! --- {item_description} ---\n")
        for command in commands:
            if command:
                self.output_text.insert(tk.END, command + "\n")
                self.config_commands.append(command)
        self.output_text.see(tk.END)
        self.update_status(f"Added: {item_description}.")

    def generate_full_config(self):
        """Generate a full configuration snippet for all configured ports and global settings.

        This method generates a complete configuration snippet that includes
        all global settings and configured ports.
        """
        # Debug output
        print("Generating full configuration")
        print(f"Configured ports: {sorted(list(self.port_configs.keys()))}")

        # Store original config commands
        original_commands = self.config_commands.copy()
        self.config_commands = []

        # First, generate global configuration commands
        self.output_text.delete("1.0", tk.END)
        self._show_global_configurations()
        global_config = self.output_text.get("1.0", tk.END).strip()

        # Then generate port configuration commands
        self.output_text.delete("1.0", tk.END)
        self.config_commands = []

        if self.port_configs:
            self._generate_port_config_commands(specific_ports=list(self.port_configs.keys()))
            port_config = self.output_text.get("1.0", tk.END).strip()
        else:
            port_config = ""

        # Check if we have any configurations
        if not global_config and not port_config:
            messagebox.showinfo("No Configurations", "No configurations have been created.", parent=self.root)
            # Restore original commands
            self.config_commands = original_commands
            return

        # Clear the output again and build the final configuration
        self.output_text.delete("1.0", tk.END)
        full_config = "!\n! --- Generated Configuration ---\n!\n"
        full_config += "enable\n"
        full_config += "configure terminal\n"
        full_config += "!\n"

        if global_config:
            full_config += global_config + "\n"

        if port_config:
            full_config += port_config + "\n"

        full_config += "!\n"
        full_config += "end\n"
        full_config += "!\n! Choose ONE save command:\n"
        full_config += "! copy running-config startup-config\n"
        full_config += "! write memory\n!\n"
        self.output_text.insert("1.0", full_config)

        # Restore original commands
        self.config_commands = original_commands

        # Update status
        port_count = len(self.port_configs)
        self.update_status(f"Full configuration generated for {port_count} port(s).")
        messagebox.showinfo("Generated", "Full configuration snippet displayed.\nReview carefully!",
                          parent=self.root)

    def clear_all(self):
        if messagebox.askyesno("Confirm Clear",
                             "Clear configuration panels, port selections, generated commands, and all applied port states within the tool?",
                             parent=self.root):
            # Clear port configurations
            self.selected_ports.clear()
            self.port_configs.clear()
            self.last_clicked_port = None
            self._update_port_visuals()
            self._reset_port_config_panel()

            # Clear global configurations
            self.configured_vlans.clear()

            # Reset global config dictionary
            self.global_configs = {
                "hostname": "",
                "enable_secret": "",
                "line_password": "",
                "vty_ssh": True,
                "vty_telnet": True,
                "pwd_encrypt": True,
                "no_domain_lookup": True,
                "vlans": {},  # {vlan_id: vlan_name}
                "svi_interface": "Vlan1",
                "svi_ip": "",
                "svi_mask": "255.255.255.0",
                "svi_desc": "",
                "gateway_ip": ""
            }

            # Clear UI elements
            self.global_hostname_entry.delete(0, tk.END)
            self.global_enable_secret_entry.delete(0, tk.END)
            self.global_line_pw_entry.delete(0, tk.END)
            self.global_vty_ssh_var.set(True)
            self.global_vty_telnet_var.set(True)
            self.global_pwd_encrypt_var.set(True)
            self.global_no_domain_lookup_var.set(True)
            self.global_vlan_id_entry.delete(0, tk.END)
            self.global_vlan_name_entry.delete(0, tk.END)
            self.vlan_listbox.delete(0, tk.END)
            self.global_svi_intf_entry.delete(0, tk.END)
            self.global_svi_intf_entry.insert(0, "Vlan1")
            self.global_svi_ip_entry.delete(0, tk.END)
            self.global_svi_mask_entry.delete(0, tk.END)
            self.global_svi_mask_entry.insert(0, "255.255.255.0")
            self.global_svi_desc_entry.delete(0, tk.END)
            self.global_gw_ip_entry.delete(0, tk.END)

            self.output_text.delete("1.0", tk.END)
            self.config_commands = []

            # Save the cleared configurations
            self._save_port_configs()
            self._save_global_configs()

            self.update_status("Cleared selections, panels, output, and applied states.")

    def copy_to_clipboard(self):
        current_config = self.output_text.get("1.0", tk.END).strip()  # Corrected syntax
        if not current_config:
            messagebox.showinfo("Nothing to Copy", "Output is empty.",
                              parent=self.root)
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(current_config)
            self.update_status("Configuration copied to clipboard!")
        except tk.TclError:
            messagebox.showerror("Clipboard Error", "Could not access clipboard.",
                               parent=self.root)

    def save_config(self):
        config_text = self.output_text.get("1.0", tk.END).strip()
        if not config_text:
            messagebox.showwarning("Nothing to Save", "Output is empty.",
                                 parent=self.root)
            return
        filename = filedialog.asksaveasfilename(
            title="Save Cisco Configuration",
            defaultextension=".txt",
            filetypes=[
                ("Text Files", "*.txt"),
                ("Config Files", "*.cfg"),
                ("All Files", "*.*")
            ],
            parent=self.root
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(config_text)
                self.update_status(f"Configuration saved to {filename}")
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save file:\n{e}",
                                   parent=self.root)
                self.update_status("Error saving configuration.")

    def _apply_template(self, template_name):
        """Apply a template to the currently selected ports only.
        This method ensures that only the selected ports are affected.
        """
        if not template_name or template_name not in self.port_templates:
            return

        if not self.selected_ports:
            messagebox.showwarning("No Selection", "Please select one or more ports first.", parent=self.root)
            return

        # Make a completely new copy of the selected ports to avoid any reference issues
        # This is critical to ensure we only modify the ports that were selected
        ports_to_configure = set(port for port in self.selected_ports)

        # Debug output
        print(f"Applying template {template_name} to ports: {sorted(list(ports_to_configure))}")
        print(f"Selected ports before applying: {sorted(list(self.selected_ports))}")

        # Save current state for undo/redo
        import copy
        prev_state = copy.deepcopy(self.port_configs)
        self.config_history = self.config_history[:self.current_step+1]
        self.config_history.append(prev_state)
        self.current_step += 1

        template = self.port_templates[template_name]

        try:
            if template["mode"] == "access":
                if not self._validate_single_vlan(template["access_vlan"]):
                    raise ValueError(f"Invalid access VLAN ID: {template['access_vlan']}")
                if "voice_vlan" in template and not self._validate_single_vlan(template["voice_vlan"]):
                    raise ValueError(f"Invalid voice VLAN ID: {template['voice_vlan']}")
            elif template["mode"] == "trunk":
                if not self._validate_single_vlan(template["native_vlan"]):
                    raise ValueError(f"Invalid native VLAN ID: {template['native_vlan']}")

                # Special handling for trunk VLANs
                if template["trunk_vlans"].upper() != "ALL":
                    # Manually validate the VLAN range
                    try:
                        parts = template["trunk_vlans"].split(",")
                        for part in parts:
                            part = part.strip()
                            if not part:
                                continue

                            if "-" in part:
                                start, end = map(str.strip, part.split("-"))
                                start_vlan = int(start)
                                end_vlan = int(end)
                                if not (1 <= start_vlan <= 4094 and 1 <= end_vlan <= 4094 and start_vlan <= end_vlan):
                                    raise ValueError(f"Invalid VLAN range: {part}. Values must be between 1-4094 and start must be <= end.")
                            else:
                                vlan = int(part)
                                if not 1 <= vlan <= 4094:
                                    raise ValueError(f"Invalid VLAN ID: {part}. Must be between 1-4094.")
                    except ValueError as e:
                        raise ValueError(f"Invalid trunk VLAN range: {e}")
        except ValueError as e:
            messagebox.showwarning("Template Error", str(e), parent=self.root)
            return

        self._reset_port_config_panel()

        self.port_mode_var.set(template["mode"])
        self._on_port_mode_change()

        self.port_desc_entry.delete(0, tk.END)
        self.port_desc_entry.insert(0, template["description"])

        if template["mode"] == "access":
            self.port_data_vlan_entry.delete(0, tk.END)
            self.port_data_vlan_entry.insert(0, template["access_vlan"])
            if "voice_vlan" in template:
                self.port_voice_vlan_entry.delete(0, tk.END)
                self.port_voice_vlan_entry.insert(0, template["voice_vlan"])

        if template["mode"] == "trunk":
            self.port_native_vlan_entry.delete(0, tk.END)
            self.port_allowed_vlan_entry.delete(0, tk.END)
            native_vlan = template.get("native_vlan", "1")
            trunk_vlans = template.get("trunk_vlans", "ALL")
            self.port_native_vlan_entry.insert(0, native_vlan)
            self.port_allowed_vlan_entry.insert(0, trunk_vlans)

        self.port_portfast_var.set(template["portfast"])
        self.port_qos_trust_var.set(template["qos_trust"])

        if template["mode"] == "access":
            vlan_id = template["access_vlan"]
            if not self._check_vlan_exists(vlan_id):
                if messagebox.askyesno("VLAN Not Found",
                                     f"VLAN {vlan_id} is not configured. Would you like to create it?",
                                     parent=self.root):
                    self._create_vlan(vlan_id)

            if "voice_vlan" in template:
                voice_vlan = template["voice_vlan"]
                if not self._check_vlan_exists(voice_vlan):
                    if messagebox.askyesno("VLAN Not Found",
                                         f"Voice VLAN {voice_vlan} is not configured. Would you like to create it?",
                                         parent=self.root):
                        self._create_vlan(voice_vlan, "VOICE")

        # Only apply the template to the ports that were selected when the method was called
        for port_num in ports_to_configure:
            config = {
                "mode": template["mode"],
                "description": template["description"],
                "portfast": template["portfast"],
                "qos_trust": template["qos_trust"]
            }

            if template["mode"] == "access":
                config["data_vlan"] = template["access_vlan"]
                if "voice_vlan" in template:
                    config["voice_vlan"] = template["voice_vlan"]
            else:
                config["native_vlan"] = native_vlan
                config["allowed_vlans"] = trunk_vlans

            self.port_configs[port_num] = config

        # Debug output
        print(f"Configured ports: {sorted(list(ports_to_configure))}")
        print(f"Selected ports after configuring: {sorted(list(self.selected_ports))}")

        # Update visuals and save configurations
        self._update_port_visuals()
        self._save_port_configs()

        # Clear output and generate commands only for the ports that were selected
        self.output_text.delete("1.0", tk.END)
        self.config_commands = []

        # IMPORTANT: Use ports_to_configure, not self.selected_ports
        configured_ports = self._generate_port_config_commands(specific_ports=ports_to_configure)

        # Update status with the number of ports that were actually configured
        num_configured = len(configured_ports) if configured_ports else 0
        self.update_status(f"Applied {template_name} template to {num_configured} port(s)")

    def _generate_port_config_commands(self, specific_ports=None):
        """Generate configuration commands for ports

        Args:
            specific_ports: If provided, only generate commands for these ports.
                           Otherwise, use self.selected_ports
        """
        # Use the provided ports or the currently selected ports
        ports_to_configure = specific_ports if specific_ports is not None else self.selected_ports

        if not ports_to_configure:
            return []

        # Convert to a list and sort for consistent output
        ports_to_configure = sorted(list(ports_to_configure))

        # Only include ports that are both in ports_to_configure and configured
        configured_ports = [p for p in ports_to_configure if p in self.port_configs]

        if not configured_ports:
            return []

        # Debug output
        print(f"Generating commands for ports: {configured_ports}")

        # Group ports by configuration to generate efficient commands
        port_groups = {}
        for port_num in configured_ports:
            config = self.port_configs[port_num]
            # Create a hashable representation of the config
            config_key = tuple(sorted((k, str(v)) for k, v in config.items()))
            if config_key not in port_groups:
                port_groups[config_key] = []
            port_groups[config_key].append(port_num)

        generated_config_lines = []

        # Generate commands for each group of ports with the same configuration
        for config_key, ports in port_groups.items():
            # Convert the config key back to a dictionary
            config_dict = {}
            for k, v in config_key:
                try:
                    # Try to convert string values to their original types
                    if v.lower() == 'true':
                        config_dict[k] = True
                    elif v.lower() == 'false':
                        config_dict[k] = False
                    elif v.isdigit():
                        config_dict[k] = int(v)
                    else:
                        config_dict[k] = v
                except:
                    config_dict[k] = v

            mode = config_dict.get("mode", "access").lower()
            description = config_dict.get("description", "")
            portfast = config_dict.get("portfast", True)
            qos_trust = config_dict.get("qos_trust", False)

            mode_cmds = []

            if mode == "access":
                mode_cmds.append(" switchport mode access")
                # Check for both data_vlan and access_vlan keys for compatibility
                data_vlan = None
                if "data_vlan" in config_dict:
                    data_vlan = config_dict["data_vlan"]
                elif "access_vlan" in config_dict:
                    data_vlan = config_dict["access_vlan"]

                if data_vlan:
                    mode_cmds.append(f" switchport access vlan {data_vlan}")

                if "voice_vlan" in config_dict and config_dict["voice_vlan"]:
                    voice_vlan = config_dict["voice_vlan"]
                    mode_cmds.append(f" switchport voice vlan {voice_vlan}")

            elif mode == "trunk":
                mode_cmds.extend([" switchport mode trunk", " switchport nonegotiate"])
                if "native_vlan" in config_dict and config_dict["native_vlan"]:
                    native_vlan = config_dict["native_vlan"]
                    mode_cmds.append(f" switchport trunk native vlan {native_vlan}")
                if "allowed_vlans" in config_dict and config_dict["allowed_vlans"]:
                    allowed_vlans = config_dict["allowed_vlans"]
                    if str(allowed_vlans).lower() == "all":
                        mode_cmds.append(f" switchport trunk allowed vlan all")
                    else:
                        mode_cmds.append(f" switchport trunk allowed vlan {allowed_vlans}")

            if portfast:
                mode_cmds.append(" spanning-tree portfast")
            if qos_trust:
                mode_cmds.append(" mls qos trust cos")

            # Generate interface ranges for this group of ports
            # IMPORTANT: Only use the ports that were explicitly requested
            interface_list = self._generate_interface_ranges(ports)

            for intf_specifier in interface_list:
                command_prefix = "interface range" if "-" in intf_specifier else "interface"
                generated_config_lines.append(f"{command_prefix} {intf_specifier}")

                if description:
                    generated_config_lines.append(f" description {description}")

                generated_config_lines.extend(mode_cmds)
                generated_config_lines.append(" no shutdown")
                generated_config_lines.append(" exit")

        if generated_config_lines:
            port_list_str = ", ".join(map(str, configured_ports))
            self.append_to_output(generated_config_lines,
                                f"Configuration for port(s) {port_list_str}")

        return configured_ports

    def _check_vlan_exists(self, vlan_id):
        try:
            vlan_id_int = int(vlan_id)
            # Check if the VLAN ID exists as either string or integer
            return vlan_id_int in self.configured_vlans or str(vlan_id_int) in self.configured_vlans
        except ValueError:
            return False

    def _create_vlan(self, vlan_id, vlan_type="DATA"):
        vlan_id_int = int(vlan_id)
        # Check if the VLAN ID exists as either string or integer
        if vlan_id_int in self.configured_vlans or str(vlan_id_int) in self.configured_vlans:
            return
        vlan_name = f"{vlan_type}_VLAN_{vlan_id}"
        cmds = [f"vlan {vlan_id}", f" name {vlan_name}", " exit"]
        self.append_to_output(cmds, f"VLAN {vlan_id} ({vlan_type})")
        # Store as integer for consistent type
        self.configured_vlans.add(vlan_id_int)

        # Store VLAN name in global configs
        if "vlans" not in self.global_configs:
            self.global_configs["vlans"] = {}
        self.global_configs["vlans"][str(vlan_id_int)] = vlan_name

        # Save global configs after adding a VLAN
        self._save_global_configs()

        self.vlan_listbox.insert(tk.END, f"VLAN {vlan_id}: {vlan_name}")

    def _show_help_window(self):
        help_window = tk.Toplevel(self.root)
        help_window.title("Port Configuration Help")
        help_window.geometry("600x400")

        help_notebook = ttk.Notebook(help_window)
        help_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        port_types_frame = ttk.Frame(help_notebook)
        help_notebook.add(port_types_frame, text="Port Types")

        # Add About tab
        about_frame = ttk.Frame(help_notebook, padding=10)
        help_notebook.add(about_frame, text="About")

        # App title
        title_label = ttk.Label(about_frame, text="Cisco Configuration Tool", font=("Arial", 16, "bold"))
        title_label.pack(pady=(10, 5))

        # Version
        version_label = ttk.Label(about_frame, text=f"Version {APP_VERSION} - Enterprise Edition")
        version_label.pack(pady=2)

        # Copyright
        copyright_label = ttk.Label(about_frame, text=APP_COPYRIGHT)
        copyright_label.pack(pady=2)

        # Description
        description = """
        This tool helps network administrators create and manage Cisco switch configurations.

        Features:
        - Configure switch ports (access and trunk)
        - Create and manage port templates
        - Configure VLANs and other global settings
        - Generate configuration commands
        """
        desc_label = ttk.Label(about_frame, text=description, justify="center", wraplength=500)
        desc_label.pack(pady=10)

        port_types_text = """
        Common Port Types:

        1. Access Port
           - Used for: End devices (PC, Printer)
           - Single VLAN access
           - PortFast enabled for quick connectivity

        2. Phone Port
           - Used for: IP Phones with PC
           - Data VLAN for PC
           - Voice VLAN for phone
           - QoS trusted for voice quality

        3. AP Port
           - Used for: Wireless Access Points
           - Trunk mode for multiple SSIDs
           - Multiple VLANs allowed
           - QoS trusted for wireless traffic

        4. Trunk Port
           - Used for: Switch-to-Switch connections
           - Carries multiple VLANs
           - PortFast typically disabled
           - Native VLAN for untagged traffic
        """

        port_types_label = ttk.Label(port_types_frame, text=port_types_text,
                                   justify=tk.LEFT, wraplength=550)
        port_types_label.pack(padx=10, pady=10)

        best_practices_frame = ttk.Frame(help_notebook)
        help_notebook.add(best_practices_frame, text="Best Practices")

        best_practices_text = """
        Port Configuration Best Practices:

        1. VLANs
           - Use VLANs 1-4094 (1,1002-1005 are reserved)
           - Avoid using VLAN 1 for user traffic
           - Document VLAN assignments

        2. Port Security
           - Enable PortFast only on end-device ports
           - Use description field for documentation
           - Consider using port-security for critical ports

        3. QoS Trust
           - Enable QoS trust for voice/video devices
           - Trust DSCP for IP phones and APs
           - Don't trust unknown devices

        4. Trunking
           - Explicitly configure trunk modes
           - Specify allowed VLANs (avoid "ALL")
           - Use a dedicated native VLAN
        """

        best_practices_label = ttk.Label(best_practices_frame, text=best_practices_text,
                                       justify=tk.LEFT, wraplength=550)
        best_practices_label.pack(padx=10, pady=10)

    def _validate_vlan_range(self, vlan_range):
        """Validate a VLAN range string.

        Valid formats:
        - 'ALL' (case-insensitive)
        - Single VLAN: '10'
        - Comma-separated VLANs: '1,10,20'
        - VLAN ranges: '1-10,20-30'
        - Mixed: '1,5-10,20,30-40'

        Args:
            vlan_range: The VLAN range string to validate

        Returns:
            bool: True if valid, False otherwise
        """
        # Always allow empty string for validation during typing
        if not vlan_range:
            return True

        # Allow 'ALL' (case-insensitive)
        if vlan_range.upper() == "ALL":
            return True

        # Handle comma-separated parts
        try:
            parts = vlan_range.split(",")
            for part in parts:
                part = part.strip()
                if not part:
                    # Allow empty parts (e.g., trailing comma)
                    continue

                if "-" in part:
                    # Handle range (e.g., '10-20')
                    start, end = map(str.strip, part.split("-"))
                    if start and not start.isdigit():
                        return False
                    if end and not end.isdigit():
                        return False

                    # Allow partial ranges during typing
                    if start and end:
                        start_vlan = int(start)
                        end_vlan = int(end)
                        if not (1 <= start_vlan <= 4094 and 1 <= end_vlan <= 4094 and start_vlan <= end_vlan):
                            return False
                else:
                    # Handle single VLAN
                    if part and not part.isdigit():
                        return False
                    if part and not 1 <= int(part) <= 4094:
                        return False
            return True
        except ValueError:
            # For validation during typing, allow partial input
            # For final validation (e.g., when saving a template), this should fail
            # We'll determine the context by checking the stack trace
            import traceback
            stack = traceback.extract_stack()
            # If called from update_template, we want to fail on invalid input
            if any('update_template' in frame[2] for frame in stack):
                return False
            return True

    def _validate_single_vlan(self, value):
        """Validate a single VLAN ID.

        Valid formats:
        - 'ALL' (case-insensitive)
        - Single VLAN ID between 1 and 4094
        - Empty string (for validation during typing)

        Args:
            value: The VLAN ID string to validate

        Returns:
            bool: True if valid, False otherwise
        """
        # Always allow empty string for validation during typing
        if not value:
            return True

        # Allow 'ALL' (case-insensitive)
        if value.upper() == "ALL":
            return True

        try:
            # Only validate complete numbers
            if value.isdigit():
                vlan_id = int(value)
                return 1 <= vlan_id <= 4094
            return True  # Allow partial input during typing
        except (ValueError, TypeError):
            # Allow partial input during typing
            return True

    def _save_port_configs(self):
        """Save port configurations to a file.

        This method saves the current port configurations to a JSON file.
        """
        # Debug output
        print(f"Saving port configurations")
        print(f"Configured ports: {sorted(list(self.port_configs.keys()))}")

        try:
            port_configs_str = {str(k): v for k, v in self.port_configs.items()}
            with open(self.port_configs_file, 'w') as f:
                json.dump(port_configs_str, f, indent=2)
            print(f"Port configurations saved successfully")
        except Exception as e:
            print(f"Error saving port configurations: {e}")

    def _load_port_configs(self):
        """Load port configurations from a file.

        This method loads port configurations from a JSON file.
        """
        # Debug output
        print(f"Loading port configurations")

        if not os.path.exists(self.port_configs_file):
            print(f"Port configurations file not found: {self.port_configs_file}")
            return

        try:
            with open(self.port_configs_file, 'r') as f:
                port_configs_str = json.load(f)
            self.port_configs = {int(k): v for k, v in port_configs_str.items()}
            print(f"Loaded port configurations: {sorted(list(self.port_configs.keys()))}")
            self._update_port_visuals()
        except Exception as e:
            print(f"Error loading port configurations: {e}")

    def _save_global_configs(self):
        """Save global configurations to a file.

        This method saves the current global configurations to a JSON file.
        """
        # Debug output
        print(f"Saving global configurations")

        # Update the global_configs with current values from the UI
        self._update_global_configs_from_ui()

        try:
            with open(self.global_configs_file, 'w') as f:
                json.dump(self.global_configs, f, indent=2)
            print(f"Global configurations saved successfully")
        except Exception as e:
            print(f"Error saving global configurations: {e}")

    def _load_global_configs(self):
        """Load global configurations from a file.

        This method loads global configurations from a JSON file.
        """
        # Debug output
        print(f"Loading global configurations")

        if not os.path.exists(self.global_configs_file):
            print(f"Global configurations file not found: {self.global_configs_file}")
            return

        try:
            with open(self.global_configs_file, 'r') as f:
                self.global_configs = json.load(f)
            print(f"Loaded global configurations")

            # Load VLANs from global configs
            if "vlans" in self.global_configs:
                for vlan_id_str, vlan_name in self.global_configs["vlans"].items():
                    try:
                        vlan_id = int(vlan_id_str)
                        self.configured_vlans.add(vlan_id)
                    except ValueError:
                        pass

            # Update the UI with loaded values
            self._update_ui_from_global_configs()

        except Exception as e:
            print(f"Error loading global configurations: {e}")

    def _update_global_configs_from_ui(self):
        """Update the global_configs dictionary with current values from the UI."""
        # Basic settings
        self.global_configs["hostname"] = self.global_hostname_entry.get().strip()
        self.global_configs["enable_secret"] = self.global_enable_secret_entry.get()
        self.global_configs["line_password"] = self.global_line_pw_entry.get()
        self.global_configs["vty_ssh"] = self.global_vty_ssh_var.get()
        self.global_configs["vty_telnet"] = self.global_vty_telnet_var.get()
        self.global_configs["pwd_encrypt"] = self.global_pwd_encrypt_var.get()
        self.global_configs["no_domain_lookup"] = self.global_no_domain_lookup_var.get()

        # SVI settings
        self.global_configs["svi_interface"] = self.global_svi_intf_entry.get().strip()
        self.global_configs["svi_ip"] = self.global_svi_ip_entry.get().strip()
        self.global_configs["svi_mask"] = self.global_svi_mask_entry.get().strip()
        self.global_configs["svi_desc"] = self.global_svi_desc_entry.get().strip()

        # Gateway
        self.global_configs["gateway_ip"] = self.global_gw_ip_entry.get().strip()

        # Update VLANs dictionary
        self.global_configs["vlans"] = {}
        for vlan_id in self.configured_vlans:
            self.global_configs["vlans"][str(vlan_id)] = f"VLAN_{vlan_id}"

    def _update_ui_from_global_configs(self):
        """Update the UI with values from the global_configs dictionary."""
        # Basic settings
        self.global_hostname_entry.delete(0, tk.END)
        self.global_hostname_entry.insert(0, self.global_configs.get("hostname", ""))

        self.global_enable_secret_entry.delete(0, tk.END)
        self.global_enable_secret_entry.insert(0, self.global_configs.get("enable_secret", ""))

        self.global_line_pw_entry.delete(0, tk.END)
        self.global_line_pw_entry.insert(0, self.global_configs.get("line_password", ""))

        self.global_vty_ssh_var.set(self.global_configs.get("vty_ssh", True))
        self.global_vty_telnet_var.set(self.global_configs.get("vty_telnet", True))
        self.global_pwd_encrypt_var.set(self.global_configs.get("pwd_encrypt", True))
        self.global_no_domain_lookup_var.set(self.global_configs.get("no_domain_lookup", True))

        # SVI settings
        self.global_svi_intf_entry.delete(0, tk.END)
        self.global_svi_intf_entry.insert(0, self.global_configs.get("svi_interface", "Vlan1"))

        self.global_svi_ip_entry.delete(0, tk.END)
        self.global_svi_ip_entry.insert(0, self.global_configs.get("svi_ip", ""))

        self.global_svi_mask_entry.delete(0, tk.END)
        self.global_svi_mask_entry.insert(0, self.global_configs.get("svi_mask", "255.255.255.0"))

        self.global_svi_desc_entry.delete(0, tk.END)
        self.global_svi_desc_entry.insert(0, self.global_configs.get("svi_desc", ""))

        # Gateway
        self.global_gw_ip_entry.delete(0, tk.END)
        self.global_gw_ip_entry.insert(0, self.global_configs.get("gateway_ip", ""))

        # Refresh VLAN list
        self._refresh_vlan_list()

    def _validate_ip_address(self, value):
        if not value:
            return True

        if not re.match(self.validation_patterns["ip_address"], value):
            return False

        try:
            octets = [int(x) for x in value.split(".")]
            return all(0 <= octet <= 255 for octet in octets)
        except ValueError:
            return False

    def _create_template_editor_widgets(self, parent_frame):
        template_list_frame = ttk.Frame(parent_frame)
        template_list_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)

        self.template_listbox = tk.Listbox(template_list_frame, selectmode=tk.SINGLE)
        self.template_listbox.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.template_listbox.bind('<<ListboxSelect>>', self._on_template_select)

        detail_frame = ttk.Frame(parent_frame)
        detail_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)

        self.template_name_var = tk.StringVar()
        ttk.Label(detail_frame, text="Template Name:").pack()
        name_entry = ttk.Entry(detail_frame, textvariable=self.template_name_var)
        name_entry.pack(pady=5, fill=tk.X)

        self.template_mode_var = tk.StringVar()
        ttk.Label(detail_frame, text="Mode:").pack()
        mode_combo = ttk.Combobox(detail_frame, textvariable=self.template_mode_var, values=["Access", "Trunk"])
        mode_combo.pack(pady=5, fill=tk.X)
        mode_combo.bind('<<ComboboxSelected>>', self._on_template_mode_change)

        ttk.Label(detail_frame, text="Description:").pack(pady=(5,0))
        self.template_description_var = tk.StringVar()
        self.template_description_entry = ttk.Entry(detail_frame, textvariable=self.template_description_var)
        self.template_description_entry.pack(pady=5, fill=tk.X)

        # We'll create the button frame later, after all the settings frames

        self.template_access_frame = ttk.LabelFrame(detail_frame, text="Access Settings", padding=5)

        ttk.Label(self.template_access_frame, text="Data VLAN:").pack(anchor="w")
        self.template_access_vlan_var = tk.StringVar()

        reg = self.root.register(self._validate_single_vlan)

        self.template_access_vlan_entry = ttk.Entry(self.template_access_frame, textvariable=self.template_access_vlan_var,
                                                 width=10, validate="key", validatecommand=(reg, "%P"))
        self.template_access_vlan_entry.pack(pady=2, fill=tk.X)

        ttk.Label(self.template_access_frame, text="Voice VLAN:").pack(anchor="w")
        self.template_voice_vlan_var = tk.StringVar()
        self.template_voice_vlan_entry = ttk.Entry(self.template_access_frame, textvariable=self.template_voice_vlan_var,
                                                width=10, validate="key", validatecommand=(reg, "%P"))
        self.template_voice_vlan_entry.pack(pady=2, fill=tk.X)

        # No buttons in the access settings frame

        self.template_trunk_frame = ttk.LabelFrame(detail_frame, text="Trunk Settings", padding=5)

        ttk.Label(self.template_trunk_frame, text="Native VLAN:").pack(anchor="w")
        self.template_native_vlan_var = tk.StringVar()
        self.template_native_vlan_entry = ttk.Entry(self.template_trunk_frame, textvariable=self.template_native_vlan_var,
                                                 width=10, validate="key", validatecommand=(reg, "%P"))
        self.template_native_vlan_entry.pack(pady=2, fill=tk.X)

        ttk.Label(self.template_trunk_frame, text="Allowed VLANs:").pack(anchor="w")
        self.template_trunk_vlans_var = tk.StringVar()

        trunk_reg = self.root.register(self._validate_vlan_range)

        self.template_trunk_vlans_entry = ttk.Entry(self.template_trunk_frame, textvariable=self.template_trunk_vlans_var,
                                                 validate="key", validatecommand=(trunk_reg, "%P"))
        self.template_trunk_vlans_entry.pack(pady=2, fill=tk.X)

        ToolTip(self.template_trunk_vlans_entry, "Enter 'ALL' or a comma-separated list of VLANs or ranges (e.g., '1,10-20,30')")

        # No buttons in the trunk settings frame
        self.template_trunk_frame.pack(pady=5, fill=tk.X, side=tk.TOP)

        common_frame = ttk.LabelFrame(detail_frame, text="Common Settings", padding=5)
        common_frame.pack(pady=5, fill=tk.X, side=tk.TOP)

        self.template_portfast_var = tk.BooleanVar(value=True)
        portfast_check = ttk.Checkbutton(common_frame, text="Enable PortFast", variable=self.template_portfast_var)
        portfast_check.pack(anchor="w")

        self.template_qos_var = tk.BooleanVar(value=False)
        qos_check = ttk.Checkbutton(common_frame, text="Trust QoS", variable=self.template_qos_var)
        qos_check.pack(anchor="w")

        # Create button frame at the bottom of the form, but not at the very bottom
        btn_frame = ttk.Frame(detail_frame)
        btn_frame.pack(pady=30, fill=tk.X, side=tk.BOTTOM, padx=5)

        new_btn = ttk.Button(btn_frame, text="New Template", command=self.clear_template_form)
        new_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        update_btn = ttk.Button(btn_frame, text="Save Template", command=self.update_template, style="Accent.TButton")
        update_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        self.delete_template_btn = ttk.Button(btn_frame, text="Delete", command=self.delete_template)
        self.delete_template_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)


        self.template_mode_var.set("Access")
        self._on_template_mode_change()

        self.load_templates()
        self._refresh_template_list()

    def _on_template_select(self, event):
        selection = self.template_listbox.curselection()
        if selection:
            template_name = self.template_listbox.get(selection[0])
            self._update_template_details(template_name)

    def _on_template_selected(self, event=None):
        """Handler for when a template is selected from the dropdown.
        This method updates the port configuration panel with the template values,
        but does not apply the template to any ports.
        """
        # Update the port configuration panel with the selected template
        template_name = self.template_var.get()
        if template_name and template_name in self.port_templates:
            template = self.port_templates[template_name]

            # Update the port configuration panel with the template values
            self.port_mode_var.set(template["mode"].capitalize())
            self.port_desc_entry.delete(0, tk.END)
            self.port_desc_entry.insert(0, template.get("description", ""))
            self.port_portfast_var.set(template.get("portfast", True))
            self.port_qos_trust_var.set(template.get("qos_trust", False))

            # Update mode-specific fields
            if template["mode"].lower() == "access":
                self.port_data_vlan_entry.delete(0, tk.END)
                self.port_data_vlan_entry.insert(0, template.get("access_vlan", ""))
                self.port_voice_vlan_entry.delete(0, tk.END)
                self.port_voice_vlan_entry.insert(0, template.get("voice_vlan", ""))
            else:  # trunk mode
                self.port_native_vlan_entry.delete(0, tk.END)
                self.port_native_vlan_entry.insert(0, template.get("native_vlan", "1"))
                self.port_allowed_vlan_entry.delete(0, tk.END)
                self.port_allowed_vlan_entry.insert(0, template.get("trunk_vlans", "ALL"))

            # Update the UI based on the mode
            self._on_port_mode_change()

            # Highlight configured ports and show a status message
            self._update_port_visuals()

            # Show a status message about the template and selected ports
            if self.selected_ports:
                # Count how many ports are already configured
                configured_count = sum(1 for p in self.selected_ports if p in self.port_configs)
                if configured_count > 0:
                    self.update_status(f"Template '{template_name}' loaded. {configured_count} of {len(self.selected_ports)} selected ports are already configured. Click 'Apply Template' to update them.")
                else:
                    self.update_status(f"Template '{template_name}' loaded. Click 'Apply Template' to configure {len(self.selected_ports)} selected port(s).")
            else:
                self.update_status(f"Template '{template_name}' loaded. Please select ports to configure.")

    def _on_template_mode_change(self, event=None):
        mode = self.template_mode_var.get().lower()

        selected = self.template_listbox.curselection()

        if not selected:
            if mode == "access":
                self.template_access_vlan_var.set("10")
                self.template_voice_vlan_var.set("")
            else:
                self.template_native_vlan_var.set("1")
                self.template_trunk_vlans_var.set("ALL")

        if mode == "access":
            # Show access frame and hide trunk frame
            self.template_access_frame.pack(fill=tk.X, pady=5, side=tk.TOP)
            self.template_trunk_frame.pack_forget()
        else:
            # Show trunk frame and hide access frame
            self.template_access_frame.pack_forget()
            self.template_trunk_frame.pack(fill=tk.X, pady=5, side=tk.TOP)

    def load_templates(self):
        try:
            with open("templates.json", "r") as f:
                self.port_templates = json.load(f)
            if hasattr(self, 'template_combo'):
                self.template_combo['values'] = list(self.port_templates.keys())
        except:
            pass

    def save_templates(self):
        with open("templates.json", "w") as f:
            json.dump(self.port_templates, f, indent=4)
        self._refresh_template_list()
        self.template_combo['values'] = list(self.port_templates.keys())
        self.update_status("Templates saved to file.")

    def add_template(self):
        new_name = f"New Template {len(self.port_templates)+1}"
        self._clear_template_fields()
        self.template_name_var.set(new_name)
        self.template_description_var.set("New Template")
        self.template_mode_var.set("Access")
        self._on_template_mode_change()
        self.template_portfast_var.set(True)
        self.template_qos_var.set(False)
        self.template_access_vlan_var.set("10")
        self.template_voice_vlan_var.set("")
        self.template_native_vlan_var.set("1")
        self.template_trunk_vlans_var.set("ALL")

        self.port_templates[new_name] = {
            "mode": "access",
            "description": "New Template",
            "access_vlan": "10",
            "portfast": True,
            "qos_trust": False
        }

        self._refresh_template_list()
        for i in range(self.template_listbox.size()):
            if self.template_listbox.get(i) == new_name:
                self.template_listbox.selection_set(i)
                break
        self.template_combo['values'] = list(self.port_templates.keys())
        self.update_status(f"Template '{new_name}' added. Click 'Update Template' to save changes.")

    def update_template(self):
        new_name = self.template_name_var.get().strip()
        if not new_name:
            messagebox.showwarning("Missing Name", "Please enter a template name.")
            return

        selected = self.template_listbox.curselection()
        if not selected:
            if new_name in self.port_templates:
                messagebox.showwarning("Duplicate Name", f"Template '{new_name}' already exists. Please use a different name.")
                return

            mode = self.template_mode_var.get().lower()
            template_data = {
                "mode": mode,
                "description": self.template_description_var.get(),
                "portfast": self.template_portfast_var.get(),
                "qos_trust": self.template_qos_var.get()
            }

            if mode == "access":
                access_vlan = self.template_access_vlan_var.get().strip()
                voice_vlan = self.template_voice_vlan_var.get().strip()

                # Validate access VLAN
                if access_vlan and not access_vlan.isdigit():
                    messagebox.showwarning("Invalid Input", f"Invalid access VLAN ID: {access_vlan}. Must be a number between 1-4094.")
                    return
                if access_vlan and not (1 <= int(access_vlan) <= 4094):
                    messagebox.showwarning("Invalid Input", f"Invalid access VLAN ID: {access_vlan}. Must be between 1-4094.")
                    return

                # Validate voice VLAN
                if voice_vlan and not voice_vlan.isdigit():
                    messagebox.showwarning("Invalid Input", f"Invalid voice VLAN ID: {voice_vlan}. Must be a number between 1-4094.")
                    return
                if voice_vlan and not (1 <= int(voice_vlan) <= 4094):
                    messagebox.showwarning("Invalid Input", f"Invalid voice VLAN ID: {voice_vlan}. Must be between 1-4094.")
                    return

                template_data["access_vlan"] = access_vlan
                template_data["voice_vlan"] = voice_vlan
            else:
                native_vlan = self.template_native_vlan_var.get().strip()
                trunk_vlans = self.template_trunk_vlans_var.get().strip()

                # Validate native VLAN
                if native_vlan and not native_vlan.isdigit():
                    messagebox.showwarning("Invalid Input", f"Invalid native VLAN ID: {native_vlan}. Must be a number between 1-4094.")
                    return
                if native_vlan and not (1 <= int(native_vlan) <= 4094):
                    messagebox.showwarning("Invalid Input", f"Invalid native VLAN ID: {native_vlan}. Must be between 1-4094.")
                    return

                # Validate trunk VLANs
                if trunk_vlans.upper() != "ALL" and trunk_vlans:
                    try:
                        parts = trunk_vlans.split(",")
                        for part in parts:
                            part = part.strip()
                            if not part:
                                continue

                            if "-" in part:
                                start, end = map(str.strip, part.split("-"))
                                if not start.isdigit() or not end.isdigit():
                                    messagebox.showwarning("Invalid Input", f"Invalid VLAN range: {part}. Must contain only numbers.")
                                    return
                                start_vlan = int(start)
                                end_vlan = int(end)
                                if not (1 <= start_vlan <= 4094 and 1 <= end_vlan <= 4094 and start_vlan <= end_vlan):
                                    messagebox.showwarning("Invalid Input", f"Invalid VLAN range: {part}. Values must be between 1-4094 and start must be <= end.")
                                    return
                            else:
                                if not part.isdigit():
                                    messagebox.showwarning("Invalid Input", f"Invalid VLAN ID: {part}. Must be a number between 1-4094.")
                                    return
                                vlan = int(part)
                                if not 1 <= vlan <= 4094:
                                    messagebox.showwarning("Invalid Input", f"Invalid VLAN ID: {part}. Must be between 1-4094.")
                                    return
                    except ValueError as e:
                        messagebox.showwarning("Invalid Input", f"Invalid trunk VLAN range: {e}")
                        return

                template_data["native_vlan"] = native_vlan
                template_data["trunk_vlans"] = trunk_vlans

            self.port_templates[new_name] = template_data
            self._refresh_template_list()

            for i in range(self.template_listbox.size()):
                if self.template_listbox.get(i) == new_name:
                    self.template_listbox.selection_set(i)
                    break
            self.update_status(f"New template '{new_name}' created.")
        else:
            template_name = self.template_listbox.get(selected[0])
            mode = self.template_mode_var.get().lower()

            template_data = {
                "mode": mode,
                "description": self.template_description_var.get(),
                "portfast": self.template_portfast_var.get(),
                "qos_trust": self.template_qos_var.get()
            }

            if mode == "access":
                access_vlan = self.template_access_vlan_var.get().strip()
                voice_vlan = self.template_voice_vlan_var.get().strip()

                # Validate access VLAN
                if access_vlan and not access_vlan.isdigit():
                    messagebox.showwarning("Invalid Input", f"Invalid access VLAN ID: {access_vlan}. Must be a number between 1-4094.")
                    return
                if access_vlan and not (1 <= int(access_vlan) <= 4094):
                    messagebox.showwarning("Invalid Input", f"Invalid access VLAN ID: {access_vlan}. Must be between 1-4094.")
                    return

                # Validate voice VLAN
                if voice_vlan and not voice_vlan.isdigit():
                    messagebox.showwarning("Invalid Input", f"Invalid voice VLAN ID: {voice_vlan}. Must be a number between 1-4094.")
                    return
                if voice_vlan and not (1 <= int(voice_vlan) <= 4094):
                    messagebox.showwarning("Invalid Input", f"Invalid voice VLAN ID: {voice_vlan}. Must be between 1-4094.")
                    return

                template_data["access_vlan"] = access_vlan
                template_data["voice_vlan"] = voice_vlan
            else:
                native_vlan = self.template_native_vlan_var.get().strip()
                trunk_vlans = self.template_trunk_vlans_var.get().strip()

                # Validate native VLAN
                if native_vlan and not native_vlan.isdigit():
                    messagebox.showwarning("Invalid Input", f"Invalid native VLAN ID: {native_vlan}. Must be a number between 1-4094.")
                    return
                if native_vlan and not (1 <= int(native_vlan) <= 4094):
                    messagebox.showwarning("Invalid Input", f"Invalid native VLAN ID: {native_vlan}. Must be between 1-4094.")
                    return

                # Validate trunk VLANs
                if trunk_vlans.upper() != "ALL" and trunk_vlans:
                    try:
                        parts = trunk_vlans.split(",")
                        for part in parts:
                            part = part.strip()
                            if not part:
                                continue

                            if "-" in part:
                                start, end = map(str.strip, part.split("-"))
                                if not start.isdigit() or not end.isdigit():
                                    messagebox.showwarning("Invalid Input", f"Invalid VLAN range: {part}. Must contain only numbers.")
                                    return
                                start_vlan = int(start)
                                end_vlan = int(end)
                                if not (1 <= start_vlan <= 4094 and 1 <= end_vlan <= 4094 and start_vlan <= end_vlan):
                                    messagebox.showwarning("Invalid Input", f"Invalid VLAN range: {part}. Values must be between 1-4094 and start must be <= end.")
                                    return
                            else:
                                if not part.isdigit():
                                    messagebox.showwarning("Invalid Input", f"Invalid VLAN ID: {part}. Must be a number between 1-4094.")
                                    return
                                vlan = int(part)
                                if not 1 <= vlan <= 4094:
                                    messagebox.showwarning("Invalid Input", f"Invalid VLAN ID: {part}. Must be between 1-4094.")
                                    return
                    except ValueError as e:
                        messagebox.showwarning("Invalid Input", f"Invalid trunk VLAN range: {e}")
                        return

                template_data["native_vlan"] = native_vlan
                template_data["trunk_vlans"] = trunk_vlans

            if new_name != template_name:
                if new_name in self.port_templates:
                    messagebox.showwarning("Duplicate Name", f"Template '{new_name}' already exists. Please use a different name.")
                    return

                self.port_templates[new_name] = template_data
                del self.port_templates[template_name]
                self._refresh_template_list()
                for i in range(self.template_listbox.size()):
                    if self.template_listbox.get(i) == new_name:
                        self.template_listbox.selection_set(i)
                        break
                self.update_status(f"Template renamed to '{new_name}' and updated.")
            else:
                self.port_templates[template_name] = template_data
                self.update_status(f"Template '{template_name}' updated.")

        self.template_combo['values'] = list(self.port_templates.keys())

    def _refresh_template_list(self):
        self.template_listbox.delete(0, tk.END)
        for name in sorted(self.port_templates.keys()):
            self.template_listbox.insert(tk.END, name)

    def _refresh_vlan_list(self):
        """Refresh the VLAN list in the Global Config tab.
        This method updates the VLAN listbox with the current configured VLANs.
        """
        self.vlan_listbox.delete(0, tk.END)
        # Convert all VLAN IDs to integers for proper sorting
        vlan_ids = []
        for vlan_id in self.configured_vlans:
            try:
                if isinstance(vlan_id, str):
                    vlan_ids.append(int(vlan_id))
                else:
                    vlan_ids.append(vlan_id)
            except ValueError:
                # Skip any values that can't be converted to integers
                pass

        for vlan_id in sorted(vlan_ids):
            # Get VLAN name from global configs if available
            vlan_name = ""
            if "vlans" in self.global_configs and str(vlan_id) in self.global_configs["vlans"]:
                vlan_name = self.global_configs["vlans"][str(vlan_id)]
                display_name = f"VLAN {vlan_id}: {vlan_name}"
            else:
                display_name = f"VLAN {vlan_id}"
            self.vlan_listbox.insert(tk.END, display_name)

    def delete_template(self):
        selected = self.template_listbox.curselection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a template to delete.")
            return

        template_name = self.template_listbox.get(selected[0])

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the template '{template_name}'?"):
            del self.port_templates[template_name]
            self._refresh_template_list()
            self.template_combo['values'] = list(self.port_templates.keys())
            self.update_status(f"Template '{template_name}' deleted.")
            self._clear_template_fields()
            self.template_mode_var.set("Access")
            self._on_template_mode_change()

    def _update_template_details(self, template_name):
        if template_name not in self.port_templates:
            return

        template = self.port_templates[template_name]
        self._clear_template_fields()
        self.template_name_var.set(template_name)
        self.template_mode_var.set(template["mode"].capitalize())
        self.template_description_var.set(template.get("description", ""))
        self.template_portfast_var.set(template.get("portfast", True))
        self.template_qos_var.set(template.get("qos_trust", False))
        self._on_template_mode_change()

        if template["mode"] == "access":
            self.template_access_vlan_var.set(template.get("access_vlan", ""))
            self.template_voice_vlan_var.set(template.get("voice_vlan", ""))
        else:
            self.template_native_vlan_var.set(template.get("native_vlan", ""))
            self.template_trunk_vlans_var.set(template.get("trunk_vlans", ""))

    def _clear_template_fields(self):
        self.template_name_var.set("")
        self.template_description_var.set("")
        self.template_access_vlan_var.set("")
        self.template_voice_vlan_var.set("")
        self.template_native_vlan_var.set("")
        self.template_trunk_vlans_var.set("")
        self.template_portfast_var.set(True)
        self.template_qos_var.set(False)

    def clear_template_form(self):
        self.template_listbox.selection_clear(0, tk.END)
        self._clear_template_fields()
        self.template_name_var.set(f"New Template {len(self.port_templates)+1}")
        self.template_description_var.set("New Template")
        self.template_mode_var.set("Access")
        self._on_template_mode_change()
        self.template_access_vlan_var.set("10")
        self.template_voice_vlan_var.set("")
        self.template_native_vlan_var.set("1")
        self.template_trunk_vlans_var.set("ALL")
        self.update_status("Template form cleared. Enter details and click 'Save Template' to create a new template.")

    def _on_tab_changed(self, event=None):
        """Handle tab change events.
        This method ensures that data is properly saved and refreshed when switching between tabs.
        """
        # Get the current tab index
        current_tab = self.config_notebook.index("current")

        # Save both port and global configurations when switching tabs
        self._save_port_configs()
        self._save_global_configs()

        # Tab index 0 = Port Config, 1 = Global Config, 2 = Template Editor
        if current_tab == 0:  # Port Config tab
            # Refresh the port configuration panel
            self._update_port_config_panel_from_selection()
            # Refresh the port visuals
            self._update_port_visuals()
        elif current_tab == 1:  # Global Config tab
            # Refresh the VLAN list
            self._refresh_vlan_list()
            # Update UI from global configs
            self._update_ui_from_global_configs()
        elif current_tab == 2:  # Template Editor tab
            # Refresh the template list
            self._refresh_template_list()

if __name__ == "__main__":
    root = tk.Tk()
    app = CiscoConfigTool(root)
    root.mainloop()