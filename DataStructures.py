#!/usr/bin/env python3
"""
Enhanced Kanban System - Simplified Business Logic Layer
Clean, efficient task management with improved architecture
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task status enumeration with validation"""
    TO_DO = "To-Do"
    IN_PROGRESS = "In Progress" 
    WAITING_REVIEW = "Waiting Review"
    FINISHED = "Finished"
    
    @classmethod
    def get_all_statuses(cls) -> List[str]:
        """Get all valid status values"""
        return [status.value for status in cls]


@dataclass
class Task:
    """Simplified Task data model with core functionality"""
    
    task_id: Optional[int] = None
    title: str = ""
    status: str = TaskStatus.TO_DO.value
    person_in_charge: int = 0
    creation_date: str = ""
    due_date: str = ""
    creator: int = 0
    editors: Optional[int] = None
    additional_info: str = ""
    
    def __post_init__(self):
        """Initialize creation date if not provided"""
        if not self.creation_date:
            self.creation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def validate(self) -> List[str]:
        """Basic task validation"""
        errors = []
        
        if not self.title or not self.title.strip():
            errors.append("Task title cannot be empty")
        
        if self.title and len(self.title.strip()) > 200:
            errors.append("Task title cannot exceed 200 characters")
        
        if self.status not in TaskStatus.get_all_statuses():
            errors.append(f"Invalid status: {self.status}")
        
        if not isinstance(self.person_in_charge, int) or self.person_in_charge <= 0:
            errors.append("Person in charge must be a positive integer")
        
        if not isinstance(self.creator, int) or self.creator <= 0:
            errors.append("Creator must be a positive integer")
        
        return errors
    
    def is_overdue(self) -> bool:
        """Check if task is overdue"""
        try:
            due = datetime.strptime(self.due_date, "%Y-%m-%d").date()
            return due < datetime.now().date()
        except ValueError:
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
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
            'is_overdue': self.is_overdue()
        }
    
    def display(self) -> str:
        """Format task for display"""
        return (f"Task {self.task_id}: {self.title}\n"
                f"Status: {self.status} | Due: {self.due_date} | "
                f"Assigned to: {self.person_in_charge}")


class TaskRepository:
    """Abstract base class for task data operations"""
    
    def get_task_by_id(self, task_id: int) -> Optional[Task]:
        """Get task by ID"""
        pass
    
    def get_all_tasks(self) -> List[Task]:
        """Get all tasks"""
        pass
    
    def add_task(self, task: Task) -> int:
        """Add new task"""
        pass
    
    def update_task(self, task_id: int, **updates) -> bool:
        """Update task"""
        pass
    
    def delete_task(self, task_id: int) -> bool:
        """Delete task"""
        pass


class UserService:
    """Abstract base class for user operations"""
    
    def get_user_display_name(self, user_id: int) -> str:
        """Get user display name"""
        pass


class KanbanBoard:
    """Simplified Kanban board with core functionality"""
    
    def __init__(self, task_repo: TaskRepository, user_service: UserService):
        self.task_repo = task_repo
        self.user_service = user_service
        self.valid_statuses = TaskStatus.get_all_statuses()
    
    def add_task(self, title: str, status: str, person_in_charge: int, 
                 due_date: str, creator: int, additional_info: str = "") -> Dict[str, Any]:
        """Add a new task with validation"""
        # Validate inputs
        if not title or not title.strip():
            return {'success': False, 'error': 'Task title is required'}
        
        if status not in self.valid_statuses:
            return {'success': False, 'error': f'Invalid status: {status}'}
        
        # Create and validate task
        task = Task(
            title=title.strip(),
            status=status,
            person_in_charge=person_in_charge,
            due_date=due_date,
            creator=creator,
            additional_info=additional_info
        )
        
        validation_errors = task.validate()
        if validation_errors:
            return {'success': False, 'errors': validation_errors}
        
        try:
            # Save to repository
            task_id = self.task_repo.add_task(task)
            logger.info(f"Task added: {title} (ID: {task_id})")
            
            return {
                'success': True,
                'task_id': task_id,
                'message': f'Task "{title}" added successfully'
            }
            
        except Exception as e:
            logger.error(f"Failed to add task: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_task(self, task_id: int) -> Dict[str, Any]:
        """Get task by ID"""
        try:
            task = self.task_repo.get_task_by_id(task_id)
            if not task:
                return {'success': False, 'error': f'Task {task_id} not found'}
            
            return {
                'success': True,
                'task': task.to_dict(),
                'display_text': task.display()
            }
            
        except Exception as e:
            logger.error(f"Error getting task {task_id}: {e}")
            return {'success': False, 'error': str(e)}
    
    def update_task(self, task_id: int, **updates) -> Dict[str, Any]:
        """Update task fields"""
        try:
            # Validate status if provided
            if 'status' in updates and updates['status'] not in self.valid_statuses:
                return {'success': False, 'error': f'Invalid status: {updates["status"]}'}
            
            # Apply updates
            success = self.task_repo.update_task(task_id, **updates)
            
            if success:
                logger.info(f"Task {task_id} updated: {list(updates.keys())}")
                return {
                    'success': True,
                    'message': f'Task {task_id} updated successfully',
                    'updated_fields': list(updates.keys())
                }
            else:
                return {'success': False, 'error': f'Task {task_id} not found'}
                
        except Exception as e:
            logger.error(f"Error updating task {task_id}: {e}")
            return {'success': False, 'error': str(e)}
    
    def delete_task(self, task_id: int) -> Dict[str, Any]:
        """Delete task by ID"""
        try:
            success = self.task_repo.delete_task(task_id)
            
            if success:
                logger.info(f"Task {task_id} deleted")
                return {'success': True, 'message': f'Task {task_id} deleted successfully'}
            else:
                return {'success': False, 'error': f'Task {task_id} not found'}
                
        except Exception as e:
            logger.error(f"Error deleting task {task_id}: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_all_tasks(self, group_by_status: bool = True) -> Dict[str, Any]:
        """Get all tasks with optional grouping"""
        try:
            tasks = self.task_repo.get_all_tasks()
            
            if group_by_status:
                grouped = self._group_tasks_by_status(tasks)
                return {
                    'success': True,
                    'tasks': grouped,
                    'total_count': len(tasks)
                }
            else:
                return {
                    'success': True,
                    'tasks': [task.to_dict() for task in tasks],
                    'total_count': len(tasks)
                }
                
        except Exception as e:
            logger.error(f"Error getting tasks: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_tasks_by_status(self, status: str) -> Dict[str, Any]:
        """Get tasks filtered by status"""
        if status not in self.valid_statuses:
            return {'success': False, 'error': f'Invalid status: {status}'}
        
        try:
            all_tasks = self.task_repo.get_all_tasks()
            filtered_tasks = [task for task in all_tasks if task.status == status]
            
            return {
                'success': True,
                'tasks': [task.to_dict() for task in filtered_tasks],
                'status': status,
                'count': len(filtered_tasks)
            }
            
        except Exception as e:
            logger.error(f"Error getting tasks by status {status}: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_overdue_tasks(self) -> Dict[str, Any]:
        """Get all overdue tasks"""
        try:
            all_tasks = self.task_repo.get_all_tasks()
            overdue_tasks = [task for task in all_tasks if task.is_overdue()]
            
            return {
                'success': True,
                'tasks': [task.to_dict() for task in overdue_tasks],
                'count': len(overdue_tasks)
            }
            
        except Exception as e:
            logger.error(f"Error getting overdue tasks: {e}")
            return {'success': False, 'error': str(e)}
    
    def display_board(self) -> str:
        """Display kanban board in formatted text"""
        try:
            result = self.get_all_tasks(group_by_status=True)
            
            if not result['success']:
                return "Error displaying board"
            
            grouped_tasks = result['tasks']
            output = []
            output.append("\n" + "="*50)
            output.append(f"{'KANBAN BOARD':^50}")
            output.append("="*50)
            
            for status in self.valid_statuses:
                tasks = grouped_tasks.get(status, [])
                if tasks:
                    output.append(f"\n{status.upper():^50}")
                    output.append("-"*50)
                    for task in tasks:
                        assignee_name = self.user_service.get_user_display_name(task.person_in_charge)
                        overdue_indicator = " [OVERDUE]" if task.is_overdue() else ""
                        output.append(f"#{task.task_id}: {task.title}{overdue_indicator}")
                        output.append(f"   Due: {task.due_date} | Assignee: {assignee_name}")
            
            output.append("\n" + "="*50)
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Error displaying board: {e}")
            return f"Error displaying board: {e}"
    
    def _group_tasks_by_status(self, tasks: List[Task]) -> Dict[str, List[Task]]:
        """Group tasks by status"""
        grouped = {status: [] for status in self.valid_statuses}
        
        for task in tasks:
            if task.status in grouped:
                grouped[task.status].append(task)
        
        return grouped


# Example implementation for demonstration
class InMemoryTaskRepository(TaskRepository):
    """In-memory implementation for demonstration"""
    
    def __init__(self):
        self.tasks = {}
        self.next_id = 1
        
        # Add sample data
        sample_task = Task(
            title="Sample Task",
            status=TaskStatus.TO_DO.value,
            person_in_charge=1001,
            due_date="2024-12-31",
            creator=1001,
            additional_info="This is a sample task"
        )
        self.add_task(sample_task)
    
    def get_task_by_id(self, task_id: int) -> Optional[Task]:
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[Task]:
        return list(self.tasks.values())
    
    def add_task(self, task: Task) -> int:
        task.task_id = self.next_id
        self.tasks[self.next_id] = task
        self.next_id += 1
        return task.task_id
    
    def update_task(self, task_id: int, **updates) -> bool:
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        for key, value in updates.items():
            if hasattr(task, key):
                setattr(task, key, value)
        
        return True
    
    def delete_task(self, task_id: int) -> bool:
        if task_id in self.tasks:
            del self.tasks[task_id]
            return True
        return False


class SimpleUserService(UserService):
    """Simple user service for demonstration"""
    
    def get_user_display_name(self, user_id: int) -> str:
        users = {
            1001: "Admin User",
            1002: "John Developer", 
            1003: "Jane Tester"
        }
        return users.get(user_id, f"User {user_id}")


# Usage example
def main():
    """Demonstrate the kanban system"""
    # Initialize components
    task_repo = InMemoryTaskRepository()
    user_service = SimpleUserService()
    kanban = KanbanBoard(task_repo, user_service)
    
    # Display initial board
    print(kanban.display_board())
    
    # Add a new task
    result = kanban.add_task(
        title="Implement New Feature",
        status=TaskStatus.TO_DO.value,
        person_in_charge=1002,
        due_date="2024-01-25",
        creator=1001,
        additional_info="Implement the new user authentication system"
    )
    
    if result['success']:
        print(f"✓ {result['message']}")
    else:
        print(f"✗ Error: {result.get('error', 'Unknown error')}")
    
    # Display updated board
    print(kanban.display_board())
    
    # Get overdue tasks
    overdue_result = kanban.get_overdue_tasks()
    if overdue_result['success'] and overdue_result['count'] > 0:
        print(f"\nOverdue tasks: {overdue_result['count']}")


if __name__ == "__main__":
    main()
