import sqlite3
import hashlib
from typing import Optional, Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class UserRepository:
    """SQLite-backed user repository for persistent user management"""
    
    def __init__(self, db_path: str = "kanban.db"):
        """
        Initialize UserRepository with SQLite database connection
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize database schema and tables"""
        try:
            with self._get_connection() as conn:
                # Create USER table with all required fields
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS USER (
                        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        PhoneNo INTEGER UNIQUE NOT NULL,
                        Name TEXT NOT NULL,
                        Position TEXT NOT NULL DEFAULT 'User',
                        PasswordHash TEXT NOT NULL,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_phone ON USER(PhoneNo)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_active ON USER(is_active)")
                
                conn.commit()
                logger.info("User database initialized successfully")
                
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def _get_connection(self) -> sqlite3.Connection:
        """
        Get database connection with proper configuration
        
        Returns:
            sqlite3.Connection: Configured database connection
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dictionary-like access
        return conn
    
    def _hash_password(self, password: str) -> str:
        """
        Hash password for secure storage
        
        Args:
            password: Plain text password
            
        Returns:
            str: SHA-256 hashed password
        """
        return hashlib.sha256(password.encode()).hexdigest()
    
    def validate_login(self, phone_number: int, password: str) -> Optional[Dict[str, Any]]:
        """
        Validate user credentials against database
        
        Args:
            phone_number: User's phone number
            password: Plain text password to validate
            
        Returns:
            Optional[Dict[str, Any]]: User data if credentials valid, None otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT user_id, PhoneNo, Name, Position, PasswordHash, is_active, created_at
                    FROM USER 
                    WHERE PhoneNo = ? AND is_active = 1
                """, (phone_number,))
                
                row = cursor.fetchone()
                
                if row:
                    # Compare hashed passwords
                    stored_hash = row['PasswordHash']
                    provided_hash = self._hash_password(password)
                    
                    if stored_hash == provided_hash:
                        return {
                            'user_id': row['user_id'],
                            'phone_number': row['PhoneNo'],
                            'name': row['Name'],
                            'position': row['Position'],
                            'is_active': bool(row['is_active']),
                            'created_at': row['created_at']
                        }
                
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Database error in validate_login: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in validate_login: {e}")
            return None
    
    def user_exists(self, phone_number: int) -> bool:
        """
        Check if a user with given phone number exists
        
        Args:
            phone_number: Phone number to check
            
        Returns:
            bool: True if user exists, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM USER WHERE PhoneNo = ?", 
                    (phone_number,)
                )
                return cursor.fetchone() is not None
                
        except sqlite3.Error as e:
            logger.error(f"Database error in user_exists: {e}")
            return False
    
    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new user account in database
        
        Args:
            user_data: Dictionary containing user registration data
            
        Returns:
            Dict[str, Any]: Result dictionary with success status and user info
        """
        try:
            # Hash password before storage
            hashed_password = self._hash_password(user_data['password'])
            
            with self._get_connection() as conn:
                # Insert new user
                cursor = conn.execute("""
                    INSERT INTO USER (PhoneNo, Name, Position, PasswordHash)
                    VALUES (?, ?, ?, ?)
                """, (
                    user_data['phone_number'],
                    user_data['name'],
                    user_data.get('position', 'User'),
                    hashed_password
                ))
                
                user_id = cursor.lastrowid
                
                # Fetch the created user to return complete data
                cursor = conn.execute("""
                    SELECT user_id, PhoneNo, Name, Position, is_active, created_at
                    FROM USER WHERE user_id = ?
                """, (user_id,))
                
                row = cursor.fetchone()
                conn.commit()
                
                if row:
                    created_user = {
                        'user_id': row['user_id'],
                        'phone_number': row['PhoneNo'],
                        'name': row['Name'],
                        'position': row['Position'],
                        'is_active': bool(row['is_active']),
                        'created_at': row['created_at']
                    }
                    
                    logger.info(f"User created successfully: {user_data['name']} (ID: {user_id})")
                    
                    return {
                        'success': True,
                        'user_id': user_id,
                        'user_data': created_user
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Failed to retrieve created user'
                    }
                
        except sqlite3.IntegrityError as e:
            error_msg = f"User with phone {user_data['phone_number']} already exists"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
        except sqlite3.Error as e:
            error_msg = f"Database error creating user: {e}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
        except Exception as e:
            error_msg = f"Unexpected error creating user: {e}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def get_user_by_phone(self, phone_number: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve user information by phone number
        
        Args:
            phone_number: User's phone number
            
        Returns:
            Optional[Dict[str, Any]]: User data if found, None otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT user_id, PhoneNo, Name, Position, is_active, created_at
                    FROM USER WHERE PhoneNo = ? AND is_active = 1
                """, (phone_number,))
                
                row = cursor.fetchone()
                
                if row:
                    return {
                        'user_id': row['user_id'],
                        'phone_number': row['PhoneNo'],
                        'name': row['Name'],
                        'position': row['Position'],
                        'is_active': bool(row['is_active']),
                        'created_at': row['created_at']
                    }
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Database error in get_user_by_phone: {e}")
            return None
    
    def update_user(self, phone_number: int, updates: Dict[str, Any]) -> bool:
        """
        Update user information
        
        Args:
            phone_number: User's phone number
            updates: Dictionary of fields to update
            
        Returns:
            bool: True if update successful, False otherwise
        """
        try:
            if not updates:
                return True
            
            with self._get_connection() as conn:
                # Build SET clause
                set_fields = []
                values = []
                
                for field, value in updates.items():
                    if field == 'password':
                        # Hash password if updating
                        set_fields.append("PasswordHash = ?")
                        values.append(self._hash_password(value))
                    elif field in ['name', 'position', 'is_active']:
                        set_fields.append(f"{field} = ?")
                        values.append(value)
                
                if not set_fields:
                    return True
                
                # Add phone number for WHERE clause
                values.append(phone_number)
                
                # Add last_modified timestamp
                set_fields.append("last_modified = CURRENT_TIMESTAMP")
                
                query = f"""
                    UPDATE USER 
                    SET {', '.join(set_fields)}
                    WHERE PhoneNo = ?
                """
                
                cursor = conn.execute(query, values)
                conn.commit()
                
                return cursor.rowcount > 0
                
        except sqlite3.Error as e:
            logger.error(f"Database error updating user {phone_number}: {e}")
            return False
    
    def deactivate_user(self, phone_number: int) -> bool:
        """
        Deactivate a user account (soft delete)
        
        Args:
            phone_number: User's phone number
            
        Returns:
            bool: True if deactivation successful, False otherwise
        """
        return self.update_user(phone_number, {'is_active': 0})
    
    def get_all_users(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get all users with optional filtering
        
        Args:
            active_only: Whether to return only active users
            
        Returns:
            List[Dict[str, Any]]: List of user dictionaries
        """
        try:
            with self._get_connection() as conn:
                query = """
                    SELECT user_id, PhoneNo, Name, Position, is_active, created_at, last_modified
                    FROM USER
                """
                
                if active_only:
                    query += " WHERE is_active = 1"
                
                query += " ORDER BY created_at DESC"
                
                cursor = conn.execute(query)
                
                users = []
                for row in cursor:
                    users.append({
                        'user_id': row['user_id'],
                        'phone_number': row['PhoneNo'],
                        'name': row['Name'],
                        'position': row['Position'],
                        'is_active': bool(row['is_active']),
                        'created_at': row['created_at'],
                        'last_modified': row['last_modified']
                    })
                
                return users
                
        except sqlite3.Error as e:
            logger.error(f"Database error getting all users: {e}")
            return []
    
    def search_users(self, search_term: str) -> List[Dict[str, Any]]:
        """
        Search users by name or phone number
        
        Args:
            search_term: Search term for name or phone number
            
        Returns:
            List[Dict[str, Any]]: List of matching users
        """
        try:
            with self._get_connection() as conn:
                search_pattern = f"%{search_term}%"
                
                cursor = conn.execute("""
                    SELECT user_id, PhoneNo, Name, Position, is_active, created_at
                    FROM USER 
                    WHERE (Name LIKE ? OR PhoneNo LIKE ?) AND is_active = 1
                    ORDER BY Name
                """, (search_pattern, search_pattern))
                
                users = []
                for row in cursor:
                    users.append({
                        'user_id': row['user_id'],
                        'phone_number': row['PhoneNo'],
                        'name': row['Name'],
                        'position': row['Position'],
                        'is_active': bool(row['is_active']),
                        'created_at': row['created_at']
                    })
                
                return users
                
        except sqlite3.Error as e:
            logger.error(f"Database error searching users: {e}")
            return []
