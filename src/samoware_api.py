# TODO: async get post
import html
import datetime
from typing import Self

import requests
import re
import logging as log
import bs4 as bs
import xml.etree.ElementTree as ET
from aiohttp import ClientSession
from urllib.error import HTTPError

SESSION_TOKEN_PATTERN = compile("^[0-9]{6}-[a-zA-Z0-9]{20}$")
HTTP_COMMON_TIMEOUT_SEC = 5
HTTP_CONENCT_LONGPOLL_TIMEOUT_SEC = 25
HTTP_TOTAL_LONGPOLL_TIMEOUT_SEC = 60


class UnauthorizedError(Exception):
    pass


class SamowarePollingContext:
    def __init__(
        self,
        session: str = "",
        request_id: int = 0,
        rand: int = 0,
        command_id: int = 0,
        ack_seq: int = 0,
        cookies: str = "",
    ) -> None:
        self.session = session
        self.request_id = request_id
        self.rand = rand
        self.command_id = command_id
        self.ack_seq = ack_seq
        self.cookies = cookies

    def make_next(
        self,
        session: str | None = None,
        request_id: int | None = None,
        rand: int | None = None,
        command_id: int | None = None,
        ack_seq: int | None = None,
        cookies: str | None = None,
    ) -> Self:
        return SamowarePollingContext(
            session=self.session if session is None else session,
            command_id=self.command_id if command_id is None else command_id,
            cookies=self.cookies if cookies is None else cookies,
            ack_seq=self.ack_seq if ack_seq is None else ack_seq,
            rand=self.rand if rand is None else rand,
            request_id=self.request_id if request_id is None else request_id,
        )


class MailHeader:
    def __init__(
        self,
        uid: str,
        flags: str,
        local_time: str,
        utc_time: str,
        to_mail: str,
        to_name: str,
        from_mail: str,
        from_name: str,
        subject: str,
    ) -> None:
        self.uid = uid
        self.flags = flags
        self.local_time = local_time
        self.utc_time = utc_time
        self.to_mail = to_mail
        self.to_name = to_name
        self.from_mail = from_mail
        self.from_name = from_name
        self.subject = subject


class MailBody:
    def __init__(self, text: str, attachment_files: list, attachment_names: list[str]):
        self.text = text
        self.attachment_files = attachment_files
        self.attachment_names = attachment_names


class Mail:
    def __init__(self, header: MailHeader, body: MailBody):
        self.header = header
        self.body = body


def login(login: str, password: str) -> SamowarePollingContext:
    loginUrl = f"https://mailstudent.bmstu.ru/XIMSSLogin/?errorAsXML=1&EnableUseCookie=1&x2auth=1&canUpdatePwd=1&version=6.1&userName={login}&password={password}"
    if SESSION_TOKEN_PATTERN.match(password):
        loginUrl = f"https://mailstudent.bmstu.ru/XIMSSLogin/?errorAsXML=1&EnableUseCookie=1&x2auth=1&canUpdatePwd=1&version=6.1&userName={login}&sessionid={password}"
    response = requests.get(loginUrl, timeout=HTTP_COMMON_TIMEOUT_SEC)
    tree = ET.fromstring(response.text)
    if tree.find("session") is None:
        return None
    session = tree.find("session").attrib["urlID"]

    # set_session_info(context)
    # open_inbox(context)

    return SamowarePollingContext(session=session)


def revalidate(login: str, session: str) -> SamowarePollingContext:
    response = requests.get(
        f"https://mailstudent.bmstu.ru/XIMSSLogin/?errorAsXML=1&EnableUseCookie=1&x2auth=1&canUpdatePwd=1&version=6.1&userName={login}&sessionid={session}&killOld=1",
        timeout=HTTP_COMMON_TIMEOUT_SEC,
    )
    log.debug(response.text)
    tree = ET.fromstring(response.text)
    if tree.find("session") is None:
        return None
    new_session = tree.find("session").attrib["urlID"]

    # set_session_info(context)
    # open_inbox(context)

    log.info(f"session for {login} has revalidated")

    return SamowarePollingContext(session=new_session)

async def longpoll_updates(
    http_session: ClientSession, context: SamowarePollingContext
) -> tuple[str, SamowarePollingContext]:
    url = f"https://student.bmstu.ru/Session/{context.session}/?ackSeq={context.ack_seq}&maxWait=20&random={context.rand}"
    response = await http_session.get(
        url=url,
        cookies=context.cookies,
    )
    response_text = await response.text()
    await http_session.close()
    log.debug(
        f"samoware longpoll response code: {response.status}, text: {response_text}"
    )
    if response.status == 550:
        log.error(
            f"received 550 code in longPollUpdates - Samoware Unauthorized\nresponse: {response_text}"
        )
        return UnauthorizedError
    if response.status != 200:
        log.error(
            f"received non 200 code in longPollUpdates: {response.status}\nresponse: {response_text}"
        )
        return HTTPError(url=url, code=response.status_code, msg=response.text)
    tree = ET.fromstring(response_text)
    ack_seq = context.ack_seq
    if "respSeq" in tree.attrib:
        ack_seq = int(tree.attrib["respSeq"])
    return (
        response_text,
        context.make_next(
            ack_seq=ack_seq,
            rand=context.rand+1
        )
    )


def get_inbox_updates(context: SamowarePollingContext) -> tuple[list[MailHeader], SamowarePollingContext]:
    url = f"https://student.bmstu.ru/Session/{context.session}/sync?reqSeq={context.request_id}&random={context.rand}"
    response = requests.get(
        url=url,
        data=f'<XIMSS><folderSync folder="INBOX-MM-1" limit="300" id="{context.command_id}"/></XIMSS>',
        cookies=context.cookies,
        timeout=HTTP_COMMON_TIMEOUT_SEC,
    )
    if response.status_code == 550:
        log.error(
            f"received 550 code in getInboxUpdates - Samoware Unauthorized\nresponse: {response.text}"
        )
        raise UnauthorizedError
    if response.status_code != 200:
        log.error(
            f"received non 200 code in getInboxUpdates: {response.status_code}\nresponse: {response.text}"
        )
        raise HTTPError(url=url, code=response.status_code, msg=response.text)
    tree = ET.fromstring(response.text)
    mail_headers = []
    for element in tree.findall("folderReport"):
        log.debug("folderReport: " + str(ET.tostring(element, encoding="utf8")))
        uid = element.attrib["UID"]
        if element.attrib["mode"] == "added":
            local_time = datetime.strptime(
                element.find("INTERNALDATE").attrib["localTime"], "%Y%m%dT%H%M%S"
            )
            utc_time = datetime.strptime(
                element.find("INTERNALDATE").text, "%Y%m%dT%H%M%SZ"
            )
            flags = element.find("FLAGS").text
            from_mail = element.find("E-From").text
            if "realName" in element.find("E-From").attrib:
                from_name = element.find("E-From").attrib["realName"]
            else:
                from_name = element.find("E-From").text
            if element.find("Subject") is not None:
                subject = html.escape(element.find("Subject").text)
            else:
                subject = "Письмо без темы"
            to_mail = []
            to_name = []
            for el in element.findall("E-To"):
                to_mail.append(el.text)
                if "realName" in el.attrib:
                    to_name.append(el.attrib["realName"])
                else:
                    to_name.append(el.text)

        mail_headers.append(
            MailHeader(
                flags=flags,
                from_mail=from_mail,
                from_name=from_name,
                local_time=local_time,
                subject=subject,
                to_mail=to_mail,
                to_name=to_name,
                uid=uid,
                utc_time=utc_time,
            )
        )
    return (
        mail_headers,
        context.make_next(
            request_id=context.request_id+1,
            rand=context.rand+1,
            command_id=context.command_id+1
        )
    )


def set_session_info(context: SamowarePollingContext) -> SamowarePollingContext:
    response = requests.post(
        f"https://student.bmstu.ru/Session/{context.session}/sync?reqSeq={context.request_id}&random={context.rand}",
        '<XIMSS><prefsRead id="1"><name>Language</name></prefsRead></XIMSS>',
        timeout=HTTP_COMMON_TIMEOUT_SEC,
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
        timeout=HTTP_COMMON_TIMEOUT_SEC,
    )
    return context.make_next(
        cookies=response.cookies,
        request_id=context.request_id+1,
        rand=context.rand+1
    )


def open_inbox(context: SamowarePollingContext) -> SamowarePollingContext:
    url = f"https://student.bmstu.ru/Session/{context.session}/sync?reqSeq={context.request_id}&random={context.rand}"
    response = requests.get(
        url=url,
        data=f'<XIMSS><listKnownValues id="{context.command_id}"/><mailboxList filter="%" pureFolder="yes" id="{context.command_id+1}"/><mailboxList filter="%/%" pureFolder="yes" id="{context.command_id+2}"/><folderOpen mailbox="INBOX" sortField="INTERNALDATE" sortOrder="desc" folder="INBOX-MM-1" id="{context.command_id+3}"><field>FLAGS</field><field>E-From</field><field>Subject</field><field>Pty</field><field>Content-Type</field><field>INTERNALDATE</field><field>SIZE</field><field>E-To</field><field>E-Cc</field><field>E-Reply-To</field><field>X-Color</field><field>Disposition-Notification-To</field><field>X-Request-DSN</field><field>References</field><field>Message-ID</field></folderOpen><setSessionOption name="reportMailboxChanges" value="yes" id="{context.command_id+4}"/></XIMSS>',
        cookies=context.cookies,
        timeout=HTTP_COMMON_TIMEOUT_SEC,
    )
    if response.status_code == 550:
        log.error(
            f"received 550 code in openInbox - Samoware Unauthorized\nresponse: {response.text}"
        )
        raise UnauthorizedError
    if response.status_code != 200:
        log.error(
            f"received non 200 code in openInbox: {response.status_code}\nresponse: {response.text}"
        )
        raise HTTPError(url=url, code=response.status_code, msg=response.text)
    
    return context.make_next(
        request_id=context.request_id+1,
        rand=context.rand+1,
        command_id=context.command_id+5,
    )


def get_mail_body_by_id(context: SamowarePollingContext, uid: int) -> MailBody:
    url = f"https://student.bmstu.ru/Session/{context.session}/FORMAT/Samoware/INBOX-MM-1/{uid}"
    response = requests.get(
        url=url,
        cookies=context.cookies,
        timeout=HTTP_COMMON_TIMEOUT_SEC,
    )
    if response.status_code == 550:
        log.error(
            f"received 550 code in getMailBodyById - Samoware Unauthorized\nresponse: {response.text}"
        )
        raise UnauthorizedError
    if response.status_code != 200:
        log.error(
            f"received non 200 code in getMailBodyById: {response.status_code}\nresponse: {response.text}"
        )
        raise HTTPError(url=url, code=response.status_code, msg=response.text)
    tree = bs.BeautifulSoup(response.text, "html.parser")
    mailBodiesHtml = tree.findAll("div", {"class": "samoware-RFC822-body"})

    text = ""
    for mailBodyHtml in mailBodiesHtml:
        log.debug("mail body: " + str(mailBodyHtml.encode()))
        foundTextBeg = False
        for element in mailBodyHtml.findChildren(recursive=False):
            if element.has_attr("class") and "textBeg" in element["class"]:
                foundTextBeg = True
                log.debug("found textBeg")
            if element.has_attr("class") and "textEnd" in element["class"]:
                log.debug("found textEnd")
                break
            if foundTextBeg:
                text += html_element_to_text(element)

    text = re.sub(r"(\r)+", "\r", text).strip()
    text = re.sub(r"(\n)+", "\n", text).strip()
    text = text.replace("\r", "\n\n")
    text = re.sub(r"(\n){2,}", "\n\n", text).strip()

    attachment_files = []
    attachment_names = []
    for attachment_html in tree.find_all("cg-message-attachment"):
        attachment_url = "https://student.bmstu.ru" + attachment_html["attachment-ref"]
        file = requests.get(
            attachment_url,
            cookies=context.cookies,
            stream=True,
            timeout=HTTP_COMMON_TIMEOUT_SEC,
        ).raw
        name = attachment_html["attachment-name"]
        attachment_files.append(file)
        attachment_names.append(name)
    return MailBody(text, attachment_files, attachment_names)


def html_element_to_text(element):
    if isinstance(element, bs.NavigableString):
        return html.escape(
            re.sub(
                r" +",
                " ",
                str(element).replace("\r", "").strip("\n").replace("\n", " "),
            )
        )
    elif isinstance(element, bs.Tag):
        if element.name == "a" and "href" in element.attrs:
            href = element["href"]
            text = f'<a href="{href}">'
            for child in element.children:
                text += html_element_to_text(child)
            text += "</a>"
            return text
        elif element.name == "style":
            return ""
        elif element.name == "br":
            return "\n"
        elif element.name == "hr":
            return "\n----------\n"
        elif element.name == "p":
            text = ""
            for child in element.children:
                text += html_element_to_text(child)
            return "\r" + text + "\r"
        elif element.name == "div":
            text = ""
            for child in element.children:
                text += html_element_to_text(child)
            return "\n" + text + "\n"
        elif element.name == "li":
            text = ""
            for child in element.children:
                text += html_element_to_text(child)
            return text + "\n"
        elif element.name == "blockquote":
            text = ""
            for child in element.children:
                text += html_element_to_text(child)
            return "<blockquote>" + text.strip() + "</blockquote>"
        else:
            text = ""
            for child in element.children:
                text += html_element_to_text(child)
            return text
