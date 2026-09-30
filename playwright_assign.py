import json
import random
import re
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright


# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent

# Input file - kept in the same folder as this Python file
CONTACTS_FILE = BASE_DIR / "contacts.txt"

# Persistent browser profile.
# This keeps your WhatsApp Web login between runs.
SESSION_DIR = BASE_DIR / "whatsapp_session"

# Screenshots are stored here.
SCREENSHOT_DIR = BASE_DIR / "screenshots"

# Daily JSON report.
TODAY = datetime.now().strftime("%Y-%m-%d")

JSON_REPORT = BASE_DIR / f"whatsapp_report_{TODAY}.json"

# WhatsApp Web
WA_URL = "https://web.whatsapp.com"

# Message used when the Message field is empty.
DEFAULT_TEMPLATE = (
    "Hi {name}, hope you're having a great day!"
)

# Timeouts
LOGIN_TIMEOUT = 120_000
CHAT_LOAD_TIMEOUT = 20_000
SEND_CONFIRM_TIMEOUT = 30_000

# Number of incoming messages to extract
MESSAGES_TO_EXTRACT = 3


# ============================================================================
# WHATSAPP SELECTORS
# ============================================================================
#
# WhatsApp Web can change its HTML structure.
# Therefore, several fallback selectors are used.
#

SEL = {

    # Visible when WhatsApp is logged in.
    "logged_in":
        "#pane-side",

    # QR-code related selector.
    "qr":
        "canvas[aria-label*='Scan'], div[data-ref] canvas",

    # WhatsApp search box.
    "search_box": [
        "#side div[contenteditable='true']",
        "#side input[type='text']",
        "div[contenteditable='true'][data-tab='3']",
        "input[aria-label*='Search']",
    ],

    # Message input box.
    "message_box": [
        "footer div[contenteditable='true'][data-tab='10']",
        "div[aria-label='Type a message'][contenteditable='true']",
        "footer div[contenteditable='true']",
    ],

    # Main chat header.
    "chat_header":
        "#main header",

    # Outgoing messages.
    "msg_out":
        "#main div.message-out",

    # Incoming messages.
    "msg_in":
        "#main div.message-in",

    # WhatsApp check/tick.
    "tick":
        "span[data-icon*='check']",

    # Dialog box.
    "dialog":
        "div[role='dialog']",
}


# ============================================================================
# LOGGING
# ============================================================================

def log(message: str) -> None:
    """
    Print a timestamped message to the terminal.
    """

    print(
        f"[{datetime.now():%H:%M:%S}] {message}",
        flush=True
    )


# ============================================================================
# RANDOM DELAY
# ============================================================================

def human_delay(
    page,
    low: float = 2,
    high: float = 5
) -> None:
    """
    Random pause between actions.

    Example:
        2.3 seconds
        4.7 seconds
        3.1 seconds
    """

    seconds = random.uniform(
        low,
        high
    )

    log(
        f"Waiting {seconds:.1f} seconds..."
    )

    page.wait_for_timeout(
        int(seconds * 1000)
    )


# ============================================================================
# HUMAN-LIKE TYPING
# ============================================================================

def human_type(
    page,
    text: str
) -> None:
    """
    Type text with a small random delay between characters.
    """

    page.keyboard.type(
        text,
        delay=random.randint(
            40,
            110
        )
    )


# ============================================================================
# COMBINE SELECTORS
# ============================================================================

def combined(key: str) -> str:
    """
    Convert a selector list into one Playwright selector.
    """

    return ", ".join(
        SEL[key]
    )


# ============================================================================
# PHONE NUMBER NORMALIZATION
# ============================================================================

def normalize_phone(raw) -> str:
    """
    Convert:

        +91 98765-43210

    into:

        919876543210

    WhatsApp click-to-chat URLs use digits only.
    """

    if raw is None:

        return ""

    return re.sub(
        r"\D",
        "",
        str(raw)
    )


# ============================================================================
# SAFE FILENAME
# ============================================================================

def safe_filename(
    text: str
) -> str:

    return (
        re.sub(
            r"[^A-Za-z0-9_-]+",
            "_",
            text
        )
        .strip("_")
        or "contact"
    )


# ============================================================================
# PERSONALIZE MESSAGE
# ============================================================================

def personalize(
    template: str,
    name: str
) -> str:
    """
    Replace {name} with the actual contact name.
    """

    if not template:

        template = DEFAULT_TEMPLATE

    return template.replace(
        "{name}",
        name
    )


# ============================================================================
# READ contacts.txt
# ============================================================================

def create_sample_contacts(
    path: Path
) -> None:
    """
    Create an example contacts.txt file if one does not exist.
    """

    sample = (
        "Name,Phone,Message\n"
        "Ravi,+919876543210,"
        "Hi {name}, your order is ready for pickup!\n"
        "Priya,+919123456789,"
        "Hello {name}, hope you are doing well!\n"
    )

    path.write_text(
        sample,
        encoding="utf-8"
    )


def read_contacts(
    path: Path
) -> list[dict]:
    """
    Read contacts.txt.

    Expected format:

    Name,Phone,Message

    Example:

    Ravi,+919876543210,Hi {name}, your order is ready!
    Priya,+919123456789,Hello {name}, how are you?
    """

    if not path.exists():

        create_sample_contacts(
            path
        )

        log(
            f"'{path.name}' was not found."
        )

        log(
            "A sample contacts.txt file "
            "has been created."
        )

        log(
            "Edit it with your contacts "
            "and run the program again."
        )

        sys.exit(0)

    contacts = []

    with path.open(
        "r",
        encoding="utf-8-sig"
    ) as file:

        for line_number, line in enumerate(
            file,
            start=1
        ):

            line = line.strip()

            # Ignore empty lines.
            if not line:
                continue

            # Ignore comments.
            if line.startswith("#"):
                continue

            # Ignore header.
            if line.lower().startswith(
                "name,phone"
            ):
                continue

            # ------------------------------------------------------------
            # Split only at the first TWO commas.
            #
            # This is important because the message itself may contain
            # commas.
            #
            # Example:
            #
            # Ravi,+919876543210,Hi {name}, your order is ready!
            #
            # becomes:
            #
            # Name    = Ravi
            # Phone   = +919876543210
            # Message = Hi {name}, your order is ready!
            # ------------------------------------------------------------

            parts = line.split(
                ",",
                2
            )

            if len(parts) < 2:

                log(
                    f"WARNING: Invalid line "
                    f"{line_number}: {line}"
                )

                continue

            name = parts[0].strip()

            phone = normalize_phone(
                parts[1]
            )

            if len(parts) >= 3:

                message = parts[2].strip()

            else:

                message = ""

            if not name:

                log(
                    f"WARNING: Missing name "
                    f"on line {line_number}"
                )

                continue

            if not phone:

                log(
                    f"WARNING: Missing phone "
                    f"on line {line_number}"
                )

                continue

            contacts.append({

                "name": name,

                "phone": phone,

                "template": message,

            })

    log(
        f"Loaded {len(contacts)} contact(s) "
        f"from {path.name}"
    )

    return contacts


# ============================================================================
# LOGIN
# ============================================================================

def login(page) -> None:
    """
    Open WhatsApp Web and login if necessary.

    This function is called only ONCE.

    The persistent SESSION_DIR keeps the login information.
    """

    log(
        "Opening WhatsApp Web..."
    )

    page.goto(
        WA_URL,
        wait_until="domcontentloaded"
    )

    # Give WhatsApp some time to initialize.
    page.wait_for_timeout(
        5000
    )

    # Already logged in?
    if page.locator(
        SEL["logged_in"]
    ).is_visible():

        log(
            "WhatsApp is already logged in."
        )

        page.wait_for_timeout(
            3000
        )

        return

    log(
        "Please scan the WhatsApp QR code..."
    )

    try:

        page.wait_for_selector(
            SEL["logged_in"],
            timeout=LOGIN_TIMEOUT
        )

    except PWTimeout:

        raise RuntimeError(
            "WhatsApp login timed out. "
            "Please scan the QR code and try again."
        )

    log(
        "WhatsApp login successful."
    )

    page.wait_for_timeout(
        4000
    )


# ============================================================================
# GET SEARCH BOX
# ============================================================================

def get_search_box(page):

    page.wait_for_selector(
        combined("search_box"),
        state="visible",
        timeout=CHAT_LOAD_TIMEOUT
    )

    return page.locator(
        combined("search_box")
    ).first


# ============================================================================
# GET MESSAGE BOX
# ============================================================================

def get_message_box(
    page,
    timeout: int = CHAT_LOAD_TIMEOUT
):

    page.wait_for_selector(
        combined("message_box"),
        state="visible",
        timeout=timeout
    )

    return page.locator(
        combined("message_box")
    ).first


# ============================================================================
# CLEAR SEARCH
# ============================================================================

def clear_search(page) -> None:

    try:

        box = get_search_box(
            page
        )

        box.click()

        page.keyboard.press(
            "ControlOrMeta+A"
        )

        page.keyboard.press(
            "Backspace"
        )

        page.keyboard.press(
            "Escape"
        )

    except Exception:

        pass


# ============================================================================
# OPEN CHAT BY NAME
# ============================================================================

def open_chat_by_name(
    page,
    name: str
) -> bool:
    """
    Search WhatsApp using the contact's name.
    """

    if not name:

        return False

    log(
        f"Searching by name: {name}"
    )

    try:

        box = get_search_box(
            page
        )

        box.click()

        page.keyboard.press(
            "ControlOrMeta+A"
        )

        page.keyboard.press(
            "Backspace"
        )

        human_type(
            page,
            name
        )

        page.wait_for_timeout(
            2500
        )

        match = (
            page.locator(
                "#side, #pane-side"
            )
            .get_by_title(
                name,
                exact=True
            )
            .first
        )

        try:

            match.wait_for(
                state="visible",
                timeout=6000
            )

        except PWTimeout:

            log(
                "Contact not found by name."
            )

            clear_search(
                page
            )

            return False

        match.click()

        get_message_box(
            page
        )

        header = (
            page.locator(
                SEL["chat_header"]
            ).inner_text()
        )

        clear_search(
            page
        )

        return (
            name.lower()
            in header.lower()
        )

    except Exception as error:

        log(
            f"Name search failed: {error}"
        )

        clear_search(
            page
        )

        return False


# ============================================================================
# OPEN CHAT BY PHONE NUMBER
# ============================================================================

def open_chat_by_number(
    page,
    phone: str
) -> bool:
    """
    Open a WhatsApp chat using only the phone number.
    """

    if not phone:

        return False

    log(
        f"Opening number: +{phone}"
    )

    url = (
        f"{WA_URL}/send"
        f"?phone={phone}"
    )

    try:

        page.goto(
            url,
            wait_until="domcontentloaded"
        )

    except Exception as error:

        log(
            f"Navigation failed: {error}"
        )

        return False

    # Wait for WhatsApp chat interface.
    msg_box = page.locator(
        combined("message_box")
    ).first

    invalid = (
        page.locator(
            SEL["dialog"]
        )
        .filter(
            has_text=re.compile(
                "invalid|not on whatsapp|"
                "couldn't find|could not find",
                re.I
            )
        )
    )

    waited = 0

    while waited < CHAT_LOAD_TIMEOUT:

        try:

            if msg_box.is_visible():

                log(
                    "Chat loaded successfully."
                )

                return True

        except Exception:

            pass

        try:

            if (
                invalid.count()
                and invalid.first.is_visible()
            ):

                log(
                    "WhatsApp says this number "
                    "is invalid or unavailable."
                )

                try:

                    invalid.first.get_by_role(
                        "button"
                    ).first.click()

                except Exception:

                    page.keyboard.press(
                        "Escape"
                    )

                return False

        except Exception:

            pass

        page.wait_for_timeout(
            500
        )

        waited += 500

    log(
        "Timed out waiting for the chat."
    )

    return False


# ============================================================================
# SEND MESSAGE
# ============================================================================

def send_message(
    page,
    text: str
):
    """
    Type and send a WhatsApp message.

    Returns:

        status
        message bubble locator
    """

    box = get_message_box(
        page
    )

    box.click()

    # Clear any old draft.
    page.keyboard.press(
        "ControlOrMeta+A"
    )

    page.keyboard.press(
        "Backspace"
    )

    # Number of outgoing messages before sending.
    before = page.locator(
        SEL["msg_out"]
    ).count()

    # ------------------------------------------------------------
    # Type message.
    #
    # Shift+Enter is used for newline because Enter sends.
    # ------------------------------------------------------------

    lines = text.split(
        "\n"
    )

    for i, line in enumerate(
        lines
    ):

        if i:

            page.keyboard.press(
                "Shift+Enter"
            )

        human_type(
            page,
            line
        )

    page.wait_for_timeout(
        random.randint(
            500,
            1200
        )
    )

    # Send.
    page.keyboard.press(
        "Enter"
    )

    # ------------------------------------------------------------
    # Wait for outgoing message bubble.
    # ------------------------------------------------------------

    page.wait_for_function(

        """
        ([selector, oldCount]) =>
            document.querySelectorAll(selector).length > oldCount
        """,

        arg=[
            SEL["msg_out"],
            before
        ],

        timeout=SEND_CONFIRM_TIMEOUT
    )

    bubble = (
        page.locator(
            SEL["msg_out"]
        ).last
    )

    # ------------------------------------------------------------
    # Check WhatsApp tick.
    # ------------------------------------------------------------

    try:

        tick = (
            bubble
            .locator(
                SEL["tick"]
            )
            .first
        )

        tick.wait_for(
            state="attached",
            timeout=SEND_CONFIRM_TIMEOUT
        )

        icon = (
            tick.get_attribute(
                "data-icon"
            )
            or ""
        ).lower()

        aria = (
            tick.get_attribute(
                "aria-label"
            )
            or ""
        ).lower()

        if "read" in aria:

            status = "Read"

        elif "dblcheck" in icon:

            status = "Delivered"

        else:

            status = "Sent"

    except PWTimeout:

        status = "Pending"

    return status, bubble


# ============================================================================
# TAKE SCREENSHOT
# ============================================================================

def take_screenshot(
    page,
    bubble,
    idx: int,
    name: str
) -> str:

    SCREENSHOT_DIR.mkdir(
        exist_ok=True
    )

    filename = (
        f"{idx:02d}_"
        f"{safe_filename(name)}_"
        f"{datetime.now():%H%M%S}.png"
    )

    path = (
        SCREENSHOT_DIR
        / filename
    )

    try:

        bubble.scroll_into_view_if_needed()

        bubble.screenshot(
            path=str(path)
        )

    except Exception:

        log(
            "Could not screenshot message "
            "bubble. Taking chat screenshot."
        )

        page.locator(
            "#main"
        ).screenshot(
            path=str(path)
        )

    return str(
        path.relative_to(
            BASE_DIR
        )
    )


# ============================================================================
# EXTRACT LAST 3 INCOMING MESSAGES
# ============================================================================

def extract_last_messages(
    page,
    n: int = MESSAGES_TO_EXTRACT
) -> list[dict]:
    """
    Extract the last N incoming messages.
    """

    page.wait_for_timeout(
        1500
    )

    incoming = page.locator(
        SEL["msg_in"]
    )

    total = incoming.count()

    messages = []

    start = max(
        0,
        total - n
    )

    for i in range(
        start,
        total
    ):

        message = incoming.nth(
            i
        )

        item = {

            "time": "",

            "sender": "",

            "text": "",

        }

        try:

            # --------------------------------------------------------
            # Timestamp and sender.
            # --------------------------------------------------------

            meta = (
                message
                .locator(
                    "[data-pre-plain-text]"
                )
                .first
            )

            if meta.count():

                pre = (
                    meta.get_attribute(
                        "data-pre-plain-text"
                    )
                    or ""
                )

                # Typical format:
                #
                # [10:32, 30/09/2026] Ravi:
                #

                parsed = re.match(
                    r"\[(.*?)\]\s*(.*?):\s*$",
                    pre
                )

                if parsed:

                    item["time"] = (
                        parsed.group(1)
                    )

                    item["sender"] = (
                        parsed.group(2)
                    )

            # --------------------------------------------------------
            # Message text.
            # --------------------------------------------------------

            text_element = (
                message
                .locator(
                    "span.selectable-text"
                )
                .first
            )

            if text_element.count():

                item["text"] = (
                    text_element
                    .inner_text()
                    .strip()
                )

            else:

                item["text"] = (
                    "[media / non-text message]"
                )

        except Exception as error:

            item["text"] = (
                f"[could not read message: "
                f"{error}]"
            )

        messages.append(
            item
        )

    return messages


# ============================================================================
# PROCESS ONE CONTACT
# ============================================================================

def process_contact(
    page,
    contact: dict,
    idx: int
) -> dict:

    name = contact["name"]

    phone = contact["phone"]

    message = personalize(
        contact["template"],
        name or "there"
    )

    result = {

        "index": idx,

        "name": name,

        "phone":
            f"+{phone}"
            if phone
            else "",

        "message": message,

        "status": "Failed",

        "found_by": "",

        "sent_at": "",

        "screenshot": "",

        "last_messages": [],

        "error": "",

    }

    log(
        f"\n[{idx}] "
        f"{name or '(no name)'} "
        f"+{phone}"
    )

    try:

        # ------------------------------------------------------------
        # Try name first.
        # ------------------------------------------------------------

        if open_chat_by_name(
            page,
            name
        ):

            result["found_by"] = "name"

        # ------------------------------------------------------------
        # If name failed, use phone number.
        # ------------------------------------------------------------

        elif open_chat_by_number(
            page,
            phone
        ):

            result["found_by"] = "phone"

        else:

            result["status"] = (
                "Not Found"
            )

            result["error"] = (
                "Contact not found by "
                "name or phone number."
            )

            log(
                "Contact not found."
            )

            return result

        # ------------------------------------------------------------
        # Small delay before sending.
        # ------------------------------------------------------------

        human_delay(
            page
        )

        # ------------------------------------------------------------
        # Send.
        # ------------------------------------------------------------

        status, bubble = send_message(
            page,
            message
        )

        result["status"] = status

        result["sent_at"] = (
            datetime.now()
            .isoformat(
                timespec="seconds"
            )
        )

        log(
            f"Message status: {status}"
        )

        # ------------------------------------------------------------
        # Screenshot.
        # ------------------------------------------------------------

        result["screenshot"] = (
            take_screenshot(
                page,
                bubble,
                idx,
                name or phone
            )
        )

        log(
            f"Screenshot saved: "
            f"{result['screenshot']}"
        )

        # ------------------------------------------------------------
        # Wait before extracting messages.
        # ------------------------------------------------------------

        human_delay(
            page
        )

        # ------------------------------------------------------------
        # Extract last 3 incoming messages.
        # ------------------------------------------------------------

        result["last_messages"] = (
            extract_last_messages(
                page
            )
        )

        log(
            f"Extracted "
            f"{len(result['last_messages'])} "
            f"incoming message(s)."
        )

    except PWTimeout as error:

        result["error"] = (
            f"Timeout: "
            f"{str(error).splitlines()[0]}"
        )

        log(
            result["error"]
        )

    except Exception as error:

        result["error"] = (
            f"{type(error).__name__}: "
            f"{error}"
        )

        log(
            f"Error: {result['error']}"
        )

    return result


# ============================================================================
# BUILD REPORT SUMMARY
# ============================================================================

def build_summary(
    results: list[dict]
) -> dict:

    successful_statuses = {
        "Sent",
        "Delivered",
        "Read"
    }

    return {

        "total":
            len(results),

        "sent_successfully":
            sum(
                r["status"]
                in successful_statuses
                for r in results
            ),

        "pending":
            sum(
                r["status"] == "Pending"
                for r in results
            ),

        "not_found":
            sum(
                r["status"] == "Not Found"
                for r in results
            ),

        "failed":
            sum(
                r["status"] == "Failed"
                for r in results
            ),

    }


# ============================================================================
# SAVE JSON REPORT
# ============================================================================

def save_json(
    results: list[dict],
    started: str
) -> None:

    report = {

        "run_date":
            TODAY,

        "started_at":
            started,

        "finished_at":
            datetime.now()
            .isoformat(
                timespec="seconds"
            ),

        "summary":
            build_summary(
                results
            ),

        "results":
            results,

    }

    JSON_REPORT.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    log(
        f"JSON report saved -> "
        f"{JSON_REPORT.name}"
    )


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:

    log(
        "=" * 70
    )

    log(
        "WHATSAPP WEB AUTOMATION BOT"
    )

    log(
        "=" * 70
    )

    # ------------------------------------------------------------
    # Read contacts.
    # ------------------------------------------------------------

    contacts = read_contacts(
        CONTACTS_FILE
    )

    if not contacts:

        log(
            "No contacts to process."
        )

        return

    started = (
        datetime.now()
        .isoformat(
            timespec="seconds"
        )
    )

    results = []

    # ------------------------------------------------------------
    # Start Playwright.
    # ------------------------------------------------------------

    with sync_playwright() as p:

        context = (
            p.chromium
            .launch_persistent_context(

                user_data_dir=str(
                    SESSION_DIR
                ),

                headless=False,

                viewport={
                    "width": 1280,
                    "height": 850
                },

            )
        )

        # ------------------------------------------------------------
        # Reuse existing page if available.
        # ------------------------------------------------------------

        if context.pages:

            page = context.pages[0]

        else:

            page = context.new_page()

        try:

            # ========================================================
            # LOGIN ONLY ONCE
            # ========================================================

            login(
                page
            )

            # ========================================================
            # PROCESS CONTACTS
            # ========================================================

            for i, contact in enumerate(
                contacts,
                start=1
            ):

                result = process_contact(
                    page,
                    contact,
                    i
                )

                results.append(
                    result
                )

                # ----------------------------------------------------
                # Save after every contact.
                # This protects the report if something goes wrong
                # later.
                # ----------------------------------------------------

                save_json(
                    results,
                    started
                )

                # ----------------------------------------------------
                # Wait before next contact.
                # The same browser/session is reused.
                # ----------------------------------------------------

                if i < len(contacts):

                    human_delay(
                        page
                    )

        except KeyboardInterrupt:

            log(
                "Stopped by user."
            )

        except Exception as error:

            log(
                f"Fatal error: "
                f"{type(error).__name__}: "
                f"{error}"
            )

        finally:

            # --------------------------------------------------------
            # Always save whatever was completed.
            # --------------------------------------------------------

            if results:

                save_json(
                    results,
                    started
                )

            page.wait_for_timeout(
                2000
            )

            context.close()

    # ================================================================
    # FINAL SUMMARY
    # ================================================================

    summary = build_summary(
        results
    )

    log(
        "=" * 70
    )

    log(
        "AUTOMATION COMPLETE"
    )

    log(
        "=" * 70
    )

    log(
        f"Total: "
        f"{summary['total']}"
    )

    log(
        f"Successfully sent: "
        f"{summary['sent_successfully']}"
    )

    log(
        f"Pending: "
        f"{summary['pending']}"
    )

    log(
        f"Not found: "
        f"{summary['not_found']}"
    )

    log(
        f"Failed: "
        f"{summary['failed']}"
    )

    log(
        f"JSON report: "
        f"{JSON_REPORT}"
    )

    log(
        f"Screenshots: "
        f"{SCREENSHOT_DIR}"
    )


# ============================================================================
# PROGRAM ENTRY POINT
# ============================================================================

if __name__ == "__main__":

    main()
