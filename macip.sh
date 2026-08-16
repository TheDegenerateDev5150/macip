#!/bin/bash
# MacIP - MAC and IP address management tool
# Interactive menu around the Python tools in ./tools

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Prefer python3, fall back to python
PYTHON="python3"
command -v "$PYTHON" >/dev/null 2>&1 || PYTHON="python"

VERSION="3.0"

# Color codes
ORANGE='\033[38;5;208m'
GREEN='\033[0;32m'
RED='\033[0;31m'
RESET='\033[0m'

# Tool display names
TOOLS=(
  "[+] MAC address change [+]"
  "[+] auto MAC address change [+]"
  "[+] IP address change [+]"
  "[+] auto IP address change [+]"
  "[+] MAC address and IP address change [+]"
  "[+] auto MAC address and IP address change [+]"
)

# Python scripts backing each tool
FILES=(
  "tools/01_mac_changer.py"
  "tools/02_auto_mac_changer.py"
  "tools/03_ip_changer.py"
  "tools/04_auto_ip_changer.py"
  "tools/05_macip_changer.py"
  "tools/06_auto_macip_changer.py"
)

display_banner() {
  clear 2>/dev/null || true
  echo -e "${ORANGE}                                                                  ${RESET}"
  echo -e "${ORANGE}                     ███╗   ███╗ █████╗  ██████╗██╗██████╗ ${RESET}"
  echo -e "${ORANGE}                     ████╗ ████║██╔══██╗██╔════╝██║██╔══██╗${RESET}"
  echo -e "${ORANGE}                     ██╔████╔██║███████║██║     ██║██████╔╝${RESET}"
  echo -e "${ORANGE}                     ██║╚██╔╝██║██╔══██║██║     ██║██╔═══╝ ${RESET}"
  echo -e "${ORANGE}                     ██║ ╚═╝ ██║██║  ██║╚██████╗██║██║    ${RESET}"
  echo -e "${ORANGE}                                                       ${RESET}"
  echo -e "${ORANGE}         =============================================================${RESET}"
  echo -e "                     𝕍𝕖𝕣𝕤𝕚𝕠𝕟 : ${VERSION}     𝕋𝕨𝕚𝕥𝕥𝕖𝕣 : anishalx7          "
  echo -e "${ORANGE}         =============================================================${RESET}"
  echo -e "${ORANGE}  START YOUR ANONYMOUS LIFE ...${RESET}"

  if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}  [!] WARNING: Not running as root. Changing MAC/IP requires root."${RESET}
    echo -e "${RED}      Re-run with: sudo ./macip.sh${RESET}"
  fi
}

main_menu() {
  tput cup 12 0 2>/dev/null || true
  echo "Main Menu"
  echo ""
  echo "  ${#TOOLS[@]} tools loaded"
  echo ""
  echo "Available Tools:"
  for i in "${!TOOLS[@]}"; do
    printf "  %d) %s\n" $((i+1)) "${TOOLS[$i]}"
  done
  echo ""
  echo "Available Commands:"
  echo "  exit        Completely exit MacIP"
  echo "  help        Show this help"
  echo "  info #      Information on a specific tool"
  echo "  interfaces  List available network interfaces"
  echo "  list        List available tools"
  echo "  options     Show MacIP configuration"
  echo "  restore     Restore the original configuration of an interface"
  echo "  update      Update MacIP"
  echo "  use #       Use a specific tool by its number"
  echo ""
  read -rp "Enter command: " command args
}

tool_info() {
  if [[ -z "$args" ]]; then
    echo "Usage: info <tool_number>"
    echo "Example: info 1"
    echo "This command provides information on a specific tool."
    return
  fi

  case $args in
    1)
      echo "[+] MAC address change [+]:"
      echo "This tool allows you to manually change the MAC address of your network interface."
      echo "Usage: Enter your network interface and new MAC address to spoof a new MAC."
      ;;
    2)
      echo "[+] auto MAC address change [+]:"
      echo "Automatically changes your MAC address to a random one at intervals."
      echo "Usage: Enter your network interface, and the tool will randomly select a new MAC address."
      ;;
    3)
      echo "[+] IP address change [+]:"
      echo "Manually change the IP address of your network interface."
      echo "Usage: Enter your network interface and new IP address to set."
      ;;
    4)
      echo "[+] auto IP address change [+]:"
      echo "Automatically changes your IP address to a random one at intervals."
      echo "Usage: Enter your network interface, and the tool will randomly assign a new IP address."
      ;;
    5)
      echo "[+] MAC address and IP address change [+]:"
      echo "Manually change both MAC and IP address of your network interface."
      echo "Usage: Enter your network interface, MAC address, and IP address."
      ;;
    6)
      echo "[+] auto MAC address and IP address change [+]:"
      echo "Automatically changes both your MAC and IP address at intervals."
      echo "Usage: Enter your network interface, and the tool will randomly assign new values for both."
      ;;
    *)
      echo "Invalid tool number. Please choose a valid tool number from the list."
      ;;
  esac
}

list_tools() {
  echo "Available Tools:"
  for i in "${!TOOLS[@]}"; do
    printf "  %d) %s\n" $((i+1)) "${TOOLS[$i]}"
  done
}

show_options() {
  echo "MacIP Configuration Options:"
  echo "  1) MAC address change:"
  echo "     - Allows you to change your MAC address manually."
  echo "  2) Auto MAC address change:"
  echo "     - Automatically assigns a random MAC address."
  echo "  3) IP address change:"
  echo "     - Change your IP address manually."
  echo "  4) Auto IP address change:"
  echo "     - Randomly assigns a new IP address at regular intervals."
  echo "  5) MAC and IP address change:"
  echo "     - Allows you to manually change both MAC and IP."
  echo "  6) Auto MAC and IP address change:"
  echo "     - Automatically assigns both new MAC and IP address at intervals."
  echo ""
  echo "Extra commands:"
  echo "  restore     - Revert an interface to its saved original MAC/IP."
  echo "  interfaces  - Show the network interfaces visible on this system."
}

show_help() {
  echo "MacIP commands:"
  echo "  exit        Completely exit MacIP"
  echo "  help        Show this help"
  echo "  info #      Information on a specific tool"
  echo "  interfaces  List available network interfaces"
  echo "  list        List available tools"
  echo "  options     Show MacIP configuration"
  echo "  restore     Restore the original configuration of an interface"
  echo "  update      Update MacIP"
  echo "  use #       Use a specific tool by its number"
}

run_tool() {
  if [[ -z "$args" ]]; then
    echo "Usage: use <tool_number>"
    echo "Example: use 1"
    echo "Please specify the tool number to use. Type 'list' to see available tools."
    return
  fi

  if [[ "$args" =~ ^[0-9]+$ ]] && (( args >= 1 && args <= ${#TOOLS[@]} )); then
    local tool_number=$args
    # shellcheck disable=SC2207
    local user_inputs=($(get_user_inputs "$tool_number"))
    if [[ $EUID -ne 0 ]]; then
      echo -e "${RED}[!] Warning: you are not root. Changes will require sudo.${RESET}"
    fi
    "$PYTHON" "$SCRIPT_DIR/${FILES[$((tool_number-1))]}" "${user_inputs[@]}" || {
      echo "An error occurred while running the tool. Please check your inputs."
    }
  else
    echo "Invalid tool number. Please choose a valid tool number from the list."
  fi
}

get_user_inputs() {
  local tool_number=$1
  local params=""

  if [[ "$tool_number" -eq 1 || "$tool_number" -eq 2 || "$tool_number" -eq 4 || "$tool_number" -eq 5 || "$tool_number" -eq 6 ]]; then
    read -rp "Enter network interface (e.g., wlan0, eth0): " interface
    params="$params -i $interface"
  fi

  if [[ "$tool_number" -eq 1 || "$tool_number" -eq 5 ]]; then
    read -rp "Enter MAC address (e.g., 00:11:22:33:44:55): " mac
    params="$params -m $mac"
  fi

  if [[ "$tool_number" -eq 3 || "$tool_number" -eq 5 ]]; then
    read -rp "Enter IP address (e.g., 192.168.1.100): " ip
    params="$params -ip $ip"
  fi

  echo "$params"
}

restore_config() {
  read -rp "Enter the network interface to restore (e.g., wlan0): " iface
  if [[ -z "$iface" ]]; then
    echo "[-] No interface given."
    return
  fi
  "$PYTHON" "$SCRIPT_DIR/tools/restore.py" -i "$iface"
}

show_interfaces() {
  "$PYTHON" "$SCRIPT_DIR/tools/interfaces.py"
}

update_macip() {
  echo "[*] Updating MacIP..."
  if [[ ! -d "$SCRIPT_DIR/.git" ]]; then
    echo "[-] This installation is not a git repository - cannot auto-update."
    echo "    Re-clone manually instead: git clone https://github.com/anishalx/macip.git"
    return
  fi
  if (cd "$SCRIPT_DIR" && git pull --ff-only); then
    echo "[+] MacIP is up to date."
  else
    echo "[-] Update failed. Check your network connection or git state."
  fi
}

trap 'echo ""; echo "Bye."; exit 0' INT

display_banner

while true; do
  main_menu
  case $command in
    exit)
      echo "Exiting MacIP."
      exit 0
      ;;
    help)
      show_help
      ;;
    info)
      tool_info
      ;;
    interfaces)
      show_interfaces
      ;;
    list)
      list_tools
      ;;
    options)
      show_options
      ;;
    restore)
      restore_config
      ;;
    update)
      update_macip
      ;;
    use)
      run_tool
      ;;
    *)
      echo "Invalid command. Please try again."
      ;;
  esac
  echo ""
  read -rp "Press Enter to return to the main menu..." _
done
