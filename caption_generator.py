"""
TikTok Auto Poster - Modular Caption Generator
Generates engaging, 100% unique captions with SHA-256 deduplication and customizable themes.
"""

import sys
import json
import random
import hashlib
from typing import List, Dict, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config import USED_CAPTIONS_FILE, CAPTION_THEME, TOKEN_OR_PRODUCT_NAME, CONTRACT_ADDRESS_OR_LINK

# ==========================================
# DUMMY TEMPLATES BY THEME
# ==========================================

TEMPLATES: Dict[str, Dict[str, List[str]]] = {
    "general": {
        "hooks": [
            "Trik sederhana ini jarang banget dibahas orang!",
            "Jangan scroll dulu kalau kamu pengen tau rahasia ini!",
            "Cuma 1% orang yang beneran nerapin hal penting ini.",
            "Ternyata begini cara paling efisien buat dapetin hasil maksimal!",
            "Stop buang-buang waktu dengan cara lama, coba teknik ini!",
            "Ini dia insight berharga yang wajib kamu simpan sekarang!",
            "Sering ngerasa stuck? Coba ubah langkah kecil ini!",
            "Pernah kepikiran nggak kenapa metode ini bisa secepat itu?",
        ],
        "bodies": [
            "Konsistensi kecil setiap hari bakal ngasih dampak eksponensial di masa depan.",
            "Banyak orang nyerah di awal cuma karena ekspektasi instan. Nikmati prosesnya!",
            "Fokus ke hal yang bisa kita kontrol, sisanya biarkan hasil yang berbicara.",
            "Eksplorasi terus peluang baru dan jangan takut buat mulai dari nol.",
            "Kunci utamanya ada di eksekusi, bukan cuma sekadar wacana atau rencana.",
        ],
        "ctas": [
            "Setuju nggak sama poin ini? Share opini kalian di komentar ya! 👇",
            "Tag temen kamu yang wajib tau info penting ini! 👥",
            "Simpan postingan ini biar nggak kelupaan pas butuh nanti! 📌",
            "Kira-kira nomor berapa yang paling relate sama kamu? Tulis di bawah! 💬",
            "Follow untuk tips dan insight menarik setiap hari! 🔔",
        ],
        "tags": [
            "#fyp", "#viral", "#foryoupage", "#trending", "#edukasi", "#inspirasi",
            "#insight", "#tipsandtricks", "#lifehacks", "#berfaedah"
        ]
    },
    "tech": {
        "hooks": [
            "Tools gratis ini bakal hemat waktu kerja kamu berkali-kali lipat! 💻",
            "Fitur tersembunyi yang bikin produktivitas kamu melesat tajam! ⚡",
            "Bocoran tools AI keren yang belum banyak orang tau!",
            "Jangan ngoding pakai cara manual lagi kalau ada jalan pintas ini!",
            "Workflow setup terbaik yang wajib dicoba developer & kreator!",
        ],
        "bodies": [
            "Otomatisasi proses repetitif bikin kamu bisa fokus ke ide-ide yang lebih bernilai.",
            "Teknologi berkembang sangat cepat, manfaatkan tools modern untuk scale up!",
            "Cuma butuh konfigurasi beberapa menit untuk hasil kerja yang jauh lebih rapi.",
        ],
        "ctas": [
            "Mau tutorial lengkapnya? Tulis di komen nanti kita buatin videonya! ✍️",
            "Save dulu videonya sebelum hilang di beranda kamu! 💾",
            "Kalian tim yang suka tools otomatis atau manual nih? Diskusi yuk! 💭",
        ],
        "tags": [
            "#tech", "#coding", "#developer", "#aitools", "#software", "#programming",
            "#productivity", "#techtok", "#learnontiktok", "#automation"
        ]
    },
    "crypto": {
        "hooks": [
            f"Analisis potensi tren berikutnya: Mengapa {TOKEN_OR_PRODUCT_NAME} menarik diperhatikan! 📈",
            f"Akumulasi di support level makin kuat, perhatikan pergerakan {TOKEN_OR_PRODUCT_NAME}! 🚀",
            f"Fundamental kuat dan likuiditas sehat, ini yang bikin {TOKEN_OR_PRODUCT_NAME} beda! 💎",
            "Jangan FOMO di puncak, pahami siklus pasar sebelum ambil keputusan!",
            f"Breakout pattern mulai terkonfirmasi pada grafik {TOKEN_OR_PRODUCT_NAME}! 📊",
        ],
        "bodies": [
            "Risiko selalu ada dalam trading, pastikan selalu DYOR dan gunakan manajemen modal bijak.",
            "Komunitas solid dan roadmap yang jelas selalu jadi penopang jangka panjang.",
            f"Info Resmi / Official Contract: `{CONTRACT_ADDRESS_OR_LINK}`",
        ],
        "ctas": [
            "Bagikan pandangan atau target analisa kalian di kolom komentar! 👇",
            "Bukan saran finansial. Selalu lakukan riset mandiri (DYOR)! ⚠️",
            "Follow untuk pantauan tren crypto dan Web3 terupdate setiap hari! 🔔",
        ],
        "tags": [
            "#crypto", "#web3", "#altcoins", "#trading", "#cryptocurrency",
            "#dyor", "#blockchain", "#investasi", "#solana", "#bitcoin"
        ]
    },
    "affiliate": {
        "hooks": [
            "Nemuin barang unik yang ternyata kepake banget sehari-hari! 📦✨",
            "Racun belanja bermanfaat yang nggak bikin kantong jebol! 🛒",
            "Review jujur setelah seminggu pemakaian, worth it banget!",
            "Daripada beli yang mahal, produk ini punya kualitas yang setara!",
        ],
        "bodies": [
            "Desainnya simpel, materialnya kokoh, dan fungsi utamanya bener-bener ngebantu.",
            f"Cek detail dan link produk langsung di bio profil atau tautan terkait!",
        ],
        "ctas": [
            "Link ada di bio ya, buruan sebelum kehabisan promo! 🛍️",
            "Menurut kalian worth it nggak dengan harga segini? Komen yuk! 👇",
        ],
        "tags": [
            "#racuntiktok", "#reviewproduk", "#unboxing", "#affiliate", "#rekomendasi",
            "#haul", "#belanjaonline", "#tiktokshop"
        ]
    }
}


def load_used_captions() -> set:
    """Memuat daftar hash caption yang sudah pernah dipakai."""
    if USED_CAPTIONS_FILE.exists():
        try:
            with open(USED_CAPTIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data.get("hashes", []))
        except Exception:
            return set()
    return set()


def save_used_caption(caption_text: str):
    """Menyimpan hash SHA-256 caption agar tidak pernah terulang."""
    c_hash = hashlib.sha256(caption_text.strip().encode("utf-8")).hexdigest()
    hashes = load_used_captions()
    hashes.add(c_hash)
    
    USED_CAPTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(USED_CAPTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump({"hashes": sorted(list(hashes))}, f, indent=2)


def generate_unique_caption(theme: Optional[str] = None, max_attempts: int = 100) -> str:
    """
    Menghasilkan caption yang 100% unik berdasarkan tema yang dipilih.
    Memanfaatkan SHA-256 deduplication untuk menjamin tidak ada duplikasi.
    """
    active_theme = theme if theme in TEMPLATES else CAPTION_THEME
    if active_theme not in TEMPLATES:
        active_theme = "general"

    pool = TEMPLATES[active_theme]
    used_hashes = load_used_captions()

    for _ in range(max_attempts):
        hook = random.choice(pool["hooks"])
        body = random.choice(pool["bodies"])
        cta = random.choice(pool["ctas"])

        # Pilih 3-5 hashtag secara acak
        tag_count = random.randint(3, 5)
        selected_tags = random.sample(pool["tags"], min(tag_count, len(pool["tags"])))
        tags_str = " ".join(selected_tags)

        # Susun caption
        caption = f"{hook}\n\n{body}\n\n{cta}\n\n{tags_str}"
        c_hash = hashlib.sha256(caption.strip().encode("utf-8")).hexdigest()

        if c_hash not in used_hashes:
            save_used_caption(caption)
            return caption

    # Fallback dengan timestamp unik jika pool terlampau sering digunakan
    fallback_id = random.randint(1000, 9999)
    caption = f"{hook}\n\n{body} (ID: #{fallback_id})\n\n{cta}\n\n{tags_str}"
    save_used_caption(caption)
    return caption


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test Caption Generator")
    parser.add_argument("--theme", type=str, default="general", choices=list(TEMPLATES.keys()), help="Tema caption")
    parser.add_argument("--count", type=int, default=3, help="Jumlah caption yang dihasilkan")
    args = parser.parse_args()

    print(f"--- PREVIEW CAPTION DUMMY (Tema: {args.theme}) ---")
    for i in range(1, args.count + 1):
        cap = generate_unique_caption(theme=args.theme)
        print(f"\n[Caption #{i}]\n{cap}\n" + "-" * 50)
