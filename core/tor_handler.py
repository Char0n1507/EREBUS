import requests
import socket
import socks
import time
import logging
import re
from stem import Signal
from stem.control import Controller
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from fake_useragent import UserAgent

try:
    from ..config import TOR_PROXY_URL, TOR_CONTROL_PORT, TOR_PASSWORD, REQUEST_TIMEOUT
except ImportError:
    # Fallback for standalone testing
    TOR_PROXY_URL = "socks5h://127.0.0.1:9050"
    TOR_CONTROL_PORT = 9051
    TOR_PASSWORD = None
    REQUEST_TIMEOUT = 45

logger = logging.getLogger(__name__)

class TorHandler:
    def __init__(self, proxy_url=None):
        self.proxy_url = proxy_url or TOR_PROXY_URL
        self.control_port = TOR_CONTROL_PORT
        self.password = TOR_PASSWORD
        self.ua = UserAgent()
        
        # Only auto-detect if NOT explicitly provided/overridden by user input
        # (Assuming TOR_PROXY_URL from config is a 'default' not a hard requirement if passed via arg)
        if not proxy_url and "9050" in self.proxy_url: 
             # If default 9050 is set but we want to be smart, try detecting.
             # If user passed a specific string, trust it.
             self._detect_ports()

    def _detect_ports(self):
        """
        Probes standard Tor ports first, then scans system for any open SOCKS proxy
        if defaults fail.
        """
        # 1. Try standard ports
        candidates = [
            (9050, 9051), # System Tor
            (9150, 9151), # Tor Browser
            (9052, 9053), # Sometimes used
            (9152, 9153)
        ]
        
        # Explicit env var check
        if self.proxy_url:
            try:
                parts = self.proxy_url.split(":")
                if len(parts) > 1:
                    env_port = int(parts[-1])
                    if env_port not in [c[0] for c in candidates]:
                        candidates.insert(0, (env_port, self.control_port))
            except:
                pass

        for p_port, c_port in candidates:
            if self._test_socks_port(p_port):
                self._set_ports(p_port, c_port)
                return

        # 2. If standard ports fail, scan all localhost listeners
        logger.info("Standard Tor ports not found. Scanning system for active SOCKS proxies...")
        found_port = self._scan_system_ports()
        if found_port:
             self._set_ports(found_port, found_port + 1) # Guess control port
             return

        logger.warning("Could not detect any active Tor proxy. Defaulting to 9050.")
        
    def _set_ports(self, p_port, c_port):
        logger.info(f"detected active Tor proxy on port {p_port}")
        self.proxy_url = f"socks5h://127.0.0.1:{p_port}"
        self.control_port = c_port

    def _test_socks_port(self, port):
        """
        Tries to perform a SOCKS5 handshake to verify it's actually a proxy.
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            if s.connect_ex(('127.0.0.1', port)) != 0:
                s.close()
                return False
            
            # SOCKS5 Handshake: Client sends [Version 5, 1 Method, Method NoAuth(0)]
            s.sendall(b'\x05\x01\x00')
            data = s.recv(2)
            s.close()
            
            # Server should respond [Version 5, Method NoAuth(0)]
            if len(data) == 2 and data[0] == 0x05 and data[1] == 0x00:
                return True
            return False
        except:
            return False

    def _scan_system_ports(self):
        """
        Parses netstat/ss output to find listening ports on localhost
        and tests them for SOCKS capabilities.
        """
        import subprocess
        import sys
        
        ports = set()
        try:
            if sys.platform == 'win32':
                # Windows: netstat -an
                output = subprocess.check_output("netstat -an", shell=True).decode()
                # Look for TCP 127.0.0.1:PORT ... LISTENING
                matches = re.findall(r'TCP\s+127\.0\.0\.1:(\d+)\s+.*LISTENING', output)
            else:
                # Linux/Mac: ss -tuln
                output = subprocess.check_output("ss -tuln", shell=True).decode()
                # Look for 127.0.0.1:PORT
                matches = re.findall(r'127\.0\.0\.1:(\d+)', output)
            
            for p in matches:
                ports.add(int(p))
                
        except Exception as e:
            logger.error(f"Port scan failed: {e}")
            return None
        
        # Test each found port
        for port in ports:
            # Skip common non-proxy ports to save time
            if port in [80, 443, 8080, 8501, 11434, 3306, 5432]: 
                continue
                
            if self._test_socks_port(port):
                return port
        return None


    def get_session(self):
        """
        Creates a requests Session with Tor SOCKS proxy, random User-Agent,
        and automatic retries.
        """
        session = requests.Session()
        
        # Configure retries
        retry = Retry(
            total=3,
            read=3,
            connect=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False
        )
        adapter = HTTPAdapter(max_retries=retry)
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set proxies
        session.proxies = {
            "http": self.proxy_url,
            "https": self.proxy_url
        }
        
        # Set random User-Agent
        session.headers.update({
            "User-Agent": self.ua.random,
            "Accept-Language": "en-US,en;q=0.9"
        })
        
        return session

    def renew_connection(self):
        """
        Signals the Tor controller to switch to a new circuit (new IP).
        Requires Tor ControlPort to be enabled (usually 9051).
        """
        try:
            with Controller.from_port(port=self.control_port) as controller:
                if self.password:
                    controller.authenticate(password=self.password)
                else:
                    controller.authenticate()
                
                controller.signal(Signal.NEWNYM)
                logger.info("Tor circuit renewed successfully.")
                time.sleep(controller.get_newnym_wait())
                return True
        except Exception as e:
            logger.error(f"Failed to renew Tor connection: {e}")
            return False

    def check_connection(self):
        """
        Verifies if traffic is being routed through Tor.
        """
        session = self.get_session()
        try:
            # check.torproject.org is reliable but sometimes slow
            # httpbin or similar IP echo services can also be used
            resp = session.get("https://check.torproject.org/api/ip", timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                is_tor = data.get("IsTor", False)
                ip = data.get("IP", "Unknown")
                logger.info(f"Connected to Tor: {is_tor} (IP: {ip})")
                return is_tor, ip
            return False, "N/A"
        except Exception as e:
            logger.error(f"Connection check failed: {e}")
            return False, str(e)

if __name__ == "__main__":
    # Simple test
    logging.basicConfig(level=logging.INFO)
    handler = TorHandler()
    print("Checking initial connection...")
    handler.check_connection()
    
    print("Renewing circuit...")
    if handler.renew_connection():
        print("Checking new connection...")
        handler.check_connection()
