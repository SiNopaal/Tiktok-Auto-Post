"""
TikTok Auto Poster - Video Queue & Wave Cycle Manager
Scans video directories, organizes multi-account posting queues, and handles auto-archiving.
"""

import sys
import json
import shutil
from pathlib import Path
from typing import List, Dict, Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config import (
    VIDEOS_DIR,
    VIDEOS_DONE_DIR,
    POST_HISTORY_FILE,
    SUPPORTED_EXTENSIONS,
    MOVE_AFTER_POST,
    ACCOUNTS_FILE
)
from caption_generator import generate_unique_caption


def ensure_account_video_folders():
    """Membuat folder video untuk setiap akun yang terdaftar."""
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    accs = get_registered_accounts()
    for acc in accs:
        folder = VIDEOS_DIR / acc
        folder.mkdir(parents=True, exist_ok=True)


def get_registered_accounts() -> List[str]:
    """Mendapatkan daftar ID akun yang terdaftar dari accounts.json atau fallback."""
    if ACCOUNTS_FILE.exists():
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return list(data.get("accounts", {}).keys())
        except Exception:
            pass

    example_file = ACCOUNTS_FILE.parent / "accounts.example.json"
    if example_file.exists():
        try:
            with open(example_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return list(data.get("accounts", {}).keys())
        except Exception:
            pass

    return ["account_1", "account_2"]


def get_posted_video_identifiers() -> set:
    """Mengambil riwayat video yang sudah sukses di-post."""
    posted = set()
    if POST_HISTORY_FILE.exists():
        try:
            with open(POST_HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
                for entry in history:
                    if entry.get("status") == "success":
                        posted.add(f"{entry.get('account_id')}:{entry.get('video_file')}")
        except Exception:
            pass
    return posted


def scan_all_videos_by_account() -> Dict[str, List[Path]]:
    """Memindai seluruh file video yang tersedia per folder akun."""
    ensure_account_video_folders()
    result: Dict[str, List[Path]] = {}
    accounts = get_registered_accounts()

    for acc in accounts:
        folder = VIDEOS_DIR / acc
        if folder.exists():
            vids = []
            for ext in SUPPORTED_EXTENSIONS:
                vids.extend(list(folder.glob(f"*{ext}")))
                vids.extend(list(folder.glob(f"*{ext.upper()}")))
            vids = sorted(list(set(vids)), key=lambda p: p.stat().st_mtime)
            result[acc] = vids

    return result


def prepare_cycle_batches() -> List[Dict[str, Any]]:
    """
    Menyusun antrean posting dalam bentuk Siklus / Wave Cycles.
    Setiap siklus berisi:
    1 video dari account_1, lalu 1 video dari account_2.
    Setelah seluruh akun di satu siklus selesai, sistem akan memberi jeda interval sebelum siklus berikutnya.
    """
    ensure_account_video_folders()
    videos_by_acc = scan_all_videos_by_account()
    posted_ids = get_posted_video_identifiers()

    clean_queues: Dict[str, List[Path]] = {}
    accounts_order = get_registered_accounts()

    max_vids = 0
    for acc in accounts_order:
        vids = videos_by_acc.get(acc, [])
        pending = [v for v in vids if f"{acc}:{v.name}" not in posted_ids]
        if pending:
            clean_queues[acc] = pending
            if len(pending) > max_vids:
                max_vids = len(pending)

    rounds = []
    for step in range(max_vids):
        round_items = []
        for acc in accounts_order:
            vids = clean_queues.get(acc, [])
            if step < len(vids):
                vid = vids[step]
                caption = generate_unique_caption(vid.name)
                round_items.append({
                    "video_path": vid,
                    "filename": vid.name,
                    "account_id": acc,
                    "caption": caption,
                    "size_mb": round(vid.stat().st_size / (1024 * 1024), 2)
                })

        if round_items:
            rounds.append({
                "round_number": step + 1,
                "items": round_items
            })

    return rounds


def mark_video_completed(item: Dict[str, Any]):
    """Memindahkan file video yang telah sukses di-post ke folder videos_done/."""
    if not MOVE_AFTER_POST:
        return

    vid_path: Path = item["video_path"]
    acc = item["account_id"]
    dest_dir = VIDEOS_DONE_DIR / acc
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / vid_path.name

    try:
        if vid_path.exists():
            shutil.move(str(vid_path), str(dest_path))
            print(f"📦 Video dipindahkan ke folder arsip: videos_done/{acc}/{vid_path.name}")
    except Exception as e:
        print(f"⚠️ Gagal memindahkan video ke folder done: {e}")


if __name__ == "__main__":
    ensure_account_video_folders()
    rounds = prepare_cycle_batches()
    total_videos = sum(len(r["items"]) for r in rounds)
    print(f"Total Video Tersedia : {total_videos}")
    print(f"Total Siklus Posting : {len(rounds)}")
    for r in rounds:
        items_str = ", ".join([f"{it['account_id']} ({it['filename']})" for it in r["items"]])
        print(f"  • Siklus #{r['round_number']:02d}: {items_str}")
