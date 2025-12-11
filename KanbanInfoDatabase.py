import sqlite3
from pathlib import Path

DB_PATH = Path("kanban.db")

def InitDB():
    Connection = sqlite3.connect(DB_PATH)
    Connection.execute("""
        CREATE TABLE IF NOT EXISTS KANBAN (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Title TEXT NOT NULL,
            Status TEXT NOT NULL,
            PersonInCharge TEXT NOT NULL,
            CreationDate TEXT NOT NULL,
            DueDate TEXT NOT NULL,           
            Creator TEXT NOT NULL,
            Editors TEXT,
            AdditionalInfo TEXT
            )
    """)
    Connection.commit()
    Connection.close()

def DisplayData(row) -> dict:
    if row is None:
        return None
    return {
        "ID": row[0],
        "Title": row[1],
        "Status": row[2],
        "Person in Charge": row[3],
        "Creation Date": row[4],
        "Duedate": row[5],
        "Creator": row[6],
        "Editors": row[7],
        "Additional Info": row[8]
    }

def AddTask(Title, Status, PersonInCharge, CreationDate, DueDate, Creator, AdditionalInfo):
    Connection = sqlite3.connect(DB_PATH)
    Connection.execute("INSERT INTO KANBAN (Title, Status, PersonInCharge, CreationDate, DueDate, Creator, AdditionalInfo) VALUES (?, ?, ?, ?, ?, ?, ?)", (Title, Status, PersonInCharge, CreationDate, DueDate, Creator, AdditionalInfo))
    Connection.commit()
    Connection.close()

def DelTask(TaskID):
    Connection = sqlite3.connect(DB_PATH)
    Connection.execute("DELETE FROM KANBAN WHERE ID = ?", (TaskID,))
    Connection.commit()
    Connection.close()

def EditTask(TaskID, NewTitle, NewStatus, NewPersonInCharge, NewDueDate, Editors, NewAdditionalInfo):
    Connection = sqlite3.connect(DB_PATH)
    Connection.execute("UPDATE KANBAN SET Title = ?, Status = ?, PersonInCharge = ?, DueDate = ?, Editors = ?, AdditionalInfo = ? WHERE ID = ? ", (NewTitle, NewStatus, NewPersonInCharge, NewDueDate, Editors, NewAdditionalInfo, TaskID))
    Connection.commit()
    Connection.close()

def GetAllTasks():
    Connection = sqlite3.connect(DB_PATH)
    Query = Connection.execute("SELECT * FROM KANBAN")
    Data = Query.fetchall()
    Connection.close()
    return [DisplayData(Datum) for Datum in Data]

def GetTaskByID(TaskID):
    Connection = sqlite3.connect(DB_PATH)
    Query = Connection.execute("SELECT * FROM KANBAN WHERE ID = ?", (TaskID,))
    Data = Query.fetchone()
    Connection.close()
    return DisplayData(Data)

