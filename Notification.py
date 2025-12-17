"""
Enhanced Notification System for Kanban Board
Refactored with improved performance, error handling, and architecture
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import sqlite3
import logging
from contextlib import contextmanager
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class NotificationConfig:
    """Configuration for notification system"""
    DB_PATH: Path = Path("kanban.db")
    DEFAULT_DAYS_AHEAD: int = 14
    NOTIFICATION_FORMAT: str = "detailed"  # "detailed" or "summary"
    ENABLE_CACHING: bool = True
    CACHE_DURATION_MINUTES: int = 5


@dataclass
class TaskNotification:
    """Data class for task notification with formatted content"""
    task_id: int
    title: str
    status: str
    due_date: str
    days_until_due: int
    assigned_to: str
    time_remaining: str
    priority: str  # "high", "medium", "low"
    
    def to_detailed_string(self) -> str:
        """Format notification as detailed string"""
        priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        icon = priority_icons.get(self.priority, "⚪")
        
        return f"""
{icon} Task #{self.task_id}: {self.title}
   Status: {self.status}
   Due: {self.due_date} ({self.time_remaining})
   Assigned to: {self.assigned_to}
   Priority: {self.priority.upper()}
{'-' * 50}"""
    
    def to_summary_string(self) -> str:
        """Format notification as summary string"""
        return f"Task #{self.task_id}: {self.title} - Due in {self.days_until_due} days"


class DatabaseManager:
    """Enhanced database manager with connection pooling and error handling"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, db_path: Path):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DatabaseManager, cls).__new__(cls)
                cls._instance._initialize(db_path)
        return cls._instance
    
    def _initialize(self, db_path: Path):
        """Initialize database manager"""
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection_pool = {}
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize database schema if needed"""
        try:
            with self.get_connection() as conn:
                # Check if KANBAN table exists
                cursor = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='KANBAN'
                """)
                if not cursor.fetchone():
                    logger.warning("KANBAN table does not exist. Notifications will be empty.")
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
    
    @contextmanager
    def get_connection(self) -> sqlite3.Connection:
        """
        Context manager for database connections with automatic cleanup
        
        Yields:
            sqlite3.Connection: Database connection
        """
        thread_id = threading.get_ident()
        connection = None
        
        try:
            if thread_id in self._connection_pool:
                connection = self._connection_pool[thread_id]
                # Verify connection is still alive
                try:
                    connection.execute("SELECT 1")
                except sqlite3.Error:
                    connection = None
                    del self._connection_pool[thread_id]
            
            if connection is None:
                connection = sqlite3.connect(
                    str(self.db_path),
                    timeout=30,
                    check_same_thread=False
                )
                connection.row_factory = sqlite3.Row
                self._connection_pool[thread_id] = connection
            
            yield connection
            
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            if connection:
                connection.rollback()
            raise
        finally:
            # Don't close connection immediately for connection pooling
            pass
    
    def cleanup_connections(self):
        """Clean up all database connections"""
        with self._lock:
            for conn in self._connection_pool.values():
                try:
                    conn.close()
                except:
                    pass
            self._connection_pool.clear()


class UserInfoService:
    """Service for retrieving and caching user information"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self._user_cache = {}
        self._cache_lock = threading.Lock()
        self._last_cache_update = datetime.min
    
    def get_user_display_name(self, phone_number: int) -> str:
        """
        Get user display name with caching for performance
        
        Args:
            phone_number: User's phone number
            
        Returns:
            Formatted user display name
        """
        # Check cache first
        with self._cache_lock:
            if phone_number in self._user_cache:
                return self._user_cache[phone_number]
        
        # Cache miss - query database
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT Name FROM USER WHERE PhoneNo = ?", 
                    (phone_number,)
                )
                result = cursor.fetchone()
                
                display_name = "Unknown User"
                if result:
                    display_name = f"{result['Name']} ({phone_number})"
                else:
                    display_name = f"User {phone_number} (Not Found)"
                
                # Update cache
                with self._cache_lock:
                    self._user_cache[phone_number] = display_name
                
                return display_name
                
        except Exception as e:
            logger.warning(f"Error fetching user {phone_number}: {e}")
            return f"User {phone_number} (Error)"
    
    def preload_users(self, phone_numbers: List[int]):
        """Preload multiple users into cache for performance"""
        if not phone_numbers:
            return
        
        try:
            with self.db_manager.get_connection() as conn:
                placeholders = ','.join('?' * len(phone_numbers))
                query = f"SELECT PhoneNo, Name FROM USER WHERE PhoneNo IN ({placeholders})"
                
                cursor = conn.execute(query, phone_numbers)
                results = {row['PhoneNo']: row['Name'] for row in cursor}
                
                # Update cache
                with self._cache_lock:
                    for phone in phone_numbers:
                        if phone in results:
                            self._user_cache[phone] = f"{results[phone]} ({phone})"
                        else:
                            self._user_cache[phone] = f"User {phone} (Not Found)"
                            
        except Exception as e:
            logger.error(f"Error preloading users: {e}")
    
    def clear_cache(self):
        """Clear user cache"""
        with self._cache_lock:
            self._user_cache.clear()


class TaskAnalysisService:
    """Service for analyzing tasks and generating notifications"""
    
    def __init__(self, db_manager: DatabaseManager, user_service: UserInfoService):
        self.db_manager = db_manager
        self.user_service = user_service
    
    def get_upcoming_tasks(self, days_ahead: int = 14) -> List[Dict[str, Any]]:
        """
        Retrieve tasks due within the specified number of days
        
        Args:
            days_ahead: Number of days to look ahead for due tasks
            
        Returns:
            List of task dictionaries with due date information
        """
        try:
            current_time = datetime.now()
            threshold_date = current_time + timedelta(days=days_ahead)
            
            with self.db_manager.get_connection() as conn:
                # Check if KANBAN table exists
                cursor = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='KANBAN'
                """)
                if not cursor.fetchone():
                    logger.warning("KANBAN table not found")
                    return []
                
                # Query for upcoming tasks with proper date handling
                cursor = conn.execute("""
                    SELECT 
                        ID, Title, Status, PersonInCharge, CreationDate, 
                        DueDate, Creator, Editors, AdditionalInfo
                    FROM KANBAN 
                    WHERE DueDate IS NOT NULL 
                    AND DueDate != ''
                    AND Status != 'Finished'
                    ORDER BY DueDate ASC
                """)
                
                upcoming_tasks = []
                unique_users = set()
                
                for row in cursor:
                    task_data = dict(row)
                    due_date_str = task_data['DueDate']
                    
                    # Parse and validate due date
                    try:
                        due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                        current_date = current_time.date()
                        
                        # Check if task is due within the specified period
                        if current_date <= due_date <= threshold_date.date():
                            days_until_due = (due_date - current_date).days
                            task_data['days_until_due'] = days_until_due
                            task_data['due_date_obj'] = due_date
                            upcoming_tasks.append(task_data)
                            
                            # Collect unique user IDs for preloading
                            unique_users.add(task_data['PersonInCharge'])
                            unique_users.add(task_data['Creator'])
                            if task_data['Editors']:
                                unique_users.add(task_data['Editors'])
                    
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid due date format for task {task_data['ID']}: {due_date_str}")
                        continue
                
                # Preload user information for better performance
                if unique_users:
                    self.user_service.preload_users(list(unique_users))
                
                return upcoming_tasks
                
        except Exception as e:
            logger.error(f"Error retrieving upcoming tasks: {e}")
            return []
    
    def calculate_task_priority(self, days_until_due: int) -> str:
        """Calculate task priority based on due date proximity"""
        if days_until_due <= 1:
            return "high"
        elif days_until_due <= 3:
            return "medium"
        else:
            return "low"
    
    def format_time_remaining(self, days_until_due: int) -> str:
        """Format time remaining in human-readable format"""
        if days_until_due == 0:
            return "Due today"
        elif days_until_due == 1:
            return "Due tomorrow"
        elif days_until_due < 7:
            return f"Due in {days_until_due} days"
        elif days_until_due < 30:
            weeks = days_until_due // 7
            return f"Due in {weeks} week{'s' if weeks > 1 else ''}"
        else:
            months = days_until_due // 30
            return f"Due in {months} month{'s' if months > 1 else ''}"


class NotificationFormatter:
    """Formats notifications for different output types"""
    
    @staticmethod
    def create_header(notification_count: int, days_ahead: int) -> str:
        """Create notification header"""
        return f"""
{'=' * 60}
UPCOMING TASK NOTIFICATIONS
{'=' * 60}
Tasks due within the next {days_ahead} days: {notification_count} found
{'=' * 60}
"""
    
    @staticmethod
    def create_footer() -> str:
        """Create notification footer"""
        return f"{'=' * 60}\n"
    
    @staticmethod
    def create_no_tasks_message() -> str:
        """Create message for when no upcoming tasks are found"""
        return f"""
{'=' * 60}
UPCOMING TASK NOTIFICATIONS
{'=' * 60}
No upcoming tasks found. Great work!
{'=' * 60}
"""
    
    @staticmethod
    def group_notifications_by_priority(notifications: List[TaskNotification]) -> Dict[str, List[TaskNotification]]:
        """Group notifications by priority level"""
        grouped = {"high": [], "medium": [], "low": []}
        
        for notification in notifications:
            if notification.priority in grouped:
                grouped[notification.priority].append(notification)
        
        return grouped
    
    @staticmethod
    def format_priority_section(priority: str, notifications: List[TaskNotification]) -> str:
        """Format a section of notifications by priority"""
        if not notifications:
            return ""
        
        priority_titles = {
            "high": "🚨 HIGH PRIORITY - DUE SOON",
            "medium": "⚠️  MEDIUM PRIORITY", 
            "low": "ℹ️  LOW PRIORITY"
        }
        
        section = f"\n{priority_titles.get(priority, priority.upper())}:\n"
        for notification in notifications:
            section += notification.to_detailed_string() + "\n"
        
        return section


class NotificationCache:
    """Simple cache for notification results to improve performance"""
    
    def __init__(self, cache_duration_minutes: int = 5):
        self.cache_duration = timedelta(minutes=cache_duration_minutes)
        self._cache = {}
        self._cache_times = {}
        self._lock = threading.Lock()
    
    def get_cached_notifications(self, cache_key: str) -> Optional[List[TaskNotification]]:
        """Get cached notifications if they exist and are fresh"""
        with self._lock:
            if cache_key in self._cache:
                if datetime.now() - self._cache_times[cache_key] < self.cache_duration:
                    return self._cache[cache_key].copy()  # Return a copy to prevent mutation
                else:
                    # Cache expired
                    del self._cache[cache_key]
                    del self._cache_times[cache_key]
            return None
    
    def set_cached_notifications(self, cache_key: str, notifications: List[TaskNotification]):
        """Cache notifications with timestamp"""
        with self._lock:
            self._cache[cache_key] = notifications.copy()  # Store a copy
            self._cache_times[cache_key] = datetime.now()
    
    def clear_cache(self):
        """Clear entire cache"""
        with self._lock:
            self._cache.clear()
            self._cache_times.clear()


class KanbanNotifier:
    """
    Main notification system for Kanban board with enhanced features
    """
    
    def __init__(self, config: NotificationConfig = None):
        self.config = config or NotificationConfig()
        self.db_manager = DatabaseManager(self.config.DB_PATH)
        self.user_service = UserInfoService(self.db_manager)
        self.task_analyzer = TaskAnalysisService(self.db_manager, self.user_service)
        self.formatter = NotificationFormatter()
        self.cache = NotificationCache(self.config.CACHE_DURATION_MINUTES) if self.config.ENABLE_CACHING else None
        
        logger.info("KanbanNotifier initialized")
    
    def get_upcoming_task_notifications(self, days_ahead: int = None, 
                                      format_type: str = None) -> List[str]:
        """
        Get formatted notifications for upcoming tasks
        
        Args:
            days_ahead: Number of days to look ahead (defaults to config)
            format_type: "detailed" or "summary" format
            
        Returns:
            List of formatted notification strings
        """
        days_ahead = days_ahead or self.config.DEFAULT_DAYS_AHEAD
        format_type = format_type or self.config.NOTIFICATION_FORMAT
        
        # Generate cache key
        cache_key = f"notifications_{days_ahead}_{format_type}"
        
        # Check cache first
        if self.cache:
            cached_notifications = self.cache.get_cached_notifications(cache_key)
            if cached_notifications:
                logger.debug("Using cached notifications")
                return self._format_notifications(cached_notifications, format_type, days_ahead)
        
        # Retrieve and process tasks
        try:
            task_data_list = self.task_analyzer.get_upcoming_tasks(days_ahead)
            
            if not task_data_list:
                return [self.formatter.create_no_tasks_message()]
            
            # Convert to notification objects
            notifications = self._create_notification_objects(task_data_list)
            
            # Cache results
            if self.cache:
                self.cache.set_cached_notifications(cache_key, notifications)
            
            return self._format_notifications(notifications, format_type, days_ahead)
            
        except Exception as e:
            logger.error(f"Error generating notifications: {e}")
            error_msg = f"Error generating notifications: {str(e)}"
            return [f"\n⚠️ NOTIFICATION ERROR\n{error_msg}\n"]
    
    def _create_notification_objects(self, task_data_list: List[Dict[str, Any]]) -> List[TaskNotification]:
        """Create TaskNotification objects from raw task data"""
        notifications = []
        
        for task_data in task_data_list:
            try:
                # Calculate priority
                days_until_due = task_data['days_until_due']
                priority = self.task_analyzer.calculate_task_priority(days_until_due)
                
                # Get user display names
                assigned_to = self.user_service.get_user_display_name(task_data['PersonInCharge'])
                
                # Format time remaining
                time_remaining = self.task_analyzer.format_time_remaining(days_until_due)
                
                # Create notification object
                notification = TaskNotification(
                    task_id=task_data['ID'],
                    title=task_data['Title'],
                    status=task_data['Status'],
                    due_date=task_data['DueDate'],
                    days_until_due=days_until_due,
                    assigned_to=assigned_to,
                    time_remaining=time_remaining,
                    priority=priority
                )
                
                notifications.append(notification)
                
            except Exception as e:
                logger.warning(f"Error processing task {task_data.get('ID', 'unknown')}: {e}")
                continue
        
        return notifications
    
    def _format_notifications(self, notifications: List[TaskNotification], 
                            format_type: str, days_ahead: int) -> List[str]:
        """Format notifications based on requested format type"""
        if not notifications:
            return [self.formatter.create_no_tasks_message()]
        
        output_lines = []
        
        # Add header
        output_lines.append(self.formatter.create_header(len(notifications), days_ahead))
        
        if format_type == "summary":
            # Simple summary format
            for notification in notifications:
                output_lines.append(notification.to_summary_string())
        else:
            # Detailed format with grouping by priority
            grouped = self.formatter.group_notifications_by_priority(notifications)
            
            # Add high priority first
            output_lines.append(self.formatter.format_priority_section("high", grouped["high"]))
            output_lines.append(self.formatter.format_priority_section("medium", grouped["medium"]))
            output_lines.append(self.formatter.format_priority_section("low", grouped["low"]))
        
        # Add footer
        output_lines.append(self.formatter.create_footer())
        
        return output_lines
    
    def print_notifications(self, days_ahead: int = None, format_type: str = None):
        """Print notifications to console"""
        notifications = self.get_upcoming_task_notifications(days_ahead, format_type)
        
        for line in notifications:
            print(line)
    
    def get_notification_statistics(self, days_ahead: int = None) -> Dict[str, Any]:
        """Get statistics about upcoming tasks"""
        days_ahead = days_ahead or self.config.DEFAULT_DAYS_AHEAD
        
        try:
            task_data_list = self.task_analyzer.get_upcoming_tasks(days_ahead)
            
            stats = {
                "total_tasks": len(task_data_list),
                "days_ahead": days_ahead,
                "high_priority": 0,
                "medium_priority": 0,
                "low_priority": 0,
                "closest_due_date": None,
                "farthest_due_date": None
            }
            
            due_dates = []
            
            for task_data in task_data_list:
                days_until_due = task_data['days_until_due']
                priority = self.task_analyzer.calculate_task_priority(days_until_due)
                
                if priority == "high":
                    stats["high_priority"] += 1
                elif priority == "medium":
                    stats["medium_priority"] += 1
                else:
                    stats["low_priority"] += 1
                
                due_dates.append(days_until_due)
            
            if due_dates:
                stats["closest_due_date"] = min(due_dates)
                stats["farthest_due_date"] = max(due_dates)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating statistics: {e}")
            return {"error": str(e)}
    
    def clear_caches(self):
        """Clear all caches (user cache and notification cache)"""
        self.user_service.clear_cache()
        if self.cache:
            self.cache.clear_cache()
        logger.info("All caches cleared")
    
    def cleanup(self):
        """Clean up resources"""
        self.db_manager.cleanup_connections()
        logger.info("KanbanNotifier cleanup completed")


# Legacy API for backward compatibility
def UpcomingTask(days_ahead: int = 14) -> List[str]:
    """
    Legacy function for backward compatibility
    Returns formatted notifications for upcoming tasks
    """
    notifier = KanbanNotifier()
    return notifier.get_upcoming_task_notifications(days_ahead, "detailed")


def PrintNotification():
    """
    Legacy function for backward compatibility
    Prints notifications to console
    """
    notifier = KanbanNotifier()
    notifier.print_notifications()


# Example usage and testing
if __name__ == "__main__":
    # Example 1: Basic usage
    print("=== Basic Notification Example ===")
    notifier = KanbanNotifier()
    notifier.print_notifications()
    
    # Example 2: Get statistics
    print("\n=== Notification Statistics ===")
    stats = notifier.get_notification_statistics()
    print(f"Upcoming tasks: {stats['total_tasks']}")
    print(f"High priority: {stats['high_priority']}")
    print(f"Medium priority: {stats['medium_priority']}")
    print(f"Low priority: {stats['low_priority']}")
    
    # Example 3: Custom configuration
    print("\n=== Custom Configuration Example ===")
    custom_config = NotificationConfig(
        DEFAULT_DAYS_AHEAD=7,
        NOTIFICATION_FORMAT="summary"
    )
    custom_notifier = KanbanNotifier(custom_config)
    custom_notifier.print_notifications()
    
    # Cleanup
    notifier.cleanup()
    custom_notifier.cleanup()
