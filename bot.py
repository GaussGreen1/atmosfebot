import json
import os
import random
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Ignore dates before this
MIN_DATE = datetime.strptime("22/06/2026", "%d/%m/%Y")

URLS = [
    {
        "name": "20:00 Dinner",
        "url": "https://atmosfera.atm.it/Home/GetAvailableDates?serviceId=1&tramId=1&reservationId=0&mealTime=20%3A00",
    },
    {
        "name": "20:30 Dinner",
        "url": "https://atmosfera.atm.it/Home/GetAvailableDates?serviceId=2&tramId=2&reservationId=0&mealTime=20%3A30",
    },
]

SEEN_FILE = "seen_slots.json"

CHECK_COUNT = 0
LAST_HEARTBEAT = 0
HEARTBEAT_INTERVAL = 60 * 60 * 6  # every 6 hours


def load_seen():
    if not Path(SEEN_FILE).exists():
        return set()

    with open(SEEN_FILE, "r") as f:
        return set(json.load(f))


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": text,
        },
        timeout=30,
    )

    response.raise_for_status()


def check_url(config):
    response = requests.get(
        config["url"],
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0 Safari/537.36"
            )
        },
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    available = []

    for item in data.get("availabilities", []):

        slot_date = datetime.strptime(item["Day"], "%d/%m/%Y")

        # Ignore dates before June 22
        if slot_date < MIN_DATE:
            continue

        seats = item.get("AvailableSeats")

        if not seats:
            continue

        for seat in seats:

            t2 = seat.get("T2", 0)

            # Tables for 2 available
            if t2 > 0:

                available.append(
                    {
                        "day": item["Day"],
                        "round": item["Round"],
                        "tram": seat["TramName"],
                        "t2": t2,
                        "service": config["name"],
                    }
                )

    return available


def main():
    global CHECK_COUNT

    CHECK_COUNT += 1

    print(f"[CHECK #{CHECK_COUNT}] Checking ATMosfera...")

    seen = load_seen()

    for config in URLS:

        try:
            slots = check_url(config)

            if not slots:
                print(f'[OK] No tables for 2 found for {config["name"]}')
                continue

            for slot in slots:

                key = (
                    f'{slot["day"]}_'
                    f'{slot["round"]}_'
                    f'{slot["tram"]}_'
                    f'{slot["service"]}'
                )

                if key in seen:
                    print("[SKIP] Already notified:", key)
                    continue

                message = (
                    f"🚨 ATMosfera table for 2 available!\n\n"
                    f"📅 Date: {slot['day']}\n"
                    f"🕗 Time: {slot['round']}\n"
                    f"🚋 Tram: {slot['tram']}\n"
                    f"🍽️ Tables for 2: {slot['t2']}\n"
                    f"🎟️ Service: {slot['service']}\n\n"
                    f"https://atmosfera.atm.it/"
                )

                send_telegram_message(message)

                print("[FOUND] Notification sent:", key)

                seen.add(key)

        except Exception as e:
            print(f'[ERROR] {config["name"]}: {e}')

            try:
                send_telegram_message(
                    f"❌ ATMosfera bot error\n\n"
                    f"{config['name']}\n"
                    f"{str(e)}"
                )
            except:
                pass

    save_seen(seen)


if __name__ == "__main__":

    print("🚀 ATMosfera watcher started")

    try:
        send_telegram_message("🚀 ATMosfera watcher started")
    except Exception as e:
        print("[ERROR] Could not send startup message:", e)

    while True:

        try:
            main()

            now = time.time()

            if now - LAST_HEARTBEAT > HEARTBEAT_INTERVAL:

                send_telegram_message(
                    f"✅ ATMosfera watcher alive\n"
                    f"Checks completed: {CHECK_COUNT}"
                )

                LAST_HEARTBEAT = now

        except Exception as e:

            print("[FATAL ERROR]", e)

            try:
                send_telegram_message(
                    f"❌ ATMosfera fatal error\n\n{str(e)}"
                )
            except:
                pass

        # Random delay between 55-75 sec
        sleep_time = random.randint(55, 75)

        print(f"[SLEEP] {sleep_time} seconds")

        time.sleep(sleep_time)