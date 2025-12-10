import DataStructures
from pathlib import Path
import argparse


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

HELP_TEXT = """
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
            return

        elif choice == "1":
            #List tasks
            board.DisplayBoard()

        elif choice == "2":
            #Add task
            Title = input("Title: ").strip()
            StatusInput = int(input("Status (1: To-Do 2: In Progress 3: Waiting Review 4: Finished): ").strip())
            if StatusInput == 1:
                Status = "To-Do"
            elif StatusInput == 2:
                Status = "In Progress"
            elif StatusInput == 3:
                Status = "Waiting Review"
            elif StatusInput == 4:
                Status = "Finished"
            else:
                print("Status is not valid")
                continue
            PersonInCharge = input("Person in charge: ").strip()
            DueDateInput = input("Due date (YYYY-MM-DD): ").strip()
            parts = DueDateInput.split("-")
            if (len(parts) == 3 and
                parts[0].isdigit() and len(parts[0]) == 4 and  # Year
                parts[1].isdigit() and len(parts[1]) == 2 and  # Month
                parts[2].isdigit() and len(parts[2]) == 2):    # Day
                DueDate = DueDateInput
            else:
                print("Invalid date format.")
                continue
            Creator = input("Creator: ").strip()
            AdditionalInfo = input("Additional information: ").strip()
            board.AddTask(Title, Status, PersonInCharge, DueDate, Creator, AdditionalInfo)

        elif choice == "3":
            #Move task

            return

        elif choice == "4":
            #Edit task
            DisplayTaskID = int(input("Task ID: ").strip())
            Editor = input("Name of Editor: ").strip()
            Title = input("New title (blank to skip): ").strip() or None
            StatusInput = int(input("New status (1: To-Do 2: In Progress 3: Waiting Review 4: Finished Blank: Skip): ").strip()) or None
            if StatusInput == 1:
                Status = "To-Do"
            elif StatusInput == 2:
                Status = "In Progress"
            elif StatusInput == 3:
                Status = "Waiting Review"
            elif StatusInput == 4:
                Status = "Finished"
            else:
                print("Status is not valid")
                continue
            PersonInCharge = input("New person in charge (blank to skip): ").strip() or None
            DueDateInput = input("New due date (YYYY-MM-DD) (blank to skip): ").strip()
            parts = DueDateInput.split("-")
            if (len(parts) == 3 and
                parts[0].isdigit() and len(parts[0]) == 4 and  # Year
                parts[1].isdigit() and len(parts[1]) == 2 and  # Month
                parts[2].isdigit() and len(parts[2]) == 2):    # Day
                DueDate = DueDateInput
            else:
                print("Invalid date format.")
                continue
            AdditionalInfo = input("New additional information (blank to skip): ").strip() or None
            
            #Increment TaskID to be more consistent to the display (ID displayed in List tasks: 1, actual internal ID: 0)
            TaskID = DisplayTaskID + 1
            board.EditTask(TaskID, Editor, NewTitle=Title, NewStatus=Status, NewPersonInCharge=PersonInCharge, NewDueDate=DueDate, NewAdditionalInfo=AdditionalInfo)

        elif choice == "5":
            #Delete task
            TaskID = int(input("Task ID: ").strip())
            Confirm = input(f"Confirm remove {TaskID}? (y/N): ").strip().lower()
            if Confirm == "y":
                board.DelTask(TaskID)
            else: print("Cancelled.")

        elif choice == "6":
            #Show task
            TaskID = int(input("Task ID: ").strip())
            board.tasks[TaskID-1].DisplayTask()
        
        elif choice == "7":
            #Advise
            return

        elif choice == "h":
            print(HELP_TEXT.strip())

        else:
            print("Invalid choice. Please enter a number from the menu.")


***
def main(argv=None):
        try:
            interactive_menu("~/.kanban/board.json")
        except KeyboardInterrupt:
            print("\nBye.")
        return

if __name__ == "__main__":
    main()
***
