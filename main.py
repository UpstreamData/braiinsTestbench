import asyncio
import json
import sys
import os

import asyncssh
from screeninfo import get_monitors
import PySimpleGUI as sg

# define constants such as the BraiinsOS package to be installed, the update tar file, and the referral ipk
REFFERRAL_FILE_S9 = os.path.join("files", "bos-referral_2021-04-28_arm_cortex-a9_neon.ipk")


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

    async def pause(self) -> None:
        """
        Pause the event loop for this miner after completion of current command
        """
        # tell the user we are pausing
        self.add_to_output("Pausing...")
        # clearing sets the event to block on wait
        self.running.clear()

    async def unpause(self) -> None:
        """
        Unpause the event loop for this miner
        """
        # tell the user we are unpausing
        self.add_to_output("Unpausing...")
        # set running again
        self.running.set()

    def add_to_output(self, message: str) -> None:
        """
        Add a message to the output of the GUI
        """
        # append data to the output of the GUI in the corresponding multiline
        window[f"data_{self.num}"].update(f"[{self.ip}] - {message}\n", append=True)

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
            # let the user know we connected
            self.add_to_output(f"Connected to port {port}...")
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
                self.add_to_output(f'Version is {data_dict["VERSION"][0][list(data_dict["VERSION"][0].keys())[0]]}...')
                return True
            except asyncio.exceptions.TimeoutError:
                # we have no version, the connection timed out
                self.add_to_output("Get version failed...")
                return False
            except ConnectionRefusedError:
                # connection was refused, tell the user
                self.add_to_output("Connection refused, retrying...")

    async def run_command(self, cmd: str, username: str, password=None) -> None:
        """
        Run a command on the miner
        """
        # pause logic
        if not self.running.is_set():
            self.add_to_output("Paused...")
        await self.running.wait()

        # create ssh connection to miner
        async with asyncssh.connect(self.ip, known_hosts=None, username=username, password=password,
                                    server_host_key_algs=['ssh-rsa']) as conn:
            # send the command and store the result
            result = await conn.run(cmd)
            # let the user know the result of the command
            self.add_to_output(result.stdout)

    async def send_file(self, l_file: str, r_dest: str, username: str, password=None) -> None:
        """
        Send a file to a miner
        """
        # pause logic
        if not self.running.is_set():
            self.add_to_output("Paused...")
        await self.running.wait()

        # tell the user we are sending a file to the miner
        self.add_to_output(f"Sending file to {self.ip}...")
        # create ssh connection to miner
        async with asyncssh.connect(self.ip, known_hosts=None, username=username, password=password,
                                    server_host_key_algs=['ssh-rsa']) as conn:
            # create sftp client using ssh connection
            async with conn.start_sftp_client() as sftp:
                # send a file over sftp
                await sftp.put(l_file, remotepath=r_dest)
        # tell the user the file was sent to the miner
        self.add_to_output(f"File sent...")

    async def get_file(self, r_file: str, l_dest: str, username: str, password=None) -> None:
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
        async with asyncssh.connect(self.ip, known_hosts=None, username=username, password=password,
                                    server_host_key_algs=['ssh-rsa']) as conn:
            # create sftp client using ssh connection
            async with conn.start_sftp_client() as sftp:
                # copy a file over sftp
                await sftp.get(r_file, localpath=l_dest)
        # tell the user we copied the file from the miner
        self.add_to_output(f"File copied...")

    async def ssh_unlock(self):
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
        print(stdout)
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

    async def send_referral(self, username: str, password=None) -> None:
        """
        Send the referral IPK to a miner
        """
        # pause logic
        if not self.running.is_set():
            self.add_to_output("Paused...")
        await self.running.wait()

        # tell the user we are sending the referral
        self.add_to_output(f"Sending referral IPK to {self.ip}...")
        # create ssh connection to miner
        try:
            async with asyncssh.connect(self.ip, known_hosts=None, username=username, password=password,
                                        server_host_key_algs=['ssh-rsa']) as conn:
                # create sftp client using ssh connection
                async with conn.start_sftp_client() as sftp:
                    # send the referral
                    await sftp.put(REFFERRAL_FILE_S9, remotepath='/tmp/referral.ipk')
                # install the referral and collect the result
                result = await conn.run(f'opkg install /tmp/referral.ipk')
                self.add_to_output(result.stdout.strip())
                # tell the user the referral completed
                self.add_to_output(f"Referral configuration completed...")
        except OSError:
            self.add_to_output(f"Unknown error...")

    async def install(self) -> None:
        """
        Run the braiinsOS installation process on the miner
        """
        # do some install stuff here separated by asyncio.wait(0) to allow the gui to remain responsive.
        pass



async def run(miner: Miner) -> None:
    while True:
        await asyncio.sleep(3)
        if await miner.ping_http():
            if await miner.ping_ssh():
                miner.add_to_output('SSH Connected...')
            else:
                miner.add_to_output('SSH Down...')
            await miner.get_version()
        else:
            window[f"data_{miner.num}"].update(f"[{miner.ip}] - Down...\n", append=True)
        # await miner.pause()


# get screen size in a tuple
monitor = get_monitors()[0]

# create window size variables
win_width = int(monitor.width / 2)
win_height = int(monitor.height)

# create the layout
layout = [[sg.Pane([
    sg.Column([[
        sg.Button("Pause", key="pause_1"),
        sg.Multiline(key="data_1", autoscroll=True, disabled=True, size=(int(win_width / 18), int(win_height / 36))),
        sg.Button("Pause", key="pause_2"),
        sg.Multiline(key="data_2", autoscroll=True, disabled=True, size=(int(win_width / 18), int(win_height / 36)))]]),
    sg.Column([[
        sg.Button("Pause", key="pause_3"),
        sg.Multiline(key="data_3", autoscroll=True, disabled=True, size=(int(win_width / 18), int(win_height / 36))),
        sg.Button("Pause", key="pause_4"),
        sg.Multiline(key="data_4", autoscroll=True, disabled=True, size=(int(win_width / 18), int(win_height / 36)))]])
], relief=sg.RELIEF_FLAT, show_handle=False)]]

# create the window
window = sg.Window('Installer', layout, size=(win_width, win_height), location=(win_width, 0))


async def run_gui(miner_list: list):
    """
    Run the GUI for the miner installer
    """
    while True:
        # event loop for the GUI
        # TODO: Add events
        await asyncio.sleep(0)
        event, value = window.read(timeout=1)
        if event in (None, 'Cancel'):
            sys.exit()
        if event == "pause_1":
            await miner_list[0].pause()
        if event == "pause_2":
            await miner_list[1].pause()
        if event == "pause_3":
            await miner_list[2].pause()
        if event == "pause_4":
            await miner_list[3].pause()


# declare all miners to be used in the GUI
miner1 = Miner('172.16.1.99', 1)
miner2 = Miner('172.16.1.98', 2)
miner3 = Miner('172.16.1.97', 3)
miner4 = Miner('172.16.1.96', 4)

# create a list of the miners
miners = [miner1, miner2, miner3, miner4]

futures = [run(miner) for miner in miners]
futures.append(run_gui(miners))

asyncio.get_event_loop().run_until_complete(asyncio.gather(*futures))
