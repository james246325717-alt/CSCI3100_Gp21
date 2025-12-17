import sqlite3
from pathlib import Path

DB_PATH = Path("kanban.db")

def InitDB():
    Connection = sqlite3.connect(DB_PATH)
    Connection.execute("PRAGMA foreign_keys = ON")
    Connection.execute("""
        CREATE TABLE IF NOT EXISTS KANBAN (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Title TEXT NOT NULL,
            Status TEXT NOT NULL,
            PersonInCharge INTEGER NOT NULL,
            CreationDate TEXT NOT NULL,
            DueDate TEXT NOT NULL,           
            Creator INTEGER NOT NULL,
            Editors INTEGER,
            AdditionalInfo TEXT,
            FOREIGN KEY (PersonInCharge) REFERENCES USER(PhoneNo) ON UPDATE CASCADE ON DELETE RESTRICT,
            FOREIGN KEY (Creator) REFERENCES USER(PhoneNo) ON UPDATE CASCADE ON DELETE RESTRICT
            )
    """)
    Connection.commit()
    Connection.close()

def FormatDate(date_obj):                
    if isinstance(date_obj, str):
        return date_obj
    return date_obj.strftime("%Y-%m-%d %H:%M:%S")

def DisplayData(row) -> dict:
    #For testing only, not used
    if row is None:
        return None
    PIC = GetUserByPhone(row[3])
    Creator = GetUserByPhone(row[6])
    Editor = GetUserByPhone(row[7])
    return {
        "ID": row[0],
        "Title": row[1],
        "Status": row[2],
        "Person in Charge": PIC,
        "Creation Date": (row[4]),
        "Duedate": row[5],
        "Creator": Creator,
        "Editors": Editor,
        "Additional Info": row[8]
    }

def AddTask(Title, Status, PersonInCharge, CreationDate, DueDate, Creator, AdditionalInfo):
    Connection = sqlite3.connect(DB_PATH)
    Connection.execute("INSERT INTO KANBAN (Title, Status, PersonInCharge, CreationDate, DueDate, Creator, AdditionalInfo) VALUES (?, ?, ?, ?, ?, ?, ?)", (Title, Status, PersonInCharge, FormatDate(CreationDate), DueDate, Creator, AdditionalInfo))
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
    return [[Datum[0], Datum[1], Datum[2], Datum[3], Datum[4], Datum[5], Datum[6], Datum[7], Datum[8]] for Datum in Data]

def GetTaskByID(TaskID):
    Connection = sqlite3.connect(DB_PATH)
    Query = Connection.execute("SELECT * FROM KANBAN WHERE ID = ?", (TaskID,))
    Data = Query.fetchone()
    Connection.close()
    return [Data[0], Data[1], Data[2], Data[3], Data[4], Data[5], Data[6], Data[7], Data[8]]

def GetUserByPhone(PhoneNo: int):
    Connection = sqlite3.connect(DB_PATH)
    Query = Connection.execute("SELECT PhoneNo, Name FROM User WHERE PhoneNo = ?", (PhoneNo,))
    Data = Query.fetchone()
    Connection.close()
    return [Data[1]] if Data else None

def CheckUserExist(PhoneNo: int):
    Connection = sqlite3.connect(DB_PATH)
    Query = Connection.execute("SELECT * FROM User WHERE PhoneNo = ?", (PhoneNo,))
    Data = Query.fetchone()
    Connection.close()
    return True if Data else False

def GetTaskByPIC():
    Connection = sqlite3.connect(DB_PATH)
    Query = Connection.execute("SELECT KANBAN.ID, KANBAN.Title, KANBAN.Status, USER.Name, KANBAN.CreationDate, KANBAN.DueDate, KANBAN.Creator, KANBAN.Editors, KANBAN.AdditionalInfo FROM KANBAN, USER WHERE USER.ID = KANBAN.PersonInCharge")
    Data = Query.fetchone()
    Connection.close()
    print(Data)
    return [[Datum[0], Datum[1], Datum[2], Datum[3], Datum[4], Datum[5], Datum[6], Datum[7], Datum[8]] for Datum in Data]