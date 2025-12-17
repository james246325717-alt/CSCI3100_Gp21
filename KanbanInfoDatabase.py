"""
Enhanced Kanban Data Access Layer
Refactored with improved architecture, performance, and maintainability
"""

import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List, Union, Tuple
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
import logging
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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


class DatabaseConfig:
    """Centralized configuration for database settings"""
    
    DB_PATH = Path("kanban.db")
    DB_BACKUP_DIR = Path("backups")
    
    # Table schema with improved constraints and indexing
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
        "CREATE INDEX IF NOT EXISTS idx_kanban_modified ON KANBAN(LastModified)"
    ]


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
        Context manager for database connections with automatic cleanup and error handling
        
        Yields:
            sqlite3.Connection: Database connection with foreign keys enabled
        """
        connection = None
        try:
            connection = sqlite3.connect(
                str(self.db_path),
                timeout=30,
                check_same_thread=False
            )
            # Enable foreign keys and set pragmas for better performance
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.row_factory = sqlite3.Row  # Enable dictionary-like access
            
            yield connection
            connection.commit()  # Auto-commit on successful exit
            
        except sqlite3.Error as e:
            if connection:
                connection.rollback()  # Rollback on error
            logger.error(f"Database error: {e}")
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


class TaskModel:
    """
    Data model for task operations with comprehensive validation and business logic
    """
    
    def __init__(self, 
                 title: str,
                 status: str,
                 person_in_charge: int,
                 due_date: str,
                 creator: int,
                 additional_info: str = "",
                 creation_date: Optional[str] = None,
                 editors: Optional[int] = None,
                 task_id: Optional[int] = None,
                 last_modified: Optional[str] = None):
        """
        Initialize a Task with comprehensive validation
        """
        self._validate_constructor_args(
            title, status, person_in_charge, due_date, creator
        )
        
        self.task_id = task_id
        self.title = title.strip()
        self.status = status
        self.person_in_charge = person_in_charge
        self.due_date = due_date
        self.creator = creator
        self.additional_info = additional_info
        self.editors = editors
        self.creation_date = creation_date or datetime.now().isoformat()
        self.last_modified = last_modified or datetime.now().isoformat()
    
    def _validate_constructor_args(self, title: str, status: str, person_in_charge: int,
                                 due_date: str, creator: int):
        """Validate constructor arguments with detailed error messages"""
        if not title or not title.strip():
            raise ValueError("Task title cannot be empty")
        
        if len(title.strip()) > 200:
            raise ValueError("Task title cannot exceed 200 characters")
        
        if not TaskStatus.is_valid_status(status):
            valid_statuses = TaskStatus.get_valid_statuses()
            raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")
        
        if not isinstance(person_in_charge, int) or person_in_charge <= 0:
            raise ValueError("Person in charge must be a positive integer")
        
        if not self._is_valid_date_format(due_date):
            raise ValueError("Due date must be in YYYY-MM-DD format")
        
        if not self._is_future_date(due_date):
            raise ValueError("Due date must be in the future")
        
        if not isinstance(creator, int) or creator <= 0:
            raise ValueError("Creator must be a positive integer")
    
    def _is_valid_date_format(self, date_str: str) -> bool:
        """Validate date format without throwing exceptions"""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False
    
    def _is_future_date(self, date_str: str) -> bool:
        """Check if date is in the future"""
        try:
            due_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            return due_date >= datetime.now().date()
        except ValueError:
            return False
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert task to dictionary, optionally including sensitive data"""
        data = {
            'task_id': self.task_id,
            'title': self.title,
            'status': self.status,
            'person_in_charge': self.person_in_charge,
            'due_date': self.due_date,
            'creator': self.creator,
            'additional_info': self.additional_info,
            'creation_date': self.creation_date,
            'last_modified': self.last_modified
        }
        
        if include_sensitive:
            data['editors'] = self.editors
        
        return data
    
    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> 'TaskModel':
        """Create TaskModel from database row"""
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
            last_modified=row['LastModified']
        )
    
    def __str__(self) -> str:
        """String representation for logging"""
        return (f"Task(id={self.task_id}, title='{self.title}', status='{self.status}', "
                f"due_date='{self.due_date}', assigned_to={self.person_in_charge})")
    
    def __repr__(self) -> str:
        """Technical representation for debugging"""
        return (f"TaskModel(title='{self.title}', status='{self.status}', "
                f"person_in_charge={self.person_in_charge}, due_date='{self.due_date}')")


class KanbanRepository:
    """
    Repository pattern implementation for Kanban data operations
    with enhanced performance and error handling
    """
    
    def __init__(self, connection_manager: DatabaseConnectionManager):
        self.connection_manager = connection_manager
        self._initialize_database()
    
    def _initialize_database(self) -> bool:
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
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Database initialization failed: {e}")
            raise DatabaseError(f"Failed to initialize database: {e}") from e
    
    def add_task(self, task: TaskModel) -> int:
        """
        Add a new task to the kanban board
        
        Args:
            task: TaskModel instance with task data
            
        Returns:
            int: ID of the newly created task
            
        Raises:
            DatabaseError: If database operation fails
            ValueError: If task data is invalid
        """
        try:
            with self.connection_manager.get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO KANBAN 
                    (Title, Status, PersonInCharge, DueDate, Creator, AdditionalInfo, Editors, LastModified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task.title, task.status, task.person_in_charge, task.due_date,
                    task.creator, task.additional_info, task.editors, task.last_modified
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
    
    def get_task_by_id(self, task_id: int) -> Optional[TaskModel]:
        """
        Retrieve a task by its ID
        
        Args:
            task_id: ID of the task to retrieve
            
        Returns:
            Optional[TaskModel]: Task instance if found, None otherwise
        """
        try:
            with self.connection_manager.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM KANBAN WHERE ID = ?", 
                    (task_id,)
                )
                row = cursor.fetchone()
                
                if row:
                    return TaskModel.from_db_row(row)
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Error retrieving task {task_id}: {e}")
            return None
    
    def get_all_tasks(self, include_inactive: bool = True) -> List[TaskModel]:
        """
        Retrieve all tasks from the database
        
        Args:
            include_inactive: Whether to include tasks with inactive assignees
            
        Returns:
            List[TaskModel]: List of all tasks
        """
        try:
            with self.connection_manager.get_connection() as conn:
                query = "SELECT * FROM KANBAN"
                if not include_inactive:
                    query += " WHERE PersonInCharge IN (SELECT PhoneNo FROM USER WHERE IsActive = 1)"
                
                query += " ORDER BY DueDate ASC, LastModified DESC"
                
                cursor = conn.execute(query)
                tasks = []
                
                for row in cursor:
                    try:
                        task = TaskModel.from_db_row(row)
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
                       'additional_info', 'editors'}
        
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
                set_clause += ", LastModified = ?"
                
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
    
    def delete_task(self, task_id: int) -> bool:
        """
        Delete a task by ID
        
        Args:
            task_id: ID of task to delete
            
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
                
                cursor = conn.execute("DELETE FROM KANBAN WHERE ID = ?", (task_id,))
                
                if cursor.rowcount > 0:
                    logger.info(f"Task deleted: {task.title} (ID: {task_id})")
                    return True
                return False
                
        except sqlite3.Error as e:
            logger.error(f"Error deleting task {task_id}: {e}")
            return False
    
    def delete_tasks_batch(self, task_ids: List[int]) -> Dict[str, Any]:
        """
        Delete multiple tasks in a batch operation
        
        Args:
            task_ids: List of task IDs to delete
            
        Returns:
            Dict with results summary
        """
        results = {
            'successful': [],
            'failed': [],
            'not_found': []
        }
        
        with self.connection_manager.get_connection() as conn:
            for task_id in task_ids:
                try:
                    # Verify task exists
                    if not self.get_task_by_id(task_id):
                        results['not_found'].append(task_id)
                        continue
                    
                    cursor = conn.execute("DELETE FROM KANBAN WHERE ID = ?", (task_id,))
                    if cursor.rowcount > 0:
                        results['successful'].append(task_id)
                    else:
                        results['failed'].append(task_id)
                        
                except Exception as e:
                    results['failed'].append((task_id, str(e)))
        
        return results
    
    def get_tasks_by_status(self, status: str) -> List[TaskModel]:
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
                    "SELECT * FROM KANBAN WHERE Status = ? ORDER BY DueDate ASC",
                    (status,)
                )
                
                tasks = []
                for row in cursor:
                    tasks.append(TaskModel.from_db_row(row))
                
                return tasks
                
        except sqlite3.Error as e:
            logger.error(f"Error retrieving tasks by status {status}: {e}")
            return []
    
    def get_tasks_by_assignee(self, person_in_charge: int) -> List[TaskModel]:
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
                    WHERE PersonInCharge = ? 
                    ORDER BY DueDate ASC, Status DESC
                """, (person_in_charge,))
                
                tasks = []
                for row in cursor:
                    tasks.append(TaskModel.from_db_row(row))
                
                return tasks
                
        except sqlite3.Error as e:
            logger.error(f"Error retrieving tasks for assignee {person_in_charge}: {e}")
            return []
    
    def get_overdue_tasks(self) -> List[TaskModel]:
        """Get all tasks that are overdue"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            
            with self.connection_manager.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM KANBAN 
                    WHERE DueDate < ? AND Status != 'Finished'
                    ORDER BY DueDate ASC
                """, (today,))
                
                tasks = []
                for row in cursor:
                    tasks.append(TaskModel.from_db_row(row))
                
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
                    GROUP BY PersonInCharge
                """)
                
                return {row['PersonInCharge']: row['count'] for row in cursor}
                
        except sqlite3.Error as e:
            logger.error("Error counting tasks by person: {e}")
            return {}
    
    def search_tasks(self, search_term: str, search_fields: List[str] = None) -> List[TaskModel]:
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
                    WHERE {conditions}
                    ORDER BY DueDate ASC
                """, [search_pattern] * len(search_fields))
                
                tasks = []
                for row in cursor:
                    tasks.append(TaskModel.from_db_row(row))
                
                return tasks
                
        except sqlite3.Error as e:
            logger.error(f"Error searching tasks: {e}")
            return []


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
    def display_task_data(row: sqlite3.Row, user_repository: Any = None) -> Dict[str, Any]:
        """
        Format task data for display with user information
        
        Args:
            row: Database row with task data
            user_repository: Optional repository for user data lookup
            
        Returns:
            Formatted task data dictionary
        """
        if row is None:
            return None
        
        formatter = DataFormatter()
        base_data = {
            "ID": row['ID'],
            "Title": row['Title'],
            "Status": row['Status'],
            "Creation Date": formatter.format_date(row['CreationDate']),
            "Due Date": row['DueDate'],
            "Additional Info": row['AdditionalInfo'] or "None"
        }
        
        # Add user information if repository is available
        if user_repository:
            try:
                base_data["Person in Charge"] = user_repository.get_user_display(row['PersonInCharge'])
                base_data["Creator"] = user_repository.get_user_display(row['Creator'])
                base_data["Editors"] = user_repository.get_user_display(row['Editors'])
            except Exception as e:
