import aiohttp
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import logging
from datetime import datetime

class SamowareContext:
    def __init__(self, login, session, request_id, command_id, rand, last_revalidate):
        self.login = login
        self.session = session
        self.request_id = request_id
        self.command_id = command_id
        self.rand = rand
        self.last_revalidate = last_revalidate


def nextRequestId(context):
    context.request_id += 1
    return context.request_id


def nextCommandId(context):
    context.command_id += 1
    return context.command_id


def nextRand(context):
    context.rand += 1
    return context.rand


def login(login, password):
    response = requests.get(
        f"https://mailstudent.bmstu.ru/XIMSSLogin/?errorAsXML=1&EnableUseCookie=1&x2auth=1&canUpdatePwd=1&version=6.1&userName={login}&password={password}"
    )
    tree = ET.fromstring(response.text)
    if tree.find("session") is None:
        return None
    session = tree.find("session").attrib["urlID"]
    context = SamowareContext(login, session, 0, 0, 0)
    return context


def revalidate(context):
    response = requests.get(
        f"https://mailstudent.bmstu.ru/XIMSSLogin/?errorAsXML=1&EnableUseCookie=1&x2auth=1&canUpdatePwd=1&version=6.1&userName={login}&sessionid={session}&killOld=1"
    )
    logging.debug(response.text)
    tree = ET.fromstring(response.text)
    if tree.find("session") is None:
        return None
    context.session = tree.find("session").attrib["urlID"]
    context.last_revalidate = datetime.now()
    return context


def openInbox(context):
    response = requests.post(
        f"https://student.bmstu.ru/Session/{context.session}/sync?reqSeq={nextRequestId(context)}&random={nextRand(context)}",
        f'<XIMSS><listKnownValues id="{nextCommandId(context)}"/><mailboxList filter="%" pureFolder="yes" id="{nextCommandId(context)}"/><mailboxList filter="%/%" pureFolder="yes" id="{nextCommandId(context)}"/><folderOpen mailbox="INBOX" sortField="INTERNALDATE" sortOrder="desc" folder="INBOX-MM-1" id="{nextCommandId(context)}"><field>FLAGS</field><field>E-From</field><field>Subject</field><field>Pty</field><field>Content-Type</field><field>INTERNALDATE</field><field>SIZE</field><field>E-To</field><field>E-Cc</field><field>E-Reply-To</field><field>X-Color</field><field>Disposition-Notification-To</field><field>X-Request-DSN</field><field>References</field><field>Message-ID</field></folderOpen><setSessionOption name="reportMailboxChanges" value="yes" id="{nextCommandId(context)}"/></XIMSS>',
    )
    if response.status_code != 200:
        logging.error("received non 200 code: " + str(response.status_code))
        logging.error("response: " + str(response.text))


def getMails(context, first, last):
    response = requests.post(
        f"https://student.bmstu.ru/Session/{context.session}/sync?reqSeq={nextRequestId(context)}&random={nextRand(context)}",
        f'<XIMSS><folderBrowse folder="INBOX-MM-1" id="{nextCommandId(context)}"><index from="{first}" till="{last}"/></folderBrowse></XIMSS>',
    )
    tree = ET.fromstring(response.text)

    mails = []
    for element in tree.findall("folderReport"):
        mail = {}
        mail["uid"] = element.attrib["UID"]
        mail["flags"] = element.find("FLAGS").text
        mail["to_mail"] = element.find("E-To").text
        mail["from_mail"] = element.find("E-From").text
        mail["from_name"] = element.find("E-From").attrib["realName"]
        mail["subject"] = element.find("Subject").text
        mails.append(mail)
    return mails


async def longPollUpdatesAsync(context, ackSeq):
    http_session = aiohttp.ClientSession()
    response = await http_session.get(
        f"https://student.bmstu.ru/Session/{context.session}/?ackSeq={ackSeq}&maxWait=20&random={nextRand(context)}"
    )
    response_text = await response.text()
    await http_session.close()
    logging.debug(
        f"Samoware longpoll response code: {response.status}, text: {response_text}"
    )
    if response.status != 200:
        logging.error(
            f"Samoware longpoll response code: {response.status}, text: {response_text}"
        )
        return ackSeq, ""
    tree = ET.fromstring(response_text)
    if "respSeq" in tree.attrib:
        ackSeq = int(tree.attrib["respSeq"])
    return ackSeq, response_text


def getInboxUpdates(context):
    response = requests.post(
        f"https://student.bmstu.ru/Session/{context.session}/sync?reqSeq={nextRequestId(context)}&random={nextRand(context)}",
        f'<XIMSS><folderSync folder="INBOX-MM-1" limit="300" id="{nextCommandId(context)}"/></XIMSS>',
    )
    if response.status_code != 200:
        logging.error("received non 200 code: " + str(response.status_code))
        logging.error("response: " + str(response.text))
        return []
    tree = ET.fromstring(response.text)
    mails = []
    for element in tree.findall("folderReport"):
        logging.debug("folderReport: " + str(ET.tostring(element, encoding="utf8")))
        mail = {}
        mail["mode"] = element.attrib["mode"]
        mail["uid"] = element.attrib["UID"]
        if element.attrib["mode"] == "added" or element.attrib["mode"] == "updated":
            mail["flags"] = element.find("FLAGS").text
            mail["to_mail"] = element.find("E-To").text
            mail["from_mail"] = element.find("E-From").text
            mail["from_name"] = element.find("E-From").attrib["realName"]
            mail["subject"] = element.find("Subject").text

        mails.append(mail)
    return mails


def getMailById(context, uid):
    response = requests.get(
        f"https://student.bmstu.ru/Session/{context.session}/FORMAT/Samoware/INBOX-MM-1/{uid}"
    )
    tree = BeautifulSoup(response.text, "html.parser")
    logging.debug("mail body: " + str(tree.encode()))
    return tree.find("tt").text
