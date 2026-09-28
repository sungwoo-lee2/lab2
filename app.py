from flask import Flask, jsonify, render_template, request, send_file
import csv
import io
import os
import sqlite3
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "stock_lab.db"))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS market_notes (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          note_date TEXT NOT NULL, author TEXT DEFAULT '',
          kospi TEXT DEFAULT '', kosdaq TEXT DEFAULT '',
          foreign_flow TEXT DEFAULT '', institution_flow TEXT DEFAULT '',
          turnover TEXT DEFAULT '', breadth TEXT DEFAULT '',
          summary TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sector_signals (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          sector TEXT NOT NULL, status TEXT NOT NULL, author TEXT DEFAULT '',
          strength INTEGER NOT NULL DEFAULT 50,
          leaders TEXT DEFAULT '', evidence TEXT DEFAULT '', next_check TEXT DEFAULT '',
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS company_reports (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          company TEXT NOT NULL, ticker TEXT DEFAULT '', author TEXT DEFAULT '',
          thesis TEXT NOT NULL, catalysts TEXT DEFAULT '', risks TEXT DEFAULT '',
          earnings TEXT DEFAULT '', supply TEXT DEFAULT '', valuation TEXT DEFAULT '',
          chart_note TEXT DEFAULT '', verdict TEXT DEFAULT '관찰',
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS watchlist (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          member TEXT NOT NULL, stock TEXT NOT NULL, reason TEXT NOT NULL,
          buy_zone TEXT DEFAULT '', checkpoint TEXT DEFAULT '',
          status TEXT NOT NULL DEFAULT '관찰', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS meetings (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          meeting_date TEXT NOT NULL, topic TEXT NOT NULL, author TEXT DEFAULT '',
          attendees TEXT DEFAULT '', conclusions TEXT NOT NULL,
          follow_up TEXT DEFAULT '', created_at TEXT NOT NULL
        );
        """
    )
    # Upgrade databases created by earlier versions without losing records.
    for table in ("market_notes", "sector_signals", "meetings"):
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if "author" not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN author TEXT DEFAULT ''")
    conn.commit()
    conn.close()


def now():
    return datetime.now().isoformat(timespec="seconds")


def clean(data, key, limit=1000):
    return str(data.get(key, "") or "").strip()[:limit]


def rows(conn, sql, params=()):
    return [dict(x) for x in conn.execute(sql, params).fetchall()]


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True, "service": "stock-meeting-lab"})


@app.get("/api/state")
def state():
    conn = db()
    market = rows(conn, "SELECT * FROM market_notes ORDER BY note_date DESC, id DESC LIMIT 12")
    sectors = rows(conn, "SELECT * FROM sector_signals ORDER BY id DESC")
    reports = rows(conn, "SELECT * FROM company_reports ORDER BY id DESC")
    watch = rows(conn, "SELECT * FROM watchlist ORDER BY CASE status WHEN '보유' THEN 1 WHEN '매수대기' THEN 2 WHEN '관찰' THEN 3 ELSE 4 END, id DESC")
    meetings = rows(conn, "SELECT * FROM meetings ORDER BY meeting_date DESC, id DESC")
    conn.close()
    return jsonify({
        "market": market,
        "sectors": sectors,
        "reports": reports,
        "watchlist": watch,
        "meetings": meetings,
        "summary": {
            "reports": len(reports),
            "watch": len(watch),
            "active_sectors": sum(1 for x in sectors if x["status"] in ("신규", "강화")),
            "meetings": len(meetings),
        },
    })


@app.post("/api/market")
def add_market():
    d = request.get_json(force=True)
    if not clean(d, "note_date", 10) or not clean(d, "summary", 1500):
        return jsonify({"error": "날짜와 시장 해석을 입력하세요."}), 400
    conn = db()
    conn.execute(
        """INSERT INTO market_notes(note_date,author,kospi,kosdaq,foreign_flow,institution_flow,turnover,breadth,summary,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (clean(d,"note_date",10),clean(d,"author",30),clean(d,"kospi",30),clean(d,"kosdaq",30),clean(d,"foreign_flow",60),
         clean(d,"institution_flow",60),clean(d,"turnover",60),clean(d,"breadth",60),clean(d,"summary",1500),now()),
    )
    conn.commit(); conn.close()
    return jsonify({"ok": True})


@app.post("/api/sectors")
def add_sector():
    d = request.get_json(force=True)
    sector, status = clean(d,"sector",40), clean(d,"status",10)
    if not sector or status not in ("신규","강화","유지","약화","탈락"):
        return jsonify({"error": "섹터와 상태를 확인하세요."}), 400
    try:
        strength = max(0, min(100, int(d.get("strength", 50))))
    except (TypeError, ValueError):
        return jsonify({"error": "강도는 0~100 숫자로 입력하세요."}), 400
    conn=db()
    conn.execute("INSERT INTO sector_signals(sector,status,author,strength,leaders,evidence,next_check,created_at) VALUES(?,?,?,?,?,?,?,?)",
                 (sector,status,clean(d,"author",30),strength,clean(d,"leaders",300),clean(d,"evidence",1000),clean(d,"next_check",600),now()))
    conn.commit();conn.close()
    return jsonify({"ok":True})


@app.post("/api/reports")
def add_report():
    d=request.get_json(force=True)
    if not clean(d,"company",60) or not clean(d,"thesis",1500):
        return jsonify({"error":"기업명과 핵심 투자논리를 입력하세요."}),400
    verdict=clean(d,"verdict",20)
    if verdict not in ("관찰","긍정","중립","주의"):
        verdict="관찰"
    conn=db()
    conn.execute("""INSERT INTO company_reports(company,ticker,author,thesis,catalysts,risks,earnings,supply,valuation,chart_note,verdict,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                 (clean(d,"company",60),clean(d,"ticker",20),clean(d,"author",30),clean(d,"thesis",1500),
                  clean(d,"catalysts",1000),clean(d,"risks",1000),clean(d,"earnings",500),clean(d,"supply",500),
                  clean(d,"valuation",500),clean(d,"chart_note",500),verdict,now()))
    conn.commit();conn.close()
    return jsonify({"ok":True})


@app.post("/api/watchlist")
def add_watch():
    d=request.get_json(force=True)
    if not all((clean(d,"member",30),clean(d,"stock",60),clean(d,"reason",1000))):
        return jsonify({"error":"작성자, 종목, 관심 이유를 입력하세요."}),400
    status=clean(d,"status",20)
    if status not in ("관찰","매수대기","보유","제외"):
        status="관찰"
    conn=db()
    conn.execute("INSERT INTO watchlist(member,stock,reason,buy_zone,checkpoint,status,created_at) VALUES(?,?,?,?,?,?,?)",
                 (clean(d,"member",30),clean(d,"stock",60),clean(d,"reason",1000),clean(d,"buy_zone",100),clean(d,"checkpoint",600),status,now()))
    conn.commit();conn.close()
    return jsonify({"ok":True})


@app.patch("/api/watchlist/<int:item_id>")
def update_watch(item_id):
    d=request.get_json(force=True); status=clean(d,"status",20)
    if status not in ("관찰","매수대기","보유","제외"):
        return jsonify({"error":"상태값을 확인하세요."}),400
    conn=db();cur=conn.execute("UPDATE watchlist SET status=? WHERE id=?",(status,item_id));conn.commit();conn.close()
    if not cur.rowcount:return jsonify({"error":"항목을 찾을 수 없습니다."}),404
    return jsonify({"ok":True})


@app.post("/api/meetings")
def add_meeting():
    d=request.get_json(force=True)
    if not clean(d,"meeting_date",10) or not clean(d,"topic",150) or not clean(d,"conclusions",2000):
        return jsonify({"error":"날짜, 주제, 최종 결론을 입력하세요."}),400
    conn=db()
    conn.execute("INSERT INTO meetings(meeting_date,topic,author,attendees,conclusions,follow_up,created_at) VALUES(?,?,?,?,?,?,?)",
                 (clean(d,"meeting_date",10),clean(d,"topic",150),clean(d,"author",30),clean(d,"attendees",500),clean(d,"conclusions",2000),clean(d,"follow_up",1500),now()))
    conn.commit();conn.close()
    return jsonify({"ok":True})


TABLES={"market":"market_notes","sectors":"sector_signals","reports":"company_reports","watchlist":"watchlist","meetings":"meetings"}

EDIT_FIELDS={
    "market": {"note_date":10,"author":30,"kospi":30,"kosdaq":30,"foreign_flow":60,"institution_flow":60,"turnover":60,"breadth":60,"summary":1500},
    "sectors": {"sector":40,"status":10,"author":30,"strength":None,"leaders":300,"evidence":1000,"next_check":600},
    "reports": {"company":60,"ticker":20,"author":30,"thesis":1500,"catalysts":1000,"risks":1000,"earnings":500,"supply":500,"valuation":500,"chart_note":500,"verdict":20},
    "watchlist": {"member":30,"stock":60,"reason":1000,"buy_zone":100,"checkpoint":600,"status":20},
    "meetings": {"meeting_date":10,"topic":150,"author":30,"attendees":500,"conclusions":2000,"follow_up":1500},
}
REQUIRED={"market":("note_date","summary"),"sectors":("sector","status"),"reports":("company","thesis"),"watchlist":("member","stock","reason"),"meetings":("meeting_date","topic","conclusions")}


@app.put("/api/<kind>/<int:item_id>")
def edit_item(kind,item_id):
    table=TABLES.get(kind)
    if not table:return jsonify({"error":"수정 대상을 찾을 수 없습니다."}),404
    data=request.get_json(silent=True)
    if not isinstance(data,dict):return jsonify({"error":"입력값을 확인하세요."}),400
    values={key:clean(data,key,limit) for key,limit in EDIT_FIELDS[kind].items() if limit is not None}
    if any(not values.get(key) for key in REQUIRED[kind]):
        return jsonify({"error":"필수 항목을 입력하세요."}),400
    valid={"sectors":{"신규","강화","유지","약화","탈락"},"reports":{"관찰","긍정","중립","주의"},"watchlist":{"관찰","매수대기","보유","제외"}}
    if kind in valid and values["status" if kind!="reports" else "verdict"] not in valid[kind]:
        return jsonify({"error":"상태값을 확인하세요."}),400
    if kind=="sectors":
        try:strength=int(data.get("strength"))
        except (ValueError,TypeError):return jsonify({"error":"강도는 0~100 숫자로 입력하세요."}),400
        if not 0<=strength<=100:return jsonify({"error":"강도는 0~100 숫자로 입력하세요."}),400
        values["strength"]=strength
    columns=list(values)
    conn=db()
    cur=conn.execute(f"UPDATE {table} SET "+", ".join(f"{col}=?" for col in columns)+" WHERE id=?",[values[col] for col in columns]+[item_id])
    conn.commit();conn.close()
    if not cur.rowcount:return jsonify({"error":"항목을 찾을 수 없습니다."}),404
    return jsonify({"ok":True})


@app.delete("/api/<kind>/<int:item_id>")
def delete_item(kind,item_id):
    table=TABLES.get(kind)
    if not table:return jsonify({"error":"삭제 대상을 찾을 수 없습니다."}),404
    conn=db();cur=conn.execute(f"DELETE FROM {table} WHERE id=?",(item_id,));conn.commit();conn.close()
    if not cur.rowcount:return jsonify({"error":"항목을 찾을 수 없습니다."}),404
    return jsonify({"ok":True})


@app.get("/api/export/watchlist.csv")
def export_watchlist():
    conn=db();data=rows(conn,"SELECT member,stock,reason,buy_zone,checkpoint,status,created_at FROM watchlist ORDER BY id DESC");conn.close()
    out=io.StringIO();w=csv.writer(out);w.writerow(["작성자","종목","관심 이유","관심 가격대","확인사항","상태","등록일"])
    for x in data:w.writerow(x.values())
    payload=io.BytesIO(out.getvalue().encode("utf-8-sig"));payload.seek(0)
    return send_file(payload,mimetype="text/csv",as_attachment=True,download_name="공동_관심종목.csv")


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_DEBUG") == "1")
