from urllib.request import Request, urlopen, urlretrieve
import re
import tarfile
import shutil
from distutils.dir_util import copy_tree
import os

versions = []

with urlopen(
        Request('https://feeds.braiins-os.com/', headers={'User-Agent': 'Mozilla/5.0'})
) as response:
    for line in response.readlines():
        match = "\d+\.\d+\.*\d*\/"
        match = re.search(match, line.decode("utf-8"))
        if match is not None:
            versions.append(match.group())

versions.reverse()
found_version = None
for version in versions:
    with urlopen(
            Request(f'https://feeds.braiins-os.com/{version}', headers={'User-Agent': 'Mozilla/5.0'})
    ) as response:
        for line in response.readlines():
            match_s9 = "braiins-os_am1-s9"
            if re.search(match_s9, line.decode("utf-8")):
                found_version = version
                break
    if found_version is not None:
        break


with urlopen(Request(f'https://feeds.braiins-os.com/{found_version}', headers={'User-Agent': 'Mozilla/5.0'})) as response:
    for line in response.readlines():
        match_ssh_pattern = "braiins-os_am1-s9_ssh_.*?\.tar\.gz"
        match_ssh = re.search(match_ssh_pattern, line.decode("utf-8"))
        if match_ssh is not None:
            matched_ssh = match_ssh.group()
            break


ssh_download_path = f"https://feeds.braiins-os.com/{found_version}{matched_ssh}"

ssh_downloaded_file_path = "ssh_fw.tar.gz"

folder_name = matched_ssh.split('.')
folder_name = ".".join(folder_name[:len(folder_name)-2])

with open(ssh_downloaded_file_path, 'wb') as file:
    remote = urlopen(
        Request(ssh_download_path, headers={'User-Agent': 'Mozilla/5.0'})
    )
    shutil.copyfileobj(remote, file)

tar = tarfile.open(ssh_downloaded_file_path, "r:gz")
tar.extractall()
tar.close()

try:
    shutil.rmtree("files/firmware")
    shutil.rmtree("files/system")
except FileNotFoundError:
    pass

copy_tree(folder_name, "files")

try:
    os.remove(ssh_downloaded_file_path)
    shutil.rmtree(folder_name)
except FileNotFoundError:
    pass

with urlopen(Request(f'https://feeds.braiins-os.com/am1-s9', headers={'User-Agent': 'Mozilla/5.0'})) as response:
    for line in response.readlines():
        match_tar_pattern = f"firmware_.*?-{found_version.replace('/', '')}-plus_arm_cortex-a9_neon\.tar"
        match_tar = re.search(match_tar_pattern, line.decode("utf-8"))
        if match_tar is not None:
            matched_tar = match_tar.group()
            break

tar_download_path = f"https://feeds.braiins-os.com/am1-s9/{matched_tar}"

tar_downloaded_file_path = "files/update.tar"

with open(tar_downloaded_file_path, 'wb') as file:
    remote = urlopen(
        Request(tar_download_path, headers={'User-Agent': 'Mozilla/5.0'})
    )
    shutil.copyfileobj(remote, file)