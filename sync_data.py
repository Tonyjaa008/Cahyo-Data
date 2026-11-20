import base64
import json
import os
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import requests
import urllib3
from bs4 import BeautifulSoup

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
}

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
            "https://datakeluaran.org/data-sdy/",
            "https://datakeluaran7.com/data-keluaran-sdy/",
            "https://datatogellengkap.info/data-sydney/",
            "https://tabelpaito.com/data-keluaran-sdy/",
            "https://paitowarna4d.com/data-sdy/",
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
            "https://datakeluaran.org/data-sdy-lotto/",
            "https://datakeluaran7.com/data-sdy-lotto/",
            "https://datatogellengkap.info/data-sydney-lotto/",
            "https://datakeluaran.org/data-sidney-lotto/",
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
            "https://datakeluaran.org/data-hk-lotto/",
            "https://datakeluaran7.com/data-hongkong-lotto/",
            "https://datatogellengkap.info/data-hongkong-lotto/",
            "https://datakeluaran.org/data-hongkong-lotto/",
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
            "https://datakeluaran7.com/data-hk-pools/",
            "https://datakeluaran.org/data-hk-pools/",
            "https://datakeluaran7.com/data-hongkong-pools/",
            "https://datatogellengkap.info/data-hongkong-pools/",
            "https://tabelpaito.com/data-keluaran-hk-pools/",
            "https://paitowarna4d.com/data-hk-pools/",
            "https://datakeluaran7.com/data-hk/",
            "https://datakeluaran.org/data-hk/",
            "https://datakeluaran7.com/data-keluaran-hk/",
            "https://datatogellengkap.info/data-hongkong/",
            "https://tabelpaito.com/data-keluaran-hk/",
            "https://paitowarna4d.com/data-hk/",
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
            "https://datakeluaran.org/data-sgp/",
            "https://datakeluaran7.com/data-keluaran-sgp/",
            "https://datatogellengkap.info/data-sgp/",
            "https://tabelpaito.com/data-keluaran-sgp/",
            "https://paitowarna4d.com/data-sgp/",
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
            "https://datakeluaran7.com/data-macau/",
            "https://datakeluaran.org/data-macau/",
            "https://datakeluaran7.com/data-keluaran-macau/",
            "https://datatogellengkap.info/data-macau/",
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
            "https://datakeluaran.org/data-cambodia/",
            "https://datakeluaran7.com/data-keluaran-cambodia/",
            "https://datatogellengkap.info/data-cambodia-togel/",
            "https://tabelpaito.com/data-keluaran-cambodia/",
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
            "https://datakeluaran7.com/data-keluaran-taiwan/",
            "https://datakeluaran7.com/data-taiwan-lotto/",
            "https://datakeluaran.org/data-taiwan/",
            "https://datakeluaran.org/taiwan/",
            "https://datatogellengkap.info/data-taiwan/",
            "https://tabelpaito.com/data-keluaran-taiwan/",
            "https://paitowarna4d.com/data-taiwan/",
            "https://rajapaito.info/data-taiwan/",
            "https://paitopaman.com/data-taiwan/",
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
            "https://datakeluaran.org/data-china/",
            "https://datakeluaran7.com/data-keluaran-china/",
            "https://datatogellengkap.info/data-china/",
            "https://tabelpaito.com/data-keluaran-china/",
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
            "https://tabelpaito.com/data-keluaran-japan/",
            "https://datatogellengkap.info/data-japan/",
            "https://paitowarna4d.com/data-japan/",
            "https://datakeluaran.org/data-japan/",
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
            "https://datakeluaran.org/data-bullseye/",
            "https://datakeluaran7.com/data-keluaran-bullseye/",
            "https://datatogellengkap.info/data-bullseye/",
            "https://tabelpaito.com/data-keluaran-bullseye/",
            "https://paitowarna4d.com/data-bullseye/",
            "https://rajapaito.info/data-bullseye/",
        ],
    },
]


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


def fetch_raw_html(url: str, timeout: int = 8):
    encoded = urllib.parse.quote(url, safe="")
    gtrans = to_google_translate_proxy(url)
    attempts = [
        ("direct", url, BASE_HEADERS),
        ("gtrans", gtrans, BASE_HEADERS) if gtrans else None,
        ("jina_html", f"https://r.jina.ai/{url}", {**BASE_HEADERS, "X-Return-Format": "html"}),
        ("allorigins", f"https://api.allorigins.win/get?url={encoded}", BASE_HEADERS),
        ("codetabs", f"https://api.codetabs.com/v1/proxy?quest={encoded}", BASE_HEADERS),
        ("jina_md", f"https://r.jina.ai/{url}", BASE_HEADERS),
    ]
    for item in attempts:
        if not item:
            continue
        mode, req_url, headers = item
        try:
            resp = requests.get(req_url, headers=headers, timeout=timeout, verify=False)
            if resp.status_code < 200 or resp.status_code >= 300 or len(resp.text) < 200:
                continue
            if mode == "allorigins":
                data = resp.json()
                contents = str(data.get("contents", ""))
                if contents.startswith("data:") and ";base64," in contents:
                    b64 = contents.split(";base64,", 1)[1].strip()
                    contents = base64.b64decode(b64).decode("utf-8", errors="ignore")
                if len(contents) > 200:
                    return contents
            else:
                return resp.text
        except Exception:
            continue
    return None


def discover_homepage_links():
    discovered = {m["id"]: [] for m in MARKETS}
    homepages = [
        "https://datakeluaran7.com/",
        "https://datakeluaran.org/",
    ]
    for home in homepages:
        raw = fetch_raw_html(home, timeout=7)
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
                    # 1. Wajib Lotto (sdy_lotto, hk_lotto): HARUS ada kata lotto/loto
                    if spec["must_lotto"]:
                        if not has_lotto_or_hktoto:
                            continue
                    # 2. Non-Lotto ketat (sdy_pools, hk_pools, sgp, ttm, cmd, chn, bls): TOLAK kata lotto/loto
                    elif not spec.get("allow_lotto_word", False):
                        if has_lotto_or_hktoto:
                            continue
                    # 3. Khusus Taiwan & Japan (allow_lotto_word=True): boleh pakai atau tanpa kata lotto

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
        if c < len(headers):
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
            p_m = re.search(r"[-#](\d{3,5})\b", meta)
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
                    # Halaman SDY Lotto / HK Lotto WAJIB punya kata lotto/loto pada judul
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
    tail_slice = fresh_tail[-200:]
    for i in range(len(tail_slice) - 1):
        a, b = tail_slice[i][0], tail_slice[i + 1][0]
        for j in range(len(long_hist) - 2, max(-1, len(long_hist) - 201), -1):
            if long_hist[j][0] == a and long_hist[j + 1][0] == b:
                return long_hist[:j] + tail_slice[i:]
    return fresh_tail if len(fresh_tail) >= 20 else long_hist


def select_best_consensus(candidates, spec):
    if len(candidates) == 1:
        return candidates[0]["draws"]

    now = datetime.now()
    best = candidates[0]
    best_score = -1e9

    for i, c in enumerate(candidates):
        score = len(c["draws"]) * 0.05
        if not spec["must_lotto"] and "pools" in c["url"].lower():
            score += 180.0
        if c["latest_date"]:
            days_old = abs((now - c["latest_date"]).days)
            if days_old <= 2:
                score += 500.0 - (days_old * 40.0)
            elif days_old > 15:
                score -= 700.0
        for j, other in enumerate(candidates):
            if i == j:
                continue
            ok, extra = compare_tail_sequences(c["draws"], other["draws"])
            if ok:
                score += 300.0
                if 0 < extra <= 6:
                    score += extra * 120.0
        if score > best_score:
            best_score = score
            best = c

    longest = best
    for c in candidates:
        if len(c["draws"]) > len(longest["draws"]) + 25:
            ok, _ = compare_tail_sequences(best["draws"], c["draws"])
            if ok:
                longest = c

    if longest is not best:
        return stitch_history(longest["draws"], best["draws"])
    return best["draws"]


def sync_single_market(spec, discovered_urls, existing_entries, forbidden_tail=None):
    forbidden_tail = forbidden_tail or []
    # Bersihkan memori lama jika terindikasi tertukar dengan pasaran lain
    if existing_entries:
        if matches_forbidden_tail(existing_entries, forbidden_tail):
            existing_entries = []
        elif spec["must_lotto"] and len(existing_entries) > 2000:
            existing_entries = []

    candidate_urls = []
    for u in discovered_urls.get(spec["id"], []) + spec["urls"]:
        if u and u not in candidate_urls:
            candidate_urls.append(u)

    valid_candidates = []
    tried_hosts = set()

    for url in candidate_urls:
        host = urllib.parse.urlparse(url).netloc
        if spec["id"] != "hk_pools" and host in tried_hosts:
            continue

        raw = fetch_raw_html(url, timeout=8)
        if not raw:
            continue
        draws, latest_dt = parse_all_table_draws(raw, spec)
        if len(draws) < 10:
            continue
        if matches_forbidden_tail(draws, forbidden_tail):
            continue

        valid_candidates.append({"url": url, "draws": draws, "latest_date": latest_dt})
        tried_hosts.add(host)

        if len(valid_candidates) == 2:
            ok, _ = compare_tail_sequences(valid_candidates[0]["draws"], valid_candidates[1]["draws"])
            if ok:
                break
        if len(valid_candidates) >= 3:
            break

    if not valid_candidates:
        return existing_entries

    consensus = select_best_consensus(valid_candidates, spec)
    if not existing_entries:
        return consensus
    if len(consensus) >= len(existing_entries):
        return consensus
    return stitch_history(existing_entries, consensus)


def load_existing_data(path="data.json"):
    if not os.path.exists(path):
        return {}
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
        return out
    except Exception:
        return {}


def main():
    existing = load_existing_data("data.json")
    discovered = discover_homepage_links()

    results = {}

    # 1. Jalankan SDY Lotto & HK Lotto dulu agar proteksi anti-duplikat Pools selalu akurat
    sdy_lotto_spec = next(m for m in MARKETS if m["id"] == "sdy_lotto")
    hk_lotto_spec = next(m for m in MARKETS if m["id"] == "hk_lotto")

    sdy_lotto_draws = sync_single_market(sdy_lotto_spec, discovered, existing.get("sdy_lotto", []))
    hk_lotto_draws = sync_single_market(hk_lotto_spec, discovered, existing.get("hk_lotto", []))

    results["sdy_lotto"] = sdy_lotto_draws
    results["hk_lotto"] = hk_lotto_draws

    sdy_lotto_tail = [x[0] for x in sdy_lotto_draws[-3:]] if len(sdy_lotto_draws) >= 3 else []
    hk_lotto_tail = [x[0] for x in hk_lotto_draws[-3:]] if len(hk_lotto_draws) >= 3 else []

    # 2. Jalankan 9 pasaran lainnya secara paralel ringan
    other_specs = [m for m in MARKETS if m["id"] not in ("sdy_lotto", "hk_lotto")]

    def worker(spec):
        forb = []
        if spec["id"] == "hk_pools":
            forb = hk_lotto_tail
        elif spec["id"] == "sdy_pools":
            forb = sdy_lotto_tail
        draws = sync_single_market(spec, discovered, existing.get(spec["id"], []), forbidden_tail=forb)
        return spec["id"], draws

    with ThreadPoolExecutor(max_workers=4) as pool:
        for m_id, draws in pool.map(worker, other_specs):
            results[m_id] = draws

    serialized_markets = {}
    for spec in MARKETS:
        m_id = spec["id"]
        draws = results.get(m_id) or existing.get(m_id) or []
        if draws:
            serialized_markets[m_id] = [f"{num}|{lbl}" for num, lbl in draws]
            print(f"[OK] {spec['name']}: {len(draws)} periode | Terbaru: {draws[-1][0]} ({draws[-1][1]})")
        else:
            print(f"[WARN] {spec['name']}: belum ada data")

    old_serialized = {
        m_id: [f"{num}|{lbl}" for num, lbl in draws]
        for m_id, draws in existing.items()
    }

    if serialized_markets == old_serialized and os.path.exists("data.json"):
        print("Tidak ada keluaran baru. Melewati penyimpanan.")
        return

    now_wib = datetime.now(WIB)
    payload = {
        "version": 1,
        "updated_at_wib": now_wib.strftime("%Y-%m-%d %H:%M:%S WIB"),
        "updated_ts": int(time.time()),
        "markets": serialized_markets,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(f"data.json berhasil diperbarui pada {payload['updated_at_wib']}")


if __name__ == "__main__":
    main()
