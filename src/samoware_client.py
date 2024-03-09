import aiohttp
import requests
import asyncio
import xml.etree.ElementTree as ET
import bs4
from bs4 import BeautifulSoup
import logging
from datetime import datetime, timedelta
import re
import urllib.error
import html

REVALIDATE_INTERVAL = timedelta(hours=5)
SESSION_TOKEN_PATTERN = re.compile("^[0-9]{6}-[a-zA-Z0-9]{20}$")


class UnauthorizedError(Exception):
    pass


class SamowareContext:
    def __init__(
        self,
        login: str,
        session: str,
        request_id: int = 0,
        command_id: int = 0,
        rand: int = 0,
        ackSeq: int = 0,
        last_revalidate: datetime = None,
        cookies: dict = {},
    ):
        self.login = login
        self.session = session
        self.request_id = request_id
        self.command_id = command_id
        self.rand = rand
        self.ackSeq = ackSeq
        self.last_revalidate = last_revalidate
        self.cookies = cookies
        if last_revalidate is None:
            self.last_revalidate = datetime.now()


class Mail:
    def __init__(
        self,
        uid,
        flags,
        local_time,
        utc_time,
        to_mail,
        to_name,
        from_mail,
        from_name,
        subject,
        text,
        attachment_files,
        attachment_names,
    ):
        self.uid = uid
        self.flags = flags
        self.local_time = local_time
        self.utc_time = utc_time
        self.to_mail = to_mail
        self.to_name = to_name
        self.from_mail = from_mail
        self.from_name = from_name
        self.subject = subject
        self.text = text
        self.attachment_files = attachment_files
        self.attachment_names = attachment_names


class MailBody:
    def __init__(self, text: str, attachment_files: list, attachment_names: list[str]):
        self.text = text
        self.attachment_files = attachment_files
        self.attachment_names = attachment_names


def nextRequestId(context: SamowareContext) -> int:
    context.request_id += 1
    return context.request_id


def nextCommandId(context: SamowareContext) -> int:
    context.command_id += 1
    return context.command_id


def nextRand(context: SamowareContext) -> int:
    context.rand += 1
    return context.rand


async def longPollingTask(
    context: SamowareContext, isActive, onMail, onContextUpdate, onSessionLost
) -> None:
    retry_count = 0
    logging.info(f"longpolling for {context.login} started")
    while await isActive():
        try:
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
                    mail = getMailBodyById(context, update["uid"])
                    await onContextUpdate(context)
                    to_str = ""
                    for i in range(len(update["to_name"])):
                        to_str += f'[{update["to_name"][i]}](copy-this-mail.example/{update["to_mail"][i]})'
                        if i != len(update["to_name"]) - 1:
                            to_str += ", "
                    mail = Mail(
                        update["uid"],
                        update["flags"],
                        update["local_time"],
                        update["utc_time"],
                        update["to_mail"],
                        update["to_name"],
                        update["from_mail"],
                        update["from_name"],
                        html.escape(update["subject"]),
                        mail.text,
                        mail.attachment_files,
                        mail.attachment_names,
                    )
                    await onMail(mail)
            if context.last_revalidate + REVALIDATE_INTERVAL < datetime.now():
                context = revalidate(context)
                await onContextUpdate(context)
            retry_count = 0
        except RuntimeError:  # It happens when samowarium has been killed
            break
        except UnauthorizedError:  # Session lost
            logging.info(f"session for {context.login} expired")
            await onSessionLost()
            break
        except Exception as error:
            logging.exception("exception in client_handler:\n" + str(error))
            if retry_count < 3:
                logging.info(
                    f"retry_count={retry_count}. Retrying longpolling for {context.login}..."
                )
                retry_count += 1
            else:
                logging.info(
                    f"retry_count={retry_count}. deleting session for {context.login}..."
                )
                await onSessionLost()
                break

    logging.info(f"longpolling for {context.login} stopped")


def startLongPolling(
    context: SamowareContext, isActive, onMail, onContextUpdate, onSessionLost
) -> None:
    asyncio.create_task(
        longPollingTask(context, isActive, onMail, onContextUpdate, onSessionLost)
    )


def login(login: str, password: str) -> SamowareContext | None:
    loginUrl = f"https://mailstudent.bmstu.ru/XIMSSLogin/?errorAsXML=1&EnableUseCookie=1&x2auth=1&canUpdatePwd=1&version=6.1&userName={login}&password={password}"
    if SESSION_TOKEN_PATTERN.match(password):
        loginUrl = f"https://mailstudent.bmstu.ru/XIMSSLogin/?errorAsXML=1&EnableUseCookie=1&x2auth=1&canUpdatePwd=1&version=6.1&userName={login}&sessionid={password}"
    response = requests.get(loginUrl)
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
    if response.status_code == 550:
        logging.error(
            f"received 550 code in openInbox - Samoware Unauthorized\nresponse: {response.text}"
        )
        raise UnauthorizedError
    if response.status_code != 200:
        logging.error(
            f"received non 200 code in openInbox: {response.status_code}\nresponse: {response.text}"
        )
        raise urllib.error.HTTPError


def getMails(context: SamowareContext, first: int, last: int) -> list:
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
        if "realName" in element.find("E-From").attrib:
            mail["from_name"] = element.find("E-From").attrib["realName"]
        else:
            mail["from_name"] = element.find("E-From").text
        mail["subject"] = html.escape(element.find("Subject").text)
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
    if response.status == 550:
        logging.error(
            f"received 550 code in longPollUpdates - Samoware Unauthorized\nresponse: {response_text}"
        )
        raise UnauthorizedError
    if response.status != 200:
        logging.error(
            f"received non 200 code in longPollUpdates: {response.status}\nresponse: {response_text}"
        )
        raise urllib.error.HTTPError
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
    if response.status_code == 550:
        logging.error(
            f"received 550 code in getInboxUpdates - Samoware Unauthorized\nresponse: {response.text}"
        )
        raise UnauthorizedError
    if response.status_code != 200:
        logging.error(
            f"received non 200 code in getInboxUpdates: {response.status_code}\nresponse: {response.text}"
        )
        raise urllib.error.HTTPError
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
            if "realName" in element.find("E-From").attrib:
                mail["from_name"] = element.find("E-From").attrib["realName"]
            else:
                mail["from_name"] = element.find("E-From").text
            mail["subject"] = html.escape(element.find("Subject").text)
            mail["to_mail"] = []
            mail["to_name"] = []
            for el in element.findall("E-To"):
                mail["to_mail"].append(el.text)
                if "realName" in el.attrib:
                    mail["to_name"].append(el.attrib["realName"])
                else:
                    mail["to_name"].append(el.text)

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


def my_get_text(element, offset=0):
    if isinstance(element, bs4.NavigableString):
        text = ""
        for line in html.escape(str(element)).splitlines(keepends=True):
            text += "  " * offset + line
        return text
    elif isinstance(element, bs4.Tag):
        if element.name == "a" and "href" in element.attrs:
            href = element["href"]
            element_text = ""
            text = ""
            for child in element.children:
                element_text += my_get_text(child, offset)
            text += f'<a href="{href}">{element_text}</a>'
            return text
        elif element.name == "hr":
            return "\n-----\n"
        elif element.name == "blockquote":
            text = ""
            for child in element.children:
                text += my_get_text(child, offset + 1)
            return text
        else:
            text = ""
            for child in element.children:
                text += my_get_text(child, offset)
            return text


def getMailBodyById(context: SamowareContext, uid: int) -> MailBody:
    response = requests.get(
        f"https://student.bmstu.ru/Session/{context.session}/FORMAT/Samoware/INBOX-MM-1/{uid}",
        cookies=context.cookies,
    )
    if response.status_code == 550:
        logging.error(
            f"received 550 code in getMailBodyById - Samoware Unauthorized\nresponse: {response.text}"
        )
        raise UnauthorizedError
    if response.status_code != 200:
        logging.error(
            f"received non 200 code in getMailBodyById: {response.status_code}\nresponse: {response.text}"
        )
        raise urllib.error.HTTPError
    tree = BeautifulSoup(response.text, "html.parser")
    mailBodiesHtml = tree.findAll("div", {"class": "samoware-RFC822-body"})

    text = ""
    for mailBodyHtml in mailBodiesHtml:
        logging.debug("mail body: " + str(mailBodyHtml.encode()))
        foundTextBeg = False
        for element in mailBodyHtml.findChildren(recursive=False):
            if element.has_attr("class") and "textBeg" in element["class"]:
                foundTextBeg = True
                logging.debug("found textBeg")
            if element.has_attr("class") and "textEnd" in element["class"]:
                logging.debug("found textEnd")
                break
            if foundTextBeg:
                text += my_get_text(element)

    attachment_files = []
    attachment_names = []
    for attachment_html in tree.find_all("cg-message-attachment"):
        attachment_url = "https://student.bmstu.ru" + attachment_html["attachment-ref"]
        file = requests.get(attachment_url, cookies=context.cookies, stream=True).raw
        name = attachment_html["attachment-name"]
        attachment_files.append(file)
        attachment_names.append(name)
    return MailBody(text, attachment_files, attachment_names)
