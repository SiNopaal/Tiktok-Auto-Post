"""
TikTok Auto Poster - Interactive Login & Session Manager
Handles human-assisted interactive login to bypass bot detection/captchas and saves cookies.
"""

import sys
import json
import time
import asyncio
import argparse
from pathlib import Path
from typing import Dict, Any, List
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config import (
    COOKIES_DIR,
    ACCOUNTS_FILE,
    USER_AGENT,
    BROWSER_CHANNEL,
    TIKTOK_UPLOAD_URL,
)

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def load_accounts() -> Dict[str, Any]:
    """Memuat data akun dari accounts.json jika ada, atau fallback ke accounts.example.json."""
    if ACCOUNTS_FILE.exists():
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    example_file = ACCOUNTS_FILE.parent / "accounts.example.json"
    if example_file.exists():
        try:
            with open(example_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {"accounts": {}}


def save_accounts(data: Dict[str, Any]):
    """Menyimpan konfigurasi akun ke accounts.json."""
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_account_cookie_path(account_id: str) -> Path:
    """Mendapatkan path file cookie untuk suatu akun."""
    return COOKIES_DIR / f"{account_id}.json"


def list_accounts():
    """Menampilkan status seluruh akun terdaftar dan keberadaan cookies."""
    acc_data = load_accounts()
    accounts = acc_data.get("accounts", {})

    print(f"\n{CYAN}{BOLD}📋 DAFTAR AKUN TIKTOK TERDAFTAR:{RESET}")
    print("=" * 65)
    if not accounts:
        print("  Belum ada akun terdaftar. Buat akun baru via login interactive:")
        print("  python login_helper.py --login account_1")
    else:
        for acc_id, info in accounts.items():
            cookie_file = get_account_cookie_path(acc_id)
            has_cookie = cookie_file.exists()
            cookie_size = f"{cookie_file.stat().st_size} bytes" if has_cookie else "Tidak ada"
            status_color = GREEN if has_cookie else RED
            status_text = "READY" if has_cookie else "BELUM LOGIN"

            print(f"  • {BOLD}{acc_id}{RESET} ({info.get('username', 'No username')})")
            print(f"    Status  : {status_color}{status_text}{RESET}")
            print(f"    Cookies : {cookie_file.name} ({cookie_size})")
    print("=" * 65 + "\n")


async def verify_session(account_id: str, headless: bool = True) -> bool:
    """Memverifikasi apakah cookie akun masih aktif dengan membuka TikTok Studio Upload."""
    cookie_file = get_account_cookie_path(account_id)
    if not cookie_file.exists():
        print(f"{RED}❌ File cookie tidak ditemukan untuk {account_id}{RESET}")
        return False

    with open(cookie_file, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                channel=BROWSER_CHANNEL,
                headless=headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
        except Exception:
            # Fallback ke bundled chromium jika channel chrome tidak ditemukan
            browser = await p.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )

        context = await browser.new_context(user_agent=USER_AGENT)
        await context.add_cookies(cookies)

        page = await context.new_page()
        stealth = Stealth()
        await stealth.apply_stealth_async(page)

        print(f"🔍 Memverifikasi sesi akun '{account_id}' pada TikTok Studio...")
        try:
            await page.goto(TIKTOK_UPLOAD_URL, wait_until="domcontentloaded", timeout=40000)
            await asyncio.sleep(4)

            current_url = page.url
            if "/login" in current_url:
                print(f"{RED}❌ Sesi untuk '{account_id}' telah KEDALUWARSA (Dialihkan ke login).{RESET}")
                await browser.close()
                return False

            file_input = page.locator('input[type="file"]')
            if await file_input.count() > 0 or "tiktokstudio" in current_url or "creator-center" in current_url:
                print(f"{GREEN}✓ Sesi untuk '{account_id}' VALID & SIAP DIGUNAKAN!{RESET}")
                await browser.close()
                return True
        except Exception as e:
            print(f"{YELLOW}⚠️ Verifikasi timeout atau terjadi kendala jaringan: {e}{RESET}")

        await browser.close()
        return False


async def login_interactive(account_id: str, timeout_seconds: int = 300) -> bool:
    """
    Membuka jendela browser Chrome visual agar pengguna dapat login langsung ke TikTok
    (via QR Code, Email, Nomor Telepon, Google, atau metode lainnya),
    lalu secara otomatis menangkap dan menyimpan cookies sesi.
    """
    print(f"\n{CYAN}{BOLD}{'='*65}{RESET}")
    print(f"{CYAN}{BOLD}🔐 LOGIN INTERAKTIF TIKTOK - AKUN: {account_id}{RESET}")
    print(f"{CYAN}{BOLD}{'='*65}{RESET}")
    print("Browser Chrome akan terbuka otomatis.")
    print("Silakan selesaikan proses login di browser:")
    print("  1. Gunakan Scan QR Code dari aplikasi TikTok (Paling Cepat & Aman)")
    print("  2. Atau masukkan Email / No HP dan password")
    print("  3. Selesaikan verifikasi captcha jika diminta")
    print(f"Waktu tunggu maksimal: {timeout_seconds // 60} menit.\n")

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                channel=BROWSER_CHANNEL,
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--start-maximized"]
            )
        except Exception:
            browser = await p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--start-maximized"]
            )

        context = await browser.new_context(
            viewport=None,
            user_agent=USER_AGENT
        )

        page = await context.new_page()
        stealth = Stealth()
        await stealth.apply_stealth_async(page)

        await page.goto("https://www.tiktok.com/login", wait_until="domcontentloaded")

        start_time = time.time()
        logged_in = False

        while time.time() - start_time < timeout_seconds:
            await asyncio.sleep(2)

            cookies = await context.cookies()
            cookie_names = [c["name"] for c in cookies]

            # Indikator autentikasi TikTok yang valid
            has_auth = "sessionid" in cookie_names or "sid_guard" in cookie_names

            current_url = page.url
            if has_auth and ("/login" not in current_url or "tiktokstudio" in current_url):
                logged_in = True
                break

            # Cek jika pengguna berhasil masuk ke TikTok Studio atau Feed
            if any(k in current_url for k in ["/foryou", "/tiktokstudio", "/creator-center"]):
                if len(cookies) > 5:
                    logged_in = True
                    break

        if not logged_in:
            print(f"\n{RED}❌ Waktu login habis atau login dibatalkan.{RESET}")
            await browser.close()
            return False

        print(f"\n{GREEN}✓ Login terdeteksi berhasil! Mengambil dan menyimpan cookies...{RESET}")
        
        # Buka TikTok Studio untuk mematangkan token sesi
        try:
            await page.goto(TIKTOK_UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(4)
        except Exception:
            pass

        final_cookies = await context.cookies()
        cookie_path = get_account_cookie_path(account_id)
        with open(cookie_path, "w", encoding="utf-8") as f:
            json.dump(final_cookies, f, indent=2)

        # Update accounts.json
        acc_data = load_accounts()
        if "accounts" not in acc_data:
            acc_data["accounts"] = {}

        if account_id not in acc_data["accounts"]:
            acc_data["accounts"][account_id] = {}

        acc_data["accounts"][account_id].update({
            "cookie_file": str(cookie_path.relative_to(ACCOUNTS_FILE.parent)),
            "enabled": True,
            "last_login": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        save_accounts(acc_data)

        print(f"{GREEN}{BOLD}🎉 Berhasil menyimpan {len(final_cookies)} cookie ke: {cookie_path.name}{RESET}")
        await browser.close()
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TikTok Login & Session Helper")
    parser.add_argument("--login", type=str, help="ID Akun untuk login interaktif (contoh: account_1)")
    parser.add_argument("--verify", type=str, help="ID Akun untuk verifikasi sesi (contoh: account_1)")
    parser.add_argument("--list", action="store_true", help="Tampilkan daftar akun dan status cookies")

    args = parser.parse_args()

    if args.list:
        list_accounts()
    elif args.login:
        asyncio.run(login_interactive(args.login))
    elif args.verify:
        asyncio.run(verify_session(args.verify))
    else:
        list_accounts()
        print("Penggunaan:")
        print("  python login_helper.py --login account_1")
        print("  python login_helper.py --verify account_1")
        print("  python login_helper.py --list")
