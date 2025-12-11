import sqlite3
from pathlib import Path
import bcrypt

DB_PATH = Path("users.db")

def InitDB():
    Connection = sqlite3.connect(DB_PATH)
    Connection.execute("""
        CREATE TABLE IF NOT EXISTS USER (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            PhoneNo INTEGER NOT NULL UNIQUE,
            Name VARCHAR2(100) NOT NULL,
            IsActive INTEGER NOT NULL DEFAULT 1,
            Position VARCHAR2(50) NOT NULL,
            PasswordHash TEXT NOT NULL
        )
    """)
    Connection.commit()
    Connection.close()

def DisplayData(row) -> dict:
    if row is None:
        return None
    return {
        "ID": row[0],
        "Phone number": row[1],
        "Name": row[2],
        "Activation status": row[3],
        "Position": row[4],
        "PasswordHash": row[5],
    }

def HashPassword(password: str) -> str:
    pw_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pw_bytes, salt)
    return hashed.decode("utf-8")

def VerifyPassword(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False

def CreateUser(PhoneNo: int, Name: str, Position: str, Password: str):
    PasswordHash = HashPassword(Password)
    Connection = sqlite3.connect(DB_PATH)
    try:
        Connection.execute("INSERT INTO USER (PhoneNo, Name, Position, PasswordHash) VALUES (?, ?, ?, ?)", (PhoneNo, Name, Position, PasswordHash))
        Connection.commit()
    except sqlite3.IntegrityError:
        raise ValueError("Phone number already exists")
    finally:
        Connection.close()

def GetUserByPhone(PhoneNo: int):
    Connection = sqlite3.connect(DB_PATH)
    Query = Connection.execute("SELECT * FROM USER WHERE PhoneNo = ?", (PhoneNo,))
    Data = Query.fetchone()
    Connection.close()
    return DisplayData(Data)

def ValidateLogin(PhoneNo: int, Password: str) -> dict | None:
    User = GetUserByPhone(PhoneNo)
    if not User:
        return None
    if not User.get("IsActive", 1):
        return None
    if not User.get("PasswordHash"):
        return None
    if VerifyPassword(Password, User["PasswordHash"]):
        return User
    return None