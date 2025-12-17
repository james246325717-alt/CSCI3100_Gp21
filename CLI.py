import DataStructures
from pathlib import Path
import Database
import KanbanInfoDatabase as kdb

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

HELP_TEXT = """
Quick help: Please read the user manual!

"""

ADMIN_HELP_TEXT = """
Quick help:

"""

def interactive_menu(store: str):
    store_path = Path(store)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    board = DataStructures.KanbanBoard()

    while True:
        print(MENU_SCREENS.strip())
        choice = input("> ").strip()

        if choice == "0":
            print("Logged out.")
            break
            # return

        elif choice == "1":
            #List tasks
            board.DisplayBoard()

        elif choice == "2":
            #Add task
            Title = input("Title: ").strip()
            if not Title:
                print("Title cannot be empty.")
                continue
            Status = HandleStatusInput(Mandatory=True)
            while True:
                try:
                    PersonInCharge = int(input("Person in charge: ").strip())
                except(ValueError):
                    print("Please enter a valid phone number.")
                    continue
                if kdb.CheckUserExist(PersonInCharge):
                    break
                print("Person in charge does not exist.")
            print(f"Pperson in charge: {kdb.GetUserByPhone(PersonInCharge)}")
            DueDate = HandleDueDateInput(DefaultResponse="Undecided", Mandatory=False)
            while True:
                try:
                    Creator = int(input("Creator: ").strip())
                except(ValueError):
                    print("Please enter a valid phone number.")
                    continue
                if kdb.CheckUserExist(Creator):
                    break
                print("Creator does not exist.")
            print(f"Creator: {kdb.GetUserByPhone(Creator)}")
            AdditionalInfo = input("Additional information: ").strip()
            board.AddTask(Title, Status, PersonInCharge, DueDate, Creator, AdditionalInfo)

        elif choice == "3":
            #Move task
            try:
                TaskID = int(input("Task ID: ").strip())
            except(ValueError):
                print("Please enter a valid number.")
                continue
            Editor = HandleEditorInput(Mandatory=True)
            print(f"Editor: {kdb.GetUserByPhone(Editor)}")
            Status = HandleStatusInput(AdditionalText=" Blank: Cancel", Mandatory=False)

            board.EditTask(TaskID, Editor, NewStatus=Status)

        elif choice == "4":
            #Edit task
            try:
                TaskID = int(input("Task ID: ").strip())
            except(ValueError):
                print("Please enter a valid number.")
                continue
            Editor = HandleEditorInput(Mandatory=True)
            print(f"Editor: {kdb.GetUserByPhone(Editor)}")
            Title = input("New title (blank to skip): ").strip() or None
            Status = HandleStatusInput(AdditionalText=" Blank: Skip", Mandatory=False)
            while True:
                PersonInCharge = int(input("Person in charge: ").strip())
                if kdb.CheckUserExist(PersonInCharge):
                    break
                print("Person in charge does not exist.")
            DueDate = HandleDueDateInput(DefaultResponse=None, Mandatory=False)
            AdditionalInfo = input("New additional information (blank to skip): ").strip() or None
            board.EditTask(TaskID, Editor, NewTitle=Title, NewStatus=Status, NewPersonInCharge=PersonInCharge, NewDueDate=DueDate, NewAdditionalInfo=AdditionalInfo)

        elif choice == "5":
            #Delete task
            TaskIDInput = (input("Task ID(s) (comma-separated for multiple): ").strip())
            IDList = [i.strip() for i in TaskIDInput.split(",")]
            TaskIDs = []
            for i in IDList:
                try:
                    if (i not in TaskIDs):
                        TaskID = int(i)
                        TaskIDs.append(i)
                except(ValueError):
                    print("Please enter a valid number")
                    continue
            if (len(TaskIDs) == 1):
                ConfirmMessage = f"Confirm remove Task {TaskIDs[0]}? (y/N): "
            else:
                IDDisplay = ", ".join(map(str, TaskIDs))
                ConfirmMessage = f"Confirm remove Tasks {IDDisplay}? (y/N): "
            Confirm = input(ConfirmMessage).strip().lower()
            if Confirm == "y":
                for TaskID in TaskIDs:
                    board.DelTask(TaskID)
            else: print("Cancelled.")

        elif choice == "6":
            #Show task
            try:
                TaskID = int(input("Task ID: ").strip())
            except(ValueError):
                print("Please enter a valid number")
                continue
            try:
                Temp = kdb.GetTaskByID(TaskID)
                task = DataStructures.Task(Temp[1], Temp[2], Temp[3], Temp[5], Temp[6], Temp[8], Temp[4], Temp[7], Temp[0])
                task.DisplayTask()
            except(IndexError):
                print("Task not found.")
        
        elif choice == "7":
            #Advise
            CountTask = kdb.CountTask()
            print("\n" + "-"*50)
            print(f"{'Advice':^50}")
            print("-"*50)
            if CountTask[0] > 10:
                print(f"Attention: Do more tasks! There are {CountTask[0]} to-do Tasks!")
            if CountTask[1] > 10:
                print(f"Attention: Work hard! There are {CountTask[1]} tasks in progress!")
            if CountTask[2] > 10:
                print(f"Attention: Review Tasks! There are {CountTask[2]} tasks waiting for review!")
            if CountTask[0] <= 10 and CountTask[0] <= 10 and CountTask[0] <= 10:
                print("No further advice for Task Status. Keep Going!")
            CountTaskByPerson = kdb.CountTaskByPerson()
            OverLoadedPeople = [f"{key} ({value} Tasks)" for key, value in CountTaskByPerson.items() if value > 3]
            ChillPeople = [f"{key} ({value} Task(s))" for key, value in CountTaskByPerson.items() if value < 3]
            print("-"*50)
            if OverLoadedPeople:
                print(f"Attention: Too much work for {', '.join(OverLoadedPeople)}!\n           Try to re-distribute tasks!\n")
            else:
                print("No one is overloaded. Keep going!")
            if ChillPeople:
                print(f"Attention: Try to give some tasks to {', '.join(ChillPeople)}!")
            else:
                print("Attention: No one is available for more tasks!")
            print("\n" + "-"*50)

        elif choice == "h":
            print(HELP_TEXT.strip())

        else:
            print("Invalid choice. Please enter a number from the menu.")

def InteractiveMenuAdmin(store: str):

    while True:
        print(ADMIN_MENU_SCREENS.strip())
        choice = input("> ").strip()

        if choice == "0":
            print("Logged out.")
            break
            # return

        elif choice == "1":
            #Update user activation status
            print("Please enter the phone number of the user.")
            PhoneNo = int(input("Phone number: ").strip())
            print("The information of the user is as follow:")
            print(Database.GetUserByPhone(PhoneNo))
            while True:
                IsActive = int(input("Please set the activation status of the user (1 for active, 0 otherwise) :").strip())
                if IsActive == 1 or IsActive == 0:
                    break
                print("Invalid input.")
            Database.ChangeActivationStatus(PhoneNo, IsActive)
            print("The information has been updated.")
            print(Database.GetUserByPhone(PhoneNo))

            
        elif choice == "2":
            #Access Kanban system
            interactive_menu(store)

        elif choice == "h":
            print(ADMIN_HELP_TEXT.strip())

        else:
            print("Invalid choice. Please enter a number from the menu.")

def HandleEditorInput(Mandatory=True):
    # Todo: Don't show Editor's name as None if Mandatory is False, instead show latest editor's name
    while True:
        Editor = input("Phone number of Editor: ").strip() or None
        if not Editor and Mandatory:
            print("Editor cannot be empty.")
        elif not Mandatory:
            break
        elif kdb.CheckUserExist(Editor):
            return Editor
        else:
            print("Editor does not exist.")

def HandleStatusInput(Mandatory=True, AdditionalText=""):
    while True:  
        StatusInput = input(f"New status (1: To-Do 2: In Progress 3: Waiting Review 4: Finished{AdditionalText}): ").strip()
        if not Mandatory and not StatusInput:
            return None
        if Mandatory and not StatusInput:
            print("Status cannot be empty")
            continue
        try:
            StatusNum = int(StatusInput)
            if StatusNum == 1:
                return "To-Do"
            elif StatusNum == 2:
                return "In Progress"
            elif StatusNum == 3:
                return "Waiting Review"
            elif StatusNum == 4:
                return "Finished"
            else:
                print("Status is not valid.")
        except ValueError:
            print("Please enter a valid number.")

def HandleDueDateInput(Mandatory=True, DefaultResponse=None):
    #Todo: Add validation for real calendar date?
    while True:
        DueDateInput = input("Due date (YYYY-MM-DD): ").strip() or None
        if DueDateInput:
            parts = DueDateInput.split("-")
            if (len(parts) == 3 and
                parts[0].isdigit() and len(parts[0]) == 4 and  # Year
                parts[1].isdigit() and len(parts[1]) == 2 and  # Month
                parts[2].isdigit() and len(parts[2]) == 2):    # Day
                return DueDateInput
            else:
                print("Invalid date format.")
        elif not Mandatory:
            return DefaultResponse

"""
def main(argv=None):
        try:
            interactive_menu("~/.kanban/board.json")
        except KeyboardInterrupt:
            print("\nBye.")
        return

if __name__ == "__main__":
    main()
"""
