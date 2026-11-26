#Enhancements over putty_test_4.py. This requires Devics.csv and commands.csv files

from netmiko import ConnectHandler
from getpass import getpass
from tkinter import Tk, filedialog
from datetime import datetime
import csv
import os
import re
import time

# ==========================================================
# PICK FILES/FOLDERS
# ==========================================================

root = Tk()
root.withdraw()

devices_csv = filedialog.askopenfilename(
    title="Select Devices CSV",
    filetypes=[("CSV Files", "*.csv")]
)

if not devices_csv:
    raise SystemExit("No devices CSV selected")

commands_csv = filedialog.askopenfilename(
    title="Select Commands CSV",
    filetypes=[("CSV Files", "*.csv")]
)

if not commands_csv:
    raise SystemExit("No commands CSV selected")

backup_root = filedialog.askdirectory(
    title="Select Backup Location"
)

if not backup_root:
    raise SystemExit("No backup folder selected")

# ==========================================================
# USER INPUTS
# ==========================================================

jump_server = input(
    "Jump Server Hostname/IP: "
).strip()

username = input(
    "Username: "
).strip()

private_key = input(
    "Private Key Path: "
).strip()

passphrase = getpass(
    "Key Passphrase / Device Password: "
)

otp = getpass(
    "RSA OTP: "
)

# ==========================================================
# LOAD DEVICES
# ==========================================================

devices = []

with open(
    devices_csv,
    mode="r",
    encoding="utf-8"
) as f:

    reader = csv.DictReader(f)

    for row in reader:

        hostname = row["hostname"].strip()

        if hostname:
            devices.append(hostname)

# ==========================================================
# LOAD COMMANDS
# ==========================================================

commands = []

with open(
    commands_csv,
    mode="r",
    encoding="utf-8"
) as f:

    reader = csv.DictReader(f)

    for row in reader:

        command = row["command"].strip()
        filename = row["filename"].strip()

        commands.append({
            "command": command,
            "filename": filename
        })

# ==========================================================
# CREATE BACKUP DIRECTORY
# ==========================================================

date_folder = os.path.join(
    backup_root,
    datetime.now().strftime("%Y-%m-%d")
)

os.makedirs(
    date_folder,
    exist_ok=True
)

report_file = os.path.join(
    date_folder,
    "backup_report.csv"
)

results = []

# ==========================================================
# CONNECT TO JUMP SERVER
# ==========================================================

jump_params = {
    "device_type": "terminal_server",
    "host": jump_server,
    "username": username,
    "use_keys": True,
    "key_file": private_key,
    "passphrase": passphrase,
    "password": otp
}

try:

    print("\nConnecting to jump server...")

    conn = ConnectHandler(**jump_params)

    print(
        f"Connected to: {conn.find_prompt()}"
    )

except Exception as e:

    print(
        f"Failed connecting to jump server:\n{e}"
    )

    raise SystemExit(1)

# ==========================================================
# PROCESS DEVICES
# ==========================================================

for count, device in enumerate(
    devices,
    start=1
):

    print(
        f"\n[{count}/{len(devices)}] "
        f"Processing {device}"
    )

    try:

        #
        # SSH TO DEVICE
        #

        conn.write_channel(
            f"ssh {username}@{device}\n"
        )

        output = ""

        timeout = 0

        while timeout < 30:

            time.sleep(1)

            output += conn.read_channel()

            if "yes/no" in output.lower():

                conn.write_channel("yes\n")
                output = ""

            elif "password:" in output.lower():

                conn.write_channel(
                    passphrase + "\n"
                )
                output = ""

            elif re.search(
                r"[>#]\s*$",
                output
            ):
                break

            timeout += 1

        if timeout >= 30:

            raise Exception(
                "SSH timeout"
            )

        #
        # DISABLE PAGING
        #

        conn.write_channel(
            "terminal length 0\n"
        )

        time.sleep(2)

        conn.read_channel()

        #
        # DEVICE FOLDER
        #

        device_folder = os.path.join(
            date_folder,
            device
        )

        os.makedirs(
            device_folder,
            exist_ok=True
        )

        #
        # RUN EACH COMMAND
        #

        for cmd in commands:

            command = cmd["command"]

            file_name = (
                cmd["filename"]
                .strip()
                + ".txt"
            )

            output_file = os.path.join(
                device_folder,
                file_name
            )

            print(
                f"   Running: {command}"
            )

            conn.write_channel(
                command + "\n"
            )

            command_output = ""

            idle = 0

            while idle < 10:

                time.sleep(1)

                data = conn.read_channel()

                if data:

                    command_output += data
                    idle = 0

                else:

                    idle += 1

            with open(
                output_file,
                "w",
                encoding="utf-8"
            ) as outfile:

                outfile.write(
                    command_output
                )

        #
        # EXIT DEVICE
        #

        conn.write_channel(
            "exit\n"
        )

        time.sleep(2)

        results.append([
            device,
            "SUCCESS"
        ])

        print(
            f"Completed {device}"
        )

    except Exception as e:

        results.append([
            device,
            f"FAILED - {e}"
        ])

        print(
            f"FAILED {device}"
        )

        try:

            conn.write_channel(
                "exit\n"
            )

            time.sleep(2)

        except:
            pass

# ==========================================================
# DISCONNECT
# ==========================================================

conn.disconnect()

# ==========================================================
# REPORT
# ==========================================================

with open(
    report_file,
    "w",
    newline="",
    encoding="utf-8"
) as f:

    writer = csv.writer(f)

    writer.writerow([
        "Device",
        "Result"
    ])

    writer.writerows(results)

print("\n=================================")
print("Backup Completed")
print("=================================")
print(f"Backup Folder : {date_folder}")
print(f"Report File   : {report_file}")