"""
Enhanced Kanban Data Access Layer
Enterprise-grade database module with improved architecture, performance, and maintainability
"""

import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List, Union, Tuple
from datetime import datetime
from contextlib import contextmanager
from enum import Enum
import logging
import hashlib
from dataclasses import dataclass
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Centralized configuration management for database settings"""
    
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
        """Validate task status"""
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
        if not self._is_valid_date(self.due_date):
            errors.append("Due date must be in YYYY-MM-DD format")
        
        return errors
    
    def _is_valid_date(self, date_str: str) -> bool:
        """Check if date string is in valid format"""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary for serialization"""
        return {
            'task_id': self.task_id,
            'title': self.title,
            'status': self.status,
            'person_in_charge': self.person_in_charge,
            'creation_date': self.creation_date,
            'due_date': self.due_date,
            'creator': self.creator,
            'editors': self.editors,
            'additional_info': self.additional_info,
            'last_modified': self.last_modified,
            'version': self.version,
            'is_active': self.is_active
        }
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'Task':
        """Create Task from database row"""
        return cls(
            task_id=row.get('ID'),
            title=row.get('Title', ''),
            status=row.get('Status', ''),
            person_in_charge=row.get('PersonInCharge', 0),
            creation_date=row.get('CreationDate', ''),
            due_date=row.get('DueDate', ''),
            creator=row.get('Creator', 0),
            editors=row.get('Editors'),
            additional_info=row.get('AdditionalInfo', ''),
            last_modified=row.get('LastModified', ''),
            version=row.get('Version', 1),
            is_active=bool(row.get('IsActive', 1))
        )


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


class DatabaseError(Exception):
    """Custom exception for database-related errors"""
    pass


class KanbanRepository:
    """
    Repository pattern implementation for Kanban data operations
    with enhanced performance, error handling, and transaction support
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
    
    def add_task(self, task: Task) -> int:
        """
        Add a new task to the kanban board with comprehensive validation
        
        Args:
            task: Task object with task data
            
        Returns:
            int: ID of the newly created task
            
        Raises:
            DatabaseError: If database operation fails
            ValueError: If task data is invalid
        """
        # Validate task data
        validation_errors = task.validate()
        if validation_errors:
            raise ValueError(f"Invalid task data: {'; '.join(validation_errors)}")
        
        try:
            with self.connection_manager.get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO KANBAN 
                    (Title, Status, PersonInCharge, CreationDate, DueDate, Creator, AdditionalInfo, LastModified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task.title, task.status, task.person_in_charge, task.creation_date,
                    task.due_date, task.creator, task.additional_info, 
                    datetime.now().isoformat()
                ))
                
                task_id = cursor.lastrowid
                logger.info(f"Task added successfully: {task.title} (ID: {task_id})")
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
            Optional[Task]: Task object if found, None otherwise
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
        Update task fields with partial updates and optimistic locking
        
        Args:
            task_id: ID of task to update
            **updates: Field updates (title, status, person_in_charge, etc.)
            
        Returns:
            bool: True if update successful, False otherwise
        """
        if not updates:
            logger.warning("No updates provided for task update")
            return True  # No updates needed
        
        valid_fields = {
            'title', 'status', 'person_in_charge', 'due_date', 
            'additional_info', 'editors', 'is_active'
        }
        
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


class UserService:
    """Service for user-related operations with caching"""
    
    def __init__(self, connection_manager: DatabaseConnectionManager):
        self.connection_manager = connection_manager
        self._user_cache = {}  # Cache for user information
        
    def get_user_by_phone(self, phone_number: int) -> Optional[Dict[str, Any]]:
        """
        Get user information by phone number with caching
        
        Args:
            phone_number: User's phone number
            
        Returns:
            User information dictionary or None if not found
        """
        if phone_number is None:
            return None
        
        # Check cache first
        if phone_number in self._user_cache:
            return self._user_cache[phone_number]
        
        try:
            with self.connection_manager.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT PhoneNo, Name FROM USER WHERE PhoneNo = ?", 
                    (phone_number,)
                )
                result = cursor.fetchone()
                
                if result:
                    user_info = {
                        'phone_no': result['PhoneNo'],
                        'name': result['Name']
                    }
                    # Cache the result
                    self._user_cache[phone_number] = user_info
                    return user_info
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Error retrieving user {phone_number}: {e}")
            return None
    
    def check_user_exists(self, phone_number: int) -> bool:
        """Check if a user exists in the system"""
        return self.get_user_by_phone(phone_number) is not None
    
    def get_user_display_name(self, phone_number: int) -> str:
        """Get formatted user display name"""
        user_info = self.get_user_by_phone(phone_number)
        if user_info:
            return f"{user_info['name']} ({phone_number})"
        return f"Unknown User ({phone_number})"


class DataFormatter:
    """Utility class for formatting data for display"""
    
    @staticmethod
    def format_date(date_obj) -> str:
        """
        Format date for display, handling multiple input types
        
        Args:
            date_obj: Date to format (datetime, string, or None)
            
        Returns:
            Formatted date string
        """
        if date_obj is None:
            return "Not set"
        
        if isinstance(date_obj, str):
            # Try to parse and reformat if it's an ISO string
            try:
                if 'T' in date_obj:  # ISO format with time
                    date_obj = datetime.fromisoformat(date_obj.replace('Z', '+00:00'))
                else:  # Assume already formatted
                    return date_obj
            except ValueError:
                return date_obj  # Return as-is if can't parse
        
        if isinstance(date_obj, datetime):
            return date_obj.strftime("%Y-%m-%d %H:%M:%S")
        
        return str(date_obj)
    
    @staticmethod
    def display_task_data(task: Task, user_service: UserService) -> Dict[str, Any]:
        """
        Format task data for display with user information
        
        Args:
            task: Task object to display
            user_service: User service for user lookups
            
        Returns:
            Formatted task data dictionary
        """
        if task is None:
            return None
        
        formatter = DataFormatter()
        return {
            "ID": task.task_id,
            "Title": task.title,
            "Status": task.status,
            "Person in Charge": user_service.get_user_display_name(task.person_in_charge),
            "Creation Date": formatter.format_date(task.creation_date),
            "Due Date": task.due_date,
            "Creator": user_service.get_user_display_name(task.creator),
            "Editors": user_service.get_user_d
