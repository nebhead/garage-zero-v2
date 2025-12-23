#!/usr/bin/env bash

# Garage-Zero v2 Installation Script
# Many thanks to the PiVPN project (pivpn.io) for much of the inspiration for this script
# Run from https://raw.githubusercontent.com/nebhead/garage-zero-v2/main/auto-install/install.sh
#
# Install with this command (from your Pi):
#
# curl https://raw.githubusercontent.com/nebhead/garage-zero-v2/main/auto-install/install.sh | bash
#
# Usage: 
# ./install.sh [options]
#
# -dev: Use this option to run the installation script from the development branch instead of the main branch.
#          This is useful for testing new features or bug fixes that are not yet in the main branch.
#          If this option is not used, the main branch will be installed by default.
# -devrepo: Used to pull the development branch repository instead of the main branch.
#          Uses the current installation script running with the development branch of the repository.
#          This is useful for testing new features or bug fixes that are not yet in the main branch.
#          If this option is not used, the main branch will be installed by default.
#          Note: This option is ignored if -dev is also used.
#          Example usage: curl https://raw.githubusercontent.com/nebhead/garage-zero-v2/development/auto-install/install.sh | bash -s -- -devrepo


# Install script version variable for logging
INSTALL_SCRIPT_VERSION="2.0.0"

# Create logs directory if it doesn't exist
mkdir -p ~/logs

# Parse command line to check for -dev flag
DEV_INSTALLER="false"
for arg in "$@"; do
  if [[ "$arg" == "-dev" ]]; then
    DEV_INSTALLER="true"
  fi
done

# Parse command line to check for -devrepo flag
DEV_REPO="false"
for arg in "$@"; do
  if [[ "$arg" == "-devrepo" ]]; then
    DEV_REPO="true"
  fi
done

# Check if -dev flag is used and run install from development branch and exit this script
if [[ $DEV_INSTALLER == "true" ]]; then
    echo " + Running installation script from development branch..." | tee -a ~/logs/install.log
    # Pass through all arguments except -dev to the development branch installer
    # Build a new argument list excluding -dev
    passthrough_args=()
    for arg in "$@"; do
        if [[ "$arg" != "-dev" ]]; then
            passthrough_args+=("$arg")
        fi
    done
    echo " + Passing through arguments to development branch installer: ${passthrough_args[*]}" | tee -a ~/logs/install.log
    curl -SL https://raw.githubusercontent.com/nebhead/garage-zero-v2/development/auto-install/install.sh | bash -s -- -devrepo "${passthrough_args[@]}"
    exit 0
elif [[ $DEV_REPO == "true" ]]; then
    echo " + Running installation script from development branch based on version $INSTALL_SCRIPT_VERSION..." | tee -a ~/logs/install.log
else
    echo " + Running installation script from main branch based on version $INSTALL_SCRIPT_VERSION..." | tee -a ~/logs/install.log
fi

# Start logging
echo "*************************************************************************" | tee ~/logs/install.log
echo "Garage-Zero Installation Started at $(date '+%Y-%m-%d %H:%M:%S')" | tee ~/logs/install.log
echo "*************************************************************************" | tee -a ~/logs/install.log
echo " ** Logging to ~/logs/install.log **" | tee -a ~/logs/install.log

# Must be root to install
if [[ $EUID -eq 0 ]];then
    echo " + You are root." | tee -a ~/logs/install.log
else
    echo " + SUDO will be used for the install." | tee -a ~/logs/install.log
    # Check if it is actually installed
    # If it isn't, exit because the install cannot complete
    if [[ $(dpkg-query -s sudo) ]];then
        export SUDO="sudo"
        export SUDOE="sudo -E"
    else
        echo " !! Installation Failed, 'sudo' not found. Please install sudo.  Exiting" | tee -a ~/logs/install.log
        exit 1
    fi
fi

# Detect OS architecture
ARCH=$(uname -m)
echo " + Detecting system architecture: $ARCH" | tee -a ~/logs/install.log

case $ARCH in
    aarch64)
        echo " + 64-bit ARM OS detected (Raspberry Pi running 64-bit OS)" | tee -a ~/logs/install.log
        OS_BITS="64"
        ;;
    armv7l|armv6l)
        echo " + 32-bit ARM OS detected (Raspberry Pi running 32-bit OS)" | tee -a ~/logs/install.log
        OS_BITS="32"
        ;;
    *)
        echo " !! Warning: Non-standard Raspberry Pi architecture detected: $ARCH" | tee -a ~/logs/install.log
        echo " !! This script is designed for Raspberry Pi systems" | tee -a ~/logs/install.log
        if ! whiptail --backtitle "Architecture Warning" --title "Non-standard Architecture" --yesno "This script is designed for Raspberry Pi systems but detected architecture: $ARCH\n\nDo you want to continue anyway?" 12 60; then
            echo " !! Installation cancelled by user" | tee -a ~/logs/install.log
            exit 1
        fi
        ;;
esac
echo " + System architecture set to: $OS_BITS-bit" | tee -a ~/logs/install.log

# Determine OS version number
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_NAME=$NAME
    OS_VERSION=$VERSION_ID
    echo " + Detected OS: $OS_NAME Version: $OS_VERSION" | tee -a ~/logs/install.log
else
    echo " !! Unable to determine OS version. /etc/os-release not found." | tee -a ~/logs/install.log
    exit 1
fi  

# Short pause to allow user to read initial messages
sleep 2

# Find the rows and columns. Will default to 80x24 if it can not be detected.
screen_size=$(stty size 2>/dev/null || echo 24 80)
rows=$(echo $screen_size | awk '{print $1}')
columns=$(echo $screen_size | awk '{print $2}')

# Divide by two so the dialogs take up half of the screen.
r=$(( rows / 2 ))
c=$(( columns / 2 ))
# If the screen is small, modify defaults
r=$(( r < 20 ? 20 : r ))
c=$(( c < 70 ? 70 : c ))

# Display the welcome dialog
whiptail --msgbox --backtitle "Welcome" --title "Garage-Zero v2 Automated Installer" "This installer will transform your Raspberry Pi into a smart garage door controller.  NOTE: This installer is intended to be run on a fresh install of Raspberry Pi OS Lite (Bookworm or later). " ${r} ${c}

# Supervisor WebUI Settings
SVISOR=$(whiptail --title "Would you like to enable the supervisor WebUI?" --radiolist "This allows you to check the status of the supervised processes via a web browser, and also allows those processes to be restarted directly from this interface. (Recommended)" 20 78 2 "ENABLE_SVISOR" "Enable the WebUI" ON "DISABLE_SVISOR" "Disable the WebUI" OFF 3>&1 1>&2 2>&3)

if [[ $SVISOR = "ENABLE_SVISOR" ]];then
   USERNAME=$(whiptail --inputbox "Choose a username [default: user]" 8 78 user --title "Choose Username" 3>&1 1>&2 2>&3)
   PASSWORD=$(whiptail --passwordbox "Enter your password" 8 78 --title "Choose Password" 3>&1 1>&2 2>&3)
   whiptail --msgbox --backtitle "Supervisor WebUI Setup" --title "Supervisor Configured" "After this installation is completed, you should be able to access the Supervisor WebUI at http://your.ip.address.here:9001 with the username and password you have chosen." ${r} ${c}
else
    echo "No Supervisor WebUI Setup." | tee -a ~/logs/install.log
fi

echo "*************************************************************************" | tee -a ~/logs/install.log
echo "**                                                                     **" | tee -a ~/logs/install.log
echo "**      Running Apt Update... (This could take several minutes)        **" | tee -a ~/logs/install.log
echo "**                                                                     **" | tee -a ~/logs/install.log
echo "*************************************************************************" | tee -a ~/logs/install.log
# Update package list, exit if failed
$SUDO apt update 2>&1 | tee -a ~/logs/install.log || exit 1

echo "*************************************************************************" | tee -a ~/logs/install.log
echo "**                                                                     **" | tee -a ~/logs/install.log
echo "**      Running Apt Upgrade... (This could take several minutes)       **" | tee -a ~/logs/install.log
echo "**                                                                     **" | tee -a ~/logs/install.log
echo "*************************************************************************" | tee -a ~/logs/install.log
# Upgrade packages, exit if failed
$SUDO DEBIAN_FRONTEND=noninteractive apt-get upgrade -y \
    -o Dpkg::Options::=--force-confdef \
    -o Dpkg::Options::=--force-confold 2>&1 | tee -a ~/logs/install.log
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo " !! Failed to upgrade packages. Installation cannot continue." | tee -a ~/logs/install.log
    exit 1
fi

# Install APT dependencies
echo "*************************************************************************" | tee -a ~/logs/install.log
echo "**                                                                     **" | tee -a ~/logs/install.log
echo "**      Installing Dependencies... (This could take several minutes)   **" | tee -a ~/logs/install.log
echo "**                                                                     **" | tee -a ~/logs/install.log
echo "*************************************************************************" | tee -a ~/logs/install.log
# Install dependencies, exit if failed
$SUDO apt install python3-dev python3-pip python3-venv python3-rpi.gpio python3-bcrypt nginx git supervisor redis-server -y 2>&1 | tee -a ~/logs/install.log
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo " !! Failed to install dependencies. Installation cannot continue." | tee -a ~/logs/install.log
    exit 1
fi

# Grab project files
echo "*************************************************************************" | tee -a ~/logs/install.log
echo "**                                                                     **" | tee -a ~/logs/install.log
echo "**      Cloning Files from GitHub...                                   **" | tee -a ~/logs/install.log
echo "**                                                                     **" | tee -a ~/logs/install.log
echo "*************************************************************************" | tee -a ~/logs/install.log
cd /usr/local/bin

# Check if -devrepo option is used
if [[ $DEV_REPO == "true" ]]; then
    echo " + Cloning development branch..." | tee -a ~/logs/install.log
    # Replace the below command to fetch development branch
    $SUDO git clone --depth 1 --branch development https://github.com/nebhead/garage-zero-v2 2>&1 | tee -a ~/logs/install.log
else
    echo " + Cloning main branch..." | tee -a ~/logs/install.log 2>&1 | tee -a ~/logs/install.log
    # Use a shallow clone to reduce download size
    $SUDO git clone --depth 1 https://github.com/nebhead/garage-zero-v2 2>&1 | tee -a ~/logs/install.log
fi

# Setup UV VENV & Install Python dependencies
echo "*************************************************************************" | tee -a ~/logs/install.log
echo "**                                                                     **" | tee -a ~/logs/install.log
echo "**      Setting up Python VENV and Installing Modules...               **" | tee -a ~/logs/install.log
echo "**            (This could take several minutes)                        **" | tee -a ~/logs/install.log
echo "**                                                                     **" | tee -a ~/logs/install.log
echo "*************************************************************************" | tee -a ~/logs/install.log
echo ""
echo " + Setting Up garagezero Group"

cd /usr/local/bin
$SUDO groupadd garagezero 
$SUDO usermod -a -G garagezero $USER 
$SUDO usermod -a -G garagezero root 
# Change ownership to group=garagezero for all files/directories in garagezero 
$SUDO chown -R $USER:garagezero garage-zero-v2 
# Change ability for garagezero group to read/write/execute 
$SUDO chmod -R 777 /usr/local/bin

echo " - Setting up VENV" | tee -a ~/logs/install.log
# Setup VENV
cd /usr/local/bin/garage-zero-v2
python3 -m venv --system-site-packages .venv

# Activate VENV
source .venv/bin/activate 

echo " - Installing module dependencies... " | tee -a ~/logs/install.log

echo " + Installing modules from requirements.txt one at a time... " | tee -a ~/logs/install.log
while IFS= read -r req || [ -n "$req" ]; do
    # Strip inline comments and trim whitespace
    req="${req%%#*}"
    req="$(echo "$req" | xargs)"
    # Skip empty lines
    [ -z "$req" ] && continue
    # Skip requirement file/options directives
    case "$req" in
        -r*|--requirement*|--find-links*|-f*|--index-url*|--extra-index-url*|--trusted-host*|--no-binary*|--only-binary*|--*)
            echo " - Skipping requirement option: $req" | tee -a ~/logs/install.log
            continue
            ;;
    esac
    echo " - Installing $req ..." | tee -a ~/logs/install.log
    pip install "$req" 2>&1 | tee -a ~/logs/install.log
    status=${PIPESTATUS[0]}
    if [ $status -ne 0 ]; then
        echo " !! Failed to install $req. Installation cannot continue." | tee -a ~/logs/install.log
        exit 1
    fi
done < /usr/local/bin/garage-zero-v2/auto-install/requirements.txt
echo " + requirements.txt installation complete." | tee -a ~/logs/install.log

### Setup nginx to proxy to gunicorn
clear
echo "*************************************************************************" | tee -a ~/logs/install.log
echo "**                                                                     **" | tee -a ~/logs/install.log
echo "**      Configuring nginx...                                           **" | tee -a ~/logs/install.log
echo "**                                                                     **" | tee -a ~/logs/install.log
echo "*************************************************************************" | tee -a ~/logs/install.log
# Move into garage-zero install directory
cd /usr/local/bin/garage-zero-v2/auto-install/nginx

# Generate Self-Signed SSL Certificate
echo " + Generating Self-Signed SSL Certificate" | tee -a ~/logs/install.log
if ! $SUDO openssl req -x509 -nodes -days 3650 -newkey rsa:2048 -keyout /etc/ssl/private/localhost.key -out /etc/ssl/certs/localhost.crt -subj "/CN=localhost" -batch; then
    echo " !! Failed to generate SSL certificate. HTTPS may not function correctly." | tee -a ~/logs/install.log
else
    echo " + SSL Certificate generation successful." | tee -a ~/logs/install.log
fi

# Delete default configuration
$SUDO rm /etc/nginx/sites-enabled/default

# Copy configuration file to nginx
$SUDO cp garage-zero.nginx /etc/nginx/sites-available/garage-zero

# Create link in sites-enabled
$SUDO ln -s /etc/nginx/sites-available/garage-zero /etc/nginx/sites-enabled

# Restart nginx
$SUDO service nginx restart

### Setup Supervisor to Start GarageZero on Boot / Restart on Failures
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Configuring Supervisord...                                     **"
echo "**                                                                     **"
echo "*************************************************************************"

# Copy configuration files (control.conf, webapp.conf) to supervisor config directory
# NOTE: If you used a different directory for garage-zero then make sure you edit the *.conf files appropriately
cd /usr/local/bin/garage-zero-v2/auto-install/supervisor

# Add the current username to the configuration files 
printf "\nuser=$USER\n" | tee -a control.conf > /dev/null
printf "\nuser=$USER\n" | tee -a webapp.conf > /dev/null

$SUDO cp *.conf /etc/supervisor/conf.d/

if [[ $SVISOR = "ENABLE_SVISOR" ]];then
   echo " " | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   echo "[inet_http_server]" | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   echo "port = 9001" | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   echo "username = " $USERNAME | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   echo "password = " $PASSWORD | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
else
   echo "No WebUI Setup." | tee -a ~/logs/install.log
fi

# If supervisor isn't already running, startup Supervisor
$SUDO service supervisor start 2>&1 | tee -a ~/logs/install.log

$SUDO mkdir -p /usr/local/bin/garage-zero-v2/logs

# Ask user if they want to reboot
if whiptail --backtitle "Install Complete" --title "Installation Completed" --yesno "Congratulations, the installation is complete.\n\nIt's recommended to reboot your system now for all changes to take effect.\n\nYou should be able to access your application by opening a browser on your PC or other device and using the IP address (or http://[hostname].local) for this device.\n\nWould you like to reboot now?" ${r} ${c}; then
    echo "Rebooting system..." | tee -a ~/logs/install.log
    $SUDO cp ~/logs/install.log /usr/local/bin/garage-zero-v2/logs/install_$(date '+%Y%m%d_%H%M%S').log
    $SUDO reboot
else
    echo "Reboot skipped. Please reboot manually when convenient." | tee -a ~/logs/install.log
    $SUDO cp ~/logs/install.log /usr/local/bin/garage-zero-v2/logs/install_$(date '+%Y%m%d_%H%M%S').log
    exit 0
fi
