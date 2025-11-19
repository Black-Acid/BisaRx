from passlib.context import CryptContext

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

# print(pwd.hash("string"))
print(pwd.hash("test123"))
