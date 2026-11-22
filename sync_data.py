import base64
import json
import os
import re
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import requests
import urllib3
from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as cffi_requests
except Exception:
    cffi_requests = None

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

WIB = timezone(timedelta(hours=7))

DAYS_7 = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
DAYS_5_SGP = ["Senin", "Rabu", "Kamis", "Sabtu", "Minggu"]

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "mei": 5, "may": 5,
    "jun": 6, "jul": 7, "agu": 8, "aug": 8, "sep": 9,
    "okt": 10, "oct": 10, "nov": 11, "des": 12, "dec": 12,
}

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
}

HOST_FAIL_LOCK = threading.Lock()
HOST_FAIL_COUNTS = {}

MARKETS = [
    {
        "id": "sdy_pools",
        "name": "Sidney Pools",
        "keywords": ["sdy", "sidney", "sydney"],
        "reject_heading": ["lotto", "loto", "sdylt", "hklt", "macau", "singapore", "hongkong"],
        "must_lotto": False,
        "allow_lotto_word": False,
        "newest_bottom": True,
        "urls": [
            "https://datakeluaran7.com/data-sdy/",
            "https://datatogellengkap.info/data-sydney/",
            "https://datakeluaran.org/data-sdy/",
            "https://tabelpaito.com/data-keluaran-sdy/",
            "https://paitowarna4d.com/data-sdy/",
            "https://datakeluaran7.com/data-keluaran-sdy/",
        ],
    },
    {
        "id": "sdy_lotto",
        "name": "Sidney Lotto",
        "keywords": ["sdy", "sidney", "sydney"],
        "reject_heading": ["hklt", "macau", "singapore", "hongkong"],
        "must_lotto": True,
        "allow_lotto_word": False,
        "newest_bottom": True,
        "urls": [
            "https://datakeluaran7.com/data-sidney-lotto/",
            "https://datatogellengkap.info/data-sydney-lotto/",
            "https://datakeluaran7.com/data-sdy-lotto/",
            "https://datakeluaran.org/data-sdy-lotto/",
            "https://tabelpaito.com/data-keluaran-sdy-lotto/",
            "https://paitowarna4d.com/data-sdy-lotto/",
        ],
    },
    {
        "id": "hk_lotto",
        "name": "Hongkong Lotto",
        "keywords": ["hk", "hongkong"],
        "reject_heading": ["sdylt", "macau", "singapore", "sidney", "sydney"],
        "must_lotto": True,
        "allow_lotto_word": False,
        "newest_bottom": True,
        "urls": [
            "https://datakeluaran7.com/data-hk-lotto/",
            "https://datatogellengkap.info/data-hongkong-lotto/",
            "https://datakeluaran7.com/data-hongkong-lotto/",
            "https://datakeluaran.org/data-hk-lotto/",
            "https://tabelpaito.com/data-keluaran-hk-lotto/",
            "https://paitowarna4d.com/data-hk-lotto/",
        ],
    },
    {
        "id": "hk_pools",
        "name": "Hongkong Pools",
        "keywords": ["hk", "hongkong"],
        "reject_heading": [
            "lotto", "loto", "hklt", "hk toto", "toto hk", "hktoto",
            "hongkong toto", "toto hongkong", "sdylt", "macau",
            "singapore", "sidney", "sydney",
        ],
        "must_lotto": False,
        "allow_lotto_word": False,
        "newest_bottom": True,
        "urls": [
            "https://datatogellengkap.info/data-hongkong/",
            "https://datakeluaran7.com/data-hk-pools/",
            "https://datatogellengkap.info/data-hongkong-pools/",
            "https://datakeluaran7.com/data-hk/",
            "https://datakeluaran.org/data-hk-pools/",
            "https://datakeluaran.org/data-hk/",
            "https://tabelpaito.com/data-keluaran-hk-pools/",
            "https://paitowarna4d.com/data-hk-pools/",
        ],
    },
    {
        "id": "sgp",
        "name": "Singapore",
        "keywords": ["sgp", "singapore", "singapura"],
        "reject_heading": [
            "lotto", "loto", "sdylt", "hklt", "macau", "hongkong", "sidney", "sydney"
        ],
        "must_lotto": False,
        "allow_lotto_word": False,
        "newest_bottom": True,
        "urls": [
            "https://datakeluaran7.com/data-sgp/",
            "https://datatogellengkap.info/data-sgp/",
            "https://datakeluaran.org/data-sgp/",
            "https://tabelpaito.com/data-keluaran-sgp/",
            "https://paitowarna4d.com/data-sgp/",
            "https://datakeluaran7.com/data-keluaran-sgp/",
        ],
    },
    {
        "id": "ttm",
        "name": "Toto Macau",
        "keywords": ["macau", "ttm", "totomacau"],
        "reject_heading": ["sdylt", "hklt", "singapore", "hongkong", "sidney", "sydney"],
        "must_lotto": False,
        "allow_lotto_word": False,
        "newest_bottom": False,
        "urls": [
            "https://datatogellengkap.info/data-macau/",
            "https://datakeluaran7.com/data-macau/",
            "https://datakeluaran.org/data-macau/",
            "https://tabelpaito.com/data-keluaran-macau/",
            "https://paitowarna4d.com/data-macau/",
        ],
    },
    {
        "id": "cmd",
        "name": "Cambodia",
        "keywords": ["cambodia", "cmd", "kamboja", "magnum"],
        "reject_heading": ["lotto", "sdylt", "hklt", "macau", "singapore"],
        "must_lotto": False,
        "allow_lotto_word": False,
        "newest_bottom": True,
        "urls": [
            "https://datakeluaran7.com/data-cambodia/",
            "https://datatogellengkap.info/data-cambodia-togel/",
            "https://datakeluaran.org/data-cambodia/",
            "https://tabelpaito.com/data-keluaran-cambodia/",
            "https://paitowarna4d.com/data-cambodia/",
        ],
    },
    {
        "id": "twn",
        "name": "Taiwan",
        "keywords": ["taiwan", "twn"],
        "reject_heading": [
            "sdylt", "hklt", "sgplt", "sdy lotto", "hk lotto",
            "sidney lotto", "hongkong lotto", "macau", "singapore",
        ],
        "must_lotto": False,
        "allow_lotto_word": True,
        "newest_bottom": True,
        "urls": [
            "https://datakeluaran7.com/data-taiwan/",
            "https://datatogellengkap.info/data-taiwan/",
            "https://datakeluaran.org/data-taiwan/",
            "https://tabelpaito.com/data-keluaran-taiwan/",
            "https://paitowarna4d.com/data-taiwan/",
            "https://datakeluaran7.com/data-taiwan-lotto/",
        ],
    },
    {
        "id": "chn",
        "name": "China",
        "keywords": ["china", "chn", "cina"],
        "reject_heading": ["lotto", "sdylt", "hklt", "macau", "singapore"],
        "must_lotto": False,
        "allow_lotto_word": False,
        "newest_bottom": True,
        "urls": [
            "https://datakeluaran7.com/data-china/",
            "https://datatogellengkap.info/data-china/",
            "https://datakeluaran.org/data-china/",
            "https://tabelpaito.com/data-keluaran-china/",
            "https://paitowarna4d.com/data-china/",
        ],
    },
    {
        "id": "jpn",
        "name": "Japan",
        "keywords": ["japan", "jpn", "jepang"],
        "reject_heading": [
            "sdylt", "hklt", "sgplt", "sdy lotto", "hk lotto",
            "sidney lotto", "hongkong lotto", "macau", "singapore",
        ],
        "must_lotto": False,
        "allow_lotto_word": True,
        "newest_bottom": True,
        "urls": [
            "https://datajapanpools.com/",
            "https://datajapan.ink/",
            "https://datalaporan.com/",
            "https://japanloto.asia/",
            "https://livedrawjapan.pro/",
            "https://datatogellengkap.info/data-japan/",
            "https://tabelpaito.com/data-keluaran-japan/",
        ],
    },
    {
        "id": "bls",
        "name": "Bullseye",
        "keywords": ["bullseye", "bulseye", "bls"],
        "reject_heading": ["lotto", "loto", "sdylt", "hklt", "macau", "singapore", "hongkong"],
        "must_lotto": False,
        "allow_lotto_word": False,
        "newest_bottom": True,
        "urls": [
            "https://datakeluaran7.com/data-bullseye/",
            "https://datatogellengkap.info/data-bullseye/",
            "https://datakeluaran.org/data-bullseye/",
            "https://tabelpaito.com/data-keluaran-bullseye/",
            "https://paitowarna4d.com/data-bullseye/",
        ],
    },
]


def is_blocked_html(text: str) -> bool:
    if not text or len(text) < 250:
        return True
    sample = text[:3500].lower()
    block_markers = [
        "just a moment...",
        "cf-browser-verification",
        "attention required! | cloudflare",
        "enable javascript and cookies to continue",
        "checking your browser before accessing",
        "403 forbidden",
        "404 not found",
        "page not found",
    ]
    return any(m in sample for m in block_markers)


def is_host_dead(host: str) -> bool:
    with HOST_FAIL_LOCK:
        return HOST_FAIL_COUNTS.get(host, 0) >= 3


def record_host_timeout(host: str):
    with HOST_FAIL_LOCK:
        HOST_FAIL_COUNTS[host] = HOST_FAIL_COUNTS.get(host, 0) + 1


def record_host_ok(host: str):
    with HOST_FAIL_LOCK:
        HOST_FAIL_COUNTS[host] = 0


def to_google_translate_proxy(original_url: str):
    try:
        parsed = urllib.parse.urlparse(original_url)
        if not parsed.netloc or "translate.goog" in parsed.netloc:
            return None
        host = parsed.netloc.replace("-", "--").replace(".", "-") + ".translate.goog"
        path = parsed.path or "/"
        q = f"{parsed.query}&" if parsed.query else ""
        return f"https://{host}{path}?{q}_x_tr_sl=en&_x_tr_tl=id&_x_tr_hl=id&_x_tr_pto=wapp"
    except Exception:
        return None


def fetch_raw_html(url: str, timeout: int = 5, allow_proxies: bool = True):
    host = urllib.parse.urlparse(url).netloc
    if not allow_proxies and is_host_dead(host):
        return None

    ts = int(time.time())
    sep = "&" if "?" in url else "?"
    bust_url = f"{url}{sep}_cb={ts}"

    # 1. JALUR UTAMA: Direct Chrome TLS via curl_cffi (1 tembakan cepat, bebas cache)
    if cffi_requests is not None:
        try:
            resp = cffi_requests.get(
                bust_url,
                headers=BASE_HEADERS,
                impersonate="chrome124",
                timeout=timeout,
                verify=False,
            )
            if 200 <= resp.status_code < 300 and not is_blocked_html(resp.text):
                record_host_ok(host)
                return resp.text
            # Jika situs menolak parameter query ?_cb=, coba URL polos sekali
            if resp.status_code in (400, 403, 404, 406):
                resp2 = cffi_requests.get(
                    url,
                    headers=BASE_HEADERS,
                    impersonate="chrome124",
                    timeout=timeout,
                    verify=False,
                )
                if 200 <= resp2.status_code < 300 and not is_blocked_html(resp2.text):
                    record_host_ok(host)
                    return resp2.text
        except Exception:
            record_host_timeout(host)
    else:
        try:
            resp = requests.get(bust_url, headers=BASE_HEADERS, timeout=timeout, verify=False)
            if 200 <= resp.status_code < 300 and not is_blocked_html(resp.text):
                record_host_ok(host)
                return resp.text
        except Exception:
            record_host_timeout(host)

    if not allow_proxies:
        return None

    # 2. CADANGAN TERAKHIR: 3 proxy tercepat dengan anti-cache (hanya saat Tahap 2)
    encoded_bust = urllib.parse.quote(bust_url, safe="")
    gtrans_fresh = to_google_translate_proxy(bust_url)
    jina_no_cache = {**BASE_HEADERS, "X-No-Cache": "true", "X-Cache-Tolerance": "0"}

    proxy_attempts = [
        ("gtrans", gtrans_fresh, BASE_HEADERS) if gtrans_fresh else None,
        ("jina_html", f"https://r.jina.ai/{url}", {**jina_no_cache, "X-Return-Format": "html"}),
        ("allorigins", f"https://api.allorigins.win/get?url={encoded_bust}", BASE_HEADERS),
    ]
    for item in proxy_attempts:
        if not item:
            continue
        mode, req_url, headers = item
        try:
            resp = requests.get(req_url, headers=headers, timeout=6, verify=False)
            if resp.status_code < 200 or resp.status_code >= 300 or len(resp.text) < 200:
                continue
            if mode == "allorigins":
                data = resp.json()
                contents = str(data.get("contents", ""))
                if contents.startswith("data:") and ";base64," in contents:
                    b64 = contents.split(";base64,", 1)[1].strip()
                    contents = base64.b64decode(b64).decode("utf-8", errors="ignore")
                if not is_blocked_html(contents):
                    return contents
            else:
                if not is_blocked_html(resp.text):
                    return resp.text
        except Exception:
            continue
    return None


def discover_homepage_links():
    discovered = {m["id"]: [] for m in MARKETS}
    homepages = [
        "https://datakeluaran7.com/",
        "https://datatogellengkap.info/",
    ]
    for home in homepages:
        raw = fetch_raw_html(home, timeout=6, allow_proxies=True)
        if not raw:
            continue
        try:
            base = urllib.parse.urlparse(home)
            soup = BeautifulSoup(raw, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                text = a.get_text(" ", strip=True).lower()
                if not href or href.startswith("#") or href.startswith("javascript"):
                    continue
                if "translate.goog" in href:
                    m_u = re.search(r"[?&]u=([^&]+)", href)
                    if m_u:
                        href = urllib.parse.unquote(m_u.group(1))
                    else:
                        u = urllib.parse.urlparse(href)
                        href = f"{base.scheme}://{base.netloc}{u.path}"
                elif href.startswith("/"):
                    href = f"{base.scheme}://{base.netloc}{href}"
                if not href.startswith("http"):
                    continue

                href = re.sub(r"[?&]_cb=\d+", "", href)
                combined = f"{href.lower()} {text}"
                if any(x in combined for x in ["45", "metro", "siang", "sore", "pagi", "6d", "live", "prediksi"]):
                    continue

                for spec in MARKETS:
                    if not any(kw in combined for kw in spec["keywords"]):
                        continue
                    has_lotto_or_hktoto = (
                        "lotto" in combined
                        or "loto" in combined
                        or (
                            spec["id"].startswith("hk_")
                            and any(
                                x in combined
                                for x in ["hk-toto", "hktoto", "toto-hk", "hk toto", "hongkong toto"]
                            )
                        )
                    )
                    if spec["must_lotto"]:
                        if not has_lotto_or_hktoto:
                            continue
                    elif not spec.get("allow_lotto_word", False):
                        if has_lotto_or_hktoto:
                            continue

                    lst = discovered[spec["id"]]
                    if href not in lst:
                        if not spec["must_lotto"] and "pools" in combined:
                            lst.insert(0, href)
                        else:
                            lst.append(href)
        except Exception:
            continue
    return discovered


def is_header_row(text: str) -> bool:
    low = text.lower()
    if sum(1 for d in DAYS_7 if d.lower() in low) >= 2:
        return True
    if "sen" in low and "sel" in low and "rab" in low:
        return True
    if "periode" in low and "result" in low:
        return True
    if "tanggal" in low and any(
        w in low for w in ["periode", "result", "keluaran", "hari", "jam", "putaran", "wib", "13:00", "16:00"]
    ):
        return True
    return False


def contains_full_date(text: str) -> bool:
    return bool(
        re.search(r"\b\d{1,2}[-/]\d{1,2}[-/]202\d\b", text)
        or re.search(r"\b202\d[-/]\d{1,2}[-/]\d{1,2}\b", text)
    )


def try_parse_date(text: str, fallback_year: int):
    m1 = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](202\d)\b", text)
    if m1:
        d, m, y = int(m1.group(1)), int(m1.group(2)), int(m1.group(3))
        if 1 <= m <= 12 and 1 <= d <= 31:
            try:
                return datetime(y, m, d)
            except ValueError:
                pass
    m2 = re.search(r"\b(202\d)[-/](\d{1,2})[-/](\d{1,2})\b", text)
    if m2:
        y, m, d = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        if 1 <= m <= 12 and 1 <= d <= 31:
            try:
                return datetime(y, m, d)
            except ValueError:
                pass
    m3 = re.search(
        r"\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|Mei|May|Jun|Jul|Agu|Aug|Sep|Okt|Oct|Nov|Des|Dec)[a-z]*\s*(202\d)?\b",
        text,
        re.IGNORECASE,
    )
    if m3:
        d = int(m3.group(1))
        mon = MONTH_MAP.get(m3.group(2).lower()[:3], 1)
        y = int(m3.group(3)) if m3.group(3) else fallback_year
        try:
            return datetime(y, mon, d)
        except ValueError:
            pass
    return None


def extract_year(text: str):
    ms = re.findall(r"\b(202[0-9])\b", text)
    return int(ms[-1]) if ms else None


def extract_clean_4d(raw_cell: str):
    s = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", raw_cell)
    s = re.sub(r"https?://\S+", " ", s)
    s = re.sub(r"\b\d{1,4}[-/]\d{1,2}[-/]\d{1,4}\b", " ", s)
    s = re.sub(
        r"\b\d{1,2}\s+(Jan|Feb|Mar|Apr|Mei|May|Jun|Jul|Agu|Aug|Sep|Okt|Oct|Nov|Des|Dec)[a-z]*\s*202\d?\b",
        " ",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"\b\d{1,2}:\d{2}(:\d{2})?\b", " ", s)
    s = re.sub(r"[A-Za-z]{1,7}\s*[-#]\s*\d+", " ", s)
    s = re.sub(r"[^\d\s]", " ", s).strip()
    if not s:
        return None
    if re.match(r"^\d\s+\d\s+\d\s+\d$", s):
        s = re.sub(r"\s+", "", s)
    matches = re.findall(r"\b\d{0,2}(\d{4})\b", s)
    if not matches:
        return None
    for cand in reversed(matches):
        val = int(cand)
        if val < 2020 or val > 2030:
            return cand
    return matches[-1]


def get_prev_title(tbl) -> str:
    cap = tbl.find("caption")
    if cap and cap.get_text(strip=True):
        return cap.get_text(" ", strip=True)
    prev = tbl.find_previous_sibling()
    steps = 0
    while prev and steps < 2:
        txt = prev.get_text(" ", strip=True)
        if txt and len(txt) < 110:
            return txt
        prev = prev.find_previous_sibling()
        steps += 1
    return ""


def extract_calendar_row(cells, headers, default_year, max_cols, is_macau=False, is_sgp=False):
    valid = []
    row_date = None
    date_prefix = ""
    yr = default_year
    draw_counter = 0

    for c, raw in enumerate(cells):
        raw_txt = raw.replace("\u00a0", " ").strip()
        if not raw_txt or raw_txt in ("-", "----", "***") or raw_txt.lower() in ("libur", "off"):
            continue

        dt = try_parse_date(raw_txt, default_year)
        if dt and extract_clean_4d(raw_txt) is None:
            row_date = dt
            date_prefix = raw_txt
            yr = dt.year
            continue

        cand = extract_clean_4d(raw_txt)
        if not cand:
            continue

        val = int(cand)
        if c == 0 and len(cells) > 5 and 2020 <= val <= 2030:
            yr = val
            continue

        draw_counter += 1
        col_label = ""
        if row_date is not None and not is_macau:
            # Hitung nama hari persis dari tanggal asli (anti-meleset)
            col_label = DAYS_7[row_date.weekday()]
        elif c < len(headers):
            h = headers[c].strip()
            if h and "tanggal" not in h.lower() and "tahun" not in h.lower():
                col_label = h

        if not col_label:
            if is_macau:
                col_label = f"Putaran {draw_counter}"
            elif is_sgp and max_cols == 5:
                col_label = DAYS_5_SGP[c % 5]
            elif max_cols <= 7:
                col_label = DAYS_7[c % 7]
            elif c >= len(cells) - 7:
                col_label = DAYS_7[(c - (len(cells) - 7)) % 7]
            else:
                col_label = DAYS_7[(draw_counter - 1) % 7]

        lbl = f"{col_label} ({date_prefix})" if date_prefix else f"{col_label} ({yr})"
        valid.append((cand, lbl))

    return row_date, valid


def extract_vertical_row(cells, default_year):
    for c in range(len(cells) - 1, 0, -1):
        num4d = extract_clean_4d(cells[c])
        if num4d:
            meta_parts = [x.strip() for x in cells[:c] if x.strip()][:2]
            meta = " • ".join(meta_parts) if meta_parts else f"Periode ({default_year})"
            dt = try_parse_date(meta, default_year)
            if dt:
                day_name = DAYS_7[dt.weekday()]
                meta = f"{day_name} ({dt.strftime('%d-%m-%Y')})"
            p_m = re.search(r"[-#](\d{3,5})\b", " ".join(meta_parts))
            p_num = int(p_m.group(1)) if p_m else None
            return dt, p_num, (num4d, meta)
    return None


def extract_universal_rows(raw_content: str, default_year: int):
    rows = []
    try:
        soup = BeautifulSoup(raw_content, "lxml")
        for tag in soup(["script", "style", "noscript", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text("\n")
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or len(line) > 140:
                continue
            stripped = re.sub(r"\b\d{1,4}[-/]\d{1,2}[-/]\d{1,4}\b", " ", line)
            stripped = re.sub(r"\b\d{1,2}:\d{2}\b", " ", stripped)
            matches = [
                m for m in re.findall(r"\b(\d{4})\b", stripped)
                if int(m) < 2020 or int(m) > 2030
            ]
            if 3 <= len(matches) <= 7:
                rows.append([(n, f"{DAYS_7[i % 7]} ({default_year})") for i, n in enumerate(matches)])
    except Exception:
        pass
    return rows


def parse_all_table_draws(raw_content: str, spec: dict):
    dated_rows = []
    undated_rows = []
    vertical_rows = []
    current_year = datetime.now(WIB).year
    is_macau = spec["id"] == "ttm"
    is_sgp = spec["id"] == "sgp"
    allow_lotto = spec.get("allow_lotto_word", False)

    bad_row_tokens = ["sdylt", "hklt", "sgplt", "hktoto"]
    if not spec["must_lotto"] and not allow_lotto:
        bad_row_tokens.extend(["lotto", "loto"])
    if spec["id"] == "sdy_lotto":
        bad_row_tokens = ["hklt", "sgplt", "hktoto"]
    elif spec["id"] == "hk_lotto":
        bad_row_tokens = ["sdylt", "sgplt"]

    if any(tag in raw_content.lower() for tag in ("<tr", "<td")):
        try:
            soup = BeautifulSoup(raw_content, "lxml")
            for tag in soup(["script", "style", "noscript", "iframe"]):
                tag.decompose()

            title_el = soup.find(["title", "h1"])
            title_txt = title_el.get_text(" ", strip=True).lower() if title_el else ""
            if title_txt:
                if spec["must_lotto"]:
                    if "lotto" not in title_txt and "loto" not in title_txt:
                        return [], None
                elif not allow_lotto:
                    is_wrong_lotto = (
                        "pools" not in title_txt
                        and any(w in title_txt for w in ["lotto", "loto", "hk toto", "hongkong toto"])
                    )
                    if is_wrong_lotto:
                        return [], None

            for tbl in soup.find_all("table"):
                trs = tbl.find_all("tr")
                if len(trs) < 2:
                    continue

                near_title = get_prev_title(tbl).lower()
                if near_title:
                    explicit_pools = not spec["must_lotto"] and "pools" in near_title
                    if not explicit_pools and any(w in near_title for w in spec["reject_heading"]):
                        continue

                max_cols = 0
                headers = []
                for tr in trs:
                    cells = tr.find_all(["td", "th"])
                    if len(cells) > max_cols:
                        max_cols = len(cells)
                    plain = re.sub(r"\s+", " ", tr.get_text(" ", strip=True)).strip()
                    if not headers and is_header_row(plain):
                        headers = [re.sub(r"\s+", " ", c.get_text(" ", strip=True)).strip() for c in cells]

                is_multi_col = max_cols >= 5
                active_yr = extract_year(near_title) or current_year

                for tr in trs:
                    cells = tr.find_all(["td", "th"])
                    if not cells:
                        continue
                    plain_row = re.sub(r"\s+", " ", tr.get_text(" ", strip=True)).strip()
                    if not plain_row:
                        continue

                    low_row = plain_row.lower()
                    if any(w in low_row for w in bad_row_tokens):
                        continue

                    yr_m = re.search(r"\b(202[0-9])\b", plain_row)
                    if len(cells) <= 2 and yr_m and not contains_full_date(plain_row) and len(plain_row) <= 28:
                        active_yr = int(yr_m.group(1))
                        continue

                    if is_header_row(plain_row):
                        continue

                    cell_texts = [c.get_text(" ", strip=True) for c in cells]
                    if is_multi_col:
                        rdt, items = extract_calendar_row(
                            cell_texts, headers, active_yr, max_cols, is_macau=is_macau, is_sgp=is_sgp
                        )
                        if not items:
                            continue
                        if not is_macau and rdt is not None and len(items) >= 2:
                            continue
                        if rdt is not None:
                            dated_rows.append((rdt, items))
                        else:
                            undated_rows.append(items)
                    elif 2 <= len(cell_texts) <= 4:
                        v = extract_vertical_row(cell_texts, active_yr)
                        if v:
                            vertical_rows.append(v)
        except Exception:
            pass

    if not dated_rows and not undated_rows and not vertical_rows:
        skip_sec = False
        in_multi = False
        max_cols = 7
        md_headers = []
        active_yr = current_year
        for line in raw_content.splitlines():
            clean = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", line)
            clean = re.sub(r"https?://\S+", " ", clean).strip()
            if not clean:
                continue
            if "|" not in clean:
                if len(clean) < 75:
                    low = clean.lower()
                    exp_pools = not spec["must_lotto"] and "pools" in low
                    has_bad = not exp_pools and any(w in low for w in spec["reject_heading"])
                    if has_bad or "hari ini" in low:
                        skip_sec = True
                        in_multi = False
                    elif any(w in low for w in ["data ", "keluaran ", "paito "]):
                        skip_sec = False
                        y = extract_year(clean)
                        if y:
                            active_yr = y
                continue
            if skip_sec or "---" in clean:
                continue
            low_line = clean.lower()
            if any(w in low_line for w in bad_row_tokens):
                continue
            parts = [p.strip() for p in clean.strip("|").split("|")]
            if not parts:
                continue
            joined = " ".join(parts)
            if is_header_row(joined):
                if len(parts) >= 5:
                    in_multi = True
                    max_cols = len(parts)
                    md_headers = parts
                else:
                    in_multi = False
                continue
            if len(parts) >= 5:
                in_multi = True
                max_cols = max(max_cols, len(parts))
            looks_3col = len(parts) <= 4 and (
                bool(re.search(r"[A-Za-z]{2,6}\s*-\s*\d{3,5}", joined)) or contains_full_date(joined)
            )
            if in_multi and not looks_3col:
                rdt, items = extract_calendar_row(
                    parts, md_headers, active_yr, max_cols, is_macau=is_macau, is_sgp=is_sgp
                )
                if not items:
                    continue
                if not is_macau and rdt is not None and len(items) >= 2:
                    continue
                if rdt is not None:
                    dated_rows.append((rdt, items))
                else:
                    undated_rows.append(items)
            elif 2 <= len(parts) <= 4:
                v = extract_vertical_row(parts, active_yr)
                if v:
                    vertical_rows.append(v)

    if not dated_rows and not undated_rows and not vertical_rows and not is_macau:
        uni = extract_universal_rows(raw_content, current_year)
        if len(uni) >= 3:
            undated_rows.extend(uni)

    if len(dated_rows) >= 3:
        ordered = list(reversed(dated_rows)) if dated_rows[0][0] > dated_rows[-1][0] else dated_rows
        out = []
        max_dt = None
        for rdt, items in ordered:
            if max_dt is None or rdt > max_dt:
                max_dt = rdt
            out.extend(items)
        return out, max_dt

    if len(undated_rows) >= 3:
        total = len(undated_rows)
        out = []
        if spec["newest_bottom"]:
            for r in range(total):
                est_yr = current_year - ((total - 1 - r) // 52)
                for num, lbl in undated_rows[r]:
                    out.append((num, re.sub(r"\(202[0-9]\)", f"({est_yr})", lbl)))
        else:
            for r in range(total - 1, -1, -1):
                est_yr = current_year - (r // 52)
                for num, lbl in undated_rows[r]:
                    out.append((num, re.sub(r"\(202[0-9]\)", f"({est_yr})", lbl)))
        return out, None

    if len(vertical_rows) >= 5:
        first_dt, first_p, _ = vertical_rows[0]
        last_dt, last_p, _ = vertical_rows[-1]
        newest_top = False
        if first_dt and last_dt and first_dt != last_dt:
            newest_top = first_dt > last_dt
        elif first_p is not None and last_p is not None and first_p != last_p:
            newest_top = first_p > last_p
        ordered = list(reversed(vertical_rows)) if newest_top else vertical_rows
        max_dt = max((r[0] for r in ordered if r[0]), default=None)
        return [r[2] for r in ordered], max_dt

    return [], None


def matches_forbidden_tail(draws, forbidden_tail):
    if len(forbidden_tail) < 3 or len(draws) < 3:
        return False
    tail3 = [x[0] for x in draws[-3:]]
    if sum(1 for a, b in zip(tail3, forbidden_tail) if a == b) >= 2:
        return True
    tail5 = [x[0] for x in draws[-5:]]
    return sum(1 for x in forbidden_tail if x in tail5) >= 3


def compare_tail_sequences(list_a, list_b):
    if len(list_a) < 4 or len(list_b) < 4:
        return False, 0
    tail_a = list_a[-200:]
    tail_b = list_b[-25:]
    for b_idx in range(len(tail_b) - 2, max(-1, len(tail_b) - 13), -1):
        n1, n2 = tail_b[b_idx][0], tail_b[b_idx + 1][0]
        for a_idx in range(len(tail_a) - 2, -1, -1):
            if tail_a[a_idx][0] == n1 and tail_a[a_idx + 1][0] == n2:
                rem_a = (len(tail_a) - 1) - (a_idx + 1)
                rem_b = (len(tail_b) - 1) - (b_idx + 1)
                return True, rem_a - rem_b
    return False, 0


def stitch_history(long_hist, fresh_tail):
    if len(fresh_tail) < 4:
        return long_hist
    if not long_hist:
        return fresh_tail
    tail_slice = fresh_tail[-200:]
    for i in range(len(tail_slice) - 2, -1, -1):
        a, b = tail_slice[i][0], tail_slice[i + 1][0]
        for j in range(len(long_hist) - 2, max(-1, len(long_hist) - 201), -1):
            if long_hist[j][0] == a and long_hist[j + 1][0] == b:
                stitched = long_hist[:j] + tail_slice[i:]
                if len(stitched) >= len(long_hist):
                    return stitched
                return long_hist
    return fresh_tail if len(fresh_tail) >= len(long_hist) else long_hist


def select_best_consensus(candidates, spec):
    if len(candidates) == 1:
        return candidates[0]["draws"], candidates[0]["url"]

    now = datetime.now()
    is_macau = spec["id"] == "ttm"
    best = candidates[0]
    best_score = -1e9

    for i, c in enumerate(candidates):
        score = min(len(c["draws"]), 1500) * 0.02
        if not spec["must_lotto"] and "pools" in c["url"].lower():
            score += 60.0
        if c["latest_date"]:
            days_old = abs((now - c["latest_date"]).days)
            # Cegah cuplikan pendek (<300 baris seperti SGP 129 baris) mengalahkan arsip 2000+ baris
            if days_old <= 2:
                date_bonus = 500.0 if (is_macau or len(c["draws"]) >= 300) else 80.0
                score += date_bonus - (days_old * 20.0)
            elif days_old > 15:
                score -= 700.0
        for j, other in enumerate(candidates):
            if i == j:
                continue
            ok, extra = compare_tail_sequences(c["draws"], other["draws"])
            if ok:
                score += 300.0
                if 0 < extra <= 8:
                    score += extra * 400.0
        if score > best_score:
            best_score = score
            best = c

    # Selalu sambungkan arsip terpanjang dengan ekor dari situs paling update
    longest = max(candidates, key=lambda x: len(x["draws"]))
    if longest is not best and len(longest["draws"]) > len(best["draws"]) + 25:
        ok, extra = compare_tail_sequences(best["draws"], longest["draws"])
        if ok and extra >= 0:
            return stitch_history(longest["draws"], best["draws"]), best["url"]
        if ok and extra < 0:
            return longest["draws"], longest["url"]

    return best["draws"], best["url"]


def sync_single_market(
    spec,
    discovered_urls,
    existing_entries,
    saved_winner_url="",
    forbidden_tail=None,
    allow_proxies=True,
    target_sites=2,
):
    forbidden_tail = forbidden_tail or []
    if existing_entries:
        if matches_forbidden_tail(existing_entries, forbidden_tail):
            existing_entries = []
        elif spec["must_lotto"] and len(existing_entries) > 2000:
            existing_entries = []

    candidate_urls = []
    # Dahulukan URL pemenang dari run sebelumnya agar langsung tembak di percobaan #1
    if saved_winner_url and saved_winner_url.startswith("http"):
        candidate_urls.append(saved_winner_url)
    for u in discovered_urls.get(spec["id"], []) + spec["urls"]:
        if u and u not in candidate_urls:
            candidate_urls.append(u)

    valid_candidates = []
    tried_hosts = set()

    for url in candidate_urls:
        host = urllib.parse.urlparse(url).netloc
        if spec["id"] != "hk_pools" and host in tried_hosts:
            continue

        raw = fetch_raw_html(url, timeout=5, allow_proxies=allow_proxies)
        if not raw:
            continue
        draws, latest_dt = parse_all_table_draws(raw, spec)
        if len(draws) < 10:
            continue
        if matches_forbidden_tail(draws, forbidden_tail):
            continue

        valid_candidates.append({"url": url, "draws": draws, "latest_date": latest_dt})
        tried_hosts.add(host)

        if len(valid_candidates) >= target_sites:
            break

    if not valid_candidates:
        return existing_entries, "cache", saved_winner_url, False

    consensus, winner_url = select_best_consensus(valid_candidates, spec)
    winner_host = urllib.parse.urlparse(winner_url).netloc or "situs"

    if not existing_entries:
        return consensus, winner_host, winner_url, True

    # Pulihkan arsip panjang (misal Singapore yang sempat tersimpan 129 periode -> kembali 2060+)
    if len(existing_entries) < 500 and len(consensus) >= 1000:
        ok_rec, extra_rec = compare_tail_sequences(consensus, existing_entries)
        if ok_rec and extra_rec >= 0:
            return consensus, winner_host, winner_url, True
        if ok_rec and extra_rec < 0:
            return stitch_history(consensus, existing_entries), winner_host, winner_url, True

    ok_mem, extra_in_consensus = compare_tail_sequences(consensus, existing_entries)
    if ok_mem and extra_in_consensus < 0:
        return existing_entries, f"cache-terbaru ({winner_host})", winner_url, True
    if ok_mem and extra_in_consensus == 0:
        if len(consensus) > len(existing_entries) + 10:
            return consensus, winner_host, winner_url, True
        return existing_entries, winner_host, winner_url, True

    if len(consensus) >= len(existing_entries):
        return consensus, winner_host, winner_url, True
    return stitch_history(existing_entries, consensus), winner_host, winner_url, True


def load_existing_data(path="data.json"):
    if not os.path.exists(path):
        return {}, {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        out = {}
        for m_id, items in raw.get("markets", {}).items():
            parsed = []
            for row in items:
                if "|" in row:
                    num, lbl = row.split("|", 1)
                    if len(num) == 4 and num.isdigit():
                        parsed.append((num, lbl))
            if parsed:
                out[m_id] = parsed
        return out, raw.get("meta", {})
    except Exception:
        return {}, {}


def main():
    existing, old_meta = load_existing_data("data.json")
    now_wib_str = datetime.now(WIB).strftime("%Y-%m-%d %H:%M:%S WIB")

    results = {}
    sources = {}
    winner_urls = {}
    live_ok = {}

    # =========================================================================
    # TAHAP 1: Penarikan Langsung Cepat (curl_cffi, 2 situs pembanding, 6 worker)
    # =========================================================================
    sdy_lotto_spec = next(m for m in MARKETS if m["id"] == "sdy_lotto")
    hk_lotto_spec = next(m for m in MARKETS if m["id"] == "hk_lotto")

    for lotto_spec in (sdy_lotto_spec, hk_lotto_spec):
        m_id = lotto_spec["id"]
        saved_u = old_meta.get(m_id, {}).get("winner_url", "")
        draws, src, w_url, ok = sync_single_market(
            lotto_spec, {}, existing.get(m_id, []), saved_winner_url=saved_u, allow_proxies=False, target_sites=2
        )
        results[m_id] = draws
        sources[m_id] = src
        winner_urls[m_id] = w_url
        live_ok[m_id] = ok

    sdy_lotto_tail = [x[0] for x in results["sdy_lotto"][-3:]] if len(results["sdy_lotto"]) >= 3 else []
    hk_lotto_tail = [x[0] for x in results["hk_lotto"][-3:]] if len(results["hk_lotto"]) >= 3 else []

    other_specs = [m for m in MARKETS if m["id"] not in ("sdy_lotto", "hk_lotto")]

    def worker_fast(spec):
        m_id = spec["id"]
        saved_u = old_meta.get(m_id, {}).get("winner_url", "")
        forb = hk_lotto_tail if m_id == "hk_pools" else (sdy_lotto_tail if m_id == "sdy_pools" else [])
        draws, src, w_url, ok = sync_single_market(
            spec,
            {},
            existing.get(m_id, []),
            saved_winner_url=saved_u,
            forbidden_tail=forb,
            allow_proxies=False,
            target_sites=2,
        )
        return m_id, draws, src, w_url, ok

    with ThreadPoolExecutor(max_workers=6) as pool:
        for m_id, draws, src, w_url, ok in pool.map(worker_fast, other_specs):
            results[m_id] = draws
            sources[m_id] = src
            winner_urls[m_id] = w_url
            live_ok[m_id] = ok

    # =========================================================================
    # TAHAP 2: Auto-Retry Khusus Pasaran Gagal / SGP yang Arsipnya Masih Pendek
    # =========================================================================
    retry_specs = [
        m for m in MARKETS
        if (not live_ok.get(m["id"], False))
        or (m["id"] == "sgp" and len(results.get("sgp", [])) < 500)
    ]
    if retry_specs:
        print(f"[RETRY] Menjalankan cadangan proxy untuk {len(retry_specs)} pasaran: {[m['id'] for m in retry_specs]}")
        discovered = discover_homepage_links()
        retry_specs.sort(key=lambda s: 0 if s["must_lotto"] else 1)

        for spec in retry_specs:
            m_id = spec["id"]
            sdy_lotto_tail = [x[0] for x in results.get("sdy_lotto", [])[-3:]]
            hk_lotto_tail = [x[0] for x in results.get("hk_lotto", [])[-3:]]
            forb = hk_lotto_tail if m_id == "hk_pools" else (sdy_lotto_tail if m_id == "sdy_pools" else [])
            draws, src, w_url, ok = sync_single_market(
                spec,
                discovered,
                results.get(m_id) or existing.get(m_id, []),
                saved_winner_url=old_meta.get(m_id, {}).get("winner_url", ""),
                forbidden_tail=forb,
                allow_proxies=True,
                target_sites=2,
            )
            if ok or not results.get(m_id):
                results[m_id] = draws
                sources[m_id] = src
                winner_urls[m_id] = w_url
                live_ok[m_id] = ok

    # =========================================================================
    # SIMPAN HASIL & LAPORAN RINGKASAN 11 PASARAN
    # =========================================================================
    serialized_markets = {}
    new_meta = {}
    ok_live_count = 0
    changed_count = 0

    for spec in MARKETS:
        m_id = spec["id"]
        draws = results.get(m_id) or existing.get(m_id) or []
        prev_draws = existing.get(m_id) or []
        is_live = live_ok.get(m_id, False)
        if is_live:
            ok_live_count += 1

        if draws:
            serialized_markets[m_id] = [f"{num}|{lbl}" for num, lbl in draws]
            src = sources.get(m_id, "-")
            w_url = winner_urls.get(m_id, old_meta.get(m_id, {}).get("winner_url", ""))
            prev_last = prev_draws[-1][0] if prev_draws else ""
            curr_last = draws[-1][0]
            has_new = (curr_last != prev_last) or (len(draws) != len(prev_draws))
            if has_new:
                changed_count += 1

            prev_changed = old_meta.get(m_id, {}).get("changed_at_wib", now_wib_str)
            tag = "BARU" if has_new else ("LIVE" if is_live else "CACHE")
            new_meta[m_id] = {
                "latest": curr_last,
                "label": draws[-1][1],
                "count": len(draws),
                "source": src,
                "winner_url": w_url,
                "checked_at_wib": now_wib_str,
                "changed_at_wib": now_wib_str if has_new else prev_changed,
                "status": tag,
            }
            print(f"[{tag}] {spec['name']}: {len(draws)} periode | Terbaru: {curr_last} ({draws[-1][1]}) [{src}]")
        else:
            print(f"[GAGAL] {spec['name']}: belum ada data")

    print(f"Ringkasan: {ok_live_count}/{len(MARKETS)} pasaran berhasil sinkron live | {changed_count} pasaran berubah.")

    old_serialized = {
        m_id: [f"{num}|{lbl}" for num, lbl in draws]
        for m_id, draws in existing.items()
    }

    if serialized_markets == old_serialized and os.path.exists("data.json"):
        print("Tidak ada keluaran baru. Melewati commit.")
        return

    payload = {
        "version": 2,
        "updated_at_wib": now_wib_str,
        "updated_ts": int(time.time()),
        "meta": new_meta,
        "markets": serialized_markets,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(f"data.json berhasil diperbarui pada {now_wib_str}")


if __name__ == "__main__":
    main()
