"""
TikTok Auto Poster - Main CLI Orchestrator
Automates multi-account video posting to TikTok Studio with wave-cycle scheduling and live countdown.
"""

import sys
import time
import random
import asyncio
import argparse
from pathlib import Path
from datetime import datetime, timedelta

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config import (
    DEFAULT_INTERVAL_MINUTES,
    INTER_ACCOUNT_DELAY,
    VIDEOS_DIR
)
from login_helper import list_accounts, load_accounts
from queue_manager import (
    ensure_account_video_folders,
    prepare_cycle_batches,
    mark_video_completed
)
from tiktok_uploader import post_video_to_tiktok
from caption_generator import generate_unique_caption

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner():
    banner = f"""{CYAN}{BOLD}
╔════════════════════════════════════════════════════════════════════╗
║               🎬 TIKTOK STUDIO AUTO POSTER BOT 🚀                  ║
║      Multi-Account Wave Scheduler • Dynamic Captions • Anti-Bot    ║
╚════════════════════════════════════════════════════════════════════╝{RESET}"""
    print(banner)


async def live_countdown_timer(total_seconds: int, next_cycle_num: int):
    """Menampilkan live countdown progress bar di terminal."""
    end_time = datetime.now() + timedelta(seconds=total_seconds)
    target_clock = end_time.strftime("%H:%M:%S")

    print(f"\n{YELLOW}{BOLD}⏳ JEDA JADWAL SIKLUS AKTIF:{RESET}")
    print(f"🎯 Jadwal Siklus #{next_cycle_num:02d} Berikutnya : {CYAN}{BOLD}{target_clock}{RESET}")
    print(f"⏱️ Durasi Jeda             : {total_seconds // 60} Menit\n")

    remaining = total_seconds
    while remaining > 0:
        mins, secs = divmod(remaining, 60)
        hours, mins = divmod(mins, 60)
        time_str = f"{hours:02d}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins:02d}:{secs:02d}"

        bar_len = 25
        pct = 1.0 - (remaining / total_seconds)
        filled = int(bar_len * pct)
        bar = "█" * filled + "░" * (bar_len - filled)

        print(f"\r  [{bar}] ⏳ Sisa Waktu: {BOLD}{time_str}{RESET} menuju siklus berikutnya... ", end="", flush=True)

        step = 1
        await asyncio.sleep(step)
        remaining -= step

    print("\r" + " " * 80 + "\r", end="", flush=True)
    print(f"{GREEN}⏰ Waktu jeda selesai! Memulai siklus posting berikutnya...{RESET}\n")


async def run_scheduled_posting(interval_minutes: int = DEFAULT_INTERVAL_MINUTES, headless: bool = False):
    """
    Menjalankan siklus posting otomatis:
    Dalam 1 siklus:
      1. Upload video untuk Akun 1
      2. Jeda singkat (20-35 detik)
      3. Upload video untuk Akun 2
      4. Jeda jadwal interval (misal 45 menit) sebelum masuk ke siklus berikutnya.
    """
    ensure_account_video_folders()
    rounds = prepare_cycle_batches()

    if not rounds:
        print(f"\n{YELLOW}⚠️ Tidak ada antrean video baru yang ditemukan di folder 'videos/'.{RESET}")
        print("Silakan masukkan video ke subfolder masing-masing akun:")
        accounts = load_accounts().get("accounts", {})
        for acc in accounts:
            print(f" 👉 {VIDEOS_DIR / acc}")
        print()
        return

    interval_sec = interval_minutes * 60
    total_rounds = len(rounds)
    total_videos = sum(len(r["items"]) for r in rounds)

    print(f"\n{CYAN}{BOLD}📋 STRUKTUR SIKLUS POSTING (Wave Cycles):{RESET}")
    print("=" * 70)
    print(f"📊 Total Video   : {BOLD}{total_videos} Video{RESET} ({total_rounds} Siklus)")
    print(f"⏱️ Delay Siklus  : {BOLD}{interval_minutes} Menit{RESET} setelah semua akun selesai di satu ronde.")
    print("=" * 70)
    for r in rounds:
        acc_str = ", ".join([f"{it['account_id']} ({it['filename']})" for it in r["items"]])
        print(f"  • Siklus #{r['round_number']:02d}: {acc_str}")
    print("=" * 70 + "\n")

    for r_idx, r_data in enumerate(rounds, 1):
        round_num = r_data["round_number"]
        items = r_data["items"]

        print(f"\n{CYAN}{BOLD}╔══════════════════════════════════════════════════════════════════╗{RESET}")
        print(f"{CYAN}{BOLD}║  🚀 MEMULAI SIKLUS #{round_num:02d} DARI {total_rounds:02d}                                       ║{RESET}")
        print(f"{CYAN}{BOLD}╚══════════════════════════════════════════════════════════════════╝{RESET}")

        for it_idx, item in enumerate(items, 1):
            vid_path = item["video_path"]
            acc = item["account_id"]
            caption = item["caption"]

            print(f"\n{CYAN}▶ [{it_idx}/{len(items)} di Siklus #{round_num}] Upload Akun: {BOLD}{acc}{RESET}")
            print(f"📁 Video: {vid_path.name}")

            try:
                res = await post_video_to_tiktok(
                    video_path=vid_path,
                    account_id=acc,
                    caption=caption,
                    headless=headless
                )
                if res.get("status") == "success":
                    mark_video_completed(item)
            except Exception as e:
                print(f"{RED}❌ Error saat posting video {vid_path.name} di {acc}: {e}{RESET}")

            # Jeda natural antar akun dalam 1 siklus
            if it_idx < len(items):
                delay = random.randint(*INTER_ACCOUNT_DELAY)
                print(f"\n{YELLOW}⏳ Jeda {delay} detik sebelum berganti ke akun berikutnya...{RESET}")
                await asyncio.sleep(delay)

        # Setelah seluruh akun di siklus ini selesai -> jeda interval sebelum siklus berikutnya
        if r_idx < total_rounds:
            print(f"\n{GREEN}✓ SIKLUS #{round_num:02d} SELESAI UNTUK SEMUA AKUN!{RESET}")
            await live_countdown_timer(interval_sec, next_cycle_num=round_num + 1)

    print(f"\n{GREEN}{BOLD}🎉 SELURUH SIKLUS POSTING TELAH SELESAI! SEMUA VIDEO TELAH DIPOSTING. 🚀{RESET}\n")


def main():
    print_banner()
    parser = argparse.ArgumentParser(description="TikTok Auto Poster Bot")
    parser.add_argument("--post-all", action="store_true", help="Jalankan semua siklus posting berjadwal")
    parser.add_argument("--single", action="store_true", help="Jalankan posting satu video langsung")
    parser.add_argument("--account", type=str, default="account_1", help="ID Akun untuk mode single (default: account_1)")
    parser.add_argument("--video", type=str, default=None, help="Path video MP4 untuk mode single")
    parser.add_argument("--caption", type=str, default=None, help="Custom caption untuk mode single")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_MINUTES, help="Jeda antar siklus dalam menit (default: 45)")
    parser.add_argument("--headless", action="store_true", help="Jalankan browser di background tanpa GUI")
    parser.add_argument("--list", action="store_true", help="Tampilkan daftar akun terdaftar")
    parser.add_argument("--status", action="store_true", help="Tampilkan status antrean video")

    args = parser.parse_args()

    if args.list:
        list_accounts()
        return

    if args.status:
        ensure_account_video_folders()
        batches = prepare_cycle_batches()
        total_vids = sum(len(b["items"]) for b in batches)
        print(f"\n📊 STATUS ANTREAN VIDEO:")
        print(f"Total Video Siap Upload: {total_vids}")
        print(f"Total Siklus Terbentuk : {len(batches)}")
        for b in batches:
            print(f"  • Siklus #{b['round_number']:02d}: {len(b['items'])} akun ({', '.join([it['account_id'] for it in b['items']])})")
        print()
        return

    if args.single:
        if not args.video:
            print(f"{RED}❌ Error: Mode --single membutuhkan argumen --video <path_ke_file.mp4>{RESET}")
            return
        asyncio.run(post_video_to_tiktok(
            video_path=Path(args.video),
            account_id=args.account,
            caption=args.caption,
            headless=args.headless
        ))
        return

    if args.post_all:
        asyncio.run(run_scheduled_posting(interval_minutes=args.interval, headless=args.headless))
        return

    # Default help menu
    parser.print_help()


if __name__ == "__main__":
    main()
