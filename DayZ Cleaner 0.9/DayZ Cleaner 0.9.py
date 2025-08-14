import ftplib
import time
import re
import requests
import os

# --- FTP and server details ---
FTP_HOST = "xx.gamedata.io"
FTP_USER = "xx"
FTP_PASS = "xx"
LOG_DIR = "/dayzps/config/"

# --- Nitrado API ---
NITRADO_API_TOKEN = "xx"
SERVICE_ID = "xx"
NITRADO_API_URL = f"https://api.nitrado.net/services/{SERVICE_ID}/gameservers/games/banlist"

# --- Flaglist file ---
FLAGLIST_FILE = "flaglist.txt"  # One UID per line

# Keep track of gamertags we’ve already banned
banned_gamertags = set()

# Regex to match connected players in ADM log
adm_pattern = re.compile(r'Player\s+"(.+?)"\(id=([A-Za-z0-9\-_]+=*)\)\s+is connected')

# --- Helper functions ---
def load_flaglist():
    if not os.path.exists(FLAGLIST_FILE):
        with open(FLAGLIST_FILE, "w") as f:
            pass
    with open(FLAGLIST_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]

def save_flaglist(flaglist):
    with open(FLAGLIST_FILE, "w") as f:
        for uid in flaglist:
            f.write(f"{uid}\n")

def connect_ftp():
    while True:
        try:
            ftp = ftplib.FTP(FTP_HOST)
            ftp.login(FTP_USER, FTP_PASS)
            print("Connected to FTP")
            return ftp
        except Exception as e:
            print(f"FTP connection failed: {e}. Retrying in 10 seconds...")
            time.sleep(10)

def get_latest_adm(ftp):
    ftp.cwd(LOG_DIR)
    files = ftp.nlst()
    adm_files = [f for f in files if f.endswith(".ADM")]
    adm_files.sort()
    return adm_files[-1] if adm_files else None

def read_new_lines(ftp, file_path, last_size=0):
    ftp.voidcmd('TYPE I')  # Binary mode
    size = ftp.size(file_path)
    lines = []
    if size > last_size:
        with open("temp_adm.log", "wb") as f:
            ftp.retrbinary(f"RETR " + file_path, f.write)
        with open("temp_adm.log", "r", encoding="utf-8", errors="ignore") as f:
            f.seek(last_size)
            lines = f.readlines()
        last_size = size
    return lines, last_size

def ban_gamertags(gamertags):
    tags_to_ban = [tag for tag in gamertags if tag not in banned_gamertags]
    if not tags_to_ban:
        return
    headers = {
        "Authorization": f"Bearer {NITRADO_API_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {"identifier": tags_to_ban}  # API accepts gamertags
    try:
        response = requests.post(NITRADO_API_URL, headers=headers, json=data)
        if response.status_code == 200:
            print(f"Banned gamertags: {', '.join(tags_to_ban)}")
            banned_gamertags.update(tags_to_ban)
        else:
            print(f"Failed to ban gamertags {tags_to_ban}: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"Error contacting Nitrado API: {e}")

def monitor(flaglist):
    ftp = connect_ftp()
    latest_adm = get_latest_adm(ftp)
    if not latest_adm:
        print("No ADM file found. Exiting monitor.")
        return
    last_size = 0

    try:
        while True:
            current_latest = get_latest_adm(ftp)
            if current_latest != latest_adm:
                print(f"Switching to new ADM file: {current_latest}")
                latest_adm = current_latest
                last_size = 0

            lines, last_size = read_new_lines(ftp, f"{LOG_DIR}{latest_adm}", last_size)
            gamertags_to_ban = []
            for line in lines:
                match = adm_pattern.search(line)
                if match:
                    gamertag, uid = match.groups()
                    if uid in flaglist:
                        gamertags_to_ban.append(gamertag)
                        print(f"Flagged UID {uid} → Gamertag: {gamertag}")

            if gamertags_to_ban:
                ban_gamertags(gamertags_to_ban)

            time.sleep(10)
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")

# --- Interactive menu ---
def menu():
    while True:
        print("\n=== DayZ Nitrado Auto-Ban Menu ===")
        print("1. Start monitoring and auto-ban")
        print("2. Show banned gamertags")
        print("3. Show/edit flaglist")
        print("4. Exit")
        choice = input("Enter your choice: ").strip()

        flaglist = load_flaglist()

        if choice == "1":
            print("Starting monitoring... Press Ctrl+C to stop.")
            monitor(flaglist)
        elif choice == "2":
            if banned_gamertags:
                print("Banned gamertags:")
                for tag in banned_gamertags:
                    print(tag)
            else:
                print("No gamertags banned yet.")
        elif choice == "3":
            print("Current flaglist UIDs:")
            for idx, uid in enumerate(flaglist, 1):
                print(f"{idx}. {uid}")
            print("\nOptions: a=add, r=remove, b=back")
            action = input("Choose action: ").strip().lower()
            if action == "a":
                new_uid = input("Enter UID to add: ").strip()
                if new_uid and new_uid not in flaglist:
                    flaglist.append(new_uid)
                    save_flaglist(flaglist)
                    print(f"UID {new_uid} added.")
            elif action == "r":
                rm_idx = input("Enter UID number to remove: ").strip()
                if rm_idx.isdigit() and 0 < int(rm_idx) <= len(flaglist):
                    removed = flaglist.pop(int(rm_idx)-1)
                    save_flaglist(flaglist)
                    print(f"UID {removed} removed.")
            elif action == "b":
                continue
            else:
                print("Invalid option.")
        elif choice == "4":
            print("Exiting program.")
            break
        else:
            print("Invalid choice. Try again.")

if __name__ == "__main__":
    menu()
