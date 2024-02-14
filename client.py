import requests
import xml.etree.ElementTree as ET

request_id = 0
command_id = 0
rand = 0
session = ""

def nextRequestId():
    global request_id
    request_id += 1
    return request_id

def nextCommandId():
    global command_id
    command_id += 1
    return command_id

def nextRand():
    global rand
    rand += 1
    return rand

def login(login, password):
    global session
    response = requests.get(f"https://mailstudent.bmstu.ru/XIMSSLogin/?errorAsXML=1&EnableUseCookie=1&x2auth=1&canUpdatePwd=1&version=6.1&userName={login}&password={password}")
    tree = ET.ElementTree(ET.fromstring(response.text))
    session = tree.find("session").attrib['urlID']

def openInbox():
    global session
    response = requests.post(f'https://student.bmstu.ru/Session/{session}/sync?reqSeq={nextRequestId()}&random={nextRand()}', f'<XIMSS><listKnownValues id="{nextCommandId()}"/><mailboxList filter="%" pureFolder="yes" id="{nextCommandId()}"/><mailboxList filter="%/%" pureFolder="yes" id="{nextCommandId()}"/><folderOpen mailbox="INBOX" sortField="INTERNALDATE" sortOrder="desc" folder="INBOX-MM-1" id="{nextCommandId()}"><field>FLAGS</field><field>E-From</field><field>Subject</field><field>Pty</field><field>Content-Type</field><field>INTERNALDATE</field><field>SIZE</field><field>E-To</field><field>E-Cc</field><field>E-Reply-To</field><field>X-Color</field><field>Disposition-Notification-To</field><field>X-Request-DSN</field><field>References</field><field>Message-ID</field></folderOpen><setSessionOption name="reportMailboxChanges" value="yes" id="{nextCommandId()}"/></XIMSS>')

def getMails(first, last):
    global session
    response = requests.post(f"https://student.bmstu.ru/Session/{session}/sync?reqSeq={nextRequestId()}&random={nextRand()}", f'<XIMSS><folderBrowse folder="INBOX-MM-1" id="{nextCommandId()}"><index from="{first}" till="{last}"/></folderBrowse></XIMSS>')
    tree = ET.ElementTree(ET.fromstring(response.text))

    mails = []
    for element in tree.findall("folderReport"):
        mail = {}
        mail["uid"] = element.attrib["UID"]
        mail["flags"] = element.find("FLAGS").text
        mail["to_mail"] = element.find("E-To").text
        mail["from_mail"] = element.find("E-From").text
        mail["from_name"] = element.find("E-From").attrib['realName']
        mail["subject"] = element.find("Subject").text
        mails.append(mail)
    return mails

def longPollUpdates(ackSeq):
    global session
    response = requests.get(f"https://student.bmstu.ru/Session/{session}/?ackSeq={ackSeq}&maxWait=20&random={nextRand}")
    tree = ET.ElementTree(ET.fromstring(response.text))
    root = tree.getroot()
    if(root != None and "respSeq" in root.attrib):
        ackSeq = int(root.attrib["respSeq"])
    return ackSeq, response.text

def getNewMails():
    global session
    response = requests.post(f"https://student.bmstu.ru/Session/{session}/sync?reqSeq={nextRequestId()}&random={nextRand()}",f'<XIMSS><folderSync folder="INBOX-MM-1" limit="300" id="{nextCommandId()}"/></XIMSS>')
    tree = ET.ElementTree(ET.fromstring(response.text))
    mails = []
    for element in tree.findall("folderReport"):
        mail = {}
        mail["uid"] = element.attrib["UID"]
        mail["flags"] = element.find("FLAGS").text
        mail["to_mail"] = element.find("E-To").text
        mail["from_mail"] = element.find("E-From").text
        mail["from_name"] = element.find("E-From").attrib['realName']
        mail["subject"] = element.find("Subject").text
        mails.append(mail)
    return mails


def getMailById(uid):
    global session
    response = requests.get(f"https://student.bmstu.ru/Session/{session}/FORMAT/Samoware/INBOX-MM-1/{uid}")
    return response.text