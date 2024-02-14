import client
from getpass import getpass

# login
login_str = input("enter login: ")
password_str = getpass("enter password: ")
client.login(login_str, password_str)

client.openInbox()

# getMails
count = int(input("how many emails to list: "))
mails = client.getMails(0,count-1)
for mail in mails:
    print(mail)

# getMail
uid = int(input("uid of email to print: "))
print(client.getMailById(uid))

# longPollUpdates
print("now longpolling new mails...")
print("new mail will get printed automatically.")
ackSeq = 0
while True:
    ackSeq, update = client.longPollUpdates(ackSeq)
    print(ackSeq, update)
    # TODO сделать UpdateType или типо того, чтобы не сравнивать строки
    if("INBOX-MM-1" in update):
        print("new mails arrived:")
        newMails = client.getNewMails()
        for mail in newMails:
            print("mail info:")
            print(mail)
            print("mail text:")
            print(client.getMailById(mail["uid"]))