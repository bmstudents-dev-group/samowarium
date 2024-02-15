import aiohttp
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import logging

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
    response = requests.get(f"https://mailstudent.bmstu.ru/XIMSSLogin/?errorAsXML=1&EnableUseCookie=1&x2auth=1&canUpdatePwd=1&version=6.1&userName={login}&password={password}")
    tree = ET.fromstring(response.text)
    if tree.find("session") == None:
        return None
    session = tree.find("session").attrib['urlID']
    return session

def openInbox(session):
    response = requests.post(f'https://student.bmstu.ru/Session/{session}/sync?reqSeq={nextRequestId()}&random={nextRand()}', f'<XIMSS><listKnownValues id="{nextCommandId()}"/><mailboxList filter="%" pureFolder="yes" id="{nextCommandId()}"/><mailboxList filter="%/%" pureFolder="yes" id="{nextCommandId()}"/><folderOpen mailbox="INBOX" sortField="INTERNALDATE" sortOrder="desc" folder="INBOX-MM-1" id="{nextCommandId()}"><field>FLAGS</field><field>E-From</field><field>Subject</field><field>Pty</field><field>Content-Type</field><field>INTERNALDATE</field><field>SIZE</field><field>E-To</field><field>E-Cc</field><field>E-Reply-To</field><field>X-Color</field><field>Disposition-Notification-To</field><field>X-Request-DSN</field><field>References</field><field>Message-ID</field></folderOpen><setSessionOption name="reportMailboxChanges" value="yes" id="{nextCommandId()}"/></XIMSS>')

def getMails(session, first, last):
    response = requests.post(f"https://student.bmstu.ru/Session/{session}/sync?reqSeq={nextRequestId()}&random={nextRand()}", f'<XIMSS><folderBrowse folder="INBOX-MM-1" id="{nextCommandId()}"><index from="{first}" till="{last}"/></folderBrowse></XIMSS>')
    tree = ET.fromstring(response.text)

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

def longPollUpdates(session, ackSeq):
    response = requests.get(f"https://student.bmstu.ru/Session/{session}/?ackSeq={ackSeq}&maxWait=20&random={nextRand}")
    response_text = response.text
    tree = ET.fromstring(response_text)
    root = tree.getroot()
    if("respSeq" in root.attrib):
        ackSeq = int(root.attrib["respSeq"])
    return ackSeq, response_text

async def longPollUpdatesAsync(session, ackSeq):
    http_session = aiohttp.ClientSession()
    response = await http_session.get(f"https://student.bmstu.ru/Session/{session}/?ackSeq={ackSeq}&maxWait=20&random={nextRand}")
    response_text = await response.text()
    await http_session.close()
    tree = ET.fromstring(response_text)
    if("respSeq" in tree.attrib):
        ackSeq = int(tree.attrib["respSeq"])
    return ackSeq, response_text

def getInboxUpdates(session):
    response = requests.post(f"https://student.bmstu.ru/Session/{session}/sync?reqSeq={nextRequestId()}&random={nextRand()}",f'<XIMSS><folderSync folder="INBOX-MM-1" limit="300" id="{nextCommandId()}"/></XIMSS>')
    tree = ET.fromstring(response.text)
    mails = []
    for element in tree.findall("folderReport"):
        logging.debug('folderReport: '+str(ET.tostring(element,encoding="utf8")))
        mail = {}
        mail['mode'] = element.attrib["mode"]
        mail["uid"] = element.attrib["UID"]
        if element.attrib["mode"] == 'added' or element.attrib["mode"] == 'updated':
            mail["flags"] = element.find("FLAGS").text
            mail["to_mail"] = element.find("E-To").text
            mail["from_mail"] = element.find("E-From").text
            mail["from_name"] = element.find("E-From").attrib['realName']
            mail["subject"] = element.find("Subject").text
        
        mails.append(mail)
    return mails


def getMailById(session, uid):
    response = requests.get(f"https://student.bmstu.ru/Session/{session}/FORMAT/Samoware/INBOX-MM-1/{uid}")
    tree = BeautifulSoup(response.text,"html.parser")
    return tree.find("tt").text