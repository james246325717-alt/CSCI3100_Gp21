#!/usr/bin/env python3
"""
Enhanced Kanban System - Login Module
Enterprise-grade authentication system with improved security and user experience
"""

import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from datetime import datetime
import logging
import hashlib

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import refactored modules
try:
    from database import DatabaseConnectionManager, UserRepository, PasswordManager, DatabaseConfig
    from models import UserSession, AuditLogger
    from utils import InputValidator, SecurityManager, ConfigManager
except ImportError as e:
    print(f"Error importing required modules: {e}")
    sys.exit(1)


class LoginSystemConfig:
    """Configuration management for login system"""
    
    # Application settings
    APP_NAME = "Kanban Task Management System"
    APP_VERSION = "2.0.0"
    DEFAULT_DATA_DIR = Path.home() / ".kanban"
    
    # Security settings
    MAX_LOGIN_ATTEMPTS = 5
    SESSION_TIMEOUT_MINUTES = 30
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_REQUIREMENTS = {
        'min_length': 8,
        'require_upper': True,
        'require_lower': True,
        'require_digit': True,
        'require_special': False
    }
    
    # UI texts
    LOGIN_PAGE = f"""
{APP_NAME} v{APP_VERSION}
{'=' * 50}
Login Portal
{'=' * 50}
Choose an option:
  1) Log in
  2) Register
  h) Help
  0) Exit
{'=' * 50}
"""

    ADMIN_LOGIN_PAGE = f"""
{APP_NAME} - Administrative Access
{'=' * 50}
Admin Authentication Required
{'=' * 50}
"""

    HELP_TEXT = f"""
{APP_NAME} - Help Guide
{'=' * 50}

Authentication Guide:
• Registration: Provide phone number, name, position, and secure password
• Login: Use registered phone number and password
• Password Requirements: {PASSWORD_MIN_LENGTH}+ characters with mixed case and numbers

Security Features:
• Account lockout after {MAX_LOGIN_ATTEMPTS} failed attempts
• Automatic session timeout: {SESSION_TIMEOUT_MINUTES} minutes
• Secure password hashing with bcrypt

Need more help? Contact system administrator.
{'=' * 50}
"""

    ADMIN_HELP_TEXT = """
Administrative Functions:
• User account management
• System access control
• Activity monitoring

Security: Admin access requires additional validation.
"""


class AuthenticationService:
    """Core authentication service with business logic"""
    
    def __init__(self, user_repository: UserRepository, audit_logger: AuditLogger):
        self.user_repo = user_repository
        self.audit_logger = audit_logger
        self.security = SecurityManager()
        self.validator = InputValidator()
        
        # Track login attempts for brute force protection
        self._login_attempts = {}
    
    def authenticate_user(self, phone_number: int, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate user with comprehensive security checks
        
        Args:
            phone_number: User's phone number
            password: Plain text password
            
        Returns:
            User data if authentication successful, None otherwise
        """
        attempt_key = f"login_attempt_{phone_number}"
        
        # Check for brute force attempts
        if self._is_account_locked(phone_number):
            print("Account temporarily locked due to multiple failed attempts. Please try again later.")
            self.audit_logger.log_security_event(
                "ACCOUNT_LOCKOUT", 
                f"Account locked for phone: {phone_number}",
                user_phone=phone_number
            )
            return None
        
        try:
            # Validate inputs
            if not self.validator.validate_phone_number(phone_number):
                print("Invalid phone number format.")
                return None
            
            if not self.validator.validate_password_strength(password):
                print("Password does not meet security requirements.")
                return None
            
            # Attempt authentication
            user_data = self.user_repo.validate_login(phone_number, password)
            
            if user_data:
                # Successful login
                self._reset_login_attempts(phone_number)
                self.audit_logger.log_security_event(
                    "LOGIN_SUCCESS", 
                    f"Successful login for user: {user_data.get('name', 'Unknown')}",
                    user_phone=phone_number
                )
                return user_data
            else:
                # Failed login
                self._record_failed_attempt(phone_number)
                remaining_attempts = LoginSystemConfig.MAX_LOGIN_ATTEMPTS - self._get_login_attempts(phone_number)
                
                self.audit_logger.log_security_event(
                    "LOGIN_FAILED", 
                    f"Failed login attempt for phone: {phone_number}. {remaining_attempts} attempts remaining",
                    user_phone=phone_number
                )
                
                if remaining_attempts > 0:
                    print(f"Invalid credentials. {remaining_attempts} attempts remaining.")
                else:
                    print("Account locked. Contact administrator.")
                
                return None
                
        except Exception as e:
            self.audit_logger.log_security_event(
                "AUTH_ERROR", 
                f"Authentication error for {phone_number}: {str(e)}",
                user_phone=phone_number
            )
            print("Authentication system error. Please try again.")
            return None
    
    def register_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Register new user with comprehensive validation
        
        Args:
            user_data: Dictionary containing user registration data
            
        Returns:
            Dictionary with registration result
        """
        try:
            # Extract and validate data
            phone_number = user_data.get('phone_number')
            name = user_data.get('name', '').strip()
            position = user_data.get('position', '').capitalize()
            password = user_data.get('password')
            validation_key = user_data.get('validation_key')
            
            # Comprehensive validation
            validation_errors = self._validate_registration_data(
                phone_number, name, position, password, validation_key
            )
            
            if validation_errors:
                return {
                    'success': False,
                    'errors': validation_errors
                }
            
            # Check if user already exists
            if self.user_repo.user_exists(phone_number):
                return {
                    'success': False,
                    'errors': ['Phone number already registered']
                }
            
            # Additional validation for admin registration
            if position == 'Admin':
                if not self._validate_admin_registration(validation_key):
                    return {
                        'success': False,
                        'errors': ['Invalid admin validation key']
                    }
            
            # Create user account
            result = self.user_repo.create_user(phone_number, name, position, password)
            
            if result.get('success'):
                self.audit_logger.log_security_event(
                    "REGISTRATION_SUCCESS", 
                    f"New user registered: {name} ({position})",
                    user_phone=phone_number
                )
                
                return {
                    'success': True,
                    'user_id': result.get('user_id'),
                    'user_data': result.get('user_data'),
                    'message': f"User {name} registered successfully as {position}"
                }
            else:
                return {
                    'success': False,
                    'errors': [result.get('error', 'Registration failed')]
                }
                
        except Exception as e:
            error_msg = f"Registration system error: {str(e)}"
            self.audit_logger.log_security_event(
                "REGISTRATION_ERROR", 
                error_msg,
                user_phone=user_data.get('phone_number')
            )
            return {
                'success': False,
                'errors': [error_msg]
            }
    
    def _validate_registration_data(self, phone_number: int, name: str, position: str, 
                                  password: str, validation_key: Optional[int] = None) -> list:
        """Validate all registration data"""
        errors = []
        
        # Phone number validation
        if not self.validator.validate_phone_number(phone_number):
            errors.append("Invalid phone number format")
        
        # Name validation
        if not name or len(name.strip()) < 2:
            errors.append("Name must be at least 2 characters long")
        elif len(name) > 100:
            errors.append("Name must be 100 characters or less")
        
        # Position validation
        valid_positions = ['User', 'Admin', 'Manager', 'Viewer']
        if position not in valid_positions:
            errors.append(f"Position must be one of: {', '.join(valid_positions)}")
        
        # Password validation
        if not self.validator.validate_password_strength(password):
            errors.append(
                f"Password must be {LoginSystemConfig.PASSWORD_MIN_LENGTH}+ characters "
                "with uppercase, lowercase, and numbers"
            )
        
        # Admin-specific validation
        if position == 'Admin' and not validation_key:
            errors.append("Admin registration requires validation key")
        
        return errors
    
    def _validate_admin_registration(self, validation_key: Optional[int]) -> bool:
        """Validate admin registration with enhanced security"""
        if not validation_key:
            return False
        
        # In production, this should use a secure key management system
        # For demo purposes, using a simple hash-based validation
        expected_key_hash = "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"  # sha256 of "admin"
        
        try:
            input_hash = hashlib.sha256(str(validation_key).encode()).hexdigest()
            return input_hash == expected_key_hash
        except:
            return False
    
    def _is_account_locked(self, phone_number: int) -> bool:
        """Check if account is temporarily locked due to failed attempts"""
        attempts = self._get_login_attempts(phone_number)
        return attempts >= LoginSystemConfig.MAX_LOGIN_ATTEMPTS
    
    def _get_login_attempts(self, phone_number: int) -> int:
        """Get number of login attempts for a phone number"""
        return self._login_attempts.get(phone_number, 0)
    
    def _record_failed_attempt(self, phone_number: int):
        """Record a failed login attempt"""
        current_attempts = self._get_login_attempts(phone_number)
        self._login_attempts[phone_number] = current_attempts + 1
    
    def _reset_login_attempts(self, phone_number: int):
        """Reset login attempts counter for successful login"""
        if phone_number in self._login_attempts:
            del self._login_attempts[phone_number]


class LoginViewController:
    """View controller for login interface with rich user experience"""
    
    def __init__(self, auth_service: AuthenticationService):
        self.auth_service = auth_service
        self.current_session = None
    
    def display_welcome_banner(self):
        """Display application welcome banner"""
        print("\n" + "=" * 60)
        print(f"{LoginSystemConfig.APP_NAME:^60}")
        print(f"{'Version ' + LoginSystemConfig.APP_VERSION:^60}")
        print("=" * 60)
        print("Secure Authentication Portal")
        print("=" * 60)
    
    def display_login_menu(self, is_admin: bool = False) -> str:
        """
        Display appropriate login menu based on context
        
        Args:
            is_admin: Whether to show admin-specific interface
            
        Returns:
            User's menu choice
        """
        if is_admin:
            print(LoginSystemConfig.ADMIN_LOGIN_PAGE)
        else:
            print(LoginSystemConfig.LOGIN_PAGE)
        
        return input("> ").strip().lower()
    
    def handle_login_choice(self, choice: str) -> bool:
        """
        Handle user's menu choice with proper routing
        
        Args:
            choice: User's menu selection
            
        Returns:
            True if should continue, False if should exit
        """
        if choice == "0":
            self._handle_exit()
            return False
        
        elif choice == "1":
            return self._handle_login()
        
        elif choice == "2":
            return self._handle_registration()
        
        elif choice == "h":
            self._display_help()
            return True
        
        else:
            print("Invalid choice. Please select a valid option.")
            return True
    
    def _handle_exit(self):
        """Handle application exit with cleanup"""
        print("\nThank you for using the Kanban System. Goodbye!")
        if self.current_session:
            self.current_session.end_session("User logged out")
    
    def _handle_login(self) -> bool:
        """Handle user login process"""
        print("\n" + "-" * 40)
        print("User Login")
        print("-" * 40)
        
        try:
            # Get credentials
            phone_input = input("Phone number: ").strip()
            password = input("Password: ").strip()
            
            if not phone_input or not password:
                print("Phone number and password are required.")
                return True
            
            # Convert and validate phone number
            try:
                phone_number = int(phone_input)
            except ValueError:
                print("Please enter a valid phone number (digits only).")
                return True
            
            # Attempt authentication
            user_data = self.auth_service.authenticate_user(phone_number, password)
            
            if user_data:
                self._handle_successful_login(user_data)
                return False  # Exit login menu on success
            else:
                return True  # Stay in menu on failure
                
        except KeyboardInterrupt:
            print("\n\nLogin cancelled.")
            return True
        except Exception as e:
            print(f"Login error: {e}")
            return True
    
    def _handle_successful_login(self, user_data: Dict[str, Any]):
        """Handle successful login and route to appropriate interface"""
        print(f"\n✓ Login successful! Welcome, {user_data.get('name', 'User')}!")
        
        # Create user session
        self.current_session = UserSession(
            user_id=user_data.get('user_id'),
            user_phone=user_data.get('phone_no'),
            user_name=user_data.get('name'),
            position=user_data.get('position')
        )
        
        # Route based on user role
        position = user_data.get('position', 'User').lower()
        
        if position == 'admin':
            self._route_to_admin_interface()
        else:
            self._route_to_user_interface()
    
    def _route_to_admin_interface(self):
        """Route admin users to administrative interface"""
        print("Redirecting to administrative console...")
        # Import here to avoid circular dependencies
        try:
            from admin_console import AdminConsole
            admin_console = AdminConsole(self.current_session)
            admin_console.start()
        except ImportError:
            print("Administrative interface not available. Using standard interface.")
            self._route_to_user_interface()
    
    def _route_to_user_interface(self):
        """Route regular users to main application interface"""
        print("Loading Kanban system...")
        try:
            from kanban_ui import KanbanUserInterface
            app_interface = KanbanUserInterface(self.current_session)
            app_interface.start()
        except ImportError:
            print("Application interface not available.")
            print("Please contact system administrator.")
    
    def _handle_registration(self) -> bool:
        """Handle new user registration process"""
        print("\n" + "=" * 40)
        print("New User Registration")
        print("=" * 40)
        
        try:
            registration_data = self._collect_registration_data()
            if not registration_data:
                return True  # Cancelled registration
            
            result = self.auth_service.register_user(registration_data)
            
            if result['success']:
                print(f"\n✓ {result['message']}")
                print("\nRegistration details:")
                self._display_user_summary(result['user_data'])
                
                # Offer immediate login
                if self._prompt_immediate_login():
                    return self._handle_login()
            else:
                print("\n✗ Registration failed:")
                for error in result.get('errors', []):
                    print(f"  • {error}")
            
            return True
            
        except KeyboardInterrupt:
            print("\n\nRegistration cancelled.")
            return True
        except Exception as e:
            print(f"\n✗ Registration error: {e}")
            return True
    
    def _collect_registration_data(self) -> Optional[Dict[str, Any]]:
        """Collect and validate registration data from user"""
        data = {}
        
        # Phone number
        while True:
            phone_input = input("Phone number: ").strip()
            if not phone_input:
                print("Registration cancelled.")
                return None
            
            try:
                data['phone_number'] = int(phone_input)
                break
            except ValueError:
                print("Please enter a valid phone number (digits only).")
        
        # Name
        data['name'] = input("Full name: ").strip()
        if not data['name']:
            print("Name is required.")
            return None
        
        # Position
        while True:
            position = input("Position (User/Admin/Manager/Viewer): ").strip().capitalize()
            valid_positions = ['User', 'Admin', 'Manager', 'Viewer']
            
            if position in valid_positions:
                data['position'] = position
                break
            else:
                print(f"Position must be one of: {', '.join(valid_positions)}")
        
        # Admin validation key
        if data['position'] == 'Admin':
            while True:
                key_input = input("Admin validation key: ").strip()
                if not key_input:
                    print("Admin registration requires validation key.")
                    continue
                
                try:
                    data['validation_key'] = int(key_input)
                    break
                except ValueError:
                    print("Please enter a valid numeric key.")
        
        # Password with confirmation
        while True:
            password = input("Password: ").strip()
            confirm_password = input("Confirm password: ").strip()
            
            if not password or not confirm_password:
                print("Password and confirmation are required.")
                continue
            
            if password != confirm_password:
                print("Passwords do not match. Please try again.")
                continue
            
            data['password'] = password
            break
        
        return data
    
    def _display_user_summary(self, user_data: Dict[str, Any]):
        """Display formatted user registration summary"""
        print("\n" + "-" * 30)
        print("Registration Summary")
        print("-" * 30)
        print(f"Name: {user_data.get('name', 'N/A')}")
        print(f"Phone: {user_data.get('phone_no', 'N/A')}")
        print(f"Position: {user_data.get('position', 'N/A')}")
        print(f"Status: {'Active' if user_data.get('is_active') else 'Inactive'}")
        print(f"Registered: {user_data.get('created_at', 'N/A')}")
        print("-" * 30)
    
    def _prompt_immediate_login(self) -> bool:
        """Prompt user for immediate login after registration"""
        response = input("\nWould you like to log in now? (y/N): ").strip().lower()
        return response in ['y', 'yes']
    
    def _display_help(self):
        """Display help information"""
        print(LoginSystemConfig.HELP_TEXT)


class LoginSystem:
    """Main login system coordinator"""
    
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or LoginSystemConfig.DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize core components
        self._initialize_components()
        
        # Initialize view controller
        self.view_controller = LoginViewController(self.auth_service)
    
    def _initialize_components(self):
        """Initialize all system components with dependency injection"""
        try:
            # Database and repository
            db_manager = DatabaseConnectionManager()
            self.user_repo = UserRepository(db_manager)
            
            # Audit logging
            log_file = self.data_dir / "audit.log"
            self.audit_logger = AuditLogger(log_file)
            
            # Authentication service
            self.auth_service = AuthenticationService(self.user_repo, self.audit_logger)
            
            # Initialize database if needed
            self._initialize_database()
            
        except Exception as e:
            print(f"System initialization failed: {e}")
            raise
    
    def _initialize_database(self):
        """Initialize database schema"""
