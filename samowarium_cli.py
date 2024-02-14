import samoware_client
from getpass import getpass

# login
login_str = input("enter login: ")
password_str = getpass("enter password: ")
session = samoware_client.login(login_str, password_str)

samoware_client.openInbox(session)

# getMails
count = int(input("how many emails to list: "))
mails = samoware_client.getMails(session,0,count-1)
for mail in mails:
    print(mail)

# getMail
uid = int(input("uid of email to print: "))
print(samoware_client.getMailById(session,uid))

# longPollUpdates
print("now longpolling new mails...")
print("new mail will get printed automatically.")
ackSeq = 0
while True:
    ackSeq, update = samoware_client.longPollUpdates(session,ackSeq)
    print("update string: "+update)
    # TODO сделать UpdateType или типо того, чтобы не сравнивать строки
    if("INBOX-MM-1" in update):
        print("new mails arrived:")
        newMails = samoware_client.getNewMails(session)
        for mail in newMails:
            print("mail info:")
            print(mail)
            print("mail text:")
            print(samoware_client.getMailById(session,mail["uid"]))