from datetime import datetime as dt
import KanbanInfoDatabase as kdb

class Task:
    def __init__(self, Title, Status, PersonInCharge, DueDate, Creator, AdditionalInfo,  CreationDate = None, Editors = None, ID = None):
        self.title = Title
        self.Status = Status
        self.PersonInCharge = PersonInCharge
        self.CreationDate = dt.now() if CreationDate == None else CreationDate
        self.DueDate = DueDate
        self.Creator = Creator
        self.Editors = Editors
        self.AdditionalInfo = AdditionalInfo
        self.ID = ID

    # Format date to prevent showing microseconds
    def FormatDate(self, date_obj):
        if isinstance(date_obj, str):
            return date_obj
        return date_obj.strftime("%Y-%m-%d %H:%M:%S")
    
    def DisplayTask(self):
        print("\n" + "-"*50)
        print(f"Task {self.ID}: {self.title}")
        print("-"*50)
        print(f"Status: {self.Status} \nAssigned to: {kdb.GetUserByPhone(self.PersonInCharge)} \nCreationTime: {self.FormatDate(self.CreationDate)} \nDue: {self.DueDate} \nCreated by: {kdb.GetUserByPhone(self.Creator)} \nEditors: {kdb.GetUserByPhone(self.Editors)} \nAdditional Info: {self.AdditionalInfo}")
        print("\n" + "-"*50)
    
    def __str__(self):
        # Reformat CreationDate
        CreationDateReformat = self.FormatDate(self.CreationDate)

        return f"Task: {self.title}, Status: {self.Status}, Assigned to: {self.PersonInCharge}, CreationTime: {CreationDateReformat}, Due: {self.DueDate}, Created by: {self.Creator}, Editors: {self.Editors}, Additional Info: {self.AdditionalInfo}"

class KanbanBoard:
    def __init__(self):
        kdb.InitDB()
        self.ValidStatus = ["To-Do", "In Progress", "Waiting Review", "Finished"]

    def AddTask(self, Title, Status, PersonInCharge, DueDate, Creator, AdditionalInfo):
        if Status in self.ValidStatus:
            task = Task(Title, Status, PersonInCharge, DueDate, Creator, AdditionalInfo)
            kdb.AddTask(Title, Status, PersonInCharge, task.CreationDate, DueDate, Creator, AdditionalInfo)
            print(f"Added: {Title}")
        else:
            print("Add Task Failed: Status is not valid")

    def EditTask(self, index, Editor, NewTitle=None, NewStatus=None, NewPersonInCharge=None, NewDueDate=None, NewAdditionalInfo=None):
        try:
            Temp = kdb.GetTaskByID(index)
            task = Task(Temp[1], Temp[2], Temp[3], Temp[5], Temp[6], Temp[8], Temp[4])
            task.Editors = Editor
            
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
            kdb.EditTask(index, task.title, task.Status, task.PersonInCharge, task.DueDate, task.Editors, task.AdditionalInfo)
            print(f"Task updated: {task.title}")
        except (IndexError, TypeError):
            print("Task not found.")

    def DelTask(self, index):
        try:
            Temp = kdb.GetTaskByID(index)
            removed_task = Task(Temp[1], Temp[2], Temp[3], Temp[5], Temp[6], Temp[8], Temp[4])
            kdb.DelTask(index)
            print(f"Deleted: {removed_task.title}")
        except (IndexError, TypeError):
            print("Task not found.")

    def DisplayBoard(self):
        temp = kdb.GetAllTasks()
        tasks = []
        for i in temp:
            tasks.append(Task(i[1], i[2], i[3], i[5], i[6], i[8], i[4], i[7], i[0]))
        # Sort tasks by due date
        sorted_tasks = sorted(tasks, key=lambda x: x.DueDate)

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
                    print(f" - Task {task.ID}: {task.title} (Due: {task.DueDate}, Assigned to: {kdb.GetUserByPhone(task.PersonInCharge)})")

        print("\n" + "-"*50)
