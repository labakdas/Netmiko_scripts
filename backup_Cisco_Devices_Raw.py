# Old Pytty_Test_4.py file. This required Commands.csv and Devices.csv file to run
from netmiko import ConnectHandler
from getpass import getpass
from tkinter import Tk, filedialog
from datetime import datetime
import csv
import time
import re
import os

# =====================================================
# FILE PICKERS
# =====================================================

root = Tk()
root.withdraw()

devices_csv = filedialog.askopenfilename(
    title="Select Devices CSV",
    filetypes=[("CSV files", "*.csv")]
)

if not devices_csv:
    print("No devices file selected.")
    quit()

commands_csv = filedialog.askopenfilename(
    title="Select Commands CSV",
    filetypes=[("CSV files", "*.csv")]
)

if not commands_csv:
    print("No commands file selected.")
    quit()

backup_root = filedialog.askdirectory(
    title="Select Backup Location"
)

if not backup_root:
    print("No backup folder selected.")
    quit()

# =====================================================
# USER INPUTS
# =====================================================

jump_server = input(
    "Jump Server Hostname/IP: "
).strip()

username = input(
    "Username: "
).strip()

private_key = input(
    "Private Key File: "
).strip()

passphrase = getpass(
    "Key Passphrase / Device Password: "
)

otp = getpass(
    "RSA OTP: "
)

# =====================================================
# LOAD DEVICES
# =====================================================

devices = []

with open(
    devices_csv,
    newline="",
    encoding="utf-8"
) as f:

    reader = csv.DictReader(f)

    for row in reader:

        hostname = row["hostname"].strip()

        if hostname:
            devices.append(hostname)

# =====================================================
# LOAD COMMANDS
# =====================================================

commands = []

with open(
    commands_csv,
    newline="",
    encoding="utf-8"
) as f:

    reader = csv.DictReader(f)

    for row in reader:

        cmd = row["command"].strip()

        if cmd:
            commands.append(cmd)

# =====================================================
# BACKUP FOLDER
# =====================================================

date_folder = os.path.join(
    backup_root,
    datetime.now().strftime("%Y-%m-%d")
)

os.makedirs(
    date_folder,
    exist_ok=True
)

# =====================================================
# REPORT
# =====================================================

report_rows = []

# =====================================================
# JUMP SERVER CONNECTION
# =====================================================

jump_params = {
    "device_type": "terminal_server",
    "host": jump_server,
    "username": username,
    "use_keys": True,
    "key_file": private_key,
    "passphrase": passphrase,
    "password": otp
}

print("\nConnecting to jump server...")

conn = ConnectHandler(**jump_params)

print(
    f"Connected to {conn.find_prompt()}"
)

# =====================================================
# DEVICE LOOP
# =====================================================

for count, device in enumerate(devices, start=1):

    print(
        f"\n[{count}/{len(devices)}] "
        f"{device}"
    )

    try:

        conn.write_channel(
            f"ssh {username}@{device}\n"
        )

        login_output = ""

        while True:

            time.sleep(1)

            login_output += conn.read_channel()

            if "yes/no" in login_output.lower():

                conn.write_channel("yes\n")
                login_output = ""

            elif "password:" in login_output.lower():

                conn.write_channel(
                    passphrase + "\n"
                )
                login_output = ""

            elif re.search(
                r"[>#]\s*$",
                login_output
            ):
                break

        #
        # Disable paging
        #

        conn.write_channel(
            "terminal length 0\n"
        )

        time.sleep(2)
        conn.read_channel()

        #
        # Create device folder
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
        # Execute commands
        #

        for cmd in commands:

            print(
                f"   Running: {cmd}"
            )

            conn.write_channel(
                cmd + "\n"
            )

            output = ""

            idle = 0

            while idle < 10:

                time.sleep(1)

                data = conn.read_channel()

                if data:

                    output += data
                    idle = 0

                else:

                    idle += 1

            #
            # filename cleanup
            #

            safe_name = re.sub(
                r"[^A-Za-z0-9]+",
                "_",
                cmd
            )

            output_file = os.path.join(
                device_folder,
                f"{safe_name}.txt"
            )

            with open(
                output_file,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(output)

        #
        # Return to jump host
        #

        conn.write_channel("exit\n")

        time.sleep(2)

        report_rows.append(
            [device, "SUCCESS"]
        )

        print(
            f"Completed {device}"
        )

    except Exception as e:

        report_rows.append(
            [device, f"FAILED: {e}"]
        )

        print(
            f"FAILED: {device}"
        )

        try:
            conn.write_channel("exit\n")
            time.sleep(2)
        except:
            pass

# =====================================================
# WRITE REPORT
# =====================================================

report_file = os.path.join(
    date_folder,
    "backup_report.csv"
)

with open(
    report_file,
    "w",
    newline="",
    encoding="utf-8"
) as report:

    writer = csv.writer(report)

    writer.writerow(
        ["Device", "Status"]
    )

    writer.writerows(
        report_rows
    )

conn.disconnect()

print("\n======================================")
print("BACKUP COMPLETE")
print("======================================")
print(f"Files saved under:\n{date_folder}")