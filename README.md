# braiinsTestbench

## Created using Python 3.9
* create a virtual environment if needed, then pip install -r requirements.txt

## Setup
*How to tailor the testbench utility to your use*

### /firmware
* Taken from BraiinsOS+ ssh install package at https://feeds.braiins-os.com/ by choosing the newest version that contains am1-s9 and getting the ssh gzip file
* Contains all firmware files for the installation of BraiinsOS+
* Should contain these files - 
  * /CONTROL
  * /JSON.awk
  * /boot.bin
  * /fit.itb
  * /jq.awk
  * /stage1.sh
  * /stage2.tgz
  * /system.bit.gz
  * /u-boot.img
  * /uboot_env.bin
  * /uboot_env.config
  
**Can be replaced with the most current version of BraiinsOS for S9, this is for version 21.04**


### /system
* Taken from BraiinsOS+ ssh install package at https://feeds.braiins-os.com/ by choosing the newest version that contains am1-s9 and getting the ssh gzip file
* Contains all system files for the installation of BraiinsOS+
* Should contain these files - 
  * /fw_printenv
  * /ld-musl-armhf.so.1
  * /sftp-server

**Can be replaced with the most current version of BraiinsOS for S9, this is for version 21.04**


### /asicseer_installer.exe
* Used for a robust SSH unlock
* Should never need to be replaced, but can be downloaded from https://asicseer.com/page/security-restoring-ssh


### /config.toml
* TOML configuration file, used after install to do a basic configuration of the miner
* Change this as needed, you can change pools, autotuning, and temps currently
* You can also add other current BraiinsOS settings to this file, it is generated in a machine running BraiinsOS in /etc/bosminer.toml


### /referral.ipk
* Used as part of the Braiins Partnership program, this is a referral file to be installed along with the firmware
* This can be replaced with a referral file of your own, or you can leave the default if you wish to support us
* Leaving this default will not cost you any of your hashrate, and it can be removed at any time


### /update.tar
* Taken from BraiinsOS feeds at https://feeds.braiins-os.com/am1-s9/, this is the most recent *.tar file
* Used to update any devices running BraiinsOS to the newest version if they are on an older version

**Can be replaced with the most current version of BraiinsOS for S9, this is for version 21.04**
