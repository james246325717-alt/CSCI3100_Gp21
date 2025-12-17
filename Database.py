"""
Enhanced Database Module for Kanban System
Refactored with improved security, error handling, and architecture
"""

import sqlite3
from pathlib import Path
import bcrypt
from typing import Optional, Dict, Any, List, Union
from contextlib import contextmanager
import logging
from datetime import datetime
import hashlib
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Centralized configuration for database settings"""
    
    # Database settings
    DB_PATH = Path("kanban.db")
    DB_BACKUP_DIR = Path("backups")
    SALT_ROUNDS = 12  # bcrypt salt rounds for password hashing
    
    # Table schemas
    USER_TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS USER (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            PhoneNo INTEGER NOT NULL UNIQUE,
            Name VARCHAR(100) NOT NULL,
            IsActive INTEGER NOT NULL DEFAULT 1,
            Position VARCHAR(50) NOT NULL,
            PasswordHash TEXT NOT NULL,
            CreatedAt TEXT DEFAULT CURRENT_TIMESTAMP,
            LastModified TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    
    # Indexes for performance
    USER_INDEXES = [
        "CREATE INDEX IF NOT EXISTS idx_user_phone ON USER(PhoneNo)",
        "CREATE INDEX IF NOT EXISTS idx_user_active ON USER(IsActive)",
        "CREATE INDEX IF NOT EXISTS idx_user_position ON USER(Position)"
    ]


class DatabaseConnectionManager:
    """Manage database connections with context managers and connection pooling"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseConnectionManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize connection manager"""
        self.db_path = DatabaseConfig.DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_backup_dir()
    
    def _ensure_backup_dir(self):
        """Ensure backup directory exists"""
        DatabaseConfig.DB_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    @contextmanager
    def get_connection(self) -> sqlite3.Connection:
        """
        Context manager for database connections with automatic cleanup
        
        Yields:
            sqlite3.Connection: Database connection
        """
        connection = None
        try:
            connection = sqlite3.connect(
                str(self.db_path),
                timeout=30,  # 30 second timeout
                check_same_thread=False  # Allow multithreaded access
            )
            connection.execute("PRAGMA foreign_keys = ON")
            connection.row_factory = sqlite3.Row  # Enable dictionary-like access
            yield connection
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if connection:
                connection.close()
    
    def backup_database(self) -> bool:
        """Create a timestamped backup of the database"""
        try:
            if not self.db_path.exists():
                logger.warning("Database file does not exist, skipping backup")
                return False
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = DatabaseConfig.DB_BACKUP_DIR / f"kanban_backup_{timestamp}.db"
            
            with self.get_connection() as conn:
                with sqlite3.connect(str(backup_path)) as backup_conn:
                    conn.backup(backup_conn)
            
            logger.info(f"Database backup created: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False


class PasswordManager:
    """Enhanced password management with security best practices"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash password with bcrypt and additional security measures
        
        Args:
            password: Plain text password
            
        Returns:
            str: Hashed password
            
        Raises:
            ValueError: If password is empty or too short
        """
        if not password or len(password.strip()) == 0:
            raise ValueError("Password cannot be empty")
        
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        
        # Additional password strength checks
        if not any(char.isdigit() for char in password):
            raise ValueError("Password must contain at least one number")
        
        if not any(char.isupper() for char in password):
            raise ValueError("Password must contain at least one uppercase letter")
        
        try:
            password_bytes = password.encode('utf-8')
            salt = bcrypt.gensalt(rounds=DatabaseConfig.SALT_ROUNDS)
            hashed = bcrypt.hashpw(password_bytes, salt)
            return hashed.decode('utf-8')
        except Exception as e:
            logger.error(f"Password hashing error: {e}")
            raise ValueError("Error processing password") from e
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """
        Verify password against hash with timing attack protection
        
        Args:
            password: Plain text password to verify
            hashed_password: Previously hashed password
            
        Returns:
            bool: True if password matches hash
        """
        if not password or not hashed_password:
            return False
        
        try:
            password_bytes = password.encode('utf-8')
            hashed_bytes = hashed_password.encode('utf-8')
            return bcrypt.checkpw(password_bytes, hashed_bytes)
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    @staticmethod
    def is_password_compromised(password: str) -> bool:
        """
        Basic check for common compromised passwords
        In production, this should use a proper compromised password API
        
        Args:
            password: Password to check
            
        Returns:
            bool: True if password is in common compromised list
        """
        # Simple check for very common passwords (expand this list in production)
        common_passwords = {
            'password', '123456', '12345678', '1234', 'qwerty', 'letmein',
            'admin', 'welcome', 'monkey', 'password1', '1234567'
        }
        
        return password.lower() in common_passwords


class UserModel:
    """Data model for user operations with validation"""
    
    def __init__(self, 
                 phone_no: int, 
                 name: str, 
                 position: str, 
                 password_hash: str,
                 user_id: Optional[int] = None,
                 is_active: bool = True,
                 created_at: Optional[str] = None,
                 last_modified: Optional[str] = None):
        
        self._validate_constructor_args(phone_no, name, position, password_hash)
        
        self.user_id = user_id
        self.phone_no = phone_no
        self.name = name.strip()
        self.position = position
        self.password_hash = password_hash
        self.is_active = is_active
        self.created_at = created_at or datetime.now().isoformat()
        self.last_modified = last_modified or datetime.now().isoformat()
    
    def _validate_constructor_args(self, phone_no: int, name: str, 
                                 position: str, password_hash: str):
        """Validate constructor arguments"""
        if not isinstance(phone_no, int) or phone_no <= 0:
            raise ValueError("Phone number must be a positive integer")
        
        if not name or not name.strip():
            raise ValueError("Name cannot be empty")
        
        if len(name.strip()) > 100:
            raise ValueError("Name must be 100 characters or less")
        
        valid_positions = {'Admin', 'User', 'Manager', 'Viewer'}
        if position not in valid_positions:
            raise ValueError(f"Position must be one of: {', '.join(valid_positions)}")
        
        if not password_hash:
            raise ValueError("Password hash cannot be empty")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary for serialization"""
        return {
            'user_id': self.user_id,
            'phone_no': self.phone_no,
            'name': self.name,
            'position': self.position,
            'is_active': self.is_active,
            'created_at': self.created_at,
            'last_modified': self.last_modified
            # Note: password_hash is intentionally excluded for security
        }
    
    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> 'UserModel':
        """Create UserModel from database row"""
        return cls(
            user_id=row['ID'],
            phone_no=row['PhoneNo'],
            name=row['Name'],
            position=row['Position'],
            password_hash=row['PasswordHash'],
            is_active=bool(row['IsActive']),
            created_at=row['CreatedAt'],
            last_modified=row['LastModified']
        )


class UserRepository:
    """Repository pattern for user data operations"""
    
    def __init__(self, connection_manager: DatabaseConnectionManager):
        self.connection_manager = connection_manager
        self.password_manager = PasswordManager()
    
    def initialize_database(self) -> bool:
        """Initialize database with tables and indexes"""
        try:
            with self.connection_manager.get_connection() as conn:
                # Create user table
                conn.execute(DatabaseConfig.USER_TABLE_SCHEMA)
                
                # Create indexes
                for index_sql in DatabaseConfig.USER_INDEXES:
                    conn.execute(index_sql)
                
                conn.commit()
                logger.info("Database initialized successfully")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Database initialization failed: {e}")
            return False
    
    def create_user(self, phone_no: int, name: str, position: str, 
                   password: str) -> Dict[str, Any]:
        """
        Create a new user with comprehensive validation
        
        Args:
            phone_no: User's phone number (unique identifier)
            name: User's full name
            position: User's position/role
            password: Plain text password
            
        Returns:
            Dict with user data and operation status
            
        Raises:
            ValueError: For validation errors
            sqlite3.IntegrityError: For duplicate phone numbers
        """
        # Pre-validation
        self._validate_user_inputs(phone_no, name, position, password)
        
        # Check if user already exists
        if self.get_user_by_phone(phone_no):
            raise ValueError(f"User with phone number {phone_no} already exists")
        
        # Hash password
        password_hash = self.password_manager.hash_password(password)
        
        # Set default activation based on position
        is_active = 1 if position == "Admin" else 0
        
        try:
            with self.connection_manager.get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO USER (PhoneNo, Name, Position, PasswordHash, IsActive)
                    VALUES (?, ?, ?, ?, ?)
                """, (phone_no, name, position, password_hash, is_active))
                
                user_id = cursor.lastrowid
                conn.commit()
                
                # Return created user data (excluding password hash)
                user = self.get_user_by_phone(phone_no)
                logger.info(f"User created successfully: {phone_no}")
                return {
                    'success': True,
                    'user_id': user_id,
                    'user_data': user
                }
                
        except sqlite3.IntegrityError as e:
            logger.error(f"User creation integrity error: {e}")
            raise ValueError(f"Phone number {phone_no} already exists") from e
        except sqlite3.Error as e:
            logger.error(f"User creation database error: {e}")
            raise ValueError(f"Database error: {e}") from e
    
    def get_user_by_phone(self, phone_no: int) -> Optional[Dict[str, Any]]:
        """Get user by phone number, excluding sensitive data"""
        try:
            with self.connection_manager.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM USER WHERE PhoneNo = ?", 
                    (phone_no,)
                )
                row = cursor.fetchone()
                
                if row:
                    user_model = UserModel.from_db_row(row)
                    return user_model.to_dict()
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Error retrieving user {phone_no}: {e}")
            return None
    
    def get_user_with_credentials(self, phone_no: int) -> Optional[Dict[str, Any]]:
        """Get user including password hash for authentication (internal use)"""
        try:
            with self.connection_manager.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM USER WHERE PhoneNo = ?", 
                    (phone_no,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
                
        except sqlite3.Error as e:
            logger.error(f"Error retrieving user credentials {phone_no}: {e}")
            return None
    
    def validate_login(self, phone_no: int, password: str) -> Optional[Dict[str, Any]]:
        """
        Validate user login credentials
        
        Args:
            phone_no: User's phone number
            password: Plain text password
            
        Returns:
            User data if valid, None otherwise
        """
        try:
            user_data = self.get_user_with_credentials(phone_no)
            
            if not user_data:
                logger.warning(f"Login attempt for non-existent user: {phone_no}")
                return None
            
            if not user_data.get('IsActive', 0):
                logger.warning(f"Login attempt for inactive user: {phone_no}")
                return None
            
            if not self.password_manager.verify_password(password, user_data['PasswordHash']):
                logger.warning(f"Invalid password for user: {phone_no}")
                return None
            
            # Return user data without password hash
            user_model = UserModel.from_db_row(user_data)
            logger.info(f"Successful login for user: {phone_no}")
            return user_model.to_dict()
            
        except Exception as e:
            logger.error(f"Login validation error for {phone_no}: {e}")
            return None
    
    def change_activation_status(self, phone_no: int, is_active: bool) -> bool:
        """Change user activation status"""
        try:
            with self.connection_manager.get_connection() as conn:
                conn.execute(
                    "UPDATE USER SET IsActive = ?, LastModified = ? WHERE PhoneNo = ?",
                    (int(is_active), datetime.now().isoformat(), phone_no)
                )
                conn.commit()
                
                logger.info(f"User {phone_no} activation set to {is_active}")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Error changing activation status for {phone_no}: {e}")
            return False
    
    def get_all_users(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """Get all users with optional active-only filter"""
        try:
            with self.connection_manager.get_connection() as conn:
                if active_only:
                    cursor = conn.execute("SELECT * FROM USER WHERE IsActive = 1")
                else:
                    cursor = conn.execute("SELECT * FROM USER")
                
                users = []
                for row in cursor:
                    user_model = UserModel.from_db_row(row)
                    users.append(user_model.to_dict())
                
                return users
                
        except sqlite3.Error as e:
            logger.error(f"Error retrieving users: {e}")
            return []
    
    def user_exists(self, phone_no: int) -> bool:
        """Check if user exists"""
        return self.get_user_by_phone(phone_no) is not None
    
    def _validate_user_inputs(self, phone_no: int, name: str, 
                           position: str, password: str):
        """Validate user input parameters"""
        if not isinstance(phone_no, int) or phone_no <= 0:
            raise ValueError("Phone number must be a positive integer")
        
        if not name or not name.strip():
            raise ValueError("Name cannot be empty")
        
        if len(name.strip()) > 100:
            raise ValueError("Name must be 100 characters or less")
        
        valid_positions = {'Admin', 'User', 'Manager', 'Viewer'}
        if position not in valid_positions:
            raise ValueError(f"Position must be one of: {', '.join(valid_positions)}")
        
        if self.password_manager.is_password_compromised(password):
            raise ValueError("Password is too common or compromised")


# Legacy API functions for backward compatibility
_db_manager = DatabaseConnectionManager()
_user_repo = UserRepository(_db_manager)

def InitDB() -> bool:
    """Initialize database (legacy function)"""
    return _user_repo.initialize_database()

def CreateUser(PhoneNo: int, Name: str, Position: str, Password: str):
    """Create user (legacy function)"""
    return _user_repo.create_user(PhoneNo, Name, Position, Password)

def GetUserByPhone(PhoneNo: int) -> Optional[Dict[str, Any]]:
    """Get user by phone (legacy function)"""
    return _user_repo.get_user_by_phone(PhoneNo)

def ValidateLogin(PhoneNo: int, Password: str) -> Optional[Dict[str, Any]]:
    """Validate login (legacy function)"""
    return _user_repo.validate_login(PhoneNo, Password)

def ChangeActivationStatus(PhoneNo: int, IsActive: int) -> bool:
    """Change activation status (legacy function)"""
    return _user_repo.change_activation_status(PhoneNo, bool(IsActive))

def HashPassword(password: str) -> str:
    """Hash password (legacy function)"""
    return PasswordManager.hash_password(password)

def VerifyPassword(password: str, password_hash: str) -> bool:
    """Verify password (legacy function)"""
    return PasswordManager.verify_password(password, password_hash)


# Example usage and testing
if __name__ == "__main__":
    # Initialize database
    if InitDB():
        print("Database initialized successfully")
    
    # Example: Create an admin user
    try:
        result = CreateUser(
            phone_no=1234567890,
            name="System Administrator",
            position="Admin",
            password="SecurePassword123!"
        )
        print("User created:", result)
    except ValueError as e:
        print("Error creating user:", e)
    
    # Example: Validate login
    user = ValidateLogin(1234567890, "SecurePassword123!")
    if user:
        print("Login successful:", user)
    else:
        print("Login failed")
    Connection.execute("UPDATE USER SET IsActive = ? WHERE PhoneNo = ?", (IsActive, PhoneNo))
    Connection.commit()
