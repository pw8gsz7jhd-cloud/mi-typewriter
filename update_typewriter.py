"""
update_typewriter.py

Lee la base de datos de Notion (columnas: Name, Date, Checkbox, Category, Type)
y reemplaza las listas de "Events" y "To do list" en index.html con las
tareas/citas de HOY.

Variables de entorno necesarias (se configuran como Secrets/Variables en GitHub):
  NOTION_TOKEN        -> el "Internal Integration Secret" de tu integración de Notion
  NOTION_DATABASE_ID  -> el ID de tu base de datos (32 caracteres)
  TIMEZONE            -> opcional, default "America/Bogota"
"""

import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
TIMEZONE = os.environ.get("TIMEZONE", "America/Bogota")

NOTION_API_URL = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

# Categorías que se agrupan bajo el estilo "work" vs "personal"
WORK_CATEGORIES = {"Work", "Study"}

HTML_PATH = "index.html"


def get_today_str():
    """Fecha de hoy como 'YYYY-MM-DD' en la zona horaria configurada."""
    return datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")


def fetch_today_rows(today_str):
    """Trae de Notion todas las filas cuya columna Date sea hoy."""
    payload = {
        "filter": {
            "property": "Date",
            "date": {"equals": today_str},
        }
    }
    resp = requests.post(NOTION_API_URL, headers=NOTION_HEADERS, json=payload)
    resp.raise_for_status()
    return resp.json().get("results", [])


def extract_fields(row):
    """Saca Name, Category, Type, hora de inicio y hora de fin de una fila de Notion."""
    props = row["properties"]

    name_prop = props.get("Name", {}).get("title", [])
    name = name_prop[0]["plain_text"] if name_prop else "(sin nombre)"

    category_select = props.get("Category", {}).get("select")
    category = category_select["name"] if category_select else "Personal"
    style = "work" if category in WORK_CATEGORIES else "personal"

    type_select = props.get("Type", {}).get("select")
    row_type = type_select["name"] if type_select else "Tarea"

    date_prop = props.get("Date", {}).get("date") or {}
    start_raw = date_prop.get("start", "")
    end_raw = date_prop.get("end", "")

    start_time = _extract_hhmm(start_raw)
    end_time = _extract_hhmm(end_raw)

    return {
        "name": name,
        "style": style,
        "type": row_type,
        "start_time": start_time,
        "end_time": end_time,
    }


def _extract_hhmm(raw_datetime):
    """De '2026-07-15T10:00:00.000-05:00' saca '10:00'. Si no hay hora, retorna ''."""
    if not raw_datetime or "T" not in raw_datetime:
        return ""
    return raw_datetime.split("T")[1][:5]


def build_events_html(rows):
    events = [r for r in rows if r["type"] == "Cita"]
    if not events:
        return (
            '<li><span class="event-icon event-personal">personal</span>'
            '<span class="label">No event YAYY</span></li>'
        )

    items = []
    for e in events:
        time_html = ""
        if e["start_time"]:
            time_html = f'<span class="time">{e["start_time"]}'
            if e["end_time"]:
                time_html += f'&ndash;{e["end_time"]}'
            time_html += "</span>"
        items.append(
            f'<li><span class="event-icon event-{e["style"]}">{e["style"]}</span>'
            f'<span class="label">{e["name"]}</span>{time_html}</li>'
        )
    return "\n".join(items)


def build_todos_html(rows):
    todos = [r for r in rows if r["type"] == "Tarea"]
    if not todos:
        return (
            '<li class="todo"><span class="todo-icon todo-personal">personal</span>'
            '<span class="label">Nothing to do YAYYY</span></li>'
        )

    items = []
    for t in todos:
        items.append(
            f'<li class="todo"><span class="todo-icon todo-{t["style"]}">{t["style"]}</span>'
            f'<span class="label">{t["name"]}</span></li>'
        )
    return "\n".join(items)


def update_html(events_html, todos_html):
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    html = re.sub(
        r'(<ul class="events">)(.*?)(</ul>)',
        lambda m: m.group(1) + "\n" + events_html + "\n" + m.group(3),
        html,
        flags=re.DOTALL,
    )
    html = re.sub(
        r'(<ul class="todos">)(.*?)(</ul>)',
        lambda m: m.group(1) + "\n" + todos_html + "\n" + m.group(3),
        html,
        flags=re.DOTALL,
    )

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    today_str = get_today_str()
    print(f"Buscando filas de Notion para: {today_str}")

    raw_rows = fetch_today_rows(today_str)
    rows = [extract_fields(r) for r in raw_rows]
    print(f"Encontradas {len(rows)} filas para hoy.")

    events_html = build_events_html(rows)
    todos_html = build_todos_html(rows)
    update_html(events_html, todos_html)

    print("index.html actualizado correctamente.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"Error actualizando el typewriter: {exc}", file=sys.stderr)
        sys.exit(1)
