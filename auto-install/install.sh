#!/usr/bin/env bash

# Garage-Zero v2 Installation Script
# Many thanks to the PiVPN project (pivpn.io) for much of the inspiration for this script
# Run from https://raw.githubusercontent.com/nebhead/garage-zero-v2/main/auto-install/install.sh
#
# Install with this command (from your Pi):
#
# curl https://raw.githubusercontent.com/nebhead/garage-zero-v2/main/auto-install/install.sh | bash
#

# Must be root to install
if [[ $EUID -eq 0 ]];then
    echo "You are root."
else
    echo "SUDO will be used for the install."
    # Check if it is actually installed
    # If it isn't, exit because the install cannot complete
    if [[ $(dpkg-query -s sudo) ]];then
        export SUDO="sudo"
        export SUDOE="sudo -E"
    else
        echo "Please install sudo."
        exit 1
    fi
fi

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
whiptail --msgbox --backtitle "Welcome" --title "Garage-Zero v2 Automated Installer" "This installer will transform your Raspberry Pi into a smart garage door controller.  NOTE: This installer is intended to be run on a fresh install of Raspberry Pi OS (Bullseye or Bookworm). " ${r} ${c}

# Starting actual steps for installation
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Setting /tmp to RAM based storage in /etc/fstab                **"
echo "**                                                                     **"
echo "*************************************************************************"
echo "tmpfs /tmp  tmpfs defaults,noatime 0 0" | sudo tee -a /etc/fstab > /dev/null

clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Running Apt Update... (This could take several minutes)        **"
echo "**                                                                     **"
echo "*************************************************************************"
$SUDO apt update
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Running Apt Upgrade... (This could take several minutes)       **"
echo "**                                                                     **"
echo "*************************************************************************"
$SUDO apt upgrade -y

# Install dependancies
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Installing Dependancies... (This could take several minutes)   **"
echo "**                                                                     **"
echo "*************************************************************************"
$SUDO apt install python3-dev python3-pip python3-venv python3-rpi.gpio nginx git supervisor redis-server -y

# Grab project files
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Cloning Garage-Zero v2 from GitHub...                          **"
echo "**                                                                     **"
echo "*************************************************************************"
cd /usr/local/bin
# Clone the software
$SUDO git clone --depth 1 https://github.com/nebhead/garage-zero-v2

# Setup Python VENV & Install Python dependencies
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Setting up Python VENV and Installing Modules...               **"
echo "**            (This could take several minutes)                        **"
echo "**                                                                     **"
echo "*************************************************************************"
echo ""
echo " - Setting Up garagezero Group"
cd /usr/local/bin
$SUDO groupadd garagezero 
$SUDO usermod -a -G garagezero $USER 
$SUDO usermod -a -G garagezero root 
# Change ownership to group=garagezero for all files/directories in garagezero 
$SUDO chown -R $USER:garagezero garage-zero-v2 
# Change ability for garagezero group to read/write/execute 
$SUDO chmod -R 775 garage-zero-v2/

echo " - Setting up VENV"
# Setup VENV
python -m venv --system-site-packages garage-zero-v2
cd /usr/local/bin/garage-zero-v2
source bin/activate 

echo " - Installing module dependencies... "
# Install module dependencies 
python -m pip install "flask==2.3.3" 
python -m pip install "bcrypt==4.1.3" 
python -m pip install "flask-bcrypt==1.0.1" 
python -m pip install "Flask-WTF==1.1.1"
python -m pip install gunicorn
python -m pip install redis
python -m pip install pushbullet.py

### Setup nginx to proxy to gunicorn
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Configuring nginx...                                           **"
echo "**                                                                     **"
echo "*************************************************************************"
# Move into garage-zero install directory
cd /usr/local/bin/garage-zero-v2/auto-install/nginx

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

SVISOR=$(whiptail --title "Would you like to enable the supervisor WebUI?" --radiolist "This allows you to check the status of the supervised processes via a web browser, and also allows those processes to be restarted directly from this interface. (Recommended)" 20 78 2 "ENABLE_SVISOR" "Enable the WebUI" ON "DISABLE_SVISOR" "Disable the WebUI" OFF 3>&1 1>&2 2>&3)

if [[ $SVISOR = "ENABLE_SVISOR" ]];then
   echo " " | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   echo "[inet_http_server]" | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   echo "port = 9001" | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   USERNAME=$(whiptail --inputbox "Choose a username [default: user]" 8 78 user --title "Choose Username" 3>&1 1>&2 2>&3)
   echo "username = " $USERNAME | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   PASSWORD=$(whiptail --passwordbox "Enter your password" 8 78 --title "Choose Password" 3>&1 1>&2 2>&3)
   echo "password = " $PASSWORD | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   whiptail --msgbox --backtitle "Supervisor WebUI Setup" --title "Setup Completed" "You now should be able to access the Supervisor WebUI at http://your.ip.address.here:9001 with the username and password you have chosen." ${r} ${c}
else
   echo "No WebUI Setup."
fi

# If supervisor isn't already running, startup Supervisor
$SUDO service supervisor start

### Edit CRONTAB for log Backups
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Configuring Crontab for log backups...                         **"
echo "**                                                                     **"
echo "*************************************************************************"

cd /usr/local/bin/garage-zero-v2/auto-install
$SUDO crontab -l > my-crontab
# Add the following line...
echo "0 0 1 * * cd /usr/local/bin/garage-zero-v2/logs && sh backup.sh" >> my-crontab
$SUDO crontab my-crontab
rm my-crontab

# Rebooting
whiptail --msgbox --backtitle "Install Complete / Reboot Required" --title "Installation Completed - Rebooting" "Congratulations, the installation is complete.  At this time, we will perform a reboot and your application should be ready.  You should be able to access your application by opening a browser on your PC or other device and using the IP address for this Pi.  Enjoy!" ${r} ${c}
clear
$SUDO reboot
