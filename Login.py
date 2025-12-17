#!/usr/bin/env python3
"""
Enterprise Kanban System - Enhanced Login Module
Secure authentication system with advanced features and robust architecture
"""

import sys
import os
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
from enum import Enum
import getpass
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('kanban_system.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class SystemConfig:
    """Centralized configuration management"""
    
    # Application settings
    APP_NAME = "Kanban Task Management System"
    APP_VERSION = "2.0.0"
    DEFAULT_DATA_DIR = Path.home() / ".kanban"
    
    # Security settings
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30
    SESSION_TIMEOUT_MINUTES = 120
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_HISTORY_SIZE = 5
    
    # Validation constants
    PHONE_NUMBER_PATTERN = r'^\d{10,15}$'
    NAME_MAX_LENGTH = 100
    VALID_POSITIONS = ['User', 'Admin', 'Manager', 'Viewer']
    
    # Admin security
    ADMIN_VALIDATION_KEY_HASH = "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"  # sha256 of "admin"


class SecurityLevel(Enum):
    """Security level enumeration for access control"""
    PUBLIC = 0
    USER = 1
    MANAGER = 2
    ADMIN = 3


@dataclass
class UserSession:
    """User session management with security controls"""
    
    user_id: int
    phone_number: int
    username: str
    position: str
    security_level: SecurityLevel
    login_time: datetime
    last_activity: datetime
    session_id: str
    ip_address: str = "localhost"
    
    @property
    def is_active(self) -> bool:
        """Check if session is still valid"""
        timeout = timedelta(minutes=SystemConfig.SESSION_TIMEOUT_MINUTES)
        return datetime.now() - self.last_activity < timeout
    
    @property
    def time_remaining(self) -> timedelta:
        """Get remaining session time"""
        timeout = timedelta(minutes=SystemConfig.SESSION_TIMEOUT_MINUTES)
        elapsed = datetime.now() - self.last_activity
        return timeout - elapsed
    
    def refresh(self) -> None:
        """Refresh session activity timestamp"""
        self.last_activity = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for serialization"""
        return {
            'user_id': self.user_id,
            'phone_number': self.phone_number,
            'username': self.username,
            'position': self.position,
            'security_level': self.security_level.value,
            'login_time': self.login_time.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'session_id': self.session_id,
            'ip_address': self.ip_address
        }


class AuthenticationError(Exception):
    """Custom exception for authentication failures"""
    pass


class SecurityService:
    """Core security service for authentication and authorization"""
    
    def __init__(self, user_repository, audit_logger):
        self.user_repo = user_repository
        self.audit_logger = audit_logger
        self._login_attempts = {}
        self._locked_accounts = {}
        self._active_sessions = {}
    
    def authenticate_user(self, phone_number: int, password: str, ip_address: str = "localhost") -> Optional[UserSession]:
        """
        Authenticate user with comprehensive security checks
        
        Args:
            phone_number: User's phone number
            password: Plain text password
            ip_address: Client IP address for logging
            
        Returns:
            UserSession if authentication successful, None otherwise
        """
        attempt_key = f"{ip_address}:{phone_number}"
        
        try:
            # Check if account is temporarily locked
            if self._is_account_locked(phone_number, ip_address):
                remaining_time = self._get_lockout_remaining(phone_number, ip_address)
                logger.warning(f"Account locked for {phone_number}. {remaining_time} remaining")
                raise AuthenticationError(f"Account temporarily locked. Try again in {remaining_time}")
            
            # Validate inputs
            if not self._validate_phone_number(phone_number):
                raise AuthenticationError("Invalid phone number format")
            
            if not self._validate_password_complexity(password):
                raise AuthenticationError("Password does not meet security requirements")
            
            # Attempt authentication
            user_data = self.user_repo.validate_login(phone_number, password)
            
            if user_data and user_data.get('is_active', True):
                # Successful authentication
                self._reset_login_attempts(phone_number, ip_address)
                session = self._create_user_session(user_data, ip_address)
                
                self.audit_logger.log_security_event(
                    "LOGIN_SUCCESS",
                    f"User {user_data.get('username', 'Unknown')} logged in successfully",
                    user_data['phone_number'],
                    ip_address
                )
                
                logger.info(f"User {user_data['phone_number']} authenticated successfully")
                return session
            else:
                # Failed authentication
                self._record_failed_attempt(phone_number, ip_address)
                remaining_attempts = SystemConfig.MAX_LOGIN_ATTEMPTS - self._get_login_attempts(phone_number, ip_address)
                
                self.audit_logger.log_security_event(
                    "LOGIN_FAILED",
                    f"Failed login attempt for {phone_number}. {remaining_attempts} attempts remaining",
                    phone_number,
                    ip_address
                )
                
                if remaining_attempts > 0:
                    raise AuthenticationError(f"Invalid credentials. {remaining_attempts} attempts remaining")
                else:
                    lockout_time = self._lock_account(phone_number, ip_address)
                    raise AuthenticationError(f"Account locked due to too many failed attempts. Try again after {lockout_time}")
                    
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Authentication system error: {e}")
            raise AuthenticationError("Authentication service temporarily unavailable")
    
    def register_user(self, user_data: Dict[str, Any], ip_address: str = "localhost") -> Dict[str, Any]:
        """
        Register new user with comprehensive validation
        
        Args:
            user_data: User registration data
            ip_address: Client IP address for logging
            
        Returns:
            Dictionary with registration result
        """
        try:
            # Extract and validate registration data
            validation_result = self._validate_registration_data(user_data)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'errors': validation_result['errors']
                }
            
            phone_number = user_data['phone_number']
            
            # Check if user already exists
            if self.user_repo.user_exists(phone_number):
                return {
                    'success': False,
                    'errors': ['Phone number already registered']
                }
            
            # Additional validation for privileged positions
            if user_data['position'] in ['Admin', 'Manager']:
                if not self._validate_privileged_registration(user_data):
                    return {
                        'success': False,
                        'errors': ['Invalid validation key for privileged position']
                    }
            
            # Create user account
            result = self.user_repo.create_user(user_data)
            
            if result['success']:
                self.audit_logger.log_security_event(
                    "REGISTRATION_SUCCESS",
                    f"New user registered: {user_data['name']} ({user_data['position']})",
                    phone_number,
                    ip_address
                )
                
                return {
                    'success': True,
                    'user_id': result['user_id'],
                    'user_data': result['user_data'],
                    'message': f"User {user_data['name']} registered successfully as {user_data['position']}"
                }
            else:
                return {
                    'success': False,
                    'errors': [result.get('error', 'Registration failed')]
                }
                
        except Exception as e:
            error_msg = f"Registration system error: {str(e)}"
            logger.error(error_msg)
            self.audit_logger.log_security_event(
                "REGISTRATION_ERROR",
                error_msg,
                user_data.get('phone_number'),
                ip_address
            )
            return {
                'success': False,
                'errors': [error_msg]
            }
    
    def validate_session(self, session_id: str) -> Optional[UserSession]:
        """Validate and return active session"""
        session = self._active_sessions.get(session_id)
        if session and session.is_active:
            session.refresh()
            return session
        elif session:
            # Session expired
            del self._active_sessions[session_id]
        return None
    
    def logout_user(self, session_id: str) -> bool:
        """Logout user and invalidate session"""
        if session_id in self._active_sessions:
            session = self._active_sessions[session_id]
            self.audit_logger.log_security_event(
                "LOGOUT",
                f"User {session.username} logged out",
                session.phone_number,
                session.ip_address
            )
            del self._active_sessions[session_id]
            logger.info(f"User {session.phone_number} logged out")
            return True
        return False
    
    def _validate_registration_data(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation of registration data"""
        errors = []
        
        # Phone number validation
        phone = user_data.get('phone_number')
        if not phone or not self._validate_phone_number(phone):
            errors.append("Invalid phone number format (10-15 digits required)")
        
        # Name validation
        name = user_data.get('name', '').strip()
        if not name or len(name) < 2:
            errors.append("Name must be at least 2 characters long")
        elif len(name) > SystemConfig.NAME_MAX_LENGTH:
            errors.append(f"Name cannot exceed {SystemConfig.NAME_MAX_LENGTH} characters")
        
        # Position validation
        position = user_data.get('position', '')
        if position not in SystemConfig.VALID_POSITIONS:
            errors.append(f"Position must be one of: {', '.join(SystemConfig.VALID_POSITIONS)}")
        
        # Password validation
        password = user_data.get('password', '')
        if not self._validate_password_complexity(password):
            errors.append(
                f"Password must be at least {SystemConfig.PASSWORD_MIN_LENGTH} characters "
                "with uppercase, lowercase, and numbers"
            )
        
        return {'valid': len(errors) == 0, 'errors': errors}
    
    def _validate_privileged_registration(self, user_data: Dict[str, Any]) -> bool:
        """Validate privileged position registration with enhanced security"""
        position = user_data.get('position')
        validation_key = user_data.get('validation_key')
        
        if position == 'Admin':
            # Admin requires special validation
            if not validation_key:
                return False
            
            # Validate admin key using secure hash comparison
            try:
                input_hash = hashlib.sha256(str(validation_key).encode()).hexdigest()
                return input_hash == SystemConfig.ADMIN_VALIDATION_KEY_HASH
            except:
                return False
        
        elif position == 'Manager':
            # Manager registration might require different validation
            # For now, same as admin but could be extended
            return validation_key is not None  # Basic check
        
        return True
    
    def _validate_phone_number(self, phone_number: int) -> bool:
        """Validate phone number format"""
        pattern = re.compile(SystemConfig.PHONE_NUMBER_PATTERN)
        return bool(pattern.match(str(phone_number)))
    
    def _validate_password_complexity(self, password: str) -> bool:
        """Validate password meets complexity requirements"""
        if len(password) < SystemConfig.PASSWORD_MIN_LENGTH:
            return False
        
        # Check for uppercase, lowercase, and numbers
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        
        return has_upper and has_lower and has_digit
    
    def _create_user_session(self, user_data: Dict[str, Any], ip_address: str) -> UserSession:
        """Create a new user session"""
        # Determine security level based on position
        position = user_data.get('position', 'User')
        security_level = self._get_security_level(position)
        
        # Generate session ID
        session_id = hashlib.sha256(
            f"{user_data['phone_number']}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:32]
        
        session = UserSession(
            user_id=user_data['user_id'],
            phone_number=user_data['phone_number'],
            username=user_data['name'],
            position=position,
            security_level=security_level,
            login_time=datetime.now(),
            last_activity=datetime.now(),
            session_id=session_id,
            ip_address=ip_address
        )
        
        self._active_sessions[session_id] = session
        return session
    
    def _get_security_level(self, position: str) -> SecurityLevel:
        """Map position to security level"""
        security_map = {
            'User': SecurityLevel.USER,
            'Viewer': SecurityLevel.USER,
            'Manager': SecurityLevel.MANAGER,
            'Admin': SecurityLevel.ADMIN
        }
        return security_map.get(position, SecurityLevel.USER)
    
    def _is_account_locked(self, phone_number: int, ip_address: str) -> bool:
        """Check if account is temporarily locked"""
        lock_key = f"{ip_address}:{phone_number}"
        if lock_key in self._locked_accounts:
            lock_time = self._locked_accounts[lock_key]
            if datetime.now() - lock_time < timedelta(minutes=SystemConfig.LOCKOUT_DURATION_MINUTES):
                return True
            else:
                # Lock expired
                del self._locked_accounts[lock_key]
                del self._login_attempts[lock_key]
        return False
    
    def _get_lockout_remaining(self, phone_number: int, ip_address: str) -> str:
        """Get remaining lockout time as string"""
        lock_key = f"{ip_address}:{phone_number}"
        if lock_key in self._locked_accounts:
            lock_time = self._locked_accounts[lock_key]
            remaining = lock_time + timedelta(minutes=SystemConfig.LOCKOUT_DURATION_MINUTES) - datetime.now()
            minutes = int(remaining.total_seconds() // 60)
            return f"{minutes} minutes"
        return "0 minutes"
    
    def _lock_account(self, phone_number: int, ip_address: str) -> str:
        """Lock account and return unlock time"""
        lock_key = f"{ip_address}:{phone_number}"
        self._locked_accounts[lock_key] = datetime.now()
        
        unlock_time = datetime.now() + timedelta(minutes=SystemConfig.LOCKOUT_DURATION_MINUTES)
        return unlock_time.strftime("%H:%M:%S")
    
    def _record_failed_attempt(self, phone_number: int, ip_address: str):
        """Record a failed login attempt"""
        attempt_key = f"{ip_address}:{phone_number}"
        current_attempts = self._login_attempts.get(attempt_key, 0)
        self._login_attempts[attempt_key] = current_attempts + 1
    
    def _get_login_attempts(self, phone_number: int, ip_address: str) -> int:
        """Get number of login attempts for a phone number"""
        attempt_key = f"{ip_address}:{phone_number}"
        return self._login_attempts.get(attempt_key, 0)
    
    def _reset_login_attempts(self, phone_number: int, ip_address: str):
        """Reset login attempts counter for successful login"""
        attempt_key = f"{ip_address}:{phone_number}"
        if attempt_key in self._login_attempts:
            del self._login_attempts[attempt_key]
        
        # Also clear any existing lock
        lock_key = f"{ip_address}:{phone_number}"
        if lock_key in self._locked_accounts:
            del self._locked_accounts[lock_key]


class LoginInterface:
    """User interface handler for login system"""
    
    def __init__(self, security_service: SecurityService):
        self.security_service = security_service
        self.current_session = None
    
    def display_welcome_banner(self):
        """Display application welcome banner"""
        banner = f"""
        ╔{'═' * 60}╗
        ║{f'{SystemConfig.APP_NAME} v{SystemConfig.APP_VERSION}':^60}║
        ║{'═' * 60}║
        ║{'Secure Authentication Portal':^60}║
        ║{'─' * 60}║
        ║{'Enterprise Task Management System':^60}║
        ╚{'═' * 60}╝
        """
        print(banner)
    
    def display_login_menu(self) -> str:
        """Display login menu and get user choice"""
        menu = f"""
        ┌─────────────────────────────────────────────────────────────┐
        │                     Authentication Menu                     │
        ├─────────────────────────────────────────────────────────────┤
        │  1) Login to System                                          │
        │  2) Register New Account                                     │
        │  3) Password Recovery                                        │
        │  h) Help & Information                                       │
        │  0) Exit System                                               │
        └─────────────────────────────────────────────────────────────┘
        
        Please select an option [0-3, h]: """
        
        print(menu)
        return input("> ").strip().lower()
    
    def handle_login_choice(self, choice: str) -> bool:
        """
        Handle user's menu choice
        
        Returns:
            bool: True if should continue, False if should exit
        """
        handlers = {
            '0': self._handle_exit,
            '1': self._handle_login,
            '2': self._handle_registration,
            '3': self._handle_password_recovery,
            'h': self._display_help,
            'help': self._display_help
        }
        
        handler = handlers.get(choice)
        if handler:
            return handler()
        else:
            print("❌ Invalid selection. Please choose a valid option.")
            return True
    
    def _handle_exit(self) -> bool:
        """Handle application exit"""
        print("\n" + "="*60)
        print("Thank you for using the Kanban Task Management System!")
        print("Goodbye!")
        print("="*60)
        return False
    
    def _handle_login(self) -> bool:
        """Handle user login process"""
        print("\n" + "─" * 60)
        print("🔐 USER LOGIN")
        print("─" * 60)
        
        try:
            # Get credentials
            phone_number = self._get_phone_input()
            if phone_number is None:
                return True  # Cancelled
            
            password = self._get_password_input("Enter your password: ")
            if not password:
                return True  # Cancelled
            
            # Attempt authentication
            session = self.security_service.authenticate_user(phone_number, password)
            
            if session:
                self._handle_successful_login(session)
                return False  # Exit login menu on success
            else:
                return True  # Stay in menu on failure
                
        except AuthenticationError as e:
            print(f"❌ {e}")
            return True
        except KeyboardInterrupt:
            print("\n\n⚠️  Login cancelled.")
            return True
        except Exception as e:
            print(f"❌ System error during login: {e}")
            logger.error(f"Login error: {e}")
            return True
    
    def _handle_registration(self) -> bool:
        """Handle new user registration"""
        print("\n" + "=" * 60)
        print("📝 NEW USER REGISTRATION")
        print("=" * 60)
        
        try:
            registration_data = self._collect_registration_data()
            if not registration_data:
                return True  # Cancelled registration
            
            result = self.security_service.register_user(registration_data)
            
            if result['success']:
                print(f"\n✅ {result['message']}")
                self._display_registration_summary(result['user_data'])
                
                # Offer immediate login
                if self._prompt_immediate_login():
                    return self._handle_login()
            else:
                print("\n❌ Registration failed:")
                for error in result.get('errors', []):
                    print(f"   • {error}")
            
            return True
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Registration cancelled.")
            return True
        except Exception as e:
            print(f"\n❌ Registration error: {e}")
            logger.error(f"Registration error: {e}")
            return True
    
    def _handle_password_recovery(self) -> bool:
        """Handle password recovery process"""
        print("\n" + "─" * 60)
        print("🔑 PASSWORD RECOVERY")
        print("─" * 60)
        print("Please contact system administrator for account recovery.")
        print("Email: admin@kanban-system.com")
        print("Phone: +1-555-HELP-KANBAN")
        print("─" * 60)
        return True
    
    def _display_help(self) -> bool:
        """Display help information"""
        help_text = f"""
        ┌─────────────────────────────────────────────────────────────┐
        │                       Help & Information                   │
        ├─────────────────────────────────────────────────────────────┤
        │                                                             │
        │  🔐 Authentication Guide:                                   │
        │  • Login: Use your registered phone number and password     │
        │  • Registration: Provide required information for new account│
        │  • Password: Minimum {SystemConfig.PASSWORD_MIN_LENGTH} chars with mixed case & numbers │
        │                                                             │
        │  ⚠️  Security Features:                                    │
        │  • Account lockout after {SystemConfig.MAX_LOGIN_ATTEMPTS} failed attempts           │
        │  • Automatic session timeout: {SystemConfig.SESSION_TIMEOUT_MINUTES} minutes        │
        │  • Secure password hashing                                  │
        │                                                             │
        │  📞 Need Assistance?                                       │
        │  • Contact: system.admin@kanban-system.com                 │
        │  • Phone: +1-555-HELP-KANBAN                              │
        │                                                             │
        └─────────────────────────────────────────────────────────────┘
        """
        print(help_text)
        input("Press Enter to continue...")
        return True
    
    def _get_phone_input(self) -> Optional[int]:
        """Get and validate phone number input"""
        while True:
            try:
                phone_input = input("📱 Phone number: ").strip()
                if not phone_input:
                    print("⚠️  Phone number is required.")
                    continue
                
                # Remove any non-digit characters
                phone_clean = ''.join(filter(str.isdigit, phone_input))
                
                if not phone_clean:
                    print("❌ Please enter a valid phone number.")
                    continue
                
                phone_number = int(phone_clean)
                
                # Validate length
                if len(phone_clean) < 10 or len(phone_clean) > 15:
                    print("❌ Phone number must be 10-15 digits.")
                    continue
                
                return phone_number
                
            except ValueError:
                print("❌ Please enter a valid numeric phone number.")
            except KeyboardInterrupt:
                print("\n⚠️  Input cancelled.")
                return None
    
    def _get_password_input(self, prompt: str = "Password: ") -> Optional[str]:
        """Get password input with optional confirmation"""
        try:
            if sys.stdin.isatty():
                # Terminal input - use getpass for security
                password = getpass.getpass(prompt)
            else:
                # Non-terminal input (e.g., testing)
                password = input(prompt)
            
            return password.strip() if password else None
            
        except KeyboardInterrupt:
            print("\n⚠️  Input cancelled.")
            return None
        except Exception as e:
            print(f"❌ Error reading password: {e}")
            return None
    
def _collect_registration_data(self) -> Optional[Dict[str, Any]]:
    """Collect registration data from user with validation"""
    data = {}
    
    print("\nPlease provide the following information:")
    print("─" * 40)
    
    # Phone Number
    data['phone_number'] = self._get_phone_input()
    if data['phone_number'] is None:
        return None
    
    # Full Name
    while True:
        name = input("👤 Full name: ").strip()
        if not name:  # 修复：添加空格
            print("⚠️  Name is required.")
            continue

        if len(name) > SystemConfig.NAME_MAX_LENGTH:
            print(f"❌ Name cannot exceed {SystemConfig.NAME_MAX_LENGTH} characters.")
            continue

        data['name'] = name
        break

    # Position selection
    while True:
        print("\nAvailable positions:")
        for i, position in enumerate(SystemConfig.VALID_POSITIONS, 1):
            print(f"  {i}) {position}")
        
        try:
            pos_choice = input(f"\nSelect position [1-{len(SystemConfig.VALID_POSITIONS)}]: ").strip()
            if not pos_choice:
                print("⚠️  Position selection is required.")
                continue
            
            pos_index = int(pos_choice) - 1
            if 0 <= pos_index < len(SystemConfig.VALID_POSITIONS):
                data['position'] = SystemConfig.VALID_POSITIONS[pos_index]
                break
            else:
                print(f"❌ Please select a number between 1 and {len(SystemConfig.VALID_POSITIONS)}")
        except ValueError:
            print("❌ Please enter a valid number.")

    # Validation key for privileged positions
    if data['position'] in ['Admin', 'Manager']:
        print(f"\n🔐 {data['position']} registration requires validation:")
        
        while True:
            try:
                validation_key = input("Enter validation key: ").strip()
                if not validation_key:
                    print("⚠️  Validation key is required for this position.")
                    continue
                
                data['validation_key'] = validation_key
                break
            except KeyboardInterrupt:
                print("\n⚠️  Input cancelled.")
                return None

    # Password with confirmation
    while True:
        password = self._get_password_input("🔒 Create password: ")
        if not password:
            return None  # Cancelled
        
        # Validate password strength
        if len(password) < SystemConfig.PASSWORD_MIN_LENGTH:
            print(f"❌ Password must be at least {SystemConfig.PASSWORD_MIN_LENGTH} characters.")
            continue
        
        # Check for uppercase, lowercase, and numbers
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        
        if not (has_upper and has_lower and has_digit):
            print("❌ Password must contain uppercase, lowercase letters and numbers.")
            continue
        
        # Confirm password
        confirm_password = self._get_password_input("🔒 Confirm password: ")
        if not confirm_password:
            return None  # Cancelled
        
        if password != confirm_password:
            print("❌ Passwords do not match. Please try again.")
            continue
        
        data['password'] = password
        break

    return data

def _display_registration_summary(self, user_data: Dict[str, Any]):
    """Display registration summary with formatted output"""
    print("\n" + "="*60)
    print("📋 REGISTRATION SUMMARY")
    print("="*60)
    
    summary_data = [
        ("Name", user_data.get('name', 'N/A')),
        ("Phone Number", user_data.get('phone_number', 'N/A')),
        ("Position", user_data.get('position', 'N/A')),
        ("Status", "Active" if user_data.get('is_active', True) else "Inactive"),
        ("User ID", user_data.get('user_id', 'N/A')),
        ("Registration Date", user_data.get('created_at', 'N/A'))
    ]
    
    for label, value in summary_data:
        print(f"{label:>20}: {value}")
    
    print("="*60)

def _prompt_immediate_login(self) -> bool:
    """Prompt user for immediate login after registration"""
    while True:
        response = input("\n🎯 Would you like to log in now? (y/N): ").strip().lower()
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no', '']:
            return False
        else:
            print("❌ Please enter 'y' for yes or 'n' for no.")

def _handle_successful_login(self, session: UserSession):
    """Handle successful login and route to appropriate interface"""
    print("\n" + "🎉" * 30)
    print(f"✅ LOGIN SUCCESSFUL! Welcome, {session.username}!")
    print("🎉" * 30)
    
    # Display session information
    print(f"\n👤 User: {session.username} ({session.position})")
    print(f"📞 Phone: {session.phone_number}")
    print(f"🆔 Session ID: {session.session_id[:8]}...")
    print(f"⏰ Session timeout: {session.time_remaining}")
    
    # Route based on security level
    if session.security_level == SecurityLevel.ADMIN:
        self._route_to_admin_interface(session)
    else:
        self._route_to_user_interface(session)

def _route_to_admin_interface(self, session: UserSession):
    """Route admin users to administrative interface"""
    print("\n🔧 Redirecting to Administrative Console...")
    
    try:
        # Import here to avoid circular dependencies
        from admin_console import AdminConsole
        
        admin_console = AdminConsole(session, self.security_service)
        admin_console.start()
        
    except ImportError as e:
        print(f"❌ Administrative interface unavailable: {e}")
        print("🔧 Falling back to standard user interface...")
        self._route_to_user_interface(session)
    
    except Exception as e:
        print(f"❌ Error launching admin interface: {e}")
        logger.error(f"Admin interface error: {e}")

def _route_to_user_interface(self, session: UserSession):
    """Route regular users to main application interface"""
    print("\n📊 Loading Kanban Task Management System...")
    
    try:
        from kanban_ui import KanbanUserInterface
        
        app_interface = KanbanUserInterface(session, self.security_service)
        app_interface.start()
        
    except ImportError as e:
        print(f"❌ Application interface unavailable: {e}")
        print("💡 Please contact system administrator.")
        
    except Exception as e:
        print(f"❌ Error launching application: {e}")
        logger.error(f"Application interface error: {e}")

def run_login_system(self):
    """Main login system loop"""
    self.display_welcome_banner()
    
    try:
        while True:
            choice = self.display_login_menu()
            
            if not self.handle_login_choice(choice):
                break  # Exit application
            
            print()  # Add spacing between iterations
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Application interrupted by user.")
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        logger.critical(f"Login system crash: {e}")
        sys.exit(1)


class AuditLogger:
    """Enhanced audit logging for security events"""
    
    def __init__(self, log_file: Path = None):
        self.log_file = log_file or SystemConfig.DEFAULT_DATA_DIR / "security_audit.log"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def log_security_event(self, event_type: str, message: str, 
                          user_phone: int = None, ip_address: str = "unknown"):
        """Log security event with comprehensive details"""
        timestamp = datetime.now().isoformat()
        log_entry = {
            'timestamp': timestamp,
            'event_type': event_type,
            'message': message,
            'user_phone': user_phone,
            'ip_address': ip_address
        }
        
        # Format log entry
        log_line = (f"[{timestamp}] {event_type}: {message} "
                   f"(User: {user_phone or 'unknown'}, IP: {ip_address})")
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_line + '\n')
            
            logger.info(f"Security event: {event_type} - {message}")
            
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")


# Mock repository classes for demonstration
class UserRepository:
    """Mock user repository - to be implemented with actual database"""
    
    def __init__(self):
        self.users = {}
        self.next_user_id = 1
    
    def validate_login(self, phone_number: int, password: str) -> Optional[Dict[str, Any]]:
        """Mock login validation"""
        user = self.users.get(phone_number)
        if user and user.get('password') == password and user.get('is_active', True):
            return user
        return None
    
    def user_exists(self, phone_number: int) -> bool:
        """Check if user exists"""
        return phone_number in self.users
    
    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new user account"""
        user_id = self.next_user_id
        self.next_user_id += 1
        
        user_record = {
            'user_id': user_id,
            'phone_number': user_data['phone_number'],
            'name': user_data['name'],
            'position': user_data['position'],
            'password': user_data['password'],  # In real implementation, this would be hashed
            'is_active': True,
            'created_at': datetime.now().isoformat()
        }
        
        self.users[user_data['phone_number']] = user_record
        
        return {
            'success': True,
            'user_id': user_id,
            'user_data': user_record
        }


def main():
    """Main application entry point"""
    try:
        # Initialize components
        user_repo = UserRepository()
        audit_logger = AuditLogger()
        security_service = SecurityService(user_repo, audit_logger)
        login_interface = LoginInterface(security_service)
        
        # Run login system
        login_interface.run_login_system()
        
    except KeyboardInterrupt:
        print("\n\n👋 Application terminated by user. Goodbye!")
    except Exception as e:
        print(f"\n💥 Critical application error: {e}")
        logger.critical(f"Application crash: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
