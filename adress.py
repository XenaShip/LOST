# -*- coding: utf-8 -*-
"""
adress.py — точное расстояние до ближайшего метро по пешеходной сети OSM
для адресов Москвы и МО, без API-ключей (Nominatim + Photon).

Зависимости:
  pip install osmnx==1.9.3 networkx==3.* shapely==2.* requests numpy

Опционально (рекомендуется для этичного использования Nominatim):
  В .env добавьте:
    NOMINATIM_USER_AGENT=arendatoriy-metro/1.0 (contact: your@email)

Запуск:
  (.venv) PS> python .\adress.py
"""

from __future__ import annotations

import os
import re
import time
import json
import requests
import osmnx as ox
import networkx as nx
import numpy as np
from math import radians, sin, cos, atan2, sqrt
from typing import Optional, Tuple, Dict, Any, List

# ---------- Настройки OSMnx / Overpass ----------
ox.settings.use_cache = True
ox.settings.log_console = False
ox.settings.timeout = 180
# Свой UA для вежливого доступа к Nominatim (можно задать через .env)
ox.settings.nominatim_user_agent = os.getenv(
    "NOMINATIM_USER_AGENT",
    "arendatoriy-metro/1.0 (contact: example@yourdomain.ru)"
)

# ---------- География: Москва и Московская область ----------
# Узкая городская рамка Москвы (south, west, north, east)
MOSCOW_VIEWBOX: Tuple[float, float, float, float] = (55.30, 37.20, 56.10, 37.95)
# Шире — для МО
MOSCOW_REGION_VIEWBOX: Tuple[float, float, float, float] = (54.80, 35.80, 56.80, 39.20)

DEFAULT_CITY = "Москва"
DEFAULT_COUNTRY = "Россия"

# ---------- Инструменты геометрии ----------

def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Геодезическое расстояние по прямой (метры)."""
    R = 6371000.0
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlmb = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(p1)*cos(p2)*sin(dlmb/2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))

# ---------- Нормализация адреса (Москва/МО) ----------

_STREET_TYPES = [
    "ул", "улица", "проспект", "пр-т", "просп.", "проезд", "пр-д",
    "переулок", "пер", "шоссе", "бульвар", "бул", "набережная", "наб",
    "аллея", "площадь", "пл", "тракт", "километр", "км", "микрорайон", "мкр",
    "проулок", "тупик", "линия", "просека"
]

def _has_street_type(s: str) -> bool:
    s_low = s.lower()
    return any(re.search(rf'\b{t}\b\.?', s_low) for t in _STREET_TYPES)

def _strip_city_prefix(s: str) -> str:
    # убираем лидирующее "Москва,", "г.Москва," и пр.
    s = re.sub(r'^\s*(г\.\s*)?москв[аы]\s*,\s*', '', s, flags=re.IGNORECASE)
    return s.strip(", ")

def _parse_house_block(s: str) -> List[str]:
    """
    Извлекаем дом/корпус/строение из фрагментов:
      "30", "30 к1", "30к1", "30с1", "27/1с1", "27к1с2", "д30 к1 стр2"
    Возвращаем компактные варианты: ["30", "30к1", "30с1", "30к1с2", "27/1с1", ...]
    """
    s = s.replace("ё", "е")
    s_norm = re.sub(r'\bдом\b|д\.', '', s, flags=re.IGNORECASE)
    s_norm = re.sub(r'\bкорпус\b|корп\.?', 'к', s_norm, flags=re.IGNORECASE)
    s_norm = re.sub(r'\bстроение\b|стр\.?', 'с', s_norm, flags=re.IGNORECASE)
    s_norm = re.sub(r'\s+', ' ', s_norm).strip()

    dom = re.search(r'(\d+[A-Za-zА-Яа-я\-]?)', s_norm)
    if not dom:
        # поддержим «27/1с1» без явного дом-номера слева
        if re.search(r'\d+\/\d+', s):
            return [re.sub(r'\s+', '', s_norm)]
        return []

    house = dom.group(1)
    korp = re.search(r'к\s*([0-9A-Za-zА-Яа-я\-]+)', s_norm)
    stro = re.search(r'с\s*([0-9A-Za-zА-Яа-я\-]+)', s_norm)

    variants = {house}
    if korp:
        variants.add(f"{house}к{korp.group(1)}")
    if stro:
        variants.add(f"{house}с{stro.group(1)}")
    if korp and stro:
        variants.add(f"{house}к{korp.group(1)}с{stro.group(1)}")
        variants.add(f"{house}с{stro.group(1)}к{korp.group(1)}")
    # «27/1с1» как есть
    if re.search(r'\d+\/\d+', s):
        variants.add(re.sub(r'\s+', '', s_norm))

    return list(variants)

def _normalize_ru_address(addr: str) -> List[str]:
    """
    Делаем УМНЫЕ варианты для Москвы/МО:
      - убираем лидирующее «Москва,»
      - при необходимости подставляем «улица»
      - собираем компактные формы дом/к/с
      - добавляем «Россия, Москва, ...» как контекст
    """
    raw = (addr or "").strip()
    raw = raw.replace("ё", "е")
    raw = re.sub(r'\s+', ' ', raw).strip(", ")

    local = _strip_city_prefix(raw)

    # пробуем «street, house» (через запятую)
    m = re.search(r'^(?P<street>[^,]+?)\s*,\s*(?P<house>.+)$', local)
    if not m:
        # вариант «Чертановская 30 к1»
        m2 = re.search(r'^(?P<street>.*?)(?P<house>\d.+)$', local)
        if m2:
            street_part = m2.group("street").strip()
            house_part = m2.group("house").strip()
        else:
            street_part, house_part = local, ""
    else:
        street_part = m.group("street").strip()
        house_part = m.group("house").strip()

    # если в street нет типа, подставим «улица»
    street_clean = street_part
    if street_part and not _has_street_type(street_part):
        street_clean = f"улица {street_part}"

    house_variants = _parse_house_block(house_part) if house_part else []

    variants: List[str] = []

    # 1) Строгий контекст + свободная форма
    variants.append(f"{DEFAULT_COUNTRY}, {DEFAULT_CITY}, {street_clean}{(', ' + house_part) if house_part else ''}".strip(", "))

    # 2) Структурные формы «улица + 30к1»
    if house_variants:
        for hv in house_variants:
            variants.append(f"{DEFAULT_COUNTRY}, {DEFAULT_CITY}, {street_clean} {hv}")

    # 3) Оригинал, но с добавленным контекстом
    variants.append(f"{DEFAULT_COUNTRY}, {DEFAULT_CITY}, {local}")

    # 4) Запасной вариант — только улица
    variants.append(f"{DEFAULT_COUNTRY}, {DEFAULT_CITY}, {street_clean}")

    # чистим повторы/пробелы
    cleaned: List[str] = []
    for v in variants:
        v = re.sub(r'\s+', ' ', v).replace(" ,", ",").strip(", ").strip()
        if v and v not in cleaned:
            cleaned.append(v)

    return cleaned

# ---------- Вызовы геокодеров ----------

def _nominatim_geocode(address: str, viewbox: Tuple[float, float, float, float] | None) -> Optional[Tuple[float, float]]:
    """
    Прямой вызов Nominatim с ограничением рамкой (viewbox) и countrycodes=ru.
    Возвращает (lat, lon) либо None.
    """
    ua = os.getenv("NOMINATIM_USER_AGENT", "arendatoriy-metro/1.0 (contact: example@yourdomain.ru)")
    headers = {"User-Agent": ua}
    params = {
        "q": address,
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 1,
        "accept-language": "ru",
        "countrycodes": "ru",
    }
    if viewbox:
        s, w, n, e = viewbox
        params["viewbox"] = f"{w},{n},{e},{s}"  # порядок: left,top,right,bottom
        params["bounded"] = 1

    try:
        r = requests.get("https://nominatim.openstreetmap.org/search", params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data:
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
            return lat, lon
    except Exception:
        return None
    return None

def _nominatim_geocode_structured(street: str, city: str, viewbox: Tuple[float, float, float, float] | None) -> Optional[Tuple[float, float]]:
    """
    Структурный запрос к Nominatim:
      street="Чертановская улица 30к1", city="Москва", countrycodes=ru
    """
    ua = os.getenv("NOMINATIM_USER_AGENT", "arendatoriy-metro/1.0 (contact: example@yourdomain.ru)")
    headers = {"User-Agent": ua}
    params = {
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 1,
        "accept-language": "ru",
        "countrycodes": "ru",
        "city": city,
        "street": street,
    }
    if viewbox:
        s, w, n, e = viewbox
        params["viewbox"] = f"{w},{n},{e},{s}"
        params["bounded"] = 1

    try:
        r = requests.get("https://nominatim.openstreetmap.org/search", params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        return None
    return None

def _photon_geocode(address: str) -> Optional[Tuple[float, float]]:
    """
    Фолбэк: Photon (Komoot), бесплатно, без ключа. Подсказываем город/страну.
    """
    q = address
    if not re.search(r'\bмоскв', q, re.IGNORECASE):
        q = f"{DEFAULT_CITY}, {q}"
    if not re.search(r'\bросси', q, re.IGNORECASE):
        q = f"{DEFAULT_COUNTRY}, {q}"

    try:
        r = requests.get("https://photon.komoot.io/api/", params={"q": q, "lang": "ru", "limit": 1}, timeout=15)
        r.raise_for_status()
        data = r.json()
        feats = data.get("features") or []
        if feats:
            lon, lat = feats[0]["geometry"]["coordinates"]
            return float(lat), float(lon)
    except Exception:
        return None
    return None

def geocode_smart_moscow(address: str) -> Optional[Tuple[float, float]]:
    """
    Жёстко нацеленный на Москву/МО геокодер:
      0) структурный Nominatim (city=Москва, street=...) с рамкой Москвы
      1) Nominatim: Москва → МО → без рамки (свободная форма)
      2) Photon (фолбэк)
    Возвращает (lat, lon) либо None.
    """
    variants = _normalize_ru_address(address)

    # 0) структурно (лучше понимает «27/1с1», «30к1»)
    for v in variants:
        street = re.sub(r'^\s*Россия\s*,\s*Москв[аы]\s*,\s*', '', v, flags=re.IGNORECASE)
        loc = _nominatim_geocode_structured(street=street, city=DEFAULT_CITY, viewbox=MOSCOW_VIEWBOX)
        if loc:
            return loc
        time.sleep(0.2)

    # 1) Nominatim (Москва → МО → без рамки)
    for vb in (MOSCOW_VIEWBOX, MOSCOW_REGION_VIEWBOX, None):
        for v in variants:
            loc = _nominatim_geocode(v, vb)
            if loc:
                return loc
            time.sleep(0.2)

    # 2) Photon
    for v in variants:
        loc = _photon_geocode(v)
        if loc:
            return loc
        time.sleep(0.2)

    return None

# ---------- Поиск ближайшего метро ----------

def _nearest_node_fallback(G: nx.MultiDiGraph, lat: float, lon: float) -> int:
    """
    Ближайший узел в графе без scikit-learn (векторизованный хаверсин).
    Работает быстро на радиусах 2–5 км.
    """
    node_ids, ys, xs = [], [], []
    for nid, data in G.nodes(data=True):
        if "y" in data and "x" in data:
            node_ids.append(nid); ys.append(data["y"]); xs.append(data["x"])
    if not node_ids:
        raise nx.NodeNotFound("В графе нет узлов с координатами.")
    ys = np.asarray(ys, dtype=float); xs = np.asarray(xs, dtype=float)

    R = 6371000.0
    lat1 = np.radians(lat); lon1 = np.radians(lon)
    lat2 = np.radians(ys);  lon2 = np.radians(xs)
    dphi = lat2 - lat1; dlmb = lon2 - lon1
    a = np.sin(dphi/2.0)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlmb/2.0)**2
    d = 2 * R * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return int(node_ids[int(np.argmin(d))])

def _nearest_node(G: nx.MultiDiGraph, lat: float, lon: float) -> int:
    try:
        return ox.distance.nearest_nodes(G, X=[lon], Y=[lat])[0]
    except ImportError:
        return _nearest_node_fallback(G, lat, lon)

def _nearest_walk_distance_to_entrances(lat: float, lon: float, search_m: int = 3000) -> Optional[Tuple[float, str, float, float]]:
    """
    Граф пешеходной сети → входы метро (railway=subway_entrance) → кратчайший путь.
    Возвращает best=(walk_m, name, elat, elon) или None.
    """
    G = ox.graph_from_point((lat, lon), dist=search_m, network_type="walk", simplify=True)
    tags = {"railway": "subway_entrance"}
    entrances = ox.features_from_point((lat, lon), tags=tags, dist=search_m)
    if entrances.empty:
        return None

    src = _nearest_node(G, lat, lon)

    best: Optional[Tuple[float, str, float, float]] = None
    for _, row in entrances.iterrows():
        geom = row.geometry
        if geom.geom_type == "Point":
            elat, elon = geom.y, geom.x
        else:
            c = geom.centroid
            elat, elon = c.y, c.x

        try:
            ent = _nearest_node(G, elat, elon)
            walk_m = nx.shortest_path_length(G, src, ent, weight="length")
        except (nx.NodeNotFound, nx.NetworkXNoPath):
            continue

        # название входа/станции, если есть
        name = None
        for k in ("name", "station", "ref"):
            if k in row and isinstance(row[k], str):
                name = row[k]; break

        cand = (float(walk_m), name or "Вход метро", elat, elon)
        if (best is None) or (cand[0] < best[0]):
            best = cand

    return best

def distance_to_nearest_metro_m(address: str, search_km: float = 3.0) -> Optional[int]:
    """
    Вводишь адрес (свободной формой по-русски из Москвы/МО) → метры пешком до ближайшего входа метро.
    """
    loc = geocode_smart_moscow(address)
    if not loc:
        print("[geocode failed] Не удалось распознать адрес в Москве/МО:", address)
        return None

    lat, lon = loc
    res = _nearest_walk_distance_to_entrances(lat, lon, search_m=int(search_km * 1000))
    if res is None:
        # Расширим радиус до 5 км, вдруг ближайшая станция дальше
        res = _nearest_walk_distance_to_entrances(lat, lon, search_m=5000)
        if res is None:
            return None
    walk_m, _, _, _ = res
    return int(round(walk_m))

def nearest_metro_details(address: str, search_km: float = 3.0) -> Dict[str, Any]:
    loc = geocode_smart_moscow(address)
    if not loc:
        return {"address": address, "note": "Геокодирование не удалось (Москва/МО)."}

    lat, lon = loc
    best = _nearest_walk_distance_to_entrances(lat, lon, search_m=int(search_km * 1000)) or \
           _nearest_walk_distance_to_entrances(lat, lon, search_m=5000)

    if best is None:
        return {
            "address": address,
            "address_lat": lat,
            "address_lon": lon,
            "note": "Входы метро не найдены поблизости или путь не построен."
        }

    walk_m, name, elat, elon = best
    crow_m = _haversine_m(lat, lon, elat, elon)
    return {
        "address": address,
        "address_lat": lat,
        "address_lon": lon,
        "distance_walk_m": int(round(walk_m)),
        "distance_straight_m": int(round(crow_m)),
        "entrance_name": name,
        "entrance_lat": elat,
        "entrance_lon": elon,
        "method": "OSM walk-network → subway_entrance (Москва/МО)"
    }

# ---------- Отладка геокодера (Москва/МО) ----------

def debug_geocode_moscow(address: str) -> Dict[str, Any]:
    """
    Подробная отладка:
      - какие варианты мы сгенерировали,
      - какие структурные/свободные попытки делали,
      - что сработало и координаты.
    """
    log: Dict[str, Any] = {
        "original": address,
        "normalized_variants": [],
        "attempts": [],   # {"provider","viewbox","query","ok","lat","lon"}
        "result": None,
    }

    variants = _normalize_ru_address(address)
    log["normalized_variants"] = variants[:]

    # 0) структурно (Москва)
    for v in variants:
        street = re.sub(r'^\s*Россия\s*,\s*Москв[аы]\s*,\s*', '', v, flags=re.IGNORECASE)
        loc = _nominatim_geocode_structured(street=street, city=DEFAULT_CITY, viewbox=MOSCOW_VIEWBOX)
        ok = loc is not None
        lat, lon = (loc if ok else (None, None))
        log["attempts"].append({
            "provider": "nominatim-structured",
            "viewbox": "Moscow",
            "query": f'street="{street}", city="{DEFAULT_CITY}"',
            "ok": ok, "lat": lat, "lon": lon
        })
        if ok:
            log["result"] = {"provider": "nominatim-structured", "viewbox": "Moscow",
                             "query": f'street="{street}", city="{DEFAULT_CITY}"', "lat": lat, "lon": lon}
            return log
        time.sleep(0.2)

    # 1) Nominatim (Москва → МО → без рамки)
    for vb_name, vb in (("Moscow", MOSCOW_VIEWBOX), ("MoscowRegion", MOSCOW_REGION_VIEWBOX), ("None", None)):
        for v in variants:
            loc = _nominatim_geocode(v, vb)
            ok = loc is not None
            lat, lon = (loc if ok else (None, None))
            log["attempts"].append({
                "provider": "nominatim",
                "viewbox": vb_name,
                "query": v,
                "ok": ok, "lat": lat, "lon": lon
            })
            if ok:
                log["result"] = {"provider": "nominatim", "viewbox": vb_name, "query": v, "lat": lat, "lon": lon}
                return log
            time.sleep(0.2)

    # 2) Photon
    for v in variants:
        loc = _photon_geocode(v)
        ok = loc is not None
        lat, lon = (loc if ok else (None, None))
        log["attempts"].append({
            "provider": "photon", "viewbox": "None", "query": v,
            "ok": ok, "lat": lat, "lon": lon
        })
        if ok:
            log["result"] = {"provider": "photon", "viewbox": "None", "query": v, "lat": lat, "lon": lon}
            return log
        time.sleep(0.2)

    return log

def print_geocode_debug(address: str, also_metro: bool = True) -> None:
    info = debug_geocode_moscow(address)
    print("=" * 80)
    print(f"Оригинал: {info['original']}")
    print("Варианты (после нормализации):")
    for i, v in enumerate(info["normalized_variants"], 1):
        print(f"  {i:02d}. {v}")

    if info["result"]:
        r = info["result"]
        print("\n✅ Успех геокодирования:")
        print(f"  Провайдер: {r['provider']} | Рамка: {r['viewbox']}")
        print(f"  Запрос: {r['query']}")
        print(f"  Координаты: lat={r['lat']:.6f}, lon={r['lon']:.6f}")

        if also_metro:
            dist = distance_to_nearest_metro_m(address)
            print(f"  🚇 Ближайшее метро (метры пешком): {dist if dist is not None else 'не найдено'}")
    else:
        print("\n❌ Не удалось геокодировать (Москва/МО + Photon). Проверьте написание дом/к/с.")

# ---------- ТВОИ ТЕСТЫ ----------

if __name__ == "__main__":
    tests = [
        # ВПИСЫВАЙ СВОИ АДРЕСА НИЖЕ — просто строками:
        "Любучанский переулок, дом 1, корпус 2, м. Щербинка",
        # Добавляй сколько угодно строк…
    ]
    for t in tests:
        print_geocode_debug(t, also_metro=True)

    # При желании — подробные детали по станции/входу:
    # print(json.dumps(nearest_metro_details("Москва, Тверская 1"), ensure_ascii=False, indent=2))
