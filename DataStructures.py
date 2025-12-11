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
    
    def DisplayTask(self):
        print("\n" + "-"*50)
        print(f"Task: {self.title}")
        print("-"*50)
        print(f"Status: {self.Status} \nAssigned to: {self.PersonInCharge} \nCreationTime: {self.FormatDate(self.CreationDate)} \nDue: {self.DueDate} \nCreated by: {self.Creator} \nEditors: {self.Editors} \nAdditional Info: {self.AdditionalInfo}")
        print("\n" + "-"*50)
    
    def __str__(self):
        # Reformat CreationDate
        CreationDateReformat = self.FormatDate(self.CreationDate)

        return f"Task: {self.title}, Status: {self.Status}, Assigned to: {self.PersonInCharge}, CreationTime: {CreationDateReformat}, Due: {self.DueDate}, Created by: {self.Creator}, Editors: {self.Editors}, Additional Info: {self.AdditionalInfo}"

class KanbanBoard:
    def __init__(self):
        self.tasks = []
        self.ValidStatus = ["To-Do", "In Progress", "Waiting Review", "Finished"]

    def AddTask(self, Title, Status, PersonInCharge, DueDate, Creator, AdditionalInfo):
        if Status in self.ValidStatus:
            self.tasks.append(Task(Title, Status, PersonInCharge, DueDate, Creator, AdditionalInfo))
            print(f"Added: {Title}")
        else:
            print("Add Task Failed: Status is not valid")

    def EditTask(self, index, Editor, NewTitle=None, NewStatus=None, NewPersonInCharge=None, NewDueDate=None, NewAdditionalInfo=None):
        try:
            task = self.tasks[index]
            task.Editors.append(Editor)  # Track who edited the task
            
            if NewTitle:
                task.title = NewTitle
            if NewStatus:
                if NewStatus in self.ValidStatus:
                    task.Status = NewStatus
                else:
                    print("Edit Task Failed: Status is not valid")
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
        # Sort tasks by due date
        sorted_tasks = sorted(self.tasks, key=lambda x: x.DueDate)

        # Group tasks by status
        grouped_tasks = {status: [] for status in self.ValidStatus}

        for task in sorted_tasks:
            grouped_tasks[task.Status].append(task)

        print("\n" + "-"*50)
        print(f"{'Kanban Board':^50}")
        print("-"*50)

        for status in self.ValidStatus:
            if grouped_tasks[status]: 
                print(f"\n{status.upper()}:")
                for task in grouped_tasks[status]:
                    print(f" - Task {self.tasks.index(task)}: {task.title} (Due: {task.DueDate}, Assigned to: {task.PersonInCharge})")

        print("\n" + "-"*50)
