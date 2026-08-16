# **MacIP: MAC and IP Address Management Tool**

## **Overview**

MacIP is a powerful command-line tool designed to manage and automate MAC and IP address changes on Linux-based systems. This tool is useful for network administrators, penetration testers, and cybersecurity professionals who require dynamic control over network interfaces for privacy, testing, and network management purposes.

MacIP offers six essential tools to manage your network interface, allowing you to change MAC and IP addresses manually or automatically. The tool is built with ease of use in mind and is compatible with most Linux distributions.

---

## **Features**

- **MAC Address Management**: Change or automate MAC address assignments on your network interfaces.
- **IP Address Management**: Modify or automate IP address assignments for greater control and privacy.
- **Combined MAC and IP Management**: Use a combination of MAC and IP address management for more complex use cases.
- **Automation**: Automate the process of changing MAC and IP addresses for network testing or enhanced privacy.
- **Backup & Restore**: Every change remembers the original interface configuration — restore it at any time with the `restore` command (or Ctrl+C during automatic changes).
- **Modern & Portable**: Uses `ip` (iproute2) by default with an automatic `ifconfig` (net-tools) fallback, so it works on modern and legacy distributions alike.
- **Safe by Default**: Random MACs are always locally administered and unicast; random IPs never pick network or broadcast addresses. `--dry-run` mode lets you preview every command without touching your system.
- **Simple Command Interface**: Easy-to-use command-line interface with clear options and commands.

---

## **Tools Available**

1. **MAC Address Change**: Manually change the MAC address on a specified network interface.
2. **Auto MAC Address Change**: Automatically change the MAC address without user input.
3. **IP Address Change**: Manually change the IP address of a specified network interface.
4. **Auto IP Address Change**: Automatically change the IP address without user input.
5. **MAC and IP Address Change**: Change both MAC and IP addresses simultaneously.
6. **Auto MAC and IP Address Change**: Automate the process of changing both MAC and IP addresses.

---

## **Software Requirements**

The following OSs are officially supported:

- Debian 8+
- Kali Linux Rolling 2018.1+

The following OSs are likely able to run MacIP:

- Deepin 15+
- Fedora 22+
- Linux Mint
- Parrot Security
- Ubuntu 15.10+
- Void Linux

> **Note:** changing MAC/IP addresses requires **root privileges**. Install either `iproute2` (preferred, ships with `ip`) or `net-tools` (ships with `ifconfig`). MacIP uses only the Python standard library — no third-party pip packages are needed.

```bash
apt update && apt upgrade -y
apt install -y iproute2   # ifconfig fallback: apt install -y net-tools
```

---

## **Installation**

### **Prerequisites**
- **Python 3.6+** installed on your system.
- `iproute2` (or `net-tools`) installed.

### **Clone the Repository**
```bash
git clone https://github.com/anishalx/macip.git
cd macip
```

### **Make the Script Executable**
```bash
chmod +x macip.sh
```

### **Run MacIP**
```bash
sudo ./macip.sh
```

---

## **Usage**

After running the tool, you will see a simple menu listing the available tools and commands. You can interact with the tool using the following commands:

### **Commands**

- `exit`: Exit MacIP completely.
- `help`: Show the command list.
- `info #`: Display information about a specific tool.
- `interfaces`: List the network interfaces visible on this system (with current MAC/IP).
- `list`: List all available tools.
- `options`: Show the current MacIP configuration.
- `restore`: Restore the original MAC/IP configuration of an interface.
- `update`: Update MacIP to the latest version.
- `use #`: Use a specific tool by its number (e.g., `use 1` to manually change the MAC address).

### **Example Usage**

**Manually Change MAC Address:**

```bash
use 1
```
- Enter the network interface (e.g., wlan0, eth0).
- Enter the new MAC address.

**Automatically Change IP Address:**

```bash
use 4
```
- Enter the network interface.

**Restore an Interface to Its Original Configuration:**

```bash
restore
```
- Enter the network interface — MacIP reverts it to the MAC/IP it had before your last change.

---

## **Advanced Usage (direct CLI)**

Every tool can be called directly for scripting and automation. Run any tool with `--help` for the full flag list. Common flags:

| Flag | Applies to | Meaning |
|------|-----------|---------|
| `-i, --interface` | all | Network interface to change (required) |
| `-m, --mac` | 1, 5 | New MAC address |
| `-ip, --ipaddress` | 3, 5 | New IPv4 address |
| `--prefix N` | 3, 4, 5, 6 | CIDR prefix length (default 24) |
| `--network CIDR` | 4, 6 | Subnet for random addresses (default 192.168.0.0/16) |
| `--times N` | 2, 4, 6 | Number of automatic changes (default 5) |
| `--interval S` | 2, 4, 6 | Seconds between automatic changes (default 1.0) |
| `--restore` | 2, 4, 6 | Restore the saved configuration, then exit |
| `--no-restore` | 2, 4, 6 | Do not restore on Ctrl+C |
| `--no-save` | 1, 3, 5 | Do not remember the original configuration |
| `--dry-run` | all | Print the commands that would run, without executing them |

**Examples:**

```bash
# Manually spoof a MAC address
sudo python3 tools/01_mac_changer.py -i wlan0 -m 00:11:22:33:44:55

# Rotate the MAC 20 times, 30 seconds apart, restoring the original on Ctrl+C
sudo python3 tools/02_auto_mac_changer.py -i wlan0 --times 20 --interval 30

# Revert an interface to its saved original configuration
sudo python3 tools/restore.py -i wlan0

# Preview exactly what a change would do, without touching the system
python3 tools/05_macip_changer.py -i eth0 -m 00:11:22:33:44:55 -ip 192.168.1.100 --dry-run

# List available interfaces
python3 tools/interfaces.py
```

---

## **Testing**

MacIP ships with a pytest test-suite covering validation, random generation, command building, backup/restore, dry-run mode and every tool's CLI. The tests are fully mocked — they never touch a real network interface.

```bash
pip install pytest
python -m pytest tests/ -v
```

A CI pipeline (`.github/workflows/ci.yml`) runs the suite on Python 3.9/3.11/3.13 plus a bash syntax check on every push and pull request.

---

### **Updating MacIP**
You can update MacIP directly from the command-line using the `update` command:

```bash
update
```
This command will pull the latest version of MacIP from the GitHub repository and update the local files.

---

### **Contribution Guidelines**
We welcome contributions from the community! If you would like to contribute, follow these steps:
1. **Fork the repository.**
2. **Create a new branch for your feature or bug fix.**
3. **Commit your changes and push them to your fork.**
4. **Create a pull request, and we will review your submission.**

---

### **License**

This project is licensed under the [MIT License](./LICENSE). See the LICENSE file for more details.

---

### **Acknowledgments**
- Special thanks to all the contributors who helped build and improve this tool.
- The project is designed to support ethical usage in cybersecurity and networking tasks.

### **Contact**
For any questions, issues, or feature requests, feel free to open an issue on GitHub or contact me at - **<a href="mailto:anishalx7@gmail.com" class="btn">Email Me</a>**
