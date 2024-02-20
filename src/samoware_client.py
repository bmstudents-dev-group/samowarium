import aiohttp
import html
import requests
import asyncio
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import logging
from datetime import datetime, timedelta

revalidate_interval = timedelta(minutes=1)

class SamowareContext:
    def __init__(self, login:str, session:str, request_id:int = 0, command_id:int = 0, rand:int = 0, ackSeq:int = 0, last_revalidate:datetime = datetime.now(), cookies:dict = {}):
        self.login = login
        self.session = session
        self.request_id = request_id
        self.command_id = command_id
        self.rand = rand
        self.ackSeq = ackSeq
        self.last_revalidate = last_revalidate
        self.cookies = cookies

class Mail:
    def __init__(self, uid, flags, local_time, utc_time, to_mail, to_name, from_mail, from_name, subject, plain_text):
        self.uid = uid
        self.flags = flags
        self.local_time = local_time
        self.utc_time = utc_time
        self.to_mail = to_mail
        self.to_name = to_name
        self.from_mail = from_mail
        self.from_name = from_name
        self.subject = subject
        self.plain_text = plain_text

def nextRequestId(context:SamowareContext) -> int:
    context.request_id += 1
    return context.request_id


def nextCommandId(context:SamowareContext) -> int:
    context.command_id += 1
    return context.command_id


def nextRand(context:SamowareContext) -> int:
    context.rand += 1
    return context.rand

async def longPollingTask(context:SamowareContext, isActive, onMail, onContextUpdate, onSessionLost) -> None:
    try:
        logging.info(f"longpolling for {context.login} started")
        while await isActive():
            longPollUpdate = await longPollUpdatesAsync(context)
            await onContextUpdate(context)
            logging.debug(f"longPollUpdate: {longPollUpdate}")
            if '<folderReport folder="INBOX-MM-1" mode="notify"/>' in longPollUpdate:
                updates = getInboxUpdates(context)
                await onContextUpdate(context)
                for update in updates:
                    if update["mode"] != "added":
                        continue
                    logging.info(f"new mail for {context.login}")
                    logging.debug(f'email flags: {update["flags"]}')
                    mail_text = getMailTextById(context, update["uid"])
                    await onContextUpdate(context)
                    mail_plaintext = html.escape(mail_text)
                    to_str = ""
                    for i in range(len(update["to_name"])):
                        to_str += f'[{update["to_name"][i]}](copy-this-mail.example/{update["to_mail"][i]})'
                        if i != len(update["to_name"]) - 1:
                            to_str += ", "
                    mail = Mail(update["uid"], update["flags"], update["local_time"], update["utc_time"], update["to_mail"], update["to_name"], update["from_mail"], update["from_name"], update["subject"], mail_plaintext)
                    await onMail(mail)
            if context.last_revalidate + revalidate_interval < datetime.now():
                context = revalidate(context)
                await onContextUpdate(context)
        logging.info(f"longpolling for {context.login} stopped")

    except RuntimeError: # this happens when killing samowarium process
        logging.info(f"longpolling for {context.login} stopped")
    except Exception as error:
        logging.exception("exception in client_handler:\n" + str(error))
        await onSessionLost()


def startLongPolling(context:SamowareContext, isActive, onMail, onContextUpdate, onSessionLost) -> None:
    asyncio.create_task(longPollingTask(context, isActive, onMail, onContextUpdate, onSessionLost))


def login(login:str, password:str) -> SamowareContext|None:
    response = requests.get(
        f"https://mailstudent.bmstu.ru/XIMSSLogin/?errorAsXML=1&EnableUseCookie=1&x2auth=1&canUpdatePwd=1&version=6.1&userName={login}&password={password}"
    )
    tree = ET.fromstring(response.text)
    if tree.find("session") is None:
        return None
    session = tree.find("session").attrib["urlID"]
    context = SamowareContext(login, session)

    setSessionInfo(context)
    openInbox(context)

    return context


def revalidate(context: SamowareContext) -> SamowareContext:
    response = requests.get(
        f"https://mailstudent.bmstu.ru/XIMSSLogin/?errorAsXML=1&EnableUseCookie=1&x2auth=1&canUpdatePwd=1&version=6.1&userName={context.login}&sessionid={context.session}&killOld=1"
    )
    logging.debug(response.text)
    tree = ET.fromstring(response.text)
    if tree.find("session") is None:
        return None

    context = SamowareContext(context.login, tree.find("session").attrib["urlID"])

    setSessionInfo(context)
    openInbox(context)

    logging.info(f"revalidated {context.login}")

    return context


def openInbox(context: SamowareContext) -> None:
    response = requests.post(
        f"https://student.bmstu.ru/Session/{context.session}/sync?reqSeq={nextRequestId(context)}&random={nextRand(context)}",
        f'<XIMSS><listKnownValues id="{nextCommandId(context)}"/><mailboxList filter="%" pureFolder="yes" id="{nextCommandId(context)}"/><mailboxList filter="%/%" pureFolder="yes" id="{nextCommandId(context)}"/><folderOpen mailbox="INBOX" sortField="INTERNALDATE" sortOrder="desc" folder="INBOX-MM-1" id="{nextCommandId(context)}"><field>FLAGS</field><field>E-From</field><field>Subject</field><field>Pty</field><field>Content-Type</field><field>INTERNALDATE</field><field>SIZE</field><field>E-To</field><field>E-Cc</field><field>E-Reply-To</field><field>X-Color</field><field>Disposition-Notification-To</field><field>X-Request-DSN</field><field>References</field><field>Message-ID</field></folderOpen><setSessionOption name="reportMailboxChanges" value="yes" id="{nextCommandId(context)}"/></XIMSS>',
        cookies=context.cookies,
    )
    if response.status_code != 200:
        logging.error("received non 200 code: " + str(response.status_code))
        logging.error("response: " + str(response.text))


def getMails(context: SamowareContext, first:int, last:int) -> list:
    response = requests.post(
        f"https://student.bmstu.ru/Session/{context.session}/sync?reqSeq={nextRequestId(context)}&random={nextRand(context)}",
        f'<XIMSS><folderBrowse folder="INBOX-MM-1" id="{nextCommandId(context)}"><index from="{first}" till="{last}"/></folderBrowse></XIMSS>',
        cookies=context.cookies,
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


async def longPollUpdatesAsync(context: SamowareContext) -> str:
    http_session = aiohttp.ClientSession()
    response = await http_session.get(
        f"https://student.bmstu.ru/Session/{context.session}/?ackSeq={context.ackSeq}&maxWait=20&random={nextRand(context)}",
        cookies=context.cookies,
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
        raise AttributeError
    tree = ET.fromstring(response_text)
    if "respSeq" in tree.attrib:
        context.ackSeq = int(tree.attrib["respSeq"])
    return response_text


def getInboxUpdates(context: SamowareContext) -> list:
    response = requests.post(
        f"https://student.bmstu.ru/Session/{context.session}/sync?reqSeq={nextRequestId(context)}&random={nextRand(context)}",
        f'<XIMSS><folderSync folder="INBOX-MM-1" limit="300" id="{nextCommandId(context)}"/></XIMSS>',
        cookies=context.cookies,
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
            mail["local_time"] = datetime.strptime(
                element.find("INTERNALDATE").attrib["localTime"], "%Y%m%dT%H%M%S"
            )
            mail["utc_time"] = datetime.strptime(
                element.find("INTERNALDATE").text, "%Y%m%dT%H%M%SZ"
            )
            mail["flags"] = element.find("FLAGS").text
            mail["from_mail"] = element.find("E-From").text
            mail["from_name"] = element.find("E-From").attrib["realName"]
            mail["subject"] = element.find("Subject").text
            mail["to_mail"] = []
            mail["to_name"] = []
            for el in element.findall("E-To"):
                mail["to_mail"].append(el.text)
                mail["to_name"].append(el.attrib["realName"])

        mails.append(mail)
    return mails


def setSessionInfo(context: SamowareContext) -> None:
    response = requests.post(
        f"https://student.bmstu.ru/Session/{context.session}/sync?reqSeq={nextRequestId(context)}&random={nextRand(context)}",
        '<XIMSS><prefsRead id="1"><name>Language</name></prefsRead></XIMSS>',
    )

    requests.post(
        f"https://student.bmstu.ru/Session/{context.session}/sessionadmin.wcgp",
        files=(
            ("op", (None, "setSessionInfo")),
            ("paramType", (None, "json")),
            (
                "param",
                (
                    None,
                    '{"platform":"Linux x86_64","clientName":"hSamoware","browser":"Firefox 122"}',
                ),
            ),
            ("session", (None, context.session)),
        ),
        cookies=response.cookies,
    )
    context.cookies = response.cookies


def getMailTextById(context: SamowareContext, uid:int) -> str:
    response = requests.get(
        f"https://student.bmstu.ru/Session/{context.session}/FORMAT/Samoware/INBOX-MM-1/{uid}",
        cookies=context.cookies,
    )
    tree = BeautifulSoup(response.text, "html.parser")
    logging.debug("mail body: " + str(tree.encode()))
    return tree.find("tt").text
