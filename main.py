import asyncio
import json
import sys
import os
import base64

import asyncssh
from screeninfo import get_monitors
import PySimpleGUI as sg

# define constants such as the BraiinsOS package to be installed, the update tar file, and the referral ipk
REFERRAL_FILE_S9 = os.path.join("files", "referral.ipk")
LIB_FILE_S9 = os.path.join(os.getcwd(), "files", "system", "ld-musl-armhf.so.1")
SFTP_SERVER_S9 = os.path.join(os.getcwd(), "files", "system", "sftp-server")
FW_PRINTENV_S9 = os.path.join(os.getcwd(), "files", "system", "fw_printenv")
FIRMWARE_PATH_S9 = os.path.join(os.getcwd(), "files", "firmware")
UPDATE_FILE_S9 = os.path.join(os.getcwd(), "files", "update.tar")
CONFIG_FILE = os.path.join(os.getcwd(), "files", "config.toml")


class Miner:
    def __init__(self, ip: str, num: int) -> None:
        # set IP of miner
        self.ip = ip
        # set numbered ID of miner
        self.num = num
        # set an event to handle pauses
        self.running = asyncio.Event()
        # set running, otherwise it will block
        self.running.set()
        # set connection to the miner up, cant be created here
        self.conn = None

    async def pause(self) -> None:
        """
        Pause the event loop for this miner after completion of current command
        """
        # check if we are running
        if self.running.is_set():
            # tell the user we are pausing
            self.add_to_output("Pausing...")
            # clearing sets the event to block on wait
            self.running.clear()

    async def resume(self) -> None:
        """
        Unpause the event loop for this miner
        """
        # check if we are paused
        if not self.running.is_set():
            # tell the user we are resuming
            self.add_to_output("Resuming...")
            # set running again
            self.running.set()
            self.add_to_output("Resumed...")

    def add_to_output(self, message: str) -> None:
        """
        Add a message to the output of the GUI
        """
        # append data to the output of the GUI in the corresponding multiline
        window[f"data_{self.num}"].update(f"[{self.ip}] - {message}\n", append=True)

    async def get_connection(self, username: str, password: str) -> asyncssh.connect:
        """
        Create a new asyncssh connection and save it
        """
        if self.conn is None:
            # if connection doesnt exist, create it
            conn = await asyncssh.connect(self.ip, known_hosts=None, username=username, password=password,
                                          server_host_key_algs=['ssh-rsa'])
            # return created connection
            self.conn = conn
        else:
            # if connection exists, return the connection
            conn = self.conn
        return conn

    async def ping(self, port: int) -> bool:
        """
        Ping a port on the miner, used by ping_ssh and ping_http
        """
        # pause logic
        if not self.running.is_set():
            self.add_to_output("Paused...")
        await self.running.wait()

        # open a connection to the miner on specified port
        connection_fut = asyncio.open_connection(self.ip, port)
        try:
            # get the read and write streams from the connection
            reader, writer = await asyncio.wait_for(connection_fut, timeout=1)
            # immediately close connection, we know connection happened
            writer.close()
            # make sure the writer is closed
            await writer.wait_closed()
            # ping was successful
            return True
        except asyncio.exceptions.TimeoutError:
            # ping failed if we time out
            return False
        except ConnectionRefusedError:
            # handle for other connection errors
            self.add_to_output("Unknown error...")
        # ping failed, likely with an exception
        return False

    async def ping_http(self) -> bool:
        """
        Ping the HTTP port of the miner
        """
        # pause logic
        if not self.running.is_set():
            self.add_to_output("Paused...")
        await self.running.wait()

        # ping port 80 (HTTP)
        if await self.ping(80):
            # ping returned true, HTTP is up
            return True
        else:
            # ping returned false, HTTP is down
            return False

    async def wait_for_disconnect(self) -> None:
        """
        Wait for the miner to disconnect
        """
        self.add_to_output('Waiting for disconnect...')
        while await self.ping_http():
            # pause logic
            if not self.running.is_set():
                self.add_to_output("Paused...")
            await self.running.wait()
            await asyncio.sleep(1)

    async def ping_ssh(self) -> bool:
        """
        Ping the SSH port of the miner
        """
        # pause logic
        if not self.running.is_set():
            self.add_to_output("Paused...")
        await self.running.wait()

        # ping port 22 (SSH)
        if await self.ping(22):
            # ping returned true, SSH is up
            return True
        else:
            # ping returned false, SSH is down
            return False

    async def get_version(self) -> str:
        """
        Get the version of the miner
        """
        # pause logic
        if not self.running.is_set():
            self.add_to_output("Paused...")
        await self.running.wait()

        # tell the user we are getting the version
        self.add_to_output("Getting version...")
        retries = 0
        while True:
            # open a connection to the [cgminer, bmminer, bosminer] API port (4028)
            connection_fut = asyncio.open_connection(self.ip, 4028)
            try:
                # get reader and writer streams from connection
                reader, writer = await asyncio.wait_for(connection_fut, timeout=5)
                # send the standard version command (JSON)
                writer.write(b'{"command":"version"}')
                # wait until command is finished sending
                await writer.drain()
                # read the returned data
                data = await reader.read(4096)
                # let the user know we recieved data
                self.add_to_output("Recieved data...")
                # close the writer
                writer.close()
                # make sure the writer is fully closed
                await writer.wait_closed()
                # load the returned data (JSON), and remove the null byte at the end
                data_dict = json.loads(data[:-1].decode('utf-8'))
                # tell the user the version of the miner
                self.add_to_output(f'Version is {data_dict["VERSION"][0][list(data_dict["VERSION"][0].keys())[1]]}...')
                if "BOSminer+" in data_dict["VERSION"][0].keys() or "BOSminer" in data_dict["VERSION"][0].keys():
                    return "BOS+"
                else:
                    return "Antminer"
            except asyncio.exceptions.TimeoutError:
                # we have no version, the connection timed out
                self.add_to_output("Get version failed...")
                return False
            except ConnectionRefusedError:
                # add to retry times
                retries += 1
                # connection was refused, tell the user
                self.add_to_output("Connection refused, retrying...")
                # make sure it doesnt get stuck here
                if retries > 3:
                    self.add_to_output('Connection refused, attempting install...')
                    return "Antminer"

    async def run_command(self, cmd: str) -> None:
        """
        Run a command on the miner
        """
        # pause logic
        if not self.running.is_set():
            self.add_to_output("Paused...")
        await self.running.wait()

        # get/create ssh connection to miner
        conn = await self.get_connection("root", "admin")
        # send the command and store the result
        try:
            result = await conn.run(cmd)
        except:
            result = await conn.run(cmd)
        # let the user know the result of the command
        if result.stdout != "":
            self.add_to_output(result.stdout)
        elif result.stderr != "":
            self.add_to_output("ERROR: " + result.stderr)
        else:
            self.add_to_output(cmd)

    async def send_dir(self, l_dir: str, r_dest: str) -> None:
        """
        Send a directory to a miner
        """
        # pause logic
        if not self.running.is_set():
            self.add_to_output("Paused...")
        await self.running.wait()

        # tell the user we are sending a file to the miner
        self.add_to_output(f"Sending directory to {self.ip}...")
        # get/create ssh connection to miner
        conn = await self.get_connection("root", "admin")
        # create sftp client using ssh connection
        async with conn.start_sftp_client() as sftp:
            # send a file over sftp
            await sftp.put(l_dir, remotepath=r_dest, recurse=True)
        # tell the user the file was sent to the miner
        self.add_to_output(f"Directory sent...")

    async def send_file(self, l_file: str, r_dest: str) -> None:
        """
        Send a file to a miner
        """
        # pause logic
        if not self.running.is_set():
            self.add_to_output("Paused...")
        await self.running.wait()

        # cget/create ssh connection to miner
        conn = await self.get_connection("root", "admin")
        # send file over scp
        await asyncssh.scp(l_file, (conn, r_dest))
        self.add_to_output(f"File sent...")

    async def get_file(self, r_file: str, l_dest: str) -> None:
        """
        Copy a file from a miner
        """
        # pause logic
        if not self.running.is_set():
            self.add_to_output("Paused...")
        await self.running.wait()

        # tell the user we are copying a file from the miner
        self.add_to_output(f"Copying file from {self.ip}...")
        # create ssh connection to miner
        conn = await self.get_connection("root", "admin")
        # create sftp client using ssh connection
        async with conn.start_sftp_client() as sftp:
            # copy a file over sftp
            await sftp.get(r_file, localpath=l_dest)
        # tell the user we copied the file from the miner
        self.add_to_output(f"File copied...")

    async def ssh_unlock(self) -> bool:
        """
        Unlock the SSH of a miner
        """
        # pause logic
        if not self.running.is_set():
            self.add_to_output("Paused...")
        await self.running.wait()

        # have to outsource this to another program
        proc = await asyncio.create_subprocess_shell(
            f'{os.path.join(os.getcwd(), "files", "asicseer_installer.exe")} -p -f {self.ip} root',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        # get stdout of the unlock
        stdout, _ = await proc.communicate()
        # check if the webUI password needs to be reset
        if str(stdout).find("webUI") != -1:
            # tell the user to reset the webUI password
            self.add_to_output("SSH unlock failed, please reset miner with reset button...")
            # ssh unlock failed
            return False
        else:
            # tell the user the SSH unlock worked
            self.add_to_output("SSH unlock success...")
            # ssh is unlocked
            return True

    async def send_referral(self) -> None:
        """
        Send the referral IPK to a miner
        """
        # pause logic
        if not self.running.is_set():
            self.add_to_output("Paused...")
        await self.running.wait()
        # check if the referral file exists
        if os.path.exists(REFERRAL_FILE_S9):
            try:
                # tell the user we are sending the referral
                self.add_to_output("Sending referral IPK...")
                # create ssh connection to miner
                conn = await self.get_connection("root", "admin")
                # create sftp client using ssh connection
                await self.send_file(REFERRAL_FILE_S9, '/tmp/referral.ipk')
                await self.send_file(CONFIG_FILE, '/etc/bosminer.toml')

                result = await conn.run(f'opkg install /tmp/referral.ipk && /etc/init.d/bosminer restart')
                self.add_to_output(result.stdout.strip())
                # tell the user the referral completed
                self.add_to_output(f"Referral configuration completed...")
            except OSError:
                self.add_to_output(f"Unknown error...")
        else:
            self.add_to_output("No referral file, skipping referral install")

    async def update(self) -> None:
        """
        Run the update process on the miner
        """
        # pause logic
        if not self.running.is_set():
            self.add_to_output("Paused...")
        await self.running.wait()

        # tell the user we are updating
        self.add_to_output(f"Updating...")
        # create ssh connection to miner
        try:
            conn = await self.get_connection("root", "admin")
            # tell the user we are sending the update file
            self.add_to_output("Sending upgrade file...")
            # send the update file
            await self.send_file(UPDATE_FILE_S9, "/tmp/firmware")
            # install the update and collect the result
            result = await conn.run(f'sysupgrade /tmp/firmware.tar')
            self.add_to_output(result.stdout.strip())
            # tell the user the update completed
            self.add_to_output(f"Update completed...")
        except OSError:
            self.add_to_output(f"Unknown error...")

    async def install(self) -> None:
        """
        Run the braiinsOS installation process on the miner
        """
        # pause logic
        if not self.running.is_set():
            self.add_to_output("Paused...")
        await self.running.wait()
        # remove temp firmware directory, making sure its empty
        await self.run_command("rm -fr /tmp/firmware")
        # recreate temp firmware directory
        await self.run_command("mkdir -p /tmp/firmware")

        # pause logic
        if not self.running.is_set():
            self.add_to_output("Paused...")
        await self.running.wait()
        # ensure lib exists
        await self.run_command("mkdir -p /lib")
        # copy ld-musl-armhf.so.1 to lib
        await self.send_file(LIB_FILE_S9, "/lib/ld-musl-armhf.so.1")
        # add execute permissions to /lib/ld-musl-armhf.so.1
        await self.run_command("chmod +x /lib/ld-musl-armhf.so.1")

        # pause logic
        if not self.running.is_set():
            self.add_to_output("Paused...")
        await self.running.wait()
        # create openssh directory in /usr/lib/openssh
        await self.run_command("mkdir -p /usr/lib/openssh")
        # copy sftp-server to /usr/lib/openssh/sftp-server
        await self.send_file(SFTP_SERVER_S9, "/usr/lib/openssh/sftp-server")
        # add execute permissions to /usr/lib/openssh/sftp-server
        await self.run_command("chmod +x /usr/lib/openssh/sftp-server")

        # pause logic
        if not self.running.is_set():
            self.add_to_output("Paused...")
        await self.running.wait()
        # ensure /usr/sbin exists
        await self.run_command("mkdir -p /usr/sbin")
        # copy fw_printenv to /usr/sbin/fw_printenv
        await self.send_file(FW_PRINTENV_S9, "/usr/sbin/fw_printenv")
        # add execute permissions to /usr/sbin/fw_printenv
        await self.run_command("chmod +x /usr/sbin/fw_printenv")

        # pause logic
        if not self.running.is_set():
            self.add_to_output("Paused...")
        await self.running.wait()
        # copy over firmware files to /tmp/firmware
        await self.send_dir(FIRMWARE_PATH_S9, "/tmp")
        # add execute permissions to firmware stage 1
        await self.run_command("chmod +x /tmp/firmware/stage1.sh")

        # pause logic
        if not self.running.is_set():
            self.add_to_output("Paused...")
        await self.running.wait()
        await self.run_command("ln -fs /usr/sbin/fw_printenv /usr/sbin/fw_setenv")

        # pause logic
        if not self.running.is_set():
            self.add_to_output("Paused...")
        await self.running.wait()
        # generate random HWID to be used in install
        hwid = base64.b64encode(os.urandom(12), b'ab').decode('ascii')
        # generate install command
        install_cmd = f"cd /tmp/firmware && ls -l && /bin/sh stage1.sh \
        '{hwid}' \
        'UpstreamDataInc.test' \
        '900' \
        'yes' \
        'cond' \
        'no' \
        'no' \
        'no'"

        # run the install
        await self.run_command(f"{install_cmd} && /sbin/reboot")
        # close ssh connection on our own, we know it will fail if not
        if self.conn is not None:
            self.conn.close()
            await self.conn.wait_closed()
            self.conn = None
        # wait 120 seconds for reboot
        self.add_to_output('Rebooting...')
        await asyncio.sleep(20)
        self.add_to_output("25% Complete...")
        await asyncio.sleep(20)
        self.add_to_output("50% Complete...")
        await asyncio.sleep(20)
        self.add_to_output("75% Complete...")
        await asyncio.sleep(20)
        self.add_to_output("Reboot Complete...")
        while not await self.ping_http():
            await asyncio.sleep(3)
        await asyncio.sleep(5)


async def run(miner: Miner) -> None:
    """
    Main run loop for the testing process of the miner
    """
    # set state to return to
    main_state = "start"
    # start the main loop
    while True:
        await asyncio.sleep(3)
        # check state
        if main_state == "start":
            # Check for http
            if await miner.ping_http():
                # check for ssh if http works
                if await miner.ping_ssh():
                    # if both ssh and http are up, the miner is on and unlocked
                    miner.add_to_output('SSH Connected...')
                    # check if BraiinsOS is already on the miner
                    if await miner.get_version() == "BOS+":
                        miner.add_to_output('BraiinsOS+ is already installed!')
                        # set state to update BraiinsOS, skip install
                        main_state = "update"
                        # restart the while loop just to be safe
                        continue
                    else:
                        # if BraiinsOS is not installed but ssh is up, move on to installing it over ssh
                        await asyncio.sleep(5)
                        main_state = "install"
                else:
                    # miner is on but has no ssh, needs to be unlocked
                    miner.add_to_output('SSH Disconnected...')
                    miner.add_to_output('Unlocking...')
                    # do the unlock
                    if await miner.ssh_unlock():
                        # set state to install now that ssh works, ssh_unlock returns True when unlock works
                        main_state = "install"
                        # restart the while loop just to be safe
                        continue
                    else:
                        # if ssh unlock fails, it needs to be reset, ssh_unlock will tell the user that and return false, so wait for disconnect
                        await miner.wait_for_disconnect()
                        # set state to start to retry after reset
                        main_state = "start"
                        # restart the while loop just to be safe
                        continue
            else:
                # if no http or ssh are present, the miner is off or not ready
                window[f"data_{miner.num}"].update(f"[{miner.ip}] - Down...\n", append=True)
        # check state
        if main_state == "install":
            # let the user know we are starting install
            miner.add_to_output('Starting install...')
            # start install
            await miner.install()
            # after install completes, move to sending referral
            main_state = "referral"
        # check state
        if main_state == "update":
            # start update
            await miner.update()
            # after update completes, move to sending referral
            main_state = "referral"
        # check state
        if main_state == "referral":
            # send the referral file, install it, and configure using config.toml
            await miner.send_referral()
            # set state to done to wait for disconnect
            main_state = "done"
        # check state
        if main_state == "done":
            # wait for the user to disconnect the miner
            await miner.wait_for_disconnect()
            # set state to start and restart the process
            main_state = "start"
            # restart main loop
            continue


# get screen size in a tuple
monitor = get_monitors()[0]

# create window size variables
win_width = int(monitor.width / 2)
win_height = int(monitor.height)

# create the layout
layout = [[sg.Pane([
    sg.Column([[
        sg.Column([
            [sg.Button("Pause", key="pause_1")],
            [sg.Button("Resume", key="resume_1")]]),
        sg.Multiline(key="data_1", autoscroll=True, disabled=True, size=(int(win_width / 20), int(win_height / 36))),
        sg.Column([
            [sg.Button("Pause", key="pause_2")],
            [sg.Button("Resume", key="resume_2")]]),
        sg.Multiline(key="data_2", autoscroll=True, disabled=True, size=(int(win_width / 20), int(win_height / 36)))]]),
    sg.Column([[
        sg.Column([
            [sg.Button("Pause", key="pause_3")],
            [sg.Button("Resume", key="resume_3")]]),
        sg.Multiline(key="data_3", autoscroll=True, disabled=True, size=(int(win_width / 20), int(win_height / 36))),
        sg.Column([
            [sg.Button("Pause", key="pause_4")],
            [sg.Button("Resume", key="resume_4")]]),
        sg.Multiline(key="data_4", autoscroll=True, disabled=True, size=(int(win_width / 20), int(win_height / 36)))]])
], relief=sg.RELIEF_FLAT, show_handle=False)]]

# create the window
window = sg.Window('Installer', layout, size=(win_width, win_height), location=(win_width, 0))


async def run_gui(miner_list: list) -> None:
    """
    Run the GUI for the miner installer
    """
    while True:
        # event loop for the GUI
        await asyncio.sleep(0)
        # read events
        event, value = window.read(timeout=1)
        # end program on closing the window
        if event in (None, 'Cancel'):
            sys.exit()

        # pause logic for miner 1
        if event == "pause_1":
            await miner_list[0].pause()
        # resume logic for miner 1
        if event == "resume_1":
            await miner_list[0].resume()

        # pause logic for miner 2
        if event == "pause_2":
            await miner_list[1].pause()
        # resume logic for miner 2
        if event == "resume_2":
            await miner_list[1].resume()

        # pause logic for miner 3
        if event == "pause_3":
            await miner_list[2].pause()
        # resume logic for miner 3
        if event == "resume_3":
            await miner_list[2].resume()

        # pause logic for miner 4
        if event == "pause_4":
            await miner_list[3].pause()
        # resume logic for miner 4
        if event == "resume_4":
            await miner_list[3].resume()


# declare all miners to be used in the GUI
miner1 = Miner('192.168.1.11', 1)
miner2 = Miner('192.168.1.12', 2)
miner3 = Miner('192.168.1.13', 3)
miner4 = Miner('192.168.1.14', 4)

# create a list of the miners
miners = [miner1, miner2, miner3, miner4]

# create futures list for the miner to be run from
futures = [run(miner) for miner in miners]
futures.append(run_gui(miners))

# run the event loop
asyncio.get_event_loop().run_until_complete(asyncio.gather(*futures))
