"""Funkcje pomocnicze: normalizacja tekstu, kwot, dat, godzin i odczyt tabel (CSV/XLSX)."""
import csv
import datetime as dt
import io
import re
import unicodedata
from pathlib import Path

AMOUNT_RE = re.compile(r"(?<![\d,.])[-−–+]?\s?\d{1,3}(?:[  .]\d{3})*,\d{2}(?![\d])|(?<![\d,.])[-−–+]?\d+\.\d{2}(?![\d])")
PL_MONTHS = ["stycz", "lut", "marz", "kwie", "maj", "czerw", "lip", "sierp", "wrzes", "pazdz", "listop", "grud"]


def norm(s) -> str:
    """Małe litery, bez polskich znaków i wielokrotnych spacji."""
    s = str(s or "").replace("ł", "l").replace("Ł", "L")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def parse_amount(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", " ").replace("−", "-").replace("–", "-")
    s = re.sub(r"(PLN|zł|zl|EUR|USD)", "", s, flags=re.I).strip()
    if not s:
        return None
    neg = s.startswith("-") or s.endswith("-") or (s.startswith("(") and s.endswith(")"))
    s = s.strip("-+() ").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        val = float(s)
    except ValueError:
        return None
    return -val if neg else val


def detect_date_order(values) -> str:
    """Rozpoznaje DD/MM/RRRR vs MM/DD/RRRR na podstawie całej kolumny (domyślnie polski DMY)."""
    for v in values:
        m = re.match(r"\s*(\d{1,2})[-./](\d{1,2})[-./](\d{4})", str(v or ""))
        if m:
            a, b = int(m[1]), int(m[2])
            if a > 12:
                return "dmy"
            if b > 12:
                return "mdy"
    return "dmy"


def parse_date(v, order="dmy"):
    if isinstance(v, dt.datetime):
        return v.date().isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, (int, float)) and 20000 < v < 80000:  # data seryjna Excela
        return (dt.date(1899, 12, 30) + dt.timedelta(days=int(v))).isoformat()
    s = str(v or "").strip()
    try:
        m = re.match(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", s)
        if m:
            return dt.date(int(m[1]), int(m[2]), int(m[3])).isoformat()
        m = re.match(r"(\d{1,2})[-./](\d{1,2})[-./](\d{4})", s)
        if m:
            a, b, y = int(m[1]), int(m[2]), int(m[3])
            d, mo = (b, a) if order == "mdy" else (a, b)
            return dt.date(y, mo, d).isoformat()
    except ValueError:
        return None
    return None


def parse_month(v, fallback=None):
    """'2026-10', '10/2026', '10.2026', 'październik 2026', data -> '2026-10'."""
    if isinstance(v, (dt.date, dt.datetime)):
        return v.strftime("%Y-%m")
    s = norm(v)
    m = re.search(r"(\d{4})[-./](\d{1,2})", s)
    if m:
        return f"{m[1]}-{int(m[2]):02d}"
    m = re.search(r"(\d{1,2})[-./](\d{4})", s)
    if m:
        return f"{m[2]}-{int(m[1]):02d}"
    for i, name in enumerate(PL_MONTHS):
        if name in s:
            y = re.search(r"\d{4}", s)
            if y:
                return f"{y[0]}-{i + 1:02d}"
    d = parse_date(v)
    return d[:7] if d else fallback


def parse_hours(v):
    if v is None or v == "":
        return None
    if isinstance(v, dt.timedelta):
        return v.total_seconds() / 3600
    if isinstance(v, dt.time):
        return v.hour + v.minute / 60 + v.second / 3600
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if ":" in s:
        parts = [float(p or 0) for p in s.split(":")]
        parts += [0] * (3 - len(parts))
        return parts[0] + parts[1] / 60 + parts[2] / 3600
    m = re.match(r"(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?", s)
    if m and (m[1] or m[2]) and not re.match(r"^\d+([.,]\d+)?$", s):
        return int(m[1] or 0) + int(m[2] or 0) / 60
    return parse_amount(s)


def month_add(m: str, n: int) -> str:
    y, mo = map(int, m.split("-"))
    mo += n
    y += (mo - 1) // 12
    mo = (mo - 1) % 12 + 1
    return f"{y}-{mo:02d}"


def month_range(a: str, b: str):
    out, m = [], a
    while m <= b and len(out) < 600:
        out.append(m)
        m = month_add(m, 1)
    return out


def read_table(path: Path):
    """Zwraca listę wierszy (listy wartości) z pliku CSV/TXT/XLSX."""
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        rows = []
        for ws in wb.worksheets:
            for r in ws.iter_rows(values_only=True):
                if any(c not in (None, "") for c in r):
                    rows.append(list(r))
            if rows:
                break  # pierwszy niepusty arkusz
        return rows
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1250", "iso-8859-2"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    sample = "\n".join(text.splitlines()[:40])
    delim = max([";", "\t", ","], key=lambda d: sample.count(d))
    return [r for r in csv.reader(io.StringIO(text), delimiter=delim) if any(c.strip() for c in r)]


def map_header(row, spec: dict):
    """Dopasowuje kolumny do kluczy wg listy aliasów (najpierw dokładnie, potem 'zawiera')."""
    cells = [norm(c) for c in row]
    idx, used = {}, set()
    for exact in (True, False):
        for key, aliases in spec.items():
            if key in idx:
                continue
            for a in aliases:
                hit = next((i for i, c in enumerate(cells) if i not in used and c and (c == a if exact else a in c)), None)
                if hit is not None:
                    idx[key] = hit
                    used.add(hit)
                    break
    return idx


def find_header(rows, spec: dict, required, scan=40):
    """Szuka wiersza nagłówka (banki często dodają kilka linii wstępu)."""
    for i, r in enumerate(rows[:scan]):
        idx = map_header(r, spec)
        if all(any(k in idx for k in (req if isinstance(req, tuple) else (req,))) for req in required):
            return i, idx
    return None, None


def cell(row, idx, key):
    i = idx.get(key)
    return row[i] if i is not None and i < len(row) else None
