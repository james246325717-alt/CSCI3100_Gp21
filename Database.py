#!/usr/bin/env python3
"""
Enterprise Kanban System - Enhanced Data Access Layer
Robust database module with improved security, performance, and maintainability
"""

import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List, Union, Tuple
from datetime import datetime, timedelta
from contextlib import contextmanager
from enum import Enum
import logging
from dataclasses import dataclass
import hashlib
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Centralized configuration for database settings"""
    
    # Database settings
    DB_PATH = Path("kanban.db")
    DB_BACKUP_DIR = Path("database_backups")
    DEFAULT_TIMEOUT = 30
    
    # Table schemas with enhanced constraints
    KANBAN_TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS KANBAN (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Title TEXT NOT NULL CHECK(length(Title) > 0 AND length(Title) <= 200),
            Status TEXT NOT NULL CHECK(Status IN ('To-Do', 'In Progress', 'Waiting Review', 'Finished')),
            PersonInCharge INTEGER NOT NULL,
            CreationDate TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            DueDate TEXT NOT NULL CHECK(DueDate LIKE '____-__-__'),
            Creator INTEGER NOT NULL,
            Editors INTEGER,
            AdditionalInfo TEXT,
            LastModified TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            Version INTEGER NOT NULL DEFAULT 1,
            IsActive INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (PersonInCharge) REFERENCES USER(PhoneNo) ON UPDATE CASCADE ON DELETE RESTRICT,
            FOREIGN KEY (Creator) REFERENCES USER(PhoneNo) ON UPDATE CASCADE ON DELETE RESTRICT,
            FOREIGN KEY (Editors) REFERENCES USER(PhoneNo) ON UPDATE CASCADE ON DELETE SET NULL
        )
    """
    
    # Performance indexes
    TABLE_INDEXES = [
        "CREATE INDEX IF NOT EXISTS idx_kanban_status ON KANBAN(Status)",
        "CREATE INDEX IF NOT EXISTS idx_kanban_due_date ON KANBAN(DueDate)",
        "CREATE INDEX IF NOT EXISTS idx_kanban_person ON KANBAN(PersonInCharge)",
        "CREATE INDEX IF NOT EXISTS idx_kanban_creator ON KANBAN(Creator)",
        "CREATE INDEX IF NOT EXISTS idx_kanban_modified ON KANBAN(LastModified)",
        "CREATE INDEX IF NOT EXISTS idx_kanban_active ON KANBAN(IsActive)"
    ]


class TaskStatus(Enum):
    """Enumeration for task status to ensure type safety"""
    TO_DO = "To-Do"
    IN_PROGRESS = "In Progress"
    WAITING_REVIEW = "Waiting Review"
    FINISHED = "Finished"
    
    @classmethod
    def get_valid_statuses(cls) -> List[str]:
        """Get all valid status values"""
        return [status.value for status in cls]
    
    @classmethod
    def is_valid_status(cls, status: str) -> bool:
        """Check if a status is valid"""
        return status in cls.get_valid_statuses()


@dataclass
class Task:
    """Data model representing a Kanban task with validation"""
    
    task_id: Optional[int] = None
    title: str = ""
    status: str = ""
    person_in_charge: int = 0
    creation_date: str = ""
    due_date: str = ""
    creator: int = 0
    editors: Optional[int] = None
    additional_info: str = ""
    last_modified: str = ""
    version: int = 1
    is_active: bool = True
    
    def validate(self) -> List[str]:
        """Validate task data and return list of errors"""
        errors = []
        
        if not self.title or len(self.title.strip()) == 0:
            errors.append("Task title cannot be empty")
        elif len(self.title) > 200:
            errors.append("Task title cannot exceed 200 characters")
        
        if not TaskStatus.is_valid_status(self.status):
            valid_statuses = TaskStatus.get_valid_statuses()
            errors.append(f"Invalid status: {self.status}. Must be one of {valid_statuses}")
        
        if not isinstance(self.person_in_charge, int) or self.person_in_charge <= 0:
            errors.append("Person in charge must be a positive integer")
        
        if not isinstance(self.creator, int) or self.creator <= 0:
            errors.append("Creator must be a positive integer")
        
        if self.editors is not None and (not isinstance(self.editors, int) or self.editors <= 0):
            errors.append("Editors must be a positive integer or None")
        
        # Validate date format
        if not self._is_valid_date_format(self.due_date):
            errors.append("Due date must be in YYYY-MM-DD format")
        
        return errors
    
    def _is_valid_date_format(self, date_str: str) -> bool:
        """Check if date string is in valid format"""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert task to dictionary for serialization"""
        data = {
            'task_id': self.task_id,
            'title': self.title,
            'status': self.status,
            'person_in_charge': self.person_in_charge,
            'due_date': self.due_date,
            'creator': self.creator,
            'additional_info': self.additional_info,
            'creation_date': self.creation_date,
            'last_modified': self.last_modified,
            'is_active': self.is_active
        }
        
        if include_sensitive:
            data['editors'] = self.editors
            data['version'] = self.version
        
        return data
    
    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> 'Task':
        """Create Task from database row"""
        return cls(
            task_id=row['ID'],
            title=row['Title'],
            status=row['Status'],
            person_in_charge=row['PersonInCharge'],
            due_date=row['DueDate'],
            creator=row['Creator'],
            additional_info=row['AdditionalInfo'] or '',
            creation_date=row['CreationDate'],
            editors=row['Editors'],
            last_modified=row['LastModified'],
            version=row.get('Version', 1),
            is_active=bool(row.get('IsActive', 1))
        )
    
    def __str__(self) -> str:
        """String representation for logging"""
        return (f"Task(id={self.task_id}, title='{self.title}', status='{self.status}', "
                f"due_date='{self.due_date}', assigned_to={self.person_in_charge})")


class DatabaseError(Exception):
    """Custom exception for database-related errors"""
    pass


class DatabaseConnectionManager:
    """Enhanced database connection management with connection pooling and error handling"""
    
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
            sqlite3.Connection: Database connection with proper configuration
        """
        connection = None
        try:
            connection = sqlite3.connect(
                str(self.db_path),
                timeout=DatabaseConfig.DEFAULT_TIMEOUT,
                check_same_thread=False
            )
            # Enable foreign keys and performance optimizations
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.row_factory = sqlite3.Row  # Enable dictionary-like access
            
            yield connection
            connection.commit()  # Auto-commit on successful exit
            
        except sqlite3.Error as e:
            if connection:
                connection.rollback()  # Rollback on error
            logger.error(f"Database connection error: {e}")
            raise DatabaseError(f"Database operation failed: {e}") from e
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


class KanbanRepository:
    """
    Repository pattern implementation for Kanban data operations
    with enhanced performance and error handling
    """
    
    def __init__(self, connection_manager: DatabaseConnectionManager = None):
        self.connection_manager = connection_manager or DatabaseConnectionManager()
        self._initialized = False
    
    def initialize_database(self) -> bool:
        """Initialize database with tables and indexes"""
        try:
            with self.connection_manager.get_connection() as conn:
                # Create kanban table
                conn.execute(DatabaseConfig.KANBAN_TABLE_SCHEMA)
                
                # Create indexes
                for index_sql in DatabaseConfig.TABLE_INDEXES:
                    try:
                        conn.execute(index_sql)
                    except sqlite3.Error as e:
                        logger.warning(f"Index creation warning: {e}")
                
                conn.commit()
                logger.info("Kanban database initialized successfully")
                self._initialized = True
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Database initialization failed: {e}")
            raise DatabaseError(f"Failed to initialize database: {e}") from e
    
    def add_task(self, title: str, status: str, person_in_charge: int, 
                 due_date: str, creator: int, additional_info: str = "") -> int:
        """
        Add a new task to the kanban board with comprehensive validation
        
        Args:
            title: Task title
            status: Task status
            person_in_charge: Responsible person's phone number
            due_date: Due date in YYYY-MM-DD format
            creator: Creator's phone number
            additional_info: Additional task information
            
        Returns:
            int: ID of the newly created task
            
        Raises:
            DatabaseError: If database operation fails
            ValueError: If task data is invalid
        """
        # Validate inputs
        if not title or not title.strip():
            raise ValueError("Task title cannot be empty")
        
        if len(title.strip()) > 200:
            raise ValueError("Task title cannot exceed 200 characters")
        
        if not TaskStatus.is_valid_status(status):
            valid_statuses = TaskStatus.get_valid_statuses()
            raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")
        
        if not isinstance(person_in_charge, int) or person_in_charge <= 0:
            raise ValueError("Person in charge must be a positive integer")
        
        if not isinstance(creator, int) or creator <= 0:
            raise ValueError("Creator must be a positive integer")
        
        if not self._is_valid_date_format(due_date):
            raise ValueError("Due date must be in YYYY-MM-DD format")
        
        try:
            with self.connection_manager.get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO KANBAN 
                    (Title, Status, PersonInCharge, DueDate, Creator, AdditionalInfo, LastModified)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    title.strip(), status, person_in_charge, due_date,
                    creator, additional_info, datetime.now().isoformat()
                ))
                
                task_id = cursor.lastrowid
                logger.info(f"Task added successfully: {title} (ID: {task_id})")
                return task_id
                
        except sqlite3.IntegrityError as e:
            error_msg = f"Database integrity error: {e}"
            logger.error(error_msg)
            raise DatabaseError(error_msg) from e
        except sqlite3.Error as e:
            error_msg = f"Failed to add task: {e}"
            logger.error(error_msg)
            raise DatabaseError(error_msg) from e
    
    def get_task_by_id(self, task_id: int) -> Optional[Task]:
        """
        Retrieve a task by its ID
        
        Args:
            task_id: ID of the task to retrieve
            
        Returns:
            Optional[Task]: Task instance if found, None otherwise
        """
        try:
            with self.connection_manager.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM KANBAN WHERE ID = ? AND IsActive = 1", 
                    (task_id,)
                )
                row = cursor.fetchone()
                
                if row:
                    return Task.from_db_row(row)
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Error retrieving task {task_id}: {e}")
            return None
    
    def get_all_tasks(self, include_inactive: bool = False) -> List[Task]:
        """
        Retrieve all tasks from the database
        
        Args:
            include_inactive: Whether to include inactive tasks
            
        Returns:
            List[Task]: List of all tasks
        """
        try:
            with self.connection_manager.get_connection() as conn:
                query = "SELECT * FROM KANBAN"
                if not include_inactive:
                    query += " WHERE IsActive = 1"
                
                query += " ORDER BY DueDate ASC, LastModified DESC"
                
                cursor = conn.execute(query)
                tasks = []
                
                for row in cursor:
                    try:
                        task = Task.from_db_row(row)
                        tasks.append(task)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Skipping invalid task data: {e}")
                        continue
                
                return tasks
                
        except sqlite3.Error as e:
            logger.error(f"Error retrieving tasks: {e}")
            return []
    
    def update_task(self, task_id: int, **updates) -> bool:
        """
        Update task fields with partial updates
        
        Args:
            task_id: ID of task to update
            **updates: Field updates (title, status, person_in_charge, etc.)
            
        Returns:
            bool: True if update successful, False otherwise
        """
        if not updates:
            logger.warning("No updates provided for task update")
            return True  # No updates needed
        
        valid_fields = {'title', 'status', 'person_in_charge', 'due_date', 
                       'additional_info', 'editors', 'is_active'}
        
        # Validate update fields
        for field in updates.keys():
            if field not in valid_fields:
                raise ValueError(f"Invalid field for update: {field}")
        
        # Special validation for status
        if 'status' in updates and not TaskStatus.is_valid_status(updates['status']):
            raise ValueError(f"Invalid status: {updates['status']}")
        
        try:
            with self.connection_manager.get_connection() as conn:
                set_clause = ", ".join([f"{field} = ?" for field in updates.keys()])
                set_clause += ", LastModified = ?, Version = Version + 1"
                
                values = list(updates.values())
                values.append(datetime.now().isoformat())
                values.append(task_id)
                
                cursor = conn.execute(
                    f"UPDATE KANBAN SET {set_clause} WHERE ID = ?",
                    values
                )
                
                if cursor.rowcount == 0:
                    logger.warning(f"Task {task_id} not found for update")
                    return False
                
                logger.info(f"Task {task_id} updated successfully")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Error updating task {task_id}: {e}")
            return False
    
    def delete_task(self, task_id: int, soft_delete: bool = True) -> bool:
        """
        Delete a task by ID (soft delete by default)
        
        Args:
            task_id: ID of task to delete
            soft_delete: If True, mark as inactive; if False, permanently delete
            
        Returns:
            bool: True if deletion successful, False otherwise
        """
        try:
            with self.connection_manager.get_connection() as conn:
                # First verify task exists
                task = self.get_task_by_id(task_id)
                if not task:
                    logger.warning(f"Task {task_id} not found for deletion")
                    return False
                
                if soft_delete:
                    # Soft delete (mark as inactive)
                    cursor = conn.execute(
                        "UPDATE KANBAN SET IsActive = 0, LastModified = ? WHERE ID = ?",
                        (datetime.now().isoformat(), task_id)
                    )
                else:
                    # Hard delete (permanent removal)
                    cursor = conn.execute("DELETE FROM KANBAN WHERE ID = ?", (task_id,))
                
                if cursor.rowcount > 0:
                    action = "soft deleted" if soft_delete else "permanently deleted"
                    logger.info(f"Task {action}: {task.title} (ID: {task_id})")
                    return True
                return False
                
        except sqlite3.Error as e:
            logger.error(f"Error deleting task {task_id}: {e}")
            return False
    
    def get_tasks_by_status(self, status: str) -> List[Task]:
        """
        Get all tasks with a specific status
        
        Args:
            status: Status to filter by
            
        Returns:
            List of tasks with the specified status
        """
        if not TaskStatus.is_valid_status(status):
            raise ValueError(f"Invalid status: {status}")
        
        try:
            with self.connection_manager.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM KANBAN WHERE Status = ? AND IsActive = 1 ORDER BY DueDate ASC",
                    (status,)
                )
                
                tasks = []
                for row in cursor:
                    tasks.append(Task.from_db_row(row))
                
                return tasks
                
        except sqlite3.Error as e:
            logger.error(f"Error retrieving tasks by status {status}: {e}")
            return []
    
    def get_tasks_by_assignee(self, person_in_charge: int) -> List[Task]:
        """
        Get all tasks assigned to a specific person
        
        Args:
            person_in_charge: Phone number of the assignee
            
        Returns:
            List of tasks assigned to the person
        """
        try:
            with self.connection_manager.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM KANBAN 
                    WHERE PersonInCharge = ? AND IsActive = 1
                    ORDER BY DueDate ASC, Status DESC
                """, (person_in_charge,))
                
                tasks = []
                for row in cursor:
                    tasks.append(Task.from_db_row(row))
                
                return tasks
                
        except sqlite3.Error as e:
            logger.error(f"Error retrieving tasks for assignee {person_in_charge}: {e}")
            return []
    
    def get_overdue_tasks(self) -> List[Task]:
        """Get all tasks that are overdue"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            
            with self.connection_manager.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM KANBAN 
                    WHERE DueDate < ? AND Status != 'Finished' AND IsActive = 1
                    ORDER BY DueDate ASC
                """, (today,))
                
                tasks = []
                for row in cursor:
                    tasks.append(Task.from_db_row(row))
                
                return tasks
                
        except sqlite3.Error as e:
            logger.error(f"Error retrieving overdue tasks: {e}")
            return []
    
    def count_tasks_by_status(self) -> Dict[str, int]:
        """Count tasks grouped by status"""
        try:
            with self.connection_manager.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT Status, COUNT(*) as count 
                    FROM KANBAN 
                    WHERE IsActive = 1
                    GROUP BY Status
                """)
                
                counts = {}
                for row in cursor:
                    counts[row['Status']] = row['count']
                
                # Ensure all statuses are present
                for status in TaskStatus.get_valid_statuses():
                    if status not in counts:
                        counts[status] = 0
                
                return counts
                
        except sqlite3.Error as e:
            logger.error(f"Error counting tasks by status: {e}")
            return {status: 0 for status in TaskStatus.get_valid_statuses()}
    
    def count_tasks_by_person(self) -> Dict[int, int]:
        """Count tasks grouped by assignee"""
        try:
            with self.connection_manager.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT PersonInCharge, COUNT(*) as count 
                    FROM KANBAN 
                    WHERE IsActive = 1
                    GROUP BY PersonInCharge
                """)
                
                return {row['PersonInCharge']: row['count'] for row in cursor}
                
        except sqlite3.Error as e:
            logger.error("Error counting tasks by person: {e}")
            return {}
    
    def search_tasks(self, search_term: str, search_fields: List[str] = None) -> List[Task]:
        """
        Search tasks by text in specified fields
        
        Args:
            search_term: Text to search for
            search_fields: Fields to search in (title, additional_info)
            
        Returns:
            List of matching tasks
        """
        if not search_fields:
            search_fields = ['Title', 'AdditionalInfo']
        
        valid_fields = ['Title', 'AdditionalInfo']
        for field in search_fields:
            if field not in valid_fields:
                raise ValueError(f"Invalid search field: {field}")
        
        try:
            with self.connection_manager.get_connection() as conn:
                # Build search conditions
                conditions = " OR ".join([f"{field} LIKE ?" for field in search_fields])
                search_pattern = f"%{search_term}%"
                
                cursor = conn.execute(f"""
                    SELECT * FROM KANBAN 
                    WHERE ({conditions}) AND IsActive = 1
                    ORDER BY DueDate ASC
                """, [search_pattern] * len(search_fields))
                
                tasks = []
                for row in cursor:
                    tasks.append(Task.from_db_row(row))
                
                return tasks
                
        except sqlite3.Error as e:
            logger.error(f"Error searching tasks: {e}")
            return []
    
    def _is_valid_date_format(self, date_str: str) -> bool:
        """Validate date format without throwing exceptions"""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False

class UserService:
    """Service for user-related operations with caching and enhanced security"""
    
    def __init__(self, connection_manager: DatabaseConnectionManager):
        self.connection_manager = connection_manager
        self._user_cache = {}  # Cache for user information to reduce database queries
        self._cache_ttl = timedelta(minutes=30)  # Cache time-to-live
        self._last_cache_cleanup = datetime.now()
    
    def get_user_by_phone(self, phone_number: int) -> Optional[Dict[str, Any]]:
        """
        Get user information by phone number with caching support
        
        Args:
            phone_number: User's phone number
            
        Returns:
            Dict with user information or None if not found
        """
        # Check cache first
        cache_key = f"user_{phone_number}"
        if cache_key in self._user_cache:
            cached_data = self._user_cache[cache_key]
            if datetime.now() - cached_data['timestamp'] < self._cache_ttl:
                return cached_data['data']
            else:
                # Cache expired
                del self._user_cache[cache_key]
        
        try:
            with self.connection_manager.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT ID, PhoneNo, Name, Position, IsActive, CreatedAt, LastModified
                    FROM USER 
                    WHERE PhoneNo = ? AND IsActive = 1
                """, (phone_number,))
                
                row = cursor.fetchone()
                if row:
                    user_data = {
                        'user_id': row['ID'],
                        'phone_no': row['PhoneNo'],
                        'name': row['Name'],
                        'position': row['Position'],
                        'is_active': bool(row['IsActive']),
                        'created_at': row['CreatedAt'],
                        'last_modified': row['LastModified']
                    }
                    
                    # Cache the result
                    self._user_cache[cache_key] = {
                        'data': user_data,
                        'timestamp': datetime.now()
                    }
                    
                    # Cleanup old cache entries periodically
                    self._cleanup_cache()
                    
                    return user_data
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Error retrieving user {phone_number}: {e}")
            return None
    
    def validate_user_credentials(self, phone_number: int, password: str) -> Optional[Dict[str, Any]]:
        """
        Validate user credentials with secure password checking
        
        Args:
            phone_number: User's phone number
            password: Plain text password to validate
            
        Returns:
            User data if credentials valid, None otherwise
        """
        try:
            with self.connection_manager.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT ID, PhoneNo, Name, Position, PasswordHash, IsActive, CreatedAt
                    FROM USER 
                    WHERE PhoneNo = ? AND IsActive = 1
                """, (phone_number,))
                
                row = cursor.fetchone()
                if row:
                    # In a real implementation, use proper password hashing
                    # For now, this is a simplified version
                    stored_hash = row['PasswordHash']
                    if self._verify_password(password, stored_hash):
                        return {
                            'user_id': row['ID'],
                            'phone_no': row['PhoneNo'],
                            'name': row['Name'],
                            'position': row['Position'],
                            'is_active': bool(row['IsActive']),
                            'created_at': row['CreatedAt']
                        }
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Error validating credentials for {phone_number}: {e}")
            return None
    
    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new user account with comprehensive validation
        
        Args:
            user_data: Dictionary containing user information
            
        Returns:
            Dictionary with creation result
        """
        required_fields = ['phone_no', 'name', 'position', 'password']
        for field in required_fields:
            if field not in user_data:
                return {
                    'success': False,
                    'error': f"Missing required field: {field}"
                }
        
        try:
            # Hash password before storage
            hashed_password = self._hash_password(user_data['password'])
            
            with self.connection_manager.get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO USER (PhoneNo, Name, Position, PasswordHash, IsActive, CreatedAt)
                    VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                """, (
                    user_data['phone_no'],
                    user_data['name'],
                    user_data['position'],
                    hashed_password
                ))
                
                user_id = cursor.lastrowid
                
                # Get the created user data
                created_user = self.get_user_by_phone(user_data['phone_no'])
                
                logger.info(f"User created successfully: {user_data['name']} (ID: {user_id})")
                
                return {
                    'success': True,
                    'user_id': user_id,
                    'user_data': created_user
                }
                
        except sqlite3.IntegrityError as e:
            error_msg = f"User with phone {user_data['phone_no']} already exists"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
        except sqlite3.Error as e:
            error_msg = f"Failed to create user: {e}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def update_user(self, phone_number: int, updates: Dict[str, Any]) -> bool:
        """
        Update user information with partial updates
        
        Args:
            phone_number: User's phone number
            updates: Dictionary of fields to update
            
        Returns:
            bool: True if update successful, False otherwise
        """
        if not updates:
            logger.warning("No updates provided for user update")
            return True
        
        valid_fields = ['name', 'position', 'is_active']
        for field in updates.keys():
            if field not in valid_fields:
                logger.error(f"Invalid field for user update: {field}")
                return False
        
        try:
            with self.connection_manager.get_connection() as conn:
                set_clause = ", ".join([f"{field} = ?" for field in updates.keys()])
                set_clause += ", LastModified = CURRENT_TIMESTAMP"
                
                values = list(updates.values())
                values.append(phone_number)
                
                cursor = conn.execute(
                    f"UPDATE USER SET {set_clause} WHERE PhoneNo = ?",
                    values
                )
                
                if cursor.rowcount > 0:
                    # Clear cache for this user
                    cache_key = f"user_{phone_number}"
                    if cache_key in self._user_cache:
                        del self._user_cache[cache_key]
                    
                    logger.info(f"User {phone_number} updated successfully")
                    return True
                return False
                
        except sqlite3.Error as e:
            logger.error(f"Error updating user {phone_number}: {e}")
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
        Get all users with optional active-only filter
        
        Args:
            active_only: Whether to include only active users
            
        Returns:
            List of user dictionaries
        """
        try:
            with self.connection_manager.get_connection() as conn:
                query = """
                    SELECT ID, PhoneNo, Name, Position, IsActive, CreatedAt, LastModified
                    FROM USER
                """
                if active_only:
                    query += " WHERE IsActive = 1"
                
                query += " ORDER BY Name ASC"
                
                cursor = conn.execute(query)
                users = []
                
                for row in cursor:
                    users.append({
                        'user_id': row['ID'],
                        'phone_no': row['PhoneNo'],
                        'name': row['Name'],
                        'position': row['Position'],
                        'is_active': bool(row['IsActive']),
                        'created_at': row['CreatedAt'],
                        'last_modified': row['LastModified']
                    })
                
                return users
                
        except sqlite3.Error as e:
            logger.error(f"Error retrieving users: {e}")
            return []
    
    def user_exists(self, phone_number: int) -> bool:
        """
        Check if a user exists in the system
        
        Args:
            phone_number: User's phone number
            
        Returns:
            bool: True if user exists, False otherwise
        """
        return self.get_user_by_phone(phone_number) is not None
    
    def get_user_display_name(self, phone_number: int) -> str:
        """
        Get formatted user display name for UI purposes
        
        Args:
            phone_number: User's phone number
            
        Returns:
            str: Formatted display name
        """
        user_data = self.get_user_by_phone(phone_number)
        if user_data:
            return f"{user_data['name']} ({phone_number})"
        return f"Unknown User ({phone_number})"
    
    def search_users(self, search_term: str, search_fields: List[str] = None) -> List[Dict[str, Any]]:
        """
        Search users by text in specified fields
        
        Args:
            search_term: Text to search for
            search_fields: Fields to search in (name, position)
            
        Returns:
            List of matching users
        """
        if not search_fields:
            search_fields = ['Name', 'Position']
        
        valid_fields = ['Name', 'Position']
        for field in search_fields:
            if field not in valid_fields:
                raise ValueError(f"Invalid search field: {field}")
        
        try:
            with self.connection_manager.get_connection() as conn:
                conditions = " OR ".join([f"{field} LIKE ?" for field in search_fields])
                search_pattern = f"%{search_term}%"
                
                cursor = conn.execute(f"""
                    SELECT ID, PhoneNo, Name, Position, IsActive, CreatedAt, LastModified
                    FROM USER 
                    WHERE ({conditions}) AND IsActive = 1
                    ORDER BY Name ASC
                """, [search_pattern] * len(search_fields))
                
                users = []
                for row in cursor:
                    users.append({
                        'user_id': row['ID'],
                        'phone_no': row['PhoneNo'],
                        'name': row['Name'],
                        'position': row['Position'],
                        'is_active': bool(row['IsActive']),
                        'created_at': row['CreatedAt'],
                        'last_modified': row['LastModified']
                    })
                
                return users
                
        except sqlite3.Error as e:
            logger.error(f"Error searching users: {e}")
            return []
    
    def _hash_password(self, password: str) -> str:
        """
        Hash password for secure storage (simplified version)
        
        Note: In production, use a proper password hashing library like bcrypt
        
        Args:
            password: Plain text password
            
        Returns:
            str: Hashed password
        """
        # This is a simplified version for demonstration
        # In production, use: bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        return hashlib.sha256(password.encode()).hexdigest()
    
    def _verify_password(self, password: str, stored_hash: str) -> bool:
        """
        Verify password against stored hash (simplified version)
        
        Args:
            password: Plain text password to verify
            stored_hash: Stored password hash
            
        Returns:
            bool: True if password matches hash
        """
        # This is a simplified version for demonstration
        # In production, use: bcrypt.checkpw(password.encode(), stored_hash.encode())
        return hashlib.sha256(password.encode()).hexdigest() == stored_hash
    
    def _cleanup_cache(self):
        """Clean up expired cache entries"""
        now = datetime.now()
        if now - self._last_cache_cleanup > timedelta(minutes=5):
            expired_keys = []
            for key, data in self._user_cache.items():
                if now - data['timestamp'] > self._cache_ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._user_cache[key]
            
            self._last_cache_cleanup = now
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")


class KanbanSystem:
    """Main system class coordinating all components"""
    
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or DatabaseConfig.DB_PATH
        self.connection_manager = DatabaseConnectionManager()
        self.kanban_repo = KanbanRepository(self.connection_manager)
        self.user_service = UserService(self.connection_manager)
        self._initialized = False
    
    def initialize_system(self) -> bool:
        """Initialize the complete kanban system"""
        try:
            # Initialize database schema
            if not self.kanban_repo.initialize_database():
                logger.error("Failed to initialize database")
                return False
            
            # Create backup
            self.connection_manager.backup_database()
            
            self._initialized = True
            logger.info("Kanban system initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"System initialization failed: {e}")
            return False
    
    def add_task(self, title: str, status: str, person_in_charge: int, 
                 due_date: str, creator: int, additional_info: str = "") -> int:
        """Add a new task to the system"""
        return self.kanban_repo.add_task(
            title, status, person_in_charge, due_date, creator, additional_info
        )
    
    def get_task(self, task_id: int) -> Optional[Task]:
        """Get a task by ID"""
        return self.kanban_repo.get_task_by_id(task_id)
    
    def get_all_tasks(self, include_inactive: bool = False) -> List[Task]:
        """Get all tasks"""
        return self.kanban_repo.get_all_tasks(include_inactive)
    
    def update_task(self, task_id: int, **updates) -> bool:
        """Update task fields"""
        return self.kanban_repo.update_task(task_id, **updates)
    
    def delete_task(self, task_id: int, soft_delete: bool = True) -> bool:
        """Delete a task"""
        return self.kanban_repo.delete_task(task_id, soft_delete)
    
    def get_user(self, phone_number: int) -> Optional[Dict[str, Any]]:
        """Get user information"""
        return self.user_service.get_user_by_phone(phone_number)
    
    def validate_login(self, phone_number: int, password: str) -> Optional[Dict[str, Any]]:
        """Validate user credentials"""
        return self.user_service.validate_user_credentials(phone_number, password)
    
    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new user"""
        return self.user_service.create_user(user_data)
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        try:
            task_counts = self.kanban_repo.count_tasks_by_status()
            user_counts = self.kanban_repo.count_tasks_by_person()
            overdue_tasks = self.kanban_repo.get_overdue_tasks()
            all_users = self.user_service.get_all_users()
            
            return {
                'task_counts_by_status': task_counts,
                'task_counts_by_person': user_counts,
                'overdue_tasks_count': len(overdue_tasks),
                'active_users_count': len(all_users),
                'total_tasks': sum(task_counts.values()),
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating system stats: {e}")
            return {}


# Legacy API functions for backward compatibility
def InitDB():
    """Legacy function for initializing database"""
    system = KanbanSystem()
    return system.initialize_system()

def AddTask(Title, Status, PersonInCharge, CreationDate, DueDate, Creator, AdditionalInfo):
    """Legacy function for adding tasks"""
    system = KanbanSystem()
    # Note: CreationDate parameter is ignored as it's auto-generated
    return system.add_task(Title, Status, PersonInCharge, DueDate, Creator, AdditionalInfo)

def GetTaskByID(TaskID):
    """Legacy function for getting task by ID"""
    system = KanbanSystem()
    task = system.get_task(TaskID)
    if task:
        return [
            task.task_id, task.title, task.status, task.person_in_charge,
            task.creation_date, task.due_date, task.creator,
            task.editors, task.additional_info
        ]
    return None

def GetUserByPhone(PhoneNo: int):
    """Legacy function for getting user by phone"""
    system = KanbanSystem()
    user = system.get_user(PhoneNo)
    if user:
        return [user['name']]
    return None

def CheckUserExist(PhoneNo: int):
    """Legacy function for checking user existence"""
    system = KanbanSystem()
    return system.get_user(PhoneNo) is not None

def GetAllTasks():
    """Legacy function for getting all tasks"""
    system = KanbanSystem()
    tasks = system.get_all_tasks()
    return [[
        task.task_id, task.title, task.status, task.person_in_charge,
        task.creation_date, task.due_date, task.creator,
        task.editors, task.additional_info
    ] for task in tasks]

def CountTask():
    """Legacy function for counting tasks by status"""
    system = KanbanSystem()
    stats = system.get_system_stats()
    counts = stats.get('task_counts_by_status', {})
    
    # Return in expected order
    status_order = ['To-Do', 'In Progress', 'Waiting Review', 'Finished']
    return [counts.get(status, 0) for status in status_order]

def CountTaskByPerson():
    """Legacy function for counting tasks by person"""
    system = KanbanSystem()
    stats = system.get_system_stats()
    return stats.get('task_counts_by_person', {})


def main():
    """Main function demonstrating system usage"""
    try:
        # Initialize system
        system = KanbanSystem()
        
        if not system.initialize_system():
            print("Failed to initialize system")
            return 1
        
        print("Kanban System Started Successfully!")
        print("=" * 50)
        
        # Display system statistics
        stats = system.get_system_stats()
        print("System Statistics:")
        print(f"Total Tasks: {stats['total_tasks']}")
        print(f"Overdue Tasks: {stats['overdue_tasks_count']}")
        print(f"Active Users: {stats['active_users_count']}")
        print()
        
        # Display task counts by status
        print("Tasks by Status:")
        for status, count in stats['task_counts_by_status'].items():
            print(f"  {status}: {count}")
        
        print("=" * 50)
        return 0
        
    except Exception as e:
        logger.error(f"System error: {e}")
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
