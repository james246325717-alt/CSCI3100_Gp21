#Internal Messages: Editors and Creators are not fully implemented, also check ToDo by ctrl+F
# All print functions are just temporary, need to be modified after implementing User Interface

from datetime import datetime as dt

class Task:
    def __init__(self, Title, Status, PersonInCharge, DueDate, Creator, AdditionalInfo):
        self.title = Title
        self.Status = Status
        self.PersonInCharge = PersonInCharge
        self.CreationDate = dt.now()
        self.DueDate = DueDate
        self.Creator = Creator
        self.Editors = []
        self.AdditionalInfo = AdditionalInfo

    # Format date to prevent showing microseconds
    def FormatDate(self, date_obj):
        if isinstance(date_obj, str):
            return date_obj
        return date_obj.strftime("%Y-%m-%d %H:%M:%S")
    
    def __str__(self):
        # Reformat CreationDate
        CreationDateReformat = self.FormatDate(self.CreationDate)

        return f"Task: {self.title}, Status: {self.Status}, Assigned to: {self.PersonInCharge}, CreationTime: {CreationDateReformat}, Due: {self.DueDate}, Created by: {self.Creator}, Editors: {self.Editors}, Additional Info: {self.AdditionalInfo}"

class KanbanBoard:
    def __init__(self):
        self.tasks = []

    def AddTask(self, Title, Status, PersonInCharge, DueDate, Creator, AdditionalInfo):
        self.tasks.append(Task(Title, Status, PersonInCharge, DueDate, Creator, AdditionalInfo))
        print(f"Added: {Title}")

    def EditTask(self, index, Editor, NewTitle=None, NewStatus=None, NewPersonInCharge=None, NewDueDate=None, NewAdditionalInfo=None):
        try:
            task = self.tasks[index]
            task.Editors.append(Editor)  # Track who edited the task
            
            if NewTitle:
                task.title = NewTitle
            if NewStatus:
                task.Status = NewStatus
            if NewPersonInCharge:
                task.PersonInCharge = NewPersonInCharge
            if NewDueDate:
                task.DueDate = NewDueDate
            if NewAdditionalInfo:
                task.AdditionalInfo = NewAdditionalInfo

            print(f"Task updated: {task.title}")
        except IndexError:
            print("Task not found.")

    def DelTask(self, index):
        try:
            removed_task = self.tasks.pop(index)
            print(f"Deleted: {removed_task.title}")
        except IndexError:
            print("Task not found.")

    def DisplayBoard(self):
        print("\nKanban Board:")
        for idx, task in enumerate(self.tasks):
            print(f"{idx + 1}: {task}")

if __name__ == "__main__":
    kanban_board = KanbanBoard()
    kanban_board.AddTask("Implement user login", "In Progress", "Alice", "2025-12-31", "Bob", "User should be able to log in")
    kanban_board.AddTask("Fix bugs in API", "To Do", "Charlie", "2025-12-20", "David", "Fix all known bugs")
    kanban_board.DisplayBoard()

    # Edit a task
    kanban_board.EditTask(0, "Roland", NewStatus="Completed", NewAdditionalInfo="User login implemented successfully")
    kanban_board.DisplayBoard()

    kanban_board.EditTask(0, "John", NewStatus="Completed", NewAdditionalInfo="User login implemented successfully")
    kanban_board.DisplayBoard()

    kanban_board.EditTask(0, "Roland", NewStatus="Completed", NewAdditionalInfo="User login implemented successfully")
    kanban_board.DisplayBoard()

    # Delete a task
    kanban_board.DelTask(1)
    kanban_board.DisplayBoard()