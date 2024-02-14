import client
from getpass import getpass

login_str = input("enter login: ")
password_str = getpass("enter password: ")
client.login(login_str, password_str)

client.openInbox()

count = int(input("how many emails to list: "))
mails = client.getMails(0,count-1)
for mail in mails:
    print(mail)

uid = int(input("uid of email to print: "))
print(client.getMail(uid))