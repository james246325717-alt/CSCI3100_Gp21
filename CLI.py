"""
Kanban System - Enhanced Menu Module
Refactored with improved architecture, error handling, and maintainability
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable

# Import modules with better error handling
try:
    import DataStructures
    import Database
    import KanbanInfoDatabase as kdb
except ImportError as e:
    print(f"Error importing required modules: {e}")
    sys.exit(1)


class MenuConfig:
    """Configuration management for menu system"""
    
    # Menu display texts
    MENU_SCREENS = """
Kanban - Main Menu
Choose an option by number:
  1) List tasks
  2) Add task
  3) Move task
  4) Edit task
  5) Delete task
  6) Show task
  7) Advice
  h) Help
  0) Exit
"""

    ADMIN_MENU_SCREENS = """
Kanban - Administrative Menu
Choose an option by number:
  1) Update user activation status
  2) Access Kanban system
  h) Help
  0) Exit
"""

    HELP_TEXTS = {
        'main': "Quick help: Please read the user manual!",
        'admin': "Quick help: Administrative functions for user management"
    }
    
    # Validation constants
    MIN_PASSWORD_LENGTH = 8
    STATUS_OPTIONS = {
        1: "To-Do",
        2: "In Progress", 
        3: "Waiting Review",
        4: "Finished"
    }


class InputHandler:
    """Unified input handling with validation and error recovery"""
    
    @staticmethod
    def get_integer_input(prompt: str, error_message: str = "Please enter a valid number") -> Optional[int]:
        """Safely get integer input with error handling"""
        try:
            return int(input(prompt).strip())
        except (ValueError, TypeError):
            print(error_message)
            return None
    
    @staticmethod
    def get_choice_input(valid_choices: List[str], case_sensitive: bool = False) -> str:
        """Get menu choice with validation"""
        choice = input("> ").strip()
        if not case_sensitive:
            choice = choice.lower()
        return choice if choice in valid_choices else ""
    
    @staticmethod
    def confirm_action(message: str) -> bool:
        """Get confirmation from user"""
        response = input(f"{message} (y/N): ").strip().lower()
        return response == 'y'


class UserInputValidator:
    """Centralized input validation for user data"""
    
    @staticmethod
    def validate_phone_number(phone_input: str) -> Optional[int]:
        """Validate and convert phone number input"""
        cleaned = phone_input.strip()
        if not cleaned.isdigit() or len(cleaned) < 10:
            print("Please enter a valid phone number (digits only, min 10 characters)")
            return None
        return int(cleaned)
    
    @staticmethod
    def validate_date(date_str: str) -> Optional[str]:
        """Validate date format and ensure it's not in the past"""
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            if date_obj < datetime.today().date():
                print("Date cannot be in the past")
                return None
            return date_str
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD")
            return None
    
    @staticmethod
    def validate_user_exists(phone_number: int, user_type: str = "user") -> bool:
        """Check if a user exists in the system"""
        if not kdb.CheckUserExist(phone_number):
            print(f"{user_type.capitalize()} does not exist in the system")
            return False
        return True


class MenuCommand:
    """Command pattern implementation for menu actions"""
    
    def __init__(self, name: str, handler: Callable, requires_auth: bool = True):
        self.name = name
        self.handler = handler
        self.requires_auth = requires_auth
    
    def execute(self, *args, **kwargs):
        """Execute the command with error handling"""
        try:
            return self.handler(*args, **kwargs)
        except Exception as e:
            print(f"Error executing {self.name}: {e}")
            return False


class KanbanMenuSystem:
    """Main menu system with improved architecture"""
    
    def __init__(self, data_store: str):
        self.store_path = Path(data_store)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.board = DataStructures.KanbanBoard()
        self.input_handler = InputHandler()
        self.validator = UserInputValidator()
        
        # Initialize menu commands
        self.main_commands = self._initialize_main_commands()
        self.admin_commands = self._initialize_admin_commands()
    
    def _initialize_main_commands(self) -> Dict[str, MenuCommand]:
        """Initialize main menu command mappings"""
        return {
            '0': MenuCommand("Exit", self._exit_system, requires_auth=False),
            '1': MenuCommand("List tasks", self._list_tasks),
            '2': MenuCommand("Add task", self._add_task),
            '3': MenuCommand("Move task", self._move_task),
            '4': MenuCommand("Edit task", self._edit_task),
            '5': MenuCommand("Delete task", self._delete_task),
            '6': MenuCommand("Show task", self._show_task),
            '7': MenuCommand("Advice", self._provide_advice),
            'h': MenuCommand("Help", self._show_help, requires_auth=False)
        }
    
    def _initialize_admin_commands(self) -> Dict[str, MenuCommand]:
        """Initialize admin menu command mappings"""
        return {
            '0': MenuCommand("Exit", self._exit_system, requires_auth=False),
            '1': MenuCommand("Update user status", self._update_user_status),
            '2': MenuCommand("Access Kanban", lambda: self.run_main_menu()),
            'h': MenuCommand("Help", self._show_admin_help, requires_auth=False)
        }
    
    def run_main_menu(self):
        """Main menu interaction loop"""
        while True:
            print(MenuConfig.MENU_SCREENS.strip())
            choice = self.input_handler.get_choice_input(list(self.main_commands.keys()))
            
            if not choice:
                print("Invalid choice. Please select from the menu.")
                continue
            
            command = self.main_commands[choice]
            if command.execute() is False and choice == '0':
                break  # Exit condition
    
    def run_admin_menu(self):
        """Admin menu interaction loop"""
        while True:
            print(MenuConfig.ADMIN_MENU_SCREENS.strip())
            choice = self.input_handler.get_choice_input(list(self.admin_commands.keys()))
            
            if not choice:
                print("Invalid choice. Please select from the menu.")
                continue
            
            command = self.admin_commands[choice]
            if command.execute() is False and choice == '0':
                break
    
    # Command implementations with improved error handling
    def _exit_system(self) -> bool:
        """Handle system exit"""
        print("Logged out successfully.")
        return False  # Signal to break menu loop
    
    def _list_tasks(self) -> bool:
        """List all tasks"""
        try:
            self.board.DisplayBoard()
            return True
        except Exception as e:
            print(f"Error displaying tasks: {e}")
            return False
    
    def _add_task(self) -> bool:
        """Add a new task with comprehensive validation"""
        try:
            # Title validation
            title = input("Title: ").strip()
            if not title:
                print("Title cannot be empty.")
                return False
            
            # Get validated inputs
            status = self._get_status_input(mandatory=True)
            person_in_charge = self._get_person_input("Person in charge", mandatory=True)
            due_date = self._get_due_date_input(mandatory=False)
            creator = self._get_person_input("Creator", mandatory=True)
            additional_info = input("Additional information: ").strip()
            
            if all([status, person_in_charge, creator]):
                self.board.AddTask(title, status, person_in_charge, due_date, creator, additional_info)
                return True
            return False
            
        except Exception as e:
            print(f"Error adding task: {e}")
            return False
    
    def _move_task(self) -> bool:
        """Move task to different status"""
        task_id = self.input_handler.get_integer_input("Task ID: ")
        if task_id is None:
            return False
        
        editor = self._get_person_input("Editor", mandatory=True)
        status = self._get_status_input(mandatory=False, additional_text="Blank: Cancel")
        
        if editor and status:
            self.board.EditTask(task_id, editor, NewStatus=status)
            return True
        return False
    
    def _edit_task(self) -> bool:
        """Edit task with partial updates"""
        task_id = self.input_handler.get_integer_input("Task ID: ")
        if task_id is None:
            return False
        
        editor = self._get_person_input("Editor", mandatory=True)
        if not editor:
            return False
        
        # Collect partial updates
        updates = {}
        title = input("New title (blank to skip): ").strip()
        if title:
            updates['NewTitle'] = title
        
        status = self._get_status_input(mandatory=False, additional_text="Blank: Skip")
        if status:
            updates['NewStatus'] = status
        
        person_in_charge = self._get_person_input("Person in charge", mandatory=False)
        if person_in_charge:
            updates['NewPersonInCharge'] = person_in_charge
        
        due_date = self._get_due_date_input(mandatory=False)
        if due_date:
            updates['NewDueDate'] = due_date
        
        additional_info = input("New additional information (blank to skip): ").strip()
        if additional_info:
            updates['NewAdditionalInfo'] = additional_info
        
        if updates:
            self.board.EditTask(task_id, editor, **updates)
            return True
        
        print("No changes specified.")
        return False
    
    def _delete_task(self) -> bool:
        """Delete one or multiple tasks with confirmation"""
        task_ids_input = input("Task ID(s) (comma-separated for multiple): ").strip()
        task_ids = []
        
        for task_id_str in task_ids_input.split(","):
            task_id = self.input_handler.get_integer_input("", f"Invalid task ID: {task_id_str}")
            if task_id is not None and task_id not in task_ids:
                task_ids.append(task_id)
        
        if not task_ids:
            print("No valid task IDs provided.")
            return False
        
        # Confirmation logic
        if len(task_ids) == 1:
            message = f"Confirm removal of Task {task_ids[0]}?"
        else:
            message = f"Confirm removal of Tasks {', '.join(map(str, task_ids))}?"
        
        if self.input_handler.confirm_action(message):
            for task_id in task_ids:
                self.board.DelTask(task_id)
            return True
        
        print("Deletion cancelled.")
        return False
    
    def _show_task(self) -> bool:
        """Display detailed task information"""
        task_id = self.input_handler.get_integer_input("Task ID: ")
        if task_id is None:
            return False
        
        try:
            task_data = kdb.GetTaskByID(task_id)
            if not task_data:
                print("Task not found.")
                return False
            
            # Reconstruct task object from database data
            task = DataStructures.Task(
                task_data[1], task_data[2], task_data[3], task_data[5], 
                task_data[6], task_data[8], task_data[4], task_data[7], task_data[0]
            )
            task.DisplayTask()
            return True
            
        except (IndexError, TypeError) as e:
            print(f"Error displaying task: {e}")
            return False
    
    def _provide_advice(self) -> bool:
        """Provide system advice based on current state"""
        try:
            task_counts = kdb.CountTask()
            person_counts = kdb.CountTaskByPerson()
            
            self._display_advice_header()
            self._display_status_advice(task_counts)
            self._display_workload_advice(person_counts)
            self._display_advice_footer()
            return True
            
        except Exception as e:
            print(f"Error generating advice: {e}")
            return False
    
    def _update_user_status(self) -> bool:
        """Update user activation status (admin function)"""
        phone_input = input("Phone number: ").strip()
        phone_number = self.validator.validate_phone_number(phone_input)
        
        if phone_number is None or not self.validator.validate_user_exists(phone_number, "user"):
            return False
        
        # Display current user info
        user_info = Database.GetUserByPhone(phone_number)
        print("Current user information:")
        print(user_info)
        
        # Get activation status
        is_active = self.input_handler.get_integer_input(
            "Set activation status (1 for active, 0 for inactive): "
        )
        
        if is_active not in [0, 1]:
            print("Invalid status. Please enter 0 or 1.")
            return False
        
        # Update status
        Database.ChangeActivationStatus(phone_number, is_active)
        print("User status updated successfully.")
        
        # Display updated info
        updated_info = Database.GetUserByPhone(phone_number)
        print("Updated user information:")
        print(updated_info)
        return True
    
    def _show_help(self) -> bool:
        """Display help information"""
        print(MenuConfig.HELP_TEXTS['main'])
        return True
    
    def _show_admin_help(self) -> bool:
        """Display admin help information"""
        print(MenuConfig.HELP_TEXTS['admin'])
        return True
    
    # Enhanced input methods with validation
    def _get_person_input(self, field_name: str, mandatory: bool = True, 
                         default: Optional[str] = None) -> Optional[int]:
        """Get validated person input (phone number)"""
        while True:
            try:
                input_value = input(f"{field_name}: ").strip() or None
                
                if not input_value:
                    if not mandatory:
                        return default
                    print(f"{field_name} cannot be empty.")
                    continue
                
                phone_number = self.validator.validate_phone_number(input_value)
                if phone_number is None:
                    continue
                
                if not self.validator.validate_user_exists(phone_number, field_name.lower()):
                    continue
                
                user_info = kdb.GetUserByPhone(phone_number)
                print(f"{field_name}: {user_info}")
                return phone_number
                
            except Exception as e:
                print(f"Error processing {field_name.lower()} input: {e}")
                return None
    
    def _get_status_input(self, mandatory: bool = True, 
                         additional_text: str = "") -> Optional[str]:
        """Get validated status input"""
        prompt = "New status (1:To-Do 2:In Progress 3:Waiting Review 4:Finished"
        if additional_text:
            prompt += f" {additional_text}"
        prompt += "): "
        
        while True:
            status_input = input(prompt).strip()
            
            if not status_input:
                if not mandatory:
                    return None
                print("Status cannot be empty.")
                continue
            
            status_num = self.input_handler.get_integer_input("", "Invalid status number")
            if status_num is None:
                continue
            
            if status_num in MenuConfig.STATUS_OPTIONS:
                return MenuConfig.STATUS_OPTIONS[status_num]
            
            print("Invalid status. Please choose 1-4.")
    
    def _get_due_date_input(self, mandatory: bool = True, 
                           default: Optional[str] = None) -> Optional[str]:
        """Get validated due date input"""
        while True:
            due_date_input = input("Due date (YYYY-MM-DD): ").strip() or None
            
            if not due_date_input:
                if not mandatory:
                    return default
                print("Due date cannot be empty.")
                continue
            
            validated_date = self.validator.validate_date(due_date_input)
            if validated_date:
                return validated_date
    
    # Advice display helpers
    def _display_advice_header(self):
        """Display advice section header"""
        print("\n" + "-" * 50)
        print(f"{'Advice':^50}")
        print("-" * 50)
    
    def _display_status_advice(self, task_counts: List[int]):
        """Display advice based on task status counts"""
        status_names = ["To-Do", "In Progress", "Waiting Review"]
        advice_given = False
        
        for i, count in enumerate(task_counts[:3]):  # First three statuses
            if count > 10:
                messages = [
                    "Do more tasks!",
                    "Work hard!",
                    "Review tasks!"
                ]
                print(f"Attention: {messages[i]} There are {count} {status_names[i].lower()} tasks!")
                advice_given = True
        
        if not advice_given:
            print("No further advice for task status. Keep going!")
    
    def _display_workload_advice(self, person_counts: Dict[str, int]):
        """Display advice based on person workload"""
        print("-" * 50)
        
        overloaded = [f"{person} ({count} tasks)" 
                     for person, count in person_counts.items() if count > 3]
        underloaded = [f"{person} ({count} task(s))" 
                      for person, count in person_counts.items() if count < 3]
        
        if overloaded:
            print(f"Attention: Too much work for {', '.join(overloaded)}!")
            print("           Try to redistribute tasks!\n")
        else:
            print("No one is overloaded. Keep going!")
        
        if underloaded:
            print(f"Attention: Try to give some tasks to {', '.join(underloaded)}!")
        else:
            print("Attention: No one is available for more tasks!")
    
    def _display_advice_footer(self):
        """Display advice section footer"""
        print("\n" + "-" * 50)


def interactive_menu(store: str):
    """Public interface for main menu (maintains backward compatibility)"""
    menu_system = KanbanMenuSystem(store)
    menu_system.run_main_menu()


def InteractiveMenuAdmin(store: str):
    """Public interface for admin menu (maintains backward compatibility)"""
    menu_system = KanbanMenuSystem(store)
    menu_system.run_admin_menu()


# Maintain legacy function interfaces for backward compatibility
def HandlePersonInChargeInput(Mandatory=True, DefaultResponse="Undecided"):
    menu_system = KanbanMenuSystem("")
    return menu_system._get_person_input("Person in charge", Mandatory, DefaultResponse)


def HandleCreatorInput(Mandatory=True, DefaultResponse="Unknown"):
    menu_system = KanbanMenuSystem("")
    return menu_system._get_person_input("Creator", Mandatory, DefaultResponse)


def HandleEditorInput(Mandatory=True, DefaultResponse="Unknown"):
    menu_system = KanbanMenuSystem("")
    return menu_system._get_person_input("Editor", Mandatory, DefaultResponse)


def HandleStatusInput(Mandatory=True, AdditionalText=""):
    menu_system = KanbanMenuSystem("")
    return menu_system._get_status_input(Mandatory, AdditionalText)


def HandleDueDateInput(Mandatory=True, DefaultResponse=None):
    menu_system = KanbanMenuSystem("")
    return menu_system._get_due_date_input(Mandatory, DefaultResponse)


# Main execution block
if __name__ == "__main__":
    try:
        # Example usage
        interactive_menu("~/.kanban/board.json")
    except KeyboardInterrupt:
        print("\nApplication terminated by user.")
    except Exception as e:
        print(f"Unexpected error: {e}")
