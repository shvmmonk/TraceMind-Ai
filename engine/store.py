"""SQLite persistence for captured *real* demo requests, incidents, and evidence."""
from __future__ import annotations
import json
import os
import sqlite3
from pathlib import Path
from threading import RLock
from datetime import datetime, timezone
from uuid import uuid4

_LOCK = RLock()
DB_PATH = Path(os.environ.get('TRACEMIND_DB', str(Path(__file__).resolve().parents[1] / 'data' / 'tracemind.db')))

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH), timeout=10, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA foreign_keys=ON')
    return db

def init():
    with _LOCK, connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          timestamp TEXT NOT NULL, trace_id TEXT NOT NULL,
          service TEXT NOT NULL, operation TEXT NOT NULL,
          duration_ms REAL NOT NULL, status_code INTEGER NOT NULL,
          severity TEXT NOT NULL, message TEXT NOT NULL, attributes TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_events_trace ON events(trace_id);
        CREATE INDEX IF NOT EXISTS idx_events_time ON events(timestamp);
        CREATE TABLE IF NOT EXISTS incidents (
          id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          title TEXT NOT NULL, severity TEXT NOT NULL, status TEXT NOT NULL,
          service TEXT NOT NULL, trace_id TEXT NOT NULL,
          scenario TEXT NOT NULL, investigation TEXT,
          proposed_fix TEXT, approval_at TEXT, verification TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_incidents_created ON incidents(created_at);
        ''')

def write_event(event):
    with _LOCK, connect() as db:
        db.execute('''INSERT INTO events(timestamp,trace_id,service,operation,duration_ms,status_code,severity,message,attributes)
                      VALUES(?,?,?,?,?,?,?,?,?)''', (
             event.get('timestamp',now()),event['trace_id'],event['service'],event['operation'],
             event['duration_ms'],event['status_code'],event['severity'],event['message'],
             json.dumps(event.get('attributes',{}),sort_keys=True)))

def events(limit=100, trace_id=None, service=None):
    where, args = [], []
    if trace_id:
        where.append('trace_id = ?'); args.append(trace_id)
    if service:
        where.append('service = ?'); args.append(service)
    sql='SELECT * FROM events'+(' WHERE '+' AND '.join(where) if where else '')+' ORDER BY id DESC LIMIT ?'
    with connect() as db:
        rows=db.execute(sql,(*args,min(int(limit),500))).fetchall()
    return [{**dict(r),'attributes':json.loads(r['attributes'])} for r in rows]

def create_incident(title, severity, service, trace_id, scenario):
    ident='INC-'+uuid4().hex[:8].upper(); t=now()
    with _LOCK, connect() as db:
        db.execute('''INSERT INTO incidents(id,created_at,updated_at,title,severity,status,service,trace_id,scenario)
                      VALUES(?,?,?,?,?,?,?,?,?)''',(ident,t,t,title,severity,'DETECTED',service,trace_id,scenario))
    return incident(ident)

def incident(ident):
    with connect() as db:
        r=db.execute('SELECT * FROM incidents WHERE id=?',(ident,)).fetchone()
    if not r:return None
    data=dict(r)
    for field in ('investigation','proposed_fix','verification'):
        data[field] = json.loads(data[field]) if data[field] else None
    return data

def incidents(limit=100):
    with connect() as db:
        ids=[r[0] for r in db.execute('SELECT id FROM incidents ORDER BY created_at DESC, rowid DESC LIMIT ?', (min(int(limit),500),))]
    return [incident(id) for id in ids]

def update_incident(ident, **fields):
    fields['updated_at']=now()
    for k in ('investigation','proposed_fix','verification'):
        if k in fields and fields[k] is not None: fields[k]=json.dumps(fields[k])
    allowed={'status','investigation','proposed_fix','approval_at','verification','updated_at'}
    if set(fields)-allowed:raise ValueError('Unrecognized incident fields')
    with _LOCK, connect() as db:
        db.execute('UPDATE incidents SET '+', '.join(f'{k}=?' for k in fields)+' WHERE id=?',(*fields.values(),ident))
    return incident(ident)

def clear():
    with _LOCK, connect() as db:
        db.execute('DELETE FROM events')
        db.execute('DELETE FROM incidents')
