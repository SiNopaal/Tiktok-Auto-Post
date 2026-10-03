"""
TikTok Auto Poster - Core Video Uploader Engine
Automates video upload and publishing via TikTok Studio Web with anti-detection and error recovery.
"""

import sys
import json
import time
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

from playwright.async_api import async_playwright, Page, Frame, Locator
from playwright_stealth import Stealth

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config import (
    COOKIES_DIR,
    SCREENSHOTS_DIR,
    POST_HISTORY_FILE,
    TIKTOK_UPLOAD_URL,
    TIKTOK_FALLBACK_URL,
    HEADLESS,
    BROWSER_CHANNEL,
    VIEWPORT,
    USER_AGENT,
    UPLOAD_TIMEOUT,
    AFTER_UPLOAD_WAIT,
    DEFAULT_VISIBILITY,
)
from caption_generator import generate_unique_caption

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def log_history(entry: Dict[str, Any]):
    """Mencatat riwayat posting ke file JSON."""
    history = []
    if POST_HISTORY_FILE.exists():
        try:
            with open(POST_HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []

    history.append(entry)
    POST_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(POST_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


async def find_file_input(page: Page) -> Tuple[Optional[Locator], Optional[Any]]:
    """Mencari elemen input[type='file'] di halaman utama atau iframe."""
    main_input = page.locator('input[type="file"]')
    if await main_input.count() > 0:
        return main_input.first, page

    for frame in page.frames:
        frame_input = frame.locator('input[type="file"]')
        if await frame_input.count() > 0:
            return frame_input.first, frame

    return None, None


async def find_caption_editor(page: Page, target_frame: Optional[Frame] = None) -> Tuple[Optional[Locator], Optional[Any]]:
    """Mencari elemen editor caption TikTok Studio (DraftEditor)."""
    context_to_search = [target_frame] if target_frame else [page] + page.frames

    selectors = [
        'div[contenteditable="true"]',
        'div.notranslate[contenteditable="true"]',
        'div[data-placeholder*="caption" i]',
        'div[data-placeholder*="Keterangan" i]',
        'div.DraftEditor-editorContainer div[contenteditable="true"]',
        'div[data-e2e="caption-editor"]',
        'div.public-DraftEditor-content'
    ]

    for ctx in context_to_search:
        if not ctx:
            continue
        for sel in selectors:
            loc = ctx.locator(sel)
            if await loc.count() > 0 and await loc.first.is_visible():
                return loc.first, ctx

    return None, None


async def wait_for_upload_finished(page: Page, target_frame: Optional[Frame] = None, timeout: int = UPLOAD_TIMEOUT) -> bool:
    """Menunggu sampai file video selesai diproses dan siap dipublikasikan."""
    print(f"{CYAN}⏳ Menunggu proses upload video ke server TikTok...{RESET}")
    start_time = time.time()
    last_reported_pct = ""

    while time.time() - start_time < timeout:
        ctxs = [target_frame] if target_frame else [page] + page.frames

        for ctx in ctxs:
            if not ctx:
                continue

            # Indikator teks sukses upload
            try:
                uploaded_indicator = ctx.locator(
                    'text="Uploaded", text="Diunggah", text="Video uploaded", text="Upload complete", div:has-text("100%")'
                )
                if await uploaded_indicator.count() > 0 and await uploaded_indicator.first.is_visible():
                    print(f"{GREEN}✓ Video berhasil terupload 100%!{RESET}")
                    await asyncio.sleep(2)
                    return True
            except Exception:
                pass

            # Indikator persentase
            try:
                progress_elem = ctx.locator('div[class*="progress"], div:has-text("%")').first
                if await progress_elem.count() > 0:
                    txt = (await progress_elem.inner_text()).strip()
                    if "%" in txt and txt != last_reported_pct:
                        print(f"  📊 Status upload: {txt[:40]}")
                        last_reported_pct = txt
                        if "100%" in txt:
                            await asyncio.sleep(2)
                            return True
            except Exception:
                pass

            # Cek form aktif
            try:
                post_btn = ctx.locator('button:has-text("Post"), button:has-text("Publikasikan")').first
                if await post_btn.count() > 0 and await post_btn.is_visible():
                    is_disabled = await post_btn.get_attribute("disabled")
                    aria_disabled = await post_btn.get_attribute("aria-disabled")
                    btn_text = (await post_btn.inner_text()).strip()

                    if is_disabled is None and aria_disabled != "true" and "uploading" not in btn_text.lower():
                        cover_elem = ctx.locator('div:has-text("Cover"), div:has-text("Sampul")')
                        if await cover_elem.count() > 0:
                            print(f"{GREEN}✓ Form post aktif dan siap dipublish!{RESET}")
                            return True
            except Exception:
                pass

        await asyncio.sleep(2)

    print(f"{YELLOW}⚠️ Batas waktu tunggu indikator upload tercapai, mencoba melanjutkan...{RESET}")
    return False


async def dismiss_tiktok_popups(page: Page):
    """Menutup dialog dan tooltip pop-up TikTok secara aman tanpa membatalkan form posting."""
    try:
        # 1. Dialog modal pop-up (TUXModal / Floating UI)
        modal = page.locator('div[class*="TUXModal"], div[class*="Modal-overlay"], div[data-floating-ui-portal]')
        if await modal.count() > 0:
            for i in range(await modal.count()):
                m = modal.nth(i)
                if await m.is_visible():
                    modal_text = (await m.inner_text()).lower()

                    # Jika pop-up "Continue to post? We're still checking your video..." -> klik Post now
                    if "continue to post" in modal_text or "post now" in modal_text:
                        post_now_btn = m.locator('button:has-text("Post now"), button:has-text("Posting sekarang")').first
                        if await post_now_btn.count() > 0 and await post_now_btn.is_visible():
                            print("Mengklik 'Post now' pada modal konfirmasi pemeriksaan konten...")
                            await post_now_btn.click()
                            await asyncio.sleep(1)
                            continue

                    # Jika pop-up "Turn on automatic content checks?" -> klik Turn on
                    turn_on_btn = m.locator('button:has-text("Turn on"), button:has-text("Aktifkan")').first
                    if await turn_on_btn.count() > 0 and await turn_on_btn.is_visible():
                        print("Menutup dialog pemeriksaan konten otomatis...")
                        await turn_on_btn.click()
                        await asyncio.sleep(1)
                        continue

                    # Jika dialog keluar / discard perubahan -> klik Cancel agar tidak keluar
                    if "exit" in modal_text or "discard" in modal_text or "keluar" in modal_text:
                        cancel_btn = m.locator('button:has-text("Cancel"), button:has-text("Batal")').first
                        if await cancel_btn.count() > 0 and await cancel_btn.is_visible():
                            await cancel_btn.click()
                            await asyncio.sleep(1)
                            continue

                    # Tutup modal lainnya
                    close_btn = m.locator('[aria-label="Close"], button:has-text("Got it"), button:has-text("Mengerti")').first
                    if await close_btn.count() > 0 and await close_btn.is_visible():
                        await close_btn.click()
                        await asyncio.sleep(1)

        # 2. Tooltip panduan mengambang ("Got it")
        for text in ["Got it", "Mengerti", "Not now", "Nanti saja"]:
            btn = page.locator(f'button:has-text("{text}")').first
            if await btn.count() > 0 and await btn.is_visible():
                print(f"Menutup tooltip panduan: {text}")
                await btn.click()
                await asyncio.sleep(0.5)
    except Exception:
        pass


async def post_video_to_tiktok(
    video_path: Path,
    account_id: str,
    caption: Optional[str] = None,
    headless: Optional[bool] = None,
    visibility: str = DEFAULT_VISIBILITY
) -> Dict[str, Any]:
    """
    Eksekusi otomatis upload dan posting video TikTok untuk suatu akun.
    """
    video_path = Path(video_path).resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"File video tidak ditemukan: {video_path}")

    cookie_file = COOKIES_DIR / f"{account_id}.json"
    if not cookie_file.exists():
        raise FileNotFoundError(
            f"File cookie untuk akun '{account_id}' tidak ditemukan di {cookie_file}. "
            f"Jalankan: python login_helper.py --login {account_id}"
        )

    with open(cookie_file, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    final_caption = caption if caption else generate_unique_caption()
    use_headless = HEADLESS if headless is None else headless

    print(f"\n{CYAN}{BOLD}{'='*60}{RESET}")
    print(f"{CYAN}{BOLD}🎬 TIKTOK AUTO POSTER ENGINE{RESET}")
    print(f"{CYAN}{BOLD}{'='*60}{RESET}")
    print(f"👤 Akun        : {BOLD}{account_id}{RESET}")
    print(f"📁 Video       : {video_path.name} ({video_path.stat().st_size / (1024*1024):.2f} MB)")
    print(f"👁️ Headless    : {use_headless}")
    print(f"📝 Caption Preview:\n{YELLOW}{final_caption[:140]}...{RESET}\n")

    result = {
        "timestamp": datetime.now().isoformat(),
        "account_id": account_id,
        "video_file": str(video_path.name),
        "video_path": str(video_path),
        "caption": final_caption,
        "status": "pending",
        "screenshot": None,
        "error": None
    }

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                channel=BROWSER_CHANNEL,
                headless=use_headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--start-maximized"]
            )
        except Exception:
            browser = await p.chromium.launch(
                headless=use_headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--start-maximized"]
            )

        context = await browser.new_context(
            viewport=None if not use_headless else VIEWPORT,
            user_agent=USER_AGENT
        )

        await context.add_cookies(cookies)
        page = await context.new_page()
        stealth = Stealth()
        await stealth.apply_stealth_async(page)

        try:
            # 1. Buka TikTok Studio Upload
            print(f"{CYAN}🌐 Membuka TikTok Studio Upload ({TIKTOK_UPLOAD_URL})...{RESET}")
            try:
                await page.goto(TIKTOK_UPLOAD_URL, wait_until="domcontentloaded", timeout=45000)
            except Exception:
                print(f"{YELLOW}Mencoba URL fallback Creator Center...{RESET}")
                await page.goto(TIKTOK_FALLBACK_URL, wait_until="domcontentloaded", timeout=45000)

            await asyncio.sleep(4)

            # Cek sesi
            current_url = page.url
            if "/login" in current_url:
                raise Exception(
                    f"Sesi login untuk '{account_id}' kedaluwarsa. "
                    f"Perbarui cookie dengan: python login_helper.py --login {account_id}"
                )

            # 2. Cari input file dan upload
            print(f"{CYAN}🔍 Mencari form upload video...{RESET}")
            file_input, target_context = await find_file_input(page)

            if not file_input:
                select_btn = page.locator(
                    'button:has-text("Select video"), button:has-text("Select file"), div[data-e2e="select-file-btn"]'
                ).first
                if await select_btn.count() > 0 and await select_btn.is_visible():
                    print("Mengklik tombol 'Select video'...")
                    async with page.expect_file_chooser() as fc_info:
                        await select_btn.click()
                    file_chooser = await fc_info.value
                    await file_chooser.set_files(str(video_path))
                    print(f"{GREEN}✓ Video berhasil dimasukkan via File Chooser!{RESET}")
                else:
                    raise Exception("Elemen input upload file video tidak ditemukan di halaman.")
            else:
                print(f"Mengunggah file video: {video_path.name}...")
                await file_input.set_input_files(str(video_path))
                print(f"{GREEN}✓ Video berhasil dimasukkan ke input upload!{RESET}")

            # 3. Tunggu upload selesai
            await wait_for_upload_finished(page, target_context, timeout=UPLOAD_TIMEOUT)
            await asyncio.sleep(AFTER_UPLOAD_WAIT)

            # 4. Bersihkan dialog & Isi Caption
            await dismiss_tiktok_popups(page)
            print(f"{CYAN}✍️ Mengisi caption video...{RESET}")
            caption_editor, caption_ctx = await find_caption_editor(page, target_context)

            if caption_editor:
                await dismiss_tiktok_popups(page)
                try:
                    await caption_editor.focus()
                except Exception:
                    pass

                # Bersihkan caption default via DOM execCommand agar tidak memicu tombol Back navigasi browser
                await page.evaluate("""() => {
                    const el = document.querySelector('div[contenteditable="true"]');
                    if (el) {
                        el.focus();
                        document.execCommand('selectAll', false, null);
                        document.execCommand('delete', false, null);
                    }
                }""")
                await asyncio.sleep(0.5)

                # Masukkan caption baru
                await page.keyboard.insert_text(final_caption)
                await asyncio.sleep(0.5)
                print(f"{GREEN}✓ Caption berhasil diisi!{RESET}")
            else:
                print(f"{YELLOW}⚠️ Editor caption otomatis tidak ditemukan, melanjutkan dengan caption default.{RESET}")

            await asyncio.sleep(2)
            await dismiss_tiktok_popups(page)

            # 5. Cari tombol Post
            print(f"{CYAN}🚀 Mencari tombol Post...{RESET}")
            post_button = None

            try:
                role_btn = page.get_by_role("button", name="Post", exact=True)
                if await role_btn.count() > 0 and await role_btn.first.is_visible():
                    post_button = role_btn.first
            except Exception:
                pass

            if not post_button:
                search_contexts = [caption_ctx, target_context, page] + page.frames
                button_selectors = [
                    'button:has-text("Post")',
                    'button:has-text("Posting")',
                    'button:has-text("Publikasikan")',
                    'button:has-text("Publish")',
                    'button[data-e2e="post_video_button"]',
                    'button[data-e2e="post-btn"]'
                ]

                for ctx in search_contexts:
                    if not ctx:
                        continue
                    for sel in button_selectors:
                        btn = ctx.locator(sel).first
                        if await btn.count() > 0 and await btn.is_visible():
                            post_button = btn
                            break
                    if post_button:
                        break

            if not post_button:
                raise Exception("Tombol 'Post' tidak ditemukan pada halaman.")

            # Tunggu tombol Post aktif
            for _ in range(30):
                is_disabled = await post_button.get_attribute("disabled")
                aria_disabled = await post_button.get_attribute("aria-disabled")
                if is_disabled is None and aria_disabled != "true":
                    break
                await asyncio.sleep(1)

            try:
                await post_button.scroll_into_view_if_needed()
            except Exception:
                pass

            await dismiss_tiktok_popups(page)
            print(f"{GREEN}🎯 Mengklik tombol 'Post' untuk mempublikasikan video...{RESET}")
            try:
                await post_button.click()
            except Exception:
                await post_button.click(force=True)
            await asyncio.sleep(3)

            # 6. Verifikasi keberhasilan Post & Tangani dialog konfirmasi
            success_detected = False
            search_contexts = [caption_ctx, target_context, page] + page.frames

            for sec_idx in range(60):
                await asyncio.sleep(1)

                if "/content" in page.url or "/manage" in page.url:
                    print(f"{GREEN}✓ URL dialihkan ke halaman konten TikTok ({page.url}){RESET}")
                    success_detected = True
                    break

                for ctx in search_contexts:
                    if not ctx:
                        continue

                    # Cek tombol konfirmasi 'Post now'
                    try:
                        role_post_now = ctx.get_by_role("button", name="Post now", exact=True)
                        if await role_post_now.count() > 0 and await role_post_now.first.is_visible():
                            print(f"{GREEN}🎯 Menemukan tombol 'Post now', mengklik untuk konfirmasi publish...{RESET}")
                            await role_post_now.first.click()
                            await asyncio.sleep(2)
                            continue
                    except Exception:
                        pass

                    try:
                        confirm_modal_btn = ctx.locator(
                            'button:has-text("Post now"), button:has-text("Posting sekarang"), '
                            'button:has-text("Post anyway"), button:has-text("Tetap posting"), '
                            'button:has-text("Continue to post"), button:has-text("Lanjutkan")'
                        ).first
                        if await confirm_modal_btn.count() > 0 and await confirm_modal_btn.is_visible():
                            print(f"{GREEN}🎯 Mengklik konfirmasi dialog TikTok: '{await confirm_modal_btn.inner_text()}'...{RESET}")
                            await confirm_modal_btn.click()
                            await asyncio.sleep(2)
                            continue
                    except Exception:
                        pass

                    # Cek indikator video terunggah
                    try:
                        modal = ctx.locator(
                            'text="Your video has been uploaded", text="Your video is being uploaded", '
                            'text="Manage your posts", text="Post another video", text="Upload another video", '
                            'text="Kelola kiriman Anda", text="Video Anda telah diunggah", '
                            'a:has-text("Manage your posts"), button:has-text("Manage your posts"), '
                            'button:has-text("Post another video"), button:has-text("Upload another video")'
                        ).first
                        if await modal.count() > 0 and await modal.is_visible():
                            print(f"{GREEN}✓ Deteksi sukses TikTok: {await modal.inner_text()}{RESET}")
                            success_detected = True
                            break
                    except Exception:
                        pass

                if success_detected:
                    break

                if sec_idx % 5 == 0:
                    await dismiss_tiktok_popups(page)

            # Ambil screenshot bukti posting
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            ss_path = SCREENSHOTS_DIR / f"post_{account_id}_{timestamp_str}.png"
            await page.screenshot(path=str(ss_path), full_page=False)

            if not success_detected:
                raise Exception("Tombol Post diklik, namun konfirmasi sukses dari TikTok belum terdeteksi dalam 60 detik.")

            result["screenshot"] = str(ss_path)
            result["status"] = "success"

            print(f"\n{GREEN}{BOLD}🎉 VIDEO BERHASIL DIPOSTING KE TIKTOK! 🚀{RESET}")
            print(f"📸 Screenshot bukti posting tersimpan di: {ss_path.name}")

            log_history(result)
            return result

        except Exception as e:
            err_msg = str(e)
            result["status"] = "failed"
            result["error"] = err_msg
            print(f"\n{RED}{BOLD}❌ Gagal memposting video: {err_msg}{RESET}")

            try:
                err_ss = SCREENSHOTS_DIR / f"error_{account_id}_{int(time.time())}.png"
                await page.screenshot(path=str(err_ss))
                result["screenshot"] = str(err_ss)
                print(f"📸 Screenshot error tersimpan di: {err_ss.name}")
            except Exception:
                pass

            log_history(result)
            raise e

        finally:
            await browser.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TikTok Video Uploader CLI")
    parser.add_argument("--video", type=str, required=True, help="Path ke file video MP4")
    parser.add_argument("--account", type=str, default="account_1", help="ID Akun (default: account_1)")
    parser.add_argument("--caption", type=str, default=None, help="Custom caption (opsional)")
    parser.add_argument("--headless", action="store_true", help="Jalankan di background tanpa jendela")

    args = parser.parse_args()

    asyncio.run(post_video_to_tiktok(
        video_path=Path(args.video),
        account_id=args.account,
        caption=args.caption,
        headless=args.headless
    ))
