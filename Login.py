import Database
# import CLI


LOGIN_PAGE = """
Kanban System Login Page
Choose an option by number:
  1) Log in
  2) Register
  h) Help
  0) Exit
"""

HELP_TEXT = """
Quick help:
- Register: enter your phone, name, position, and a password (typed twice).
- Log in: use your phone number and password.
"""

def Login():

    Database.InitDB()

    while True:
        print(LOGIN_PAGE.strip())
        choice = input("> ").strip()

        if choice == "0":
            print("Thank you for using our system.")
            return

        elif choice == "1":
            # Login
            PhoneNo = int(input("Phone number: ").strip())
            Password = input("Password: ").strip()
            User = Database.ValidateLogin(PhoneNo, Password)
            if User:
                print(f"Login successfully.")
                # CLI.interactive_menu("~/.kanban/board.json")
                return
            else:
                print("Invalid phone number or password, or your account is inactive.")

        elif choice == "2":
            # Register
            PhoneNo = int(input("Phone number: ").strip())
            Name = input("Name: ").strip()
            Position = input("Position: ").strip()
            Password = PasswordInput()
            Database.CreateUser(PhoneNo, Name, Position, Password)
            print(Database.GetUserByPhone(PhoneNo))

        elif choice == "h":
            print(HELP_TEXT.strip())

        else:
            print("Invalid choice. Please enter a number from the menu.")

def PasswordInput():
    while True:
        pw1 = input("Password: ").strip()
        pw2 = input("Confirm password: ").strip()
        if pw1 != pw2:
            print("Passwords do not match. Please try again.")
            continue
        if len(pw1) < 8:
            print("Password too short (min 8 chars). Please try again.")
            continue
        return pw1

# """
def main(argv=None):
        try:
            Login()
        except KeyboardInterrupt:
            print("\nBye.")
        return

if __name__ == "__main__":
    main()
# """
