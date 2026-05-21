import asyncio
import random
from functools import partial

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

COMMON_AREA_CODES = [
    "212", "213", "312", "404", "415", "512", "617", "713", "718", "805",
    "818", "917", "929", "310", "347", "646", "201", "609", "732", "908",
    "973", "702", "725", "303", "720", "206", "253", "360", "425", "503",
    "971", "602", "480", "623", "520", "214", "469", "972", "817", "682",
    "704", "980", "336", "919", "757", "804", "571", "703", "305", "786",
]


# ─── Sync helpers (run in executor) ─────────────────────────────────────────

def _validate_sync(account_sid: str, auth_token: str):
    client = Client(account_sid, auth_token)
    account = client.api.accounts(account_sid).fetch()
    return {
        "status": account.status,
        "friendly_name": account.friendly_name,
        "type": account.type,
    }


def _get_balance_sync(account_sid: str, auth_token: str):
    client = Client(account_sid, auth_token)
    balance = client.api.v2010.accounts(account_sid).balance.fetch()
    return {"balance": balance.balance, "currency": balance.currency}


def _search_numbers_sync(account_sid: str, auth_token: str, area_code: str):
    client = Client(account_sid, auth_token)
    numbers = client.available_phone_numbers("US").local.list(
        area_code=area_code,
        sms_enabled=True,
        limit=5,
    )
    return [n.phone_number for n in numbers]


def _purchase_number_sync(account_sid: str, auth_token: str, phone_number: str):
    client = Client(account_sid, auth_token)
    number = client.incoming_phone_numbers.create(phone_number=phone_number)
    return number.phone_number


def _get_owned_numbers_sync(account_sid: str, auth_token: str):
    client = Client(account_sid, auth_token)
    numbers = client.incoming_phone_numbers.list()
    return [n.phone_number for n in numbers]


def _get_messages_sync(account_sid: str, auth_token: str, to_number: str):
    client = Client(account_sid, auth_token)
    messages = client.messages.list(to=to_number, limit=10)
    return [
        {
            "sid": m.sid,
            "from": m.from_,
            "body": m.body,
            "date_sent": str(m.date_sent),
        }
        for m in messages
        if m.direction == "inbound"
    ]


def _get_all_inbound_sync(account_sid: str, auth_token: str):
    client = Client(account_sid, auth_token)
    messages = client.messages.list(limit=50)
    return [
        {
            "sid": m.sid,
            "from": m.from_,
            "to": m.to,
            "body": m.body,
            "date_sent": str(m.date_sent),
        }
        for m in messages
        if m.direction == "inbound"
    ]


# ─── Async wrappers ───────────────────────────────────────────────────────────

async def _run(fn, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(fn, *args))


async def validate_credentials(account_sid: str, auth_token: str):
    return await _run(_validate_sync, account_sid, auth_token)


async def get_balance(account_sid: str, auth_token: str):
    return await _run(_get_balance_sync, account_sid, auth_token)


async def search_numbers(account_sid: str, auth_token: str, area_code: str):
    return await _run(_search_numbers_sync, account_sid, auth_token, area_code)


async def purchase_number(account_sid: str, auth_token: str, phone_number: str):
    return await _run(_purchase_number_sync, account_sid, auth_token, phone_number)


async def get_owned_numbers(account_sid: str, auth_token: str):
    return await _run(_get_owned_numbers_sync, account_sid, auth_token)


async def get_messages(account_sid: str, auth_token: str, to_number: str):
    return await _run(_get_messages_sync, account_sid, auth_token, to_number)


async def get_all_inbound_messages(account_sid: str, auth_token: str):
    return await _run(_get_all_inbound_sync, account_sid, auth_token)
