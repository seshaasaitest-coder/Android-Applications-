from flask import Flask, render_template_string, request, redirect, url_for, session
import pyodbc
import os
import configparser
from datetime import datetime

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini'))

DB_SERVER = config['database']['server']
DB_NAME = config['database']['name']
DB_DRIVER = config['database']['driver']
DB_TRUSTED = config['database'].get('trusted_connection', 'yes').strip().lower() in ('yes', 'true', '1')
DB_USER = config['database'].get('user', '').strip()
DB_PASSWORD = config['database'].get('password', '').strip()

app = Flask(__name__)
app.secret_key = "change-this-secret-key-in-production"


def get_conn():
    if DB_TRUSTED:
        # Windows Authentication
        conn_str = (
            f"DRIVER={DB_DRIVER};"
            f"SERVER={DB_SERVER};"
            f"DATABASE={DB_NAME};"
            f"Trusted_Connection=yes;"
            f"TrustServerCertificate=yes;"
        )
    else:
        # SQL Server Authentication (remote server ke liye)
        conn_str = (
            f"DRIVER={DB_DRIVER};"
            f"SERVER={DB_SERVER};"
            f"DATABASE={DB_NAME};"
            f"UID={DB_USER};"
            f"PWD={DB_PASSWORD};"
            f"TrustServerCertificate=yes;"
        )
    return pyodbc.connect(conn_str)


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        IF OBJECT_ID('dbo.sites', 'U') IS NULL
        CREATE TABLE dbo.sites (
            id INT IDENTITY(1,1) PRIMARY KEY,
            name NVARCHAR(255) NOT NULL,
            location NVARCHAR(255) NOT NULL,
            username NVARCHAR(255) UNIQUE NOT NULL,
            password NVARCHAR(255) NOT NULL,
            created_date NVARCHAR(20) NULL,
            site_start_date NVARCHAR(20) NULL,
            site_end_date NVARCHAR(20) NULL
        )
    ''')
    c.execute('''
        IF OBJECT_ID('dbo.staff', 'U') IS NULL
        CREATE TABLE dbo.staff (
            id INT IDENTITY(1,1) PRIMARY KEY,
            site_id INT NOT NULL,
            category NVARCHAR(50) NOT NULL,
            count INT NOT NULL,
            hire_type NVARCHAR(50) NOT NULL,
            created_date NVARCHAR(20) NULL,
            FOREIGN KEY(site_id) REFERENCES dbo.sites(id)
        )
    ''')
    c.execute('''
        IF OBJECT_ID('dbo.materials', 'U') IS NULL
        CREATE TABLE dbo.materials (
            id INT IDENTITY(1,1) PRIMARY KEY,
            site_id INT NOT NULL,
            item NVARCHAR(255) NOT NULL,
            quantity FLOAT NOT NULL,
            unit NVARCHAR(50) NOT NULL,
            entry_type NVARCHAR(10) NOT NULL,
            source NVARCHAR(50) NOT NULL,
            related_site_id INT NULL,
            vendor_id INT NULL,
            entry_date NVARCHAR(50) NOT NULL,
            FOREIGN KEY(site_id) REFERENCES dbo.sites(id)
        )
    ''')
    c.execute('''
        IF OBJECT_ID('dbo.owner_config', 'U') IS NULL
        CREATE TABLE dbo.owner_config (
            id INT PRIMARY KEY CHECK (id = 1),
            password NVARCHAR(255) NOT NULL
        )
    ''')
    conn.commit()
    c.execute("IF NOT EXISTS (SELECT 1 FROM dbo.owner_config WHERE id = 1) INSERT INTO dbo.owner_config (id, password) VALUES (1, 'owner123')")
    conn.commit()

    # ---- NEW MODULES ----
    c.execute('''
        IF OBJECT_ID('dbo.material_master', 'U') IS NULL
        CREATE TABLE dbo.material_master (
            id INT IDENTITY(1,1) PRIMARY KEY,
            code NVARCHAR(50) UNIQUE NOT NULL,
            name NVARCHAR(255) NOT NULL,
            category NVARCHAR(100) NOT NULL,
            uom NVARCHAR(50) NOT NULL,
            min_stock FLOAT NOT NULL DEFAULT 0,
            created_date NVARCHAR(20) NULL
        )
    ''')
    c.execute('''
        IF OBJECT_ID('dbo.vendors', 'U') IS NULL
        CREATE TABLE dbo.vendors (
            id INT IDENTITY(1,1) PRIMARY KEY,
            name NVARCHAR(255) NOT NULL,
            phone NVARCHAR(50),
            email NVARCHAR(255),
            gst_number NVARCHAR(50),
            pending_payment FLOAT NOT NULL DEFAULT 0,
            created_date NVARCHAR(20) NULL
        )
    ''')
    c.execute('''
        IF OBJECT_ID('dbo.warehouses', 'U') IS NULL
        CREATE TABLE dbo.warehouses (
            id INT IDENTITY(1,1) PRIMARY KEY,
            name NVARCHAR(255) NOT NULL,
            location NVARCHAR(255),
            keeper_name NVARCHAR(255),
            keeper_phone NVARCHAR(50),
            created_date NVARCHAR(20) NULL
        )
    ''')
    c.execute('''
        IF OBJECT_ID('dbo.stock_ledger', 'U') IS NULL
        CREATE TABLE dbo.stock_ledger (
            id INT IDENTITY(1,1) PRIMARY KEY,
            txn_date NVARCHAR(50) NOT NULL,
            txn_type NVARCHAR(30) NOT NULL,
            warehouse_id INT NOT NULL,
            material_id INT NOT NULL,
            quantity FLOAT NOT NULL,
            vendor_id INT NULL,
            invoice_number NVARCHAR(100) NULL,
            rate FLOAT NULL,
            site_id INT NULL,
            related_warehouse_id INT NULL,
            worker_id INT NULL,
            purpose NVARCHAR(255) NULL,
            transporter NVARCHAR(255) NULL,
            vehicle_number NVARCHAR(50) NULL,
            status NVARCHAR(30) NULL,
            FOREIGN KEY(warehouse_id) REFERENCES dbo.warehouses(id),
            FOREIGN KEY(material_id) REFERENCES dbo.material_master(id)
        )
    ''')
    c.execute('''
        IF OBJECT_ID('dbo.workers', 'U') IS NULL
        CREATE TABLE dbo.workers (
            id INT IDENTITY(1,1) PRIMARY KEY,
            site_id INT NOT NULL,
            name NVARCHAR(255) NOT NULL,
            phone NVARCHAR(50),
            role NVARCHAR(100) NOT NULL,
            worker_type NVARCHAR(50) NOT NULL,
            rate_type NVARCHAR(30) NOT NULL,
            rate_amount FLOAT NOT NULL DEFAULT 0,
            id_proof_note NVARCHAR(255),
            created_date NVARCHAR(20) NULL,
            FOREIGN KEY(site_id) REFERENCES dbo.sites(id)
        )
    ''')
    c.execute('''
        IF OBJECT_ID('dbo.worker_attendance', 'U') IS NULL
        CREATE TABLE dbo.worker_attendance (
            id INT IDENTITY(1,1) PRIMARY KEY,
            worker_id INT NOT NULL,
            att_date NVARCHAR(20) NOT NULL,
            status NVARCHAR(20) NOT NULL,
            time_in NVARCHAR(10) NULL,
            time_out NVARCHAR(10) NULL,
            hours FLOAT NOT NULL DEFAULT 0,
            overtime_hours FLOAT NOT NULL DEFAULT 0,
            FOREIGN KEY(worker_id) REFERENCES dbo.workers(id)
        )
    ''')
    conn.commit()
    # migration: add columns to older installs where tables already existed
    c.execute("IF COL_LENGTH('dbo.worker_attendance', 'time_in') IS NULL ALTER TABLE dbo.worker_attendance ADD time_in NVARCHAR(10) NULL")
    c.execute("IF COL_LENGTH('dbo.worker_attendance', 'time_out') IS NULL ALTER TABLE dbo.worker_attendance ADD time_out NVARCHAR(10) NULL")
    c.execute("IF COL_LENGTH('dbo.material_master', 'created_date') IS NULL ALTER TABLE dbo.material_master ADD created_date NVARCHAR(20) NULL")
    c.execute("IF COL_LENGTH('dbo.vendors', 'created_date') IS NULL ALTER TABLE dbo.vendors ADD created_date NVARCHAR(20) NULL")
    c.execute("IF COL_LENGTH('dbo.warehouses', 'created_date') IS NULL ALTER TABLE dbo.warehouses ADD created_date NVARCHAR(20) NULL")
    c.execute("IF COL_LENGTH('dbo.workers', 'created_date') IS NULL ALTER TABLE dbo.workers ADD created_date NVARCHAR(20) NULL")
    c.execute("IF COL_LENGTH('dbo.sites', 'created_date') IS NULL ALTER TABLE dbo.sites ADD created_date NVARCHAR(20) NULL")
    c.execute("IF COL_LENGTH('dbo.sites', 'site_start_date') IS NULL ALTER TABLE dbo.sites ADD site_start_date NVARCHAR(20) NULL")
    c.execute("IF COL_LENGTH('dbo.sites', 'site_end_date') IS NULL ALTER TABLE dbo.sites ADD site_end_date NVARCHAR(20) NULL")
    c.execute("UPDATE dbo.sites SET site_start_date = created_date WHERE site_start_date IS NULL")
    c.execute("IF COL_LENGTH('dbo.materials', 'vendor_id') IS NULL ALTER TABLE dbo.materials ADD vendor_id INT NULL")
    c.execute("IF COL_LENGTH('dbo.staff', 'created_date') IS NULL ALTER TABLE dbo.staff ADD created_date NVARCHAR(20) NULL")
    conn.commit()
    conn.close()


OWNER_USERNAME = "owner"

STYLE = '''
<style>
    @import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --charcoal: #1a1f27;
        --charcoal-light: #262d38;
        --steel: #3d5a73;
        --safety-orange: #e8590c;
        --safety-orange-dark: #c94a08;
        --concrete: #eef0ef;
        --paper: #ffffff;
        --ink: #1a1f27;
        --ink-soft: #5b6472;
        --line: #e2e5e3;
        --ok: #1c7c47;
        --danger: #c62828;
    }

    * { box-sizing: border-box; }
    body {
        font-family: 'Inter', Arial, sans-serif;
        margin: 0;
        color: var(--ink);
        background:
            linear-gradient(rgba(238, 240, 239, 0.94), rgba(238, 240, 239, 0.97)),
            url('https://images.unsplash.com/photo-1541976590-713941681591?auto=format&fit=crop&w=1600&q=60');
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        min-height: 100vh;
    }
    h1, h2, h3, .brand, nav a {
        font-family: 'Barlow Condensed', 'Inter', sans-serif;
        letter-spacing: 0.02em;
    }
    h2 {
        font-size: 30px;
        font-weight: 700;
        text-transform: uppercase;
        color: var(--charcoal);
        border-left: 5px solid var(--safety-orange);
        padding-left: 12px;
        margin: 0 0 20px 0;
    }
    h3 {
        font-size: 20px;
        font-weight: 700;
        text-transform: uppercase;
        color: var(--charcoal);
        margin: 30px 0 12px 0;
    }

    nav {
        background: var(--charcoal);
        padding: 0 24px;
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        border-bottom: 3px solid var(--safety-orange);
    }
    nav .brand {
        color: #fff;
        font-size: 24px;
        font-weight: 700;
        text-transform: uppercase;
        padding: 16px 24px 16px 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    nav a {
        color: #b7c0cc;
        text-decoration: none;
        padding: 20px 16px;
        display: inline-block;
        font-size: 16px;
        font-weight: 600;
        text-transform: uppercase;
        border-bottom: 3px solid transparent;
        transition: color 0.15s, border-color 0.15s;
    }
    nav a:hover, nav a.active { color: #fff; border-bottom-color: var(--safety-orange); }
    nav .spacer { flex: 1; }
    nav .who {
        color: #8b95a3;
        padding: 18px 16px;
        font-family: 'Inter', sans-serif;
        font-size: 13px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    .container { padding: 32px 25px; max-width: 1100px; margin: 0 auto; }

    .cards { display: flex; gap: 18px; flex-wrap: wrap; margin-bottom: 30px; }
    .stat-card {
        flex: 1; min-width: 170px;
        background: var(--paper);
        padding: 22px 20px;
        border-radius: 6px;
        border-top: 4px solid var(--safety-orange);
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }
    .stat-card .label {
        color: var(--ink-soft);
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 600;
    }
    .stat-card .value {
        font-family: 'Barlow Condensed', sans-serif;
        font-size: 34px;
        font-weight: 700;
        color: var(--charcoal);
        margin-top: 4px;
    }

    .toggle-btn {
        background: var(--steel);
        color: white;
        padding: 10px 18px;
        border: none;
        border-radius: 4px;
        font-weight: 700;
        text-transform: uppercase;
        cursor: pointer;
        margin-bottom: 15px;
        display: inline-block;
        width: auto;
    }
    .toggle-btn:hover { background: var(--charcoal); }

    .collapsible-form { display: none; }

    form.card {
        background: var(--paper);
        padding: 24px;
        border-radius: 6px;
        margin-bottom: 24px;
        max-width: 440px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        border: 1px solid var(--line);
    }
    label.field-label {
        display: block;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--ink-soft);
        margin-bottom: 4px;
    }
    input, select {
        width: 100%;
        padding: 10px 12px;
        margin: 0 0 16px 0;
        border: 1px solid #cfd4d9;
        border-radius: 4px;
        font-family: 'Inter', sans-serif;
        font-size: 14px;
        background: var(--paper);
        color: var(--ink);
    }
    input:focus, select:focus { outline: none; border-color: var(--safety-orange); }
    button[type="submit"] {
        background: var(--safety-orange);
        color: white;
        padding: 12px;
        border: none;
        width: 100%;
        cursor: pointer;
        border-radius: 4px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-size: 14px;
        transition: background 0.15s;
    }
    button[type="submit"]:hover { background: var(--safety-orange-dark); }

    table {
        width: 100%;
        background: var(--paper);
        border-collapse: collapse;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        margin-bottom: 24px;
        border-radius: 6px;
        overflow: hidden;
    }
    th, td { border-bottom: 1px solid var(--line); padding: 12px; text-align: center; font-size: 14px; }
    th {
        background: var(--charcoal);
        color: #fff;
        text-transform: uppercase;
        font-size: 12px;
        letter-spacing: 0.06em;
        font-weight: 600;
    }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: #fafafa; }

    .in-tag { color: var(--ok); font-weight: 700; }
    .out-tag { color: var(--danger); font-weight: 700; }
    .delete-link { color: var(--danger); text-decoration: none; font-weight: 600; font-size: 13px; }
    .delete-link:hover { text-decoration: underline; }

    .login-wrap {
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 100vh;
        background:
            linear-gradient(rgba(15, 20, 28, 0.78), rgba(15, 20, 28, 0.85)),
            url('https://images.unsplash.com/photo-1541976590-713941681591?auto=format&fit=crop&w=1600&q=80');
        background-size: cover;
        background-position: center;
    }
    .login-box {
        background: var(--paper);
        padding: 40px 36px;
        border-radius: 8px;
        width: 360px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.4);
        border-top: 5px solid var(--safety-orange);
    }
    .login-box .brand-mark {
        text-align: center;
        margin-bottom: 6px;
        font-family: 'Barlow Condensed', sans-serif;
        font-size: 30px;
        font-weight: 700;
        text-transform: uppercase;
        color: var(--charcoal);
        letter-spacing: 0.03em;
    }
    .login-box .tagline {
        text-align: center;
        color: var(--ink-soft);
        font-size: 13px;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 26px;
    }
    .error {
        color: var(--danger);
        text-align: center;
        font-size: 14px;
        font-weight: 600;
        margin-top: 4px;
    }
    .success-msg {
        color: var(--ok);
        text-align: center;
        font-size: 14px;
        font-weight: 600;
    }

    .site-link {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: var(--paper);
        padding: 18px 20px;
        border-radius: 6px;
        margin-bottom: 10px;
        text-decoration: none;
        color: var(--ink);
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        border-left: 4px solid var(--steel);
        transition: border-color 0.15s, transform 0.1s;
    }
    .site-link:hover { border-left-color: var(--safety-orange); transform: translateX(2px); }
    .site-link .site-name { font-weight: 700; font-size: 17px; }
    .site-link .site-meta { color: var(--ink-soft); font-size: 13px; }
    .page-head{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;margin-bottom:24px}
    .muted,.card-note{color:var(--ink-soft);font-size:13px}
    .primary-link{background:var(--safety-orange);color:#fff;padding:11px 16px;border-radius:5px;text-decoration:none;font-weight:700}
    .stat-link{text-decoration:none;color:inherit;display:block}
    .stat-link:hover{transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,.12)}
    .dashboard-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:24px}
    .panel{background:var(--paper);border:1px solid var(--line);border-radius:7px;padding:22px;margin-bottom:24px;box-shadow:0 1px 4px rgba(0,0,0,.06)}
    .panel-title{font-family:'Barlow Condensed',sans-serif;font-size:20px;font-weight:700;text-transform:uppercase;margin-bottom:18px}
    .status-bars{display:flex;flex-direction:column;gap:16px}
    .bar-row{display:grid;grid-template-columns:70px 1fr 40px;align-items:center;gap:12px;font-size:13px}
    .bar{height:12px;background:#e7eaed;border-radius:20px;overflow:hidden}.bar i{display:block;height:100%;background:var(--safety-orange);border-radius:20px}
    .mini-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.mini-stats div{padding:15px;background:var(--concrete);border-radius:6px;text-align:center}.mini-stats strong{display:block;font-size:28px}.mini-stats span{font-size:12px;color:var(--ink-soft);text-transform:uppercase}
    .portfolio-table{width:100%}.portfolio-row{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:12px;align-items:center;padding:13px 10px;border-bottom:1px solid var(--line);text-decoration:none;color:inherit}.portfolio-row small{display:block;color:var(--ink-soft);font-size:11px}.portfolio-head{font-size:11px;text-transform:uppercase;font-weight:700;background:var(--charcoal);color:#fff}
    .status-live,.status-closed{font-weight:700}.status-live{color:var(--ok)}.status-closed{color:var(--danger)}
    .status-badge{padding:7px 12px;border-radius:20px;font-weight:700;font-size:12px;text-transform:uppercase}.status-badge.live{background:#e5f4ec;color:var(--ok)}.status-badge.closed{background:#fdeaea;color:var(--danger)}
    .site-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:14px}.site-card{display:block;padding:18px;border:1px solid var(--line);border-radius:7px;text-decoration:none;color:inherit;background:#fff}.site-card:hover{border-color:var(--safety-orange);transform:translateY(-1px)}.site-card-top{display:flex;justify-content:space-between;gap:10px}.site-dates{font-size:12px;color:var(--ink-soft);margin:10px 0}.site-metrics{display:grid;grid-template-columns:1fr 1fr;gap:7px;font-size:12px}.site-metrics span{background:var(--concrete);padding:7px;border-radius:4px}.filter-links{display:flex;gap:8px}.filter-links a{padding:8px 12px;border:1px solid var(--line);border-radius:5px;text-decoration:none;color:var(--ink);font-size:12px}.empty{color:var(--ink-soft);padding:16px;text-align:center}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 16px}.narrow{max-width:900px}.card{max-width:none}
    @media(max-width:760px){.dashboard-grid,.form-grid{grid-template-columns:1fr}.page-head{flex-direction:column}.portfolio-row{grid-template-columns:1fr 1fr}.mini-stats{grid-template-columns:1fr 1fr}}
</style>
'''

# ---------------- LOGIN ----------------
LOGIN_TEMPLATE = STYLE + '''
<div class="login-wrap">
    <div class="login-box">
        <div class="brand-mark">🏗️ BuildTrack</div>
        <div class="tagline">Site &amp; Resource Management</div>
        <form method="post">
            <label class="field-label">Username</label>
            <input type="text" name="username" placeholder="Enter your site or owner username" required>
            <label class="field-label">Password</label>
            <input type="password" name="password" placeholder="Enter your password" required>
            <button type="submit">Sign In</button>
        </form>
        {% if error %}<p class="error">{{ error }}</p>{% endif %}
'''


def nav(active, site_name=None, is_owner=False):
    who = "Owner" if is_owner else (site_name or "")
    if is_owner:
        links = '''
        <a href="/owner/add-site" class="{a1}">Add Site</a>
        <a href="/owner/sites" class="{a2}">Sites</a>
        <a href="/owner/reports" class="{a3}">Reports</a>
        <a href="/owner/change-password" class="{a4}">Change Password</a>
        '''.format(
            a1='active' if active == 'add_site' else '',
            a2='active' if active in ('owner', 'sites') else '',
            a3='active' if active == 'reports' else '',
            a4='active' if active == 'owner_password' else '',
        )
    else:
        links = '''
        <a href="/dashboard" class="{a1}">Dashboard</a>
        <a href="/work" class="{a2}">Work</a>
        <a href="/materials" class="{a3}">Materials</a>
        <a href="/change-password" class="{a4}">Change Password</a>
        '''.format(
            a1='active' if active == 'dashboard' else '',
            a2='active' if active == 'work' else '',
            a3='active' if active == 'materials' else '',
            a4='active' if active == 'change_password' else '',
        )
    return '''
    <nav>
        <a class="brand" href="/owner" style="text-decoration:none;">🏗️ BuildTrack</a>
        {links}
        <div class="who">{who}</div>
        <a href="/logout">Log Out</a>
    </nav>
    '''.format(links=links, who=who)


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template_string(LOGIN_TEMPLATE, error=None)

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()

    conn = get_conn()
    c = conn.cursor()

    if username == OWNER_USERNAME:
        c.execute("SELECT password FROM owner_config WHERE id=1")
        owner_pass = c.fetchone()[0]
        conn.close()
        if password == owner_pass:
            session['role'] = 'owner'
            return redirect(url_for('owner_overview'))
        return render_template_string(LOGIN_TEMPLATE, error="Incorrect owner password.")

    c.execute("SELECT id, name, password FROM sites WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()

    if row and row[2] == password:
        session['role'] = 'site'
        session['site_id'] = row[0]
        session['site_name'] = row[1]
        return redirect(url_for('dashboard'))

    return render_template_string(LOGIN_TEMPLATE, error="Incorrect username or password. Please try again.")


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


def require_site():
    return session.get('role') == 'site' and 'site_id' in session


def require_owner():
    return session.get('role') == 'owner'


def get_site_status(site_end_date):
    """A site is Live until its configured end date; no end date means ongoing."""
    if not site_end_date:
        return 'Live'
    try:
        return 'Closed' if datetime.strptime(str(site_end_date), '%Y-%m-%d').date() < datetime.now().date() else 'Live'
    except (TypeError, ValueError):
        return 'Live'


# ---------------- OWNER VIEWS ----------------
OWNER_TEMPLATE = STYLE + '''
<div class="container">
    <div class="page-head"><div><h2>Owner Dashboard</h2><p class="muted">Live project status, workforce and material activity at a glance.</p></div><a class="primary-link" href="/owner/sites">View All Sites →</a></div>
    <div class="cards dashboard-cards">
        <a class="stat-card stat-link" href="/owner/sites"><div class="label">Total Sites</div><div class="value">{{ total_sites }}</div><div class="card-note">Open site portfolio</div></a>
        <a class="stat-card stat-link" href="/owner/sites?status=live"><div class="label">Live Sites</div><div class="value">{{ live_sites }}</div><div class="card-note">Currently active</div></a>
        <a class="stat-card stat-link" href="/owner/sites?status=closed"><div class="label">Closed Sites</div><div class="value">{{ closed_sites }}</div><div class="card-note">End date completed</div></a>
        <div class="stat-card"><div class="label">Total Workforce</div><div class="value">{{ total_workers }}</div><div class="card-note">Workers + Engineers + Masons</div></div>
    </div>
    <div class="dashboard-grid">
        <section class="panel"><div class="panel-title">Site Status</div><div class="status-bars">
            <div class="bar-row"><span>Live</span><div class="bar"><i style="width:{{ live_pct }}%"></i></div><strong>{{ live_sites }}</strong></div>
            <div class="bar-row"><span>Closed</span><div class="bar"><i style="width:{{ closed_pct }}%"></i></div><strong>{{ closed_sites }}</strong></div>
        
'''


OWNER_SITES_TEMPLATE = STYLE + '''
<div class="container">
<div class="page-head"><div><h2>Site Portfolio</h2><p class="muted">Click any site to open complete site details. Dashboard keeps this list hidden.</p></div>
<div class="filter-links"><a href="/owner/sites">All</a><a href="/owner/sites?status=live">Live</a><a href="/owner/sites?status=closed">Closed</a></div></div>
<div class="cards">
<a class="stat-card stat-link" href="/owner/sites"><div class="label">Total Sites</div><div class="value">{{total_sites}}</div></a>
<a class="stat-card stat-link" href="/owner/sites?status=live"><div class="label">Live Sites</div><div class="value">{{live_sites}}</div></a>
<a class="stat-card stat-link" href="/owner/sites?status=closed"><div class="label">Closed Sites</div><div class="value">{{closed_sites}}</div></a>
</div>
<section class="panel"><div class="panel-title">Site Status Graph</div>
<div class="status-bars"><div class="bar-row"><span>Live</span><div class="bar"><i style="width:{{live_pct}}%"></i></div><strong>{{live_sites}}</strong></div>
<div class="bar-row"><span>Closed</span><div class="bar"><i style="width:{{closed_pct}}%"></i></div><strong>{{closed_sites}}</strong></div></div></section>
<section class="panel"><div class="panel-title">All Sites — {{filter_status|title}}</div>
<div class="site-grid">{% for s in sites %}<a class="site-card" href="/owner/site/{{s.id}}">
<div class="site-card-top"><strong>{{s.name}}</strong><span class="{{ 'status-live' if s.status=='Live' else 'status-closed' }}">{{s.status}}</span></div>
<div class="muted">{{s.location}}</div><div class="site-dates">Start: {{s.start_date or '—'}} · End: {{s.end_date or 'Ongoing'}}</div>
<div class="site-metrics"><span>Workers <b>{{s.workers}}</b></span><span>Engineers <b>{{s.engineers}}</b></span><span>Masons <b>{{s.masons}}</b></span><span>Materials <b>{{s.materials}}</b></span></div>
</a>{% else %}<div class="empty">No sites found for this filter.</div>{% endfor %}</div></section>
</div>
'''
ADD_SITE_TEMPLATE = STYLE + '''
<div class="container narrow"><h2>Add Site</h2>
<form class="card" action="/owner/add-site" method="post"><div class="form-grid">
<div><label class="field-label">Site Name</label><input type="text" name="name" required></div>
<div><label class="field-label">Location</label><input type="text" name="location" required></div>
<div><label class="field-label">Site Start Date</label><input type="date" name="site_start_date" required></div>
<div><label class="field-label">Site End Date</label><input type="date" name="site_end_date"></div>
<div><label class="field-label">Site Login Username</label><input type="text" name="username" required></div>
<div><label class="field-label">Site Login Password</label><input type="password" name="password" required></div>
</div><button type="submit">Create Site</button></form>
{% if error %}<p class="error">{{ error }}</p>{% endif %}{% if success %}<p class="success-msg">{{ success }}</p>{% endif %}
</div>
'''


SITE_DETAIL_TEMPLATE = STYLE + '''
<div class="container">
<div class="page-head"><div><h2>{{ site_name }}</h2><p class="muted">{{ location }} · {{ site_start_date or 'Start date not set' }} → {{ site_end_date or 'Ongoing' }}</p></div>
<span class="{{ 'status-badge live' if site_status == 'Live' else 'status-badge closed' }}">{{ site_status }}</span></div>
<div class="cards"><div class="stat-card"><div class="label">Workers</div><div class="value">{{ workforce.workers }}</div></div><div class="stat-card"><div class="label">Engineers</div><div class="value">{{ workforce.engineers }}</div></div><div class="stat-card"><div class="label">Masons</div><div class="value">{{ workforce.masons }}</div></div><div class="stat-card"><div class="label">Material Entries</div><div class="value">{{ materials|length }}</div></div></div>

<section class="panel"><div class="panel-title">Site Details</div>
<form action="/owner/site/{{ site_id }}/edit" method="post"><div class="form-grid">
<div><label class="field-label">Site Name</label><input type="text" name="name" value="{{ site_name }}" required></div>
<div><label class="field-label">Location</label><input type="text" name="location" value="{{ location }}" required></div>
<div><label class="field-label">Start Date</label><input type="date" name="site_start_date" value="{{ site_start_date or '' }}" required></div>
<div><label class="field-label">End Date</label><input type="date" name="site_end_date" value="{{ site_end_date or '' }}"></div>
<div><label class="field-label">Login Username</label><input type="text" name="username" value="{{ username }}" required></div>
<div><label class="field-label">New Login Password</label><input type="password" name="password" placeholder="Leave blank to keep current"></div>
</div><button type="submit">Save Site Details</button></form>
{% if edit_error %}<p class="error">{{ edit_error }}</p>{% endif %}{% if edit_success %}<p class="success-msg">{{ edit_success }}</p>{% endif %}
</section>

<section class="panel"><div class="panel-title">Workforce</div><button type="button" class="toggle-btn" onclick="toggleForm('staffForm')">＋ Add Workforce</button>
<form class="card collapsible-form" id="staffForm" action="/owner/site/{{ site_id }}/staff/add" method="post"><div class="form-grid">
<div><label class="field-label">Category</label><select name="category"><option>Worker</option><option>Engineer</option><option>Mason</option></select></div>
<div><label class="field-label">Count</label><input type="number" min="1" name="count" required></div>
<div><label class="field-label">Engagement Type</label><select name="hire_type"><option value="Hired">Hired (Contracted)</option><option value="Self">Self (Company Staff)</option></select></div>
</div><button type="submit">Save Workforce</button></form>
<table><tr><th>Date</th><th>Category</th><th>Count</th><th>Engagement</th></tr>{% for s in staff %}<tr><td>{{s[4]}}</td><td>{{s[1]}}</td><td>{{s[2]}}</td><td>{{s[3]}}</td></tr>{% else %}<tr><td colspan="4" class="empty">No workforce entries.</td></tr>{% endfor %}</table>
</section>

<section class="panel"><div class="panel-title">Material Log</div><button type="button" class="toggle-btn" onclick="toggleForm('materialForm')">＋ Add Material</button>
<form class="card collapsible-form" id="materialForm" action="/owner/site/{{ site_id }}/materials/add" method="post"><div class="form-grid">
<div><label class="field-label">Material</label><input type="text" name="item" required></div><div><label class="field-label">Quantity</label><input type="number" step="0.01" min="0.01" name="quantity" required></div>
<div><label class="field-label">Unit</label><input type="text" name="unit" required></div><div><label class="field-label">Direction</label><select name="entry_type"><option value="IN">Incoming</option><option value="OUT">Outgoing</option></select></div>
<div><label class="field-label">Source</label><select name="source" id="source_owner" onchange="toggleOwnerMaterialFields()"><option value="Purchased">Purchased Externally</option><option value="Self">Company Stock</option><option value="Transfer">Transfer To/From Another Site</option></select></div>
<div id="vendor_owner_wrap"><label class="field-label">Vendor</label><select name="vendor_id"><option value="">Select Vendor</option>{% for v in vendors %}<option value="{{v[0]}}">{{v[1]}}</option>{% endfor %}</select></div>
<div id="transfer_owner_wrap" style="display:none;"><label class="field-label">Other Site</label><select name="related_site_id"><option value="">Select Site</option>{% for s in all_sites %}{% if s[0] != site_id %}<option value="{{s[0]}}">{{s[1]}}</option>{% endif %}{% endfor %}</select></div>
</div><button type="submit">Save Material</button></form>
<table><tr><th>Date</th><th>Item</th><th>Qty</th><th>Direction</th><th>Source</th><th>Vendor</th><th>Site</th></tr>
{% for m in materials %}<tr><td>{{m[1]}}</td><td>{{m[2]}}</td><td>{{m[3]}} {{m[4]}}</td><td class="{{ 'in-tag' if m[5]=='IN' else 'out-tag' }}">{{'Incoming' if m[5]=='IN' else 'Outgoing'}}</td><td>{{m[6]}}</td><td>{{m[8] or '—'}}</td><td>{{m[7] or '—'}}</td></tr>{% else %}<tr><td colspan="7" class="empty">No material entries.</td></tr>{% endfor %}</table>
<script>
function toggleForm(id){var f=document.getElementById(id);f.style.display=f.style.display==='block'?'none':'block';}
function toggleOwnerMaterialFields(){var transfer=document.getElementById('source_owner').value==='Transfer';document.getElementById('transfer_owner_wrap').style.display=transfer?'block':'none';document.getElementById('vendor_owner_wrap').style.display=transfer?'none':'block';}
</script>
'''


OWNER_PASSWORD_TEMPLATE = STYLE + '''
<div class="container">
    <h2>Change Owner Password</h2>
    <form class="card" method="post">
        <label class="field-label">Current Password</label>
        <input type="password" name="current_password" placeholder="Enter current owner password" required>
        <label class="field-label">New Password</label>
        <input type="password" name="new_password" placeholder="Enter new password" required>
        <label class="field-label">Confirm New Password</label>
        <input type="password" name="confirm_password" placeholder="Re-enter new password" required>
        <button type="submit">Update Owner Password</button>
    </form>
    {% if error %}<p class="error">{{ error }}</p>{% endif %}
    {% if success %}<p class="success-msg">{{ success }}</p>{% endif %}
</div>
'''


@app.route('/owner')
def owner_overview():
    if not require_owner():
        return redirect(url_for('login'))
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name, location, created_date, site_start_date, site_end_date FROM sites ORDER BY name")
    rows = c.fetchall()
    c.execute("SELECT COALESCE(SUM(count),0) FROM staff")
    total_workers = c.fetchone()[0] or 0
    c.execute("SELECT COALESCE(SUM(count),0) FROM staff WHERE category='Engineer'")
    total_engineers = c.fetchone()[0] or 0
    c.execute("SELECT COALESCE(SUM(count),0) FROM staff WHERE category='Mason'")
    total_mason = c.fetchone()[0] or 0
    snapshot=[]
    live_sites=closed_sites=0
    for sid,name,location,created_date,start_date,end_date in rows:
        status=get_site_status(end_date)
        live_sites += status == 'Live'
        closed_sites += status == 'Closed'
        c.execute("SELECT COALESCE(SUM(count),0) FROM staff WHERE site_id=?", (sid,))
        workers=c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*) FROM materials WHERE site_id=?", (sid,))
        material_count=c.fetchone()[0] or 0
        snapshot.append({'id':sid,'name':name,'location':location,'status':status,'workers':workers,'materials':material_count})
    conn.close()
    total_sites=len(rows)
    denom=max(total_sites,1)
    return render_template_string(
        nav('owner', is_owner=True) + OWNER_TEMPLATE,
        total_sites=total_sites, live_sites=live_sites, closed_sites=closed_sites,
        total_workers=total_workers, total_engineers=total_engineers, total_mason=total_mason,
        live_pct=round(live_sites*100/denom,1), closed_pct=round(closed_sites*100/denom,1),
        site_snapshot=snapshot
    )


@app.route('/owner/sites')
def owner_sites():
    if not require_owner():
        return redirect(url_for('login'))
    filter_status=request.args.get('status','all').lower()
    conn=get_conn()
    c=conn.cursor()
    c.execute("SELECT id,name,location,username,created_date,site_start_date,site_end_date FROM sites ORDER BY name")
    rows=c.fetchall()
    sites=[]
    live=closed=0
    for sid,name,location,username,created_date,start_date,end_date in rows:
        status=get_site_status(end_date)
        live += status == 'Live'; closed += status == 'Closed'
        c.execute("SELECT category,COALESCE(SUM(count),0) FROM staff WHERE site_id=? GROUP BY category",(sid,))
        counts={r[0]:r[1] for r in c.fetchall()}
        c.execute("SELECT COUNT(*) FROM materials WHERE site_id=?",(sid,))
        materials=c.fetchone()[0] or 0
        site={'id':sid,'name':name,'location':location,'username':username,'created_date':created_date,
              'start_date':start_date or created_date,'end_date':end_date,'status':status,
              'workers':counts.get('Worker',0),'engineers':counts.get('Engineer',0),'masons':counts.get('Mason',0),
              'total_work':sum(counts.values()),'materials':materials}
        if filter_status in ('live','closed') and status.lower()!=filter_status:
            continue
        sites.append(site)
    conn.close()
    total=len(rows)
    return render_template_string(nav('sites',is_owner=True)+OWNER_SITES_TEMPLATE,
        sites=sites,total_sites=total,live_sites=live,closed_sites=closed,
        live_pct=round(live*100/max(total,1),1),closed_pct=round(closed*100/max(total,1),1),
        filter_status=filter_status)


@app.route('/owner/change-password', methods=['GET', 'POST'])
def owner_change_password():
    if not require_owner():
        return redirect(url_for('login'))

    error = None
    success = None
    if request.method == 'POST':
        current = request.form.get('current_password', '').strip()
        new = request.form.get('new_password', '').strip()
        confirm = request.form.get('confirm_password', '').strip()

        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT password FROM owner_config WHERE id=1")
        db_pass = c.fetchone()[0]

        if current != db_pass:
            error = "Current owner password is incorrect."
        elif not new:
            error = "New password cannot be empty."
        elif new != confirm:
            error = "New password and confirmation do not match."
        else:
            c.execute("UPDATE owner_config SET password=? WHERE id=1", (new,))
            conn.commit()
            success = "Owner password updated successfully."
        conn.close()

    return render_template_string(
        nav('owner_password', is_owner=True) + OWNER_PASSWORD_TEMPLATE,
        error=error, success=success
    )


@app.route('/owner/add-site', methods=['GET', 'POST'])
def add_site():
    if not require_owner():
        return redirect(url_for('login'))

    error = None
    success = None
    if request.method == 'POST':
        try:
            name = request.form['name'].strip()
            location = request.form['location'].strip()
            username = request.form['username'].strip()
            password = request.form['password'].strip()
            site_start_date = request.form.get('site_start_date', '').strip()
            site_end_date = request.form.get('site_end_date', '').strip() or None
            if not (name and location and username and password and site_start_date):
                raise ValueError
            conn = get_conn()
            c = conn.cursor()
            c.execute("INSERT INTO sites (name, location, username, password, created_date, site_start_date, site_end_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (name, location, username, password, datetime.now().strftime('%Y-%m-%d'), site_start_date, site_end_date))
            conn.commit()
            conn.close()
            success = f"Site '{name}' created successfully. Login username: {username}"
        except pyodbc.IntegrityError:
            error = "This username is already taken."
        except (ValueError, KeyError):
            error = "Please fill in all fields."

    return render_template_string(nav('add_site', is_owner=True) + ADD_SITE_TEMPLATE, error=error, success=success)


@app.route('/owner/site/<int:site_id>')
def owner_site_detail(site_id):
    if not require_owner():
        return redirect(url_for('login'))
    conn=get_conn(); c=conn.cursor()
    c.execute("SELECT name,location,username,created_date,site_start_date,site_end_date FROM sites WHERE id=?",(site_id,))
    row=c.fetchone()
    if not row:
        conn.close(); return redirect(url_for('owner_sites'))
    site_name,location,username,created_date,site_start_date,site_end_date=row
    c.execute("SELECT id,category,count,hire_type,created_date FROM staff WHERE site_id=? ORDER BY id DESC",(site_id,))
    staff=c.fetchall()
    c.execute('''SELECT m.id,m.entry_date,m.item,m.quantity,m.unit,m.entry_type,m.source,
                 (SELECT name FROM sites WHERE id=m.related_site_id),
                 (SELECT name FROM vendors WHERE id=m.vendor_id)
                 FROM materials m WHERE m.site_id=? ORDER BY m.entry_date DESC,m.id DESC''',(site_id,))
    materials=c.fetchall()
    c.execute("SELECT id,name FROM sites ORDER BY name"); all_sites=c.fetchall()
    c.execute("SELECT id,name FROM vendors ORDER BY name"); vendors=c.fetchall()
    c.execute("SELECT category,COALESCE(SUM(count),0) FROM staff WHERE site_id=? GROUP BY category",(site_id,))
    counts={r[0]:r[1] for r in c.fetchall()}
    conn.close()
    return render_template_string(nav('owner',is_owner=True)+SITE_DETAIL_TEMPLATE,
        site_id=site_id,site_name=site_name,location=location,username=username,
        created_date=created_date,site_start_date=site_start_date or created_date,site_end_date=site_end_date,
        site_status=get_site_status(site_end_date),staff=staff,materials=materials,all_sites=all_sites,vendors=vendors,
        workforce={'workers':counts.get('Worker',0),'engineers':counts.get('Engineer',0),'masons':counts.get('Mason',0)},
        edit_error=None,edit_success=None)


@app.route('/owner/site/<int:site_id>/edit', methods=['POST'])
def owner_edit_site(site_id):
    if not require_owner():
        return redirect(url_for('login'))

    conn = get_conn()
    c = conn.cursor()
    edit_error = None
    edit_success = None
    try:
        name = request.form['name'].strip()
        location = request.form['location'].strip()
        username = request.form['username'].strip()
        password = request.form.get('password', '').strip()
        site_start_date = request.form.get('site_start_date', '').strip()
        site_end_date = request.form.get('site_end_date', '').strip() or None

        if not (name and location and username and site_start_date):
            edit_error = "Site name, location, and username cannot be empty."
        else:
            if password:
                c.execute("UPDATE sites SET name=?, location=?, username=?, password=?, site_start_date=?, site_end_date=? WHERE id=?",
                          (name, location, username, password, site_start_date, site_end_date, site_id))
            else:
                c.execute("UPDATE sites SET name=?, location=?, username=?, site_start_date=?, site_end_date=? WHERE id=?",
                          (name, location, username, site_start_date, site_end_date, site_id))
            conn.commit()
            edit_success = "Site details updated successfully."
    except pyodbc.IntegrityError:
        edit_error = "This username is already taken by another site."
    except KeyError:
        edit_error = "Please fill in all required fields."

    c.execute("SELECT name,location,username,created_date,site_start_date,site_end_date FROM sites WHERE id=?",(site_id,))
    site_name,location,username,created_date,site_start_date,site_end_date=c.fetchone()
    c.execute("SELECT id,category,count,hire_type,created_date FROM staff WHERE site_id=? ORDER BY id DESC",(site_id,)); staff=c.fetchall()
    c.execute('''SELECT m.id,m.entry_date,m.item,m.quantity,m.unit,m.entry_type,m.source,
                 (SELECT name FROM sites WHERE id=m.related_site_id),
                 (SELECT name FROM vendors WHERE id=m.vendor_id)
                 FROM materials m WHERE m.site_id=? ORDER BY m.entry_date DESC,m.id DESC''',(site_id,)); materials=c.fetchall()
    c.execute("SELECT id,name FROM sites ORDER BY name"); all_sites=c.fetchall()
    c.execute("SELECT id,name FROM vendors ORDER BY name"); vendors=c.fetchall()
    c.execute("SELECT category,COALESCE(SUM(count),0) FROM staff WHERE site_id=? GROUP BY category",(site_id,)); counts={r[0]:r[1] for r in c.fetchall()}
    conn.close()
    return render_template_string(nav('owner',is_owner=True)+SITE_DETAIL_TEMPLATE,
        site_id=site_id,site_name=site_name,location=location,username=username,created_date=created_date,
        site_start_date=site_start_date or created_date,site_end_date=site_end_date,site_status=get_site_status(site_end_date),
        staff=staff,materials=materials,all_sites=all_sites,vendors=vendors,
        workforce={'workers':counts.get('Worker',0),'engineers':counts.get('Engineer',0),'masons':counts.get('Mason',0)},
        edit_error=edit_error,edit_success=edit_success)


@app.route('/owner/site/<int:site_id>/staff/add', methods=['POST'])
def owner_add_staff(site_id):
    if not require_owner():
        return redirect(url_for('login'))
    try:
        category = request.form['category']
        count = int(request.form['count'])
        hire_type = request.form['hire_type']
        if category in ('Worker', 'Engineer', 'Mason') and hire_type in ('Hired', 'Self') and count > 0:
            conn = get_conn()
            c = conn.cursor()
            c.execute("INSERT INTO staff (site_id, category, count, hire_type, created_date) VALUES (?, ?, ?, ?, ?)",
                      (site_id, category, count, hire_type, datetime.now().strftime('%Y-%m-%d')))
            conn.commit()
            conn.close()
    except (ValueError, KeyError):
        pass
    return redirect(url_for('owner_site_detail', site_id=site_id))


@app.route('/owner/site/<int:site_id>/materials/add', methods=['POST'])
def owner_add_material(site_id):
    if not require_owner():
        return redirect(url_for('login'))
    try:
        item = request.form['item'].strip()
        quantity = float(request.form['quantity'])
        unit = request.form['unit'].strip()
        entry_type = request.form['entry_type']
        source = request.form['source']
        related_site_id = request.form.get('related_site_id') or None
        vendor_id = request.form.get('vendor_id') or None
        if related_site_id:
            related_site_id = int(related_site_id)
        if vendor_id:
            vendor_id = int(vendor_id)
        if source != 'Purchased':
            vendor_id = None
        if source != 'Transfer':
            related_site_id = None

        if item and unit and entry_type in ('IN', 'OUT') and source in ('Purchased', 'Self', 'Transfer') and quantity > 0:
            conn = get_conn()
            c = conn.cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M')
            c.execute('''INSERT INTO materials
                (site_id, item, quantity, unit, entry_type, source, related_site_id, vendor_id, entry_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (site_id, item, quantity, unit, entry_type, source, related_site_id, vendor_id, now))

            if source == 'Transfer' and related_site_id:
                mirror_type = 'OUT' if entry_type == 'IN' else 'IN'
                c.execute('''INSERT INTO materials
                    (site_id, item, quantity, unit, entry_type, source, related_site_id, vendor_id, entry_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (related_site_id, item, quantity, unit, mirror_type, 'Transfer', site_id, None, now))
            conn.commit()
            conn.close()
    except (ValueError, KeyError):
        pass
    return redirect(url_for('owner_site_detail', site_id=site_id))


# ---------------- SITE VIEWS ----------------
DASHBOARD_TEMPLATE = STYLE + '''
<div class="container">
<div class="page-head"><div><h2>{{site_name}} Dashboard</h2><p class="muted">{{location}} · Site {{site_status}} · {{site_start_date or 'Start date not set'}} → {{site_end_date or 'Ongoing'}}</p></div>
<span class="{{ 'status-badge live' if site_status=='Live' else 'status-badge closed' }}">{{site_status}}</span></div>
<div class="cards"><div class="stat-card"><div class="label">Workers</div><div class="value">{{workers}}</div></div><div class="stat-card"><div class="label">Engineers</div><div class="value">{{engineers}}</div></div><div class="stat-card"><div class="label">Masons</div><div class="value">{{mason}}</div></div><div class="stat-card"><div class="label">Material Entries</div><div class="value">{{material_count}}</div></div></div>
<section class="panel"><div class="panel-title">Site Snapshot</div><div class="mini-stats"><div><strong>{{workers+engineers+mason}}</strong><span>Total Workforce</span></div><div><strong>{{material_in}}</strong><span>Material In</span></div><div><strong>{{material_out}}</strong><span>Material Out</span></div></div></section>
</div>
'''


STAFF_TEMPLATE = STYLE + '''
<div class="container">
    <h2>Workforce — {{ site_name }}</h2>
    <button type="button" class="toggle-btn" onclick="toggleForm('staffForm')">➕ Add Workforce</button>
    <form class="card collapsible-form" id="staffForm" action="/staff" method="post">
        <label class="field-label">Category</label>
        <select name="category" required>
            <option value="Worker">Worker</option>
            <option value="Engineer">Engineer</option>
            <option value="Mason">Mason</option>
        </select>
        <label class="field-label">Count</label>
        <input type="number" min="1" name="count" placeholder="Number of people" required>
        <label class="field-label">Engagement Type</label>
        <select name="hire_type" required>
            <option value="Hired">Hired (Contracted)</option>
            <option value="Self">Self (Company Staff)</option>
        </select>
        <button type="submit">Save Workforce Entry</button>
    </form>
    <table>
        <tr><th>Date Added</th><th>Category</th><th>Count</th><th>Engagement</th></tr>
        {% for s in staff %}
        <tr>
            <td>{{s[4]}}</td><td>{{s[1]}}</td><td>{{s[2]}}</td><td>{{s[3]}}</td>
        </tr>
        {% else %}
        <tr><td colspan="4" style="color:var(--ink-soft);">No workforce entries recorded yet.</td></tr>
        {% endfor %}
<script>
    function toggleForm(formId) {
        var f = document.getElementById(formId);
        f.style.display = (f.style.display === "block") ? "none" : "block";
    }
</script>
'''

MATERIALS_TEMPLATE = STYLE + '''
<div class="container">
<div class="page-head"><div><h2>Materials — {{site_name}}</h2><p class="muted">Purchases, company stock and site-to-site transfers.</p></div></div>
<section class="panel"><div class="panel-title">Material Entry</div>
<button type="button" class="toggle-btn" onclick="toggleForm('materialForm')">＋ Add Material</button>
<form class="card collapsible-form" id="materialForm" action="/materials" method="post"><div class="form-grid">
<div><label class="field-label">Material</label><input type="text" name="item" required></div>
<div><label class="field-label">Quantity</label><input type="number" step="0.01" min="0.01" name="quantity" required></div>
<div><label class="field-label">Unit</label><input type="text" name="unit" required></div>
<div><label class="field-label">Direction</label><select name="entry_type"><option value="IN">Incoming</option><option value="OUT">Outgoing</option></select></div>
<div><label class="field-label">Source</label><select name="source" id="source" onchange="toggleMaterialFields()"><option value="Purchased">Purchased Externally</option><option value="Self">Company Stock</option><option value="Transfer">Transfer To/From Another Site</option></select></div>
<div id="vendor_wrap"><label class="field-label">Vendor</label><input type="text" name="vendor_name" placeholder="Enter vendor name"><input type="hidden" name="vendor_id" value=""></div>
<div id="transfer_wrap" style="display:none;"><label class="field-label">Other Site</label><select name="related_site_id"><option value="">Select Site</option>{% for s in all_sites %}{% if s[0] != site_id %}<option value="{{s[0]}}">{{s[1]}}</option>{% endif %}{% endfor %}</select></div>
</div><button type="submit">Save Material</button></form></section>
<section class="panel"><div class="panel-title">Material History</div>
<table><tr><th>Date</th><th>Item</th><th>Qty</th><th>Direction</th><th>Source</th><th>Vendor</th><th>Site / Transfer</th></tr>
{% for m in materials %}<tr><td>{{m[1]}}</td><td>{{m[2]}}</td><td>{{m[3]}} {{m[4]}}</td><td class="{{ 'in-tag' if m[5]=='IN' else 'out-tag' }}">{{'Incoming' if m[5]=='IN' else 'Outgoing'}}</td><td>{{m[6]}}</td><td>{{m[8] or '—'}}</td><td>{% if m[6]=='Transfer' %}{{m[7] or '—'}}{% else %}—{% endif %}</td></tr>
{% else %}<tr><td colspan="7" class="empty">No material entries.</td></tr>{% endfor %}</table>
<script>
function toggleForm(id){var f=document.getElementById(id);f.style.display=f.style.display==='block'?'none':'block';}
function toggleMaterialFields(){var transfer=document.getElementById('source').value==='Transfer';document.getElementById('transfer_wrap').style.display=transfer?'block':'none';document.getElementById('vendor_wrap').style.display=transfer?'none':'block';}
</script>
'''


CHANGE_PASSWORD_TEMPLATE = STYLE + '''
<div class="container">
    <h2>Change Password — {{ site_name }}</h2>
    <form class="card" method="post">
        <label class="field-label">Current Password</label>
        <input type="password" name="current_password" placeholder="Enter current password" required>
        <label class="field-label">New Password</label>
        <input type="password" name="new_password" placeholder="Enter new password" required>
        <label class="field-label">Confirm New Password</label>
        <input type="password" name="confirm_password" placeholder="Re-enter new password" required>
        <button type="submit">Update Password</button>
    </form>
    {% if error %}<p class="error">{{ error }}</p>{% endif %}
    {% if success %}<p class="success-msg">{{ success }}</p>{% endif %}
</div>
'''


WORK_TEMPLATE = STYLE + '''
<div class="container">
<div class="page-head"><div><h2>Work — {{site_name}}</h2><p class="muted">Workforce, employees, attendance and material issue in one place.</p></div></div>
<div class="cards">
<div class="stat-card"><div class="label">Workforce Entries</div><div class="value">{{staff|length}}</div></div>
<div class="stat-card"><div class="label">Employees</div><div class="value">{{workers|length}}</div></div>
<div class="stat-card"><div class="label">Pending Time-Out</div><div class="value">{{pending_attendance|length}}</div></div>
<div class="stat-card"><div class="label">Material Issues</div><div class="value">{{issues|length}}</div></div>
</div>



<section class="panel"><div class="panel-title">Employee Directory</div>
<button type="button" class="toggle-btn" onclick="toggleForm('workerForm')">＋ Add Employee</button>
<form class="card collapsible-form" id="workerForm" action="/workers" method="post"><div class="form-grid">
<div><label class="field-label">Name</label><input type="text" name="name" required></div><div><label class="field-label">Contact</label><input type="text" name="phone"></div>
<div><label class="field-label">Role</label><select name="role"><option>Mistri (Mason)</option><option>Helper</option><option>Supervisor</option><option>Electrician</option><option>Plumber</option><option>JCB Driver</option></select></div>
<div><label class="field-label">Worker Type</label><select name="worker_type"><option>Company Staff</option><option>Daily Wager</option><option>Sub-Contractor</option></select></div>
<div><label class="field-label">Rate Type</label><select name="rate_type"><option>Daily</option><option>Monthly</option><option>PerSqFt</option></select></div>
<div><label class="field-label">Rate Amount</label><input type="number" step="0.01" min="0" name="rate_amount" required></div>
</div><button type="submit">Save Employee</button></form>
<table><tr><th>Date</th><th>Name</th><th>Phone</th><th>Role</th><th>Type</th><th>Rate</th></tr>{% for w in workers %}<tr><td>{{w[7]}}</td><td>{{w[1]}}</td><td>{{w[2] or '—'}}</td><td>{{w[3]}}</td><td>{{w[4]}}</td><td>{{w[6]}} ({{w[5]}})</td></tr>{% else %}<tr><td colspan="6" class="empty">No employees added.</td></tr>{% endfor %}</table>
</section>

<section class="panel"><div class="panel-title">Attendance</div>
<div class="form-grid">
<form class="card" action="/workers/attendance/in" method="post"><h3>Time In</h3><label class="field-label">Employee</label><select name="worker_id">{% for w in workers %}<option value="{{w[0]}}">{{w[1]}}</option>{% endfor %}</select><label class="field-label">Date</label><input type="date" name="att_date" required><label class="field-label">Time In</label><input type="time" name="time_in" required><button type="submit">Mark In</button></form>
<form class="card" action="/workers/attendance/out" method="post"><h3>Time Out</h3><label class="field-label">Pending Entry</label><select name="attendance_id">{% for p in pending_attendance %}<option value="{{p[0]}}">{{p[5]}} — {{p[1]}} — In {{p[3]}}</option>{% else %}<option value="">No pending entry</option>{% endfor %}</select><label class="field-label">Time Out</label><input type="time" name="time_out" required><button type="submit">Mark Out</button></form>
<form class="card" action="/workers/attendance/absent" method="post"><h3>Absent</h3><label class="field-label">Employee</label><select name="worker_id">{% for w in workers %}<option value="{{w[0]}}">{{w[1]}}</option>{% endfor %}</select><label class="field-label">Date</label><input type="date" name="att_date" required><button type="submit">Mark Absent</button></form>
</div>
<table><tr><th>Date</th><th>Employee</th><th>Status</th><th>In</th><th>Out</th><th>Hours</th><th>OT</th></tr>{% for a in attendance %}<tr><td>{{a[1]}}</td><td>{{a[7]}}</td><td>{{a[2]}}</td><td>{{a[3] or '—'}}</td><td>{{a[4] or '—'}}</td><td>{{a[5]}}</td><td>{{a[6]}}</td></tr>{% else %}<tr><td colspan="7" class="empty">No attendance.</td></tr>{% endfor %}</table>
</div>
</div><button type="submit">Issue Material</button></form>
<table><tr><th>Date</th><th>Employee</th><th>Warehouse</th><th>Material</th><th>Qty</th><th>Purpose</th></tr>{% for i in issues %}<tr><td>{{i[1]}}</td><td>{{i[16]}}</td><td>{{i[17]}}</td><td>{{i[18]}}</td><td>{{i[5]}}</td><td>{{i[12]}}</td></tr>{% else %}<tr><td colspan="6" class="empty">No material issued.</td></tr>{% endfor %}</table>
<script>function toggleForm(id){var f=document.getElementById(id);f.style.display=f.style.display==='block'?'none':'block';}</script>
'''


@app.route('/dashboard')
def dashboard():
    if not require_site():
        return redirect(url_for('login'))
    site_id=session['site_id']
    conn=get_conn(); c=conn.cursor()
    c.execute("SELECT name,location,created_date,site_start_date,site_end_date FROM sites WHERE id=?",(site_id,))
    row=c.fetchone()
    if not row:
        conn.close(); session.clear(); return redirect(url_for('login'))
    site_name,location,created_date,site_start_date,site_end_date=row
    c.execute("SELECT category,COALESCE(SUM(count),0) FROM staff WHERE site_id=? GROUP BY category",(site_id,))
    counts={r[0]:r[1] for r in c.fetchall()}
    c.execute("SELECT COUNT(*) FROM materials WHERE site_id=? AND entry_type='IN'",(site_id,)); material_in=c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM materials WHERE site_id=? AND entry_type='OUT'",(site_id,)); material_out=c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM materials WHERE site_id=?",(site_id,)); material_count=c.fetchone()[0] or 0
    conn.close()
    return render_template_string(nav('dashboard',site_name=site_name)+DASHBOARD_TEMPLATE,
        site_name=site_name,location=location,site_start_date=site_start_date or created_date,site_end_date=site_end_date,
        site_status=get_site_status(site_end_date),workers=counts.get('Worker',0),engineers=counts.get('Engineer',0),
        mason=counts.get('Mason',0),material_count=material_count,material_in=material_in,material_out=material_out)


@app.route('/work')
def work():
    if not require_site():
        return redirect(url_for('login'))
    site_id=session['site_id']
    conn=get_conn(); c=conn.cursor()
    c.execute("SELECT id,category,count,hire_type,created_date FROM staff WHERE site_id=? ORDER BY id DESC",(site_id,)); staff_rows=c.fetchall()
    c.execute("SELECT id,name,phone,role,worker_type,rate_type,rate_amount,created_date FROM workers WHERE site_id=? ORDER BY name",(site_id,)); worker_rows=c.fetchall()
    c.execute('''SELECT wa.id,wa.att_date,wa.status,wa.time_in,wa.time_out,wa.hours,wa.overtime_hours,w.name
                 FROM worker_attendance wa JOIN workers w ON w.id=wa.worker_id
                 WHERE w.site_id=? ORDER BY wa.att_date DESC,wa.id DESC''',(site_id,)); attendance_rows=c.fetchall()
    c.execute('''SELECT wa.id,wa.att_date,wa.status,wa.time_in,wa.time_out,w.name
                 FROM worker_attendance wa JOIN workers w ON w.id=wa.worker_id
                 WHERE w.site_id=? AND wa.time_out IS NULL AND wa.status='Present'
                 ORDER BY wa.att_date DESC,wa.id DESC''',(site_id,)); pending=c.fetchall()
    c.execute("SELECT id,name,location,keeper_name,keeper_phone FROM warehouses ORDER BY name"); warehouses=c.fetchall()
    c.execute("SELECT id,name,category,uom,min_stock FROM material_master ORDER BY name"); materials=c.fetchall()
    c.execute('''SELECT sl.*,w.name,wh.name,mm.name FROM stock_ledger sl JOIN workers w ON w.id=sl.worker_id
                 JOIN warehouses wh ON wh.id=sl.warehouse_id JOIN material_master mm ON mm.id=sl.material_id
                 WHERE sl.txn_type='ISSUE_WORKER' AND w.site_id=? ORDER BY sl.txn_date DESC,sl.id DESC''',(site_id,)); issues=c.fetchall()
    conn.close()
    return render_template_string(nav('work',site_name=session['site_name'])+WORK_TEMPLATE,
        site_name=session['site_name'],staff=staff_rows,workers=worker_rows,attendance=attendance_rows,
        pending_attendance=pending,warehouses=warehouses,materials=materials,issues=issues,
        issue_error=request.args.get('issue_error'))
@app.route('/staff', methods=['GET', 'POST'])
def staff():
    if not require_site():
        return redirect(url_for('login'))
    if request.method == 'GET':
        return redirect(url_for('work'))
    site_id = session['site_id']
    conn = get_conn()
    c = conn.cursor()
    if request.method == 'POST':
        try:
            category = request.form['category']
            count = int(request.form['count'])
            hire_type = request.form['hire_type']
            if category in ('Worker', 'Engineer', 'Mason') and hire_type in ('Hired', 'Self') and count > 0:
                c.execute("INSERT INTO staff (site_id, category, count, hire_type, created_date) VALUES (?, ?, ?, ?, ?)",
                          (site_id, category, count, hire_type, datetime.now().strftime('%Y-%m-%d')))
                conn.commit()
        except (ValueError, KeyError):
            pass
    c.execute("SELECT id, category, count, hire_type, created_date FROM staff WHERE site_id=?", (site_id,))
    staff_rows = c.fetchall()
    conn.close()
    return redirect(url_for('work'))


@app.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if not require_site():
        return redirect(url_for('login'))

    error = None
    success = None
    if request.method == 'POST':
        current = request.form.get('current_password', '').strip()
        new = request.form.get('new_password', '').strip()
        confirm = request.form.get('confirm_password', '').strip()

        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT password FROM sites WHERE id=?", (session['site_id'],))
        row = c.fetchone()

        if not row or row[0] != current:
            error = "Current password is incorrect."
        elif not new:
            error = "New password cannot be empty."
        elif new != confirm:
            error = "New password and confirmation do not match."
        else:
            c.execute("UPDATE sites SET password=? WHERE id=?", (new, session['site_id']))
            conn.commit()
            success = "Password updated successfully."
        conn.close()

    return render_template_string(
        nav('change_password', site_name=session['site_name']) + CHANGE_PASSWORD_TEMPLATE,
        site_name=session['site_name'], error=error, success=success
    )


@app.route('/materials', methods=['GET', 'POST'])
def materials():
    if not require_site():
        return redirect(url_for('login'))
    site_id=session['site_id']
    conn=get_conn(); c=conn.cursor()
    if request.method=='POST':
        try:
            item=request.form['item'].strip(); quantity=float(request.form['quantity']); unit=request.form['unit'].strip()
            entry_type=request.form['entry_type']; source=request.form['source']
            related_site_id=request.form.get('related_site_id') or None
            vendor_id=request.form.get('vendor_id') or None
            vendor_name=request.form.get('vendor_name','').strip()
            if related_site_id: related_site_id=int(related_site_id)
            if vendor_name and source=='Purchased':
                c.execute("SELECT id FROM vendors WHERE name=?",(vendor_name,))
                vr=c.fetchone()
                if vr:
                    vendor_id=vr[0]
                else:
                    c.execute("INSERT INTO vendors (name,created_date) VALUES (?,?)",(vendor_name,datetime.now().strftime('%Y-%m-%d')))
                    c.execute("SELECT id FROM vendors WHERE name=?",(vendor_name,))
                    vr=c.fetchone()
                    vendor_id=vr[0] if vr else None
            elif vendor_id:
                vendor_id=int(vendor_id)
            if source!='Transfer': related_site_id=None
            if source!='Purchased': vendor_id=None
            if item and unit and entry_type in ('IN','OUT') and source in ('Purchased','Self','Transfer') and quantity>0:
                now=datetime.now().strftime('%Y-%m-%d %H:%M')
                c.execute('''INSERT INTO materials
                    (site_id,item,quantity,unit,entry_type,source,related_site_id,vendor_id,entry_date)
                    VALUES (?,?,?,?,?,?,?,?,?)''',
                    (site_id,item,quantity,unit,entry_type,source,related_site_id,vendor_id,now))
                if source=='Transfer' and related_site_id:
                    mirror_type='OUT' if entry_type=='IN' else 'IN'
                    c.execute('''INSERT INTO materials
                        (site_id,item,quantity,unit,entry_type,source,related_site_id,vendor_id,entry_date)
                        VALUES (?,?,?,?,?,?,?,?,?)''',
                        (related_site_id,item,quantity,unit,mirror_type,'Transfer',site_id,None,now))
                conn.commit()
        except (ValueError,KeyError):
            pass
    c.execute('''SELECT m.id,m.entry_date,m.item,m.quantity,m.unit,m.entry_type,m.source,
                 (SELECT name FROM sites WHERE id=m.related_site_id),
                 (SELECT name FROM vendors WHERE id=m.vendor_id)
                 FROM materials m WHERE m.site_id=? ORDER BY m.entry_date DESC,m.id DESC''',(site_id,))
    material_rows=c.fetchall()
    c.execute("SELECT id,name FROM sites ORDER BY name"); all_sites=c.fetchall()
    c.execute("SELECT id,name FROM vendors ORDER BY name"); vendors=c.fetchall()
    conn.close()
    return render_template_string(nav('materials',site_name=session['site_name'])+MATERIALS_TEMPLATE,
        site_name=session['site_name'],materials=material_rows,all_sites=all_sites,vendors=vendors,site_id=site_id)


import webbrowser
import time
import io
from flask import Response
from threading import Timer
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

def open_browser():
    webbrowser.open_new('http://127.0.0.1:8080/')


# =====================================================================
# NEW MODULES: Material Master, Vendors, Warehouses, Stock Ledger,
# Reports, Workers & Attendance
# =====================================================================

MATERIAL_MASTER_TEMPLATE = STYLE + '''
<div class="container">
    <h2>Material Master</h2>
    <button type="button" class="toggle-btn" onclick="toggleForm('matForm')">➕ Add Material</button>
    <form class="card collapsible-form" id="matForm" method="post">
        <label class="field-label">Material Code</label>
        <input type="text" name="code" placeholder="e.g. MAT-001" required>
        <label class="field-label">Material Name</label>
        <input type="text" name="name" placeholder="e.g. Cement, Rebar, Sand, Bricks" required>
        <label class="field-label">Category</label>
        <select name="category" required>
            <option value="Civil">Civil</option>
            <option value="Electrical">Electrical</option>
            <option value="Plumbing">Plumbing</option>
            <option value="Finishing">Finishing</option>
        </select>
        <label class="field-label">Unit of Measurement</label>
        <input type="text" name="uom" placeholder="e.g. Bags, Tons, Cu.Ft, Sq.Ft, Nos" required>
        <label class="field-label">Minimum Stock Level (reorder alert)</label>
        <input type="number" step="0.01" min="0" name="min_stock" placeholder="e.g. 50" required>
        <button type="submit">Save Material</button>
    </form>
    <table>
        <tr><th>Date Added</th><th>Code</th><th>Name</th><th>Category</th><th>UOM</th><th>Min Stock</th></tr>
        {% for m in materials %}
        <tr>
            <td>{{m[6]}}</td><td>{{m[1]}}</td><td>{{m[2]}}</td><td>{{m[3]}}</td><td>{{m[4]}}</td><td>{{m[5]}}</td>
        </tr>
        {% else %}
        <tr><td colspan="6" style="color:var(--ink-soft);">No materials in catalogue yet.</td></tr>
        {% endfor %}
<script>
    function toggleForm(formId) {
        var f = document.getElementById(formId);
        f.style.display = (f.style.display === "block") ? "none" : "block";
    }
</script>
'''

VENDORS_TEMPLATE = STYLE + '''
<div class="container">
    <h2>Vendor / Supplier Master</h2>
    <button type="button" class="toggle-btn" onclick="toggleForm('vendForm')">➕ Add Vendor</button>
    <form class="card collapsible-form" id="vendForm" method="post">
        <label class="field-label">Vendor Name</label>
        <input type="text" name="name" placeholder="Supplier / dealer name" required>
        <label class="field-label">Phone</label>
        <input type="text" name="phone" placeholder="Contact number">
        <label class="field-label">Email</label>
        <input type="text" name="email" placeholder="Email address">
        <label class="field-label">GST Number</label>
        <input type="text" name="gst_number" placeholder="For billing">
        <label class="field-label">Pending Payment / Balance</label>
        <input type="number" step="0.01" name="pending_payment" placeholder="0" value="0">
        <button type="submit">Save Vendor</button>
    </form>
    <table>
        <tr><th>Date Added</th><th>Name</th><th>Phone</th><th>Email</th><th>GST No.</th><th>Pending Payment</th></tr>
        {% for v in vendors %}
        <tr>
            <td>{{v[6]}}</td><td>{{v[1]}}</td><td>{{v[2] or '—'}}</td><td>{{v[3] or '—'}}</td><td>{{v[4] or '—'}}</td><td>₹{{v[5]}}</td>
        </tr>
        {% else %}
        <tr><td colspan="6" style="color:var(--ink-soft);">No vendors added yet.</td></tr>
        {% endfor %}
<script>
    function toggleForm(formId) {
        var f = document.getElementById(formId);
        f.style.display = (f.style.display === "block") ? "none" : "block";
    }
</script>
'''

WAREHOUSES_TEMPLATE = STYLE + '''
<div class="container">
    <h2>Warehouse / Godown Master</h2>
    <button type="button" class="toggle-btn" onclick="toggleForm('whForm')">➕ Add Warehouse</button>
    <form class="card collapsible-form" id="whForm" method="post">
        <label class="field-label">Warehouse Name</label>
        <input type="text" name="name" placeholder="e.g. WH-01 Central Store" required>
        <label class="field-label">Location / Address</label>
        <input type="text" name="location" placeholder="Full address">
        <label class="field-label">Store Keeper Name</label>
        <input type="text" name="keeper_name" placeholder="Manager / storekeeper name">
        <label class="field-label">Store Keeper Phone</label>
        <input type="text" name="keeper_phone" placeholder="Contact number">
        <button type="submit">Save Warehouse</button>
    </form>
    <table>
        <tr><th>Date Added</th><th>Name</th><th>Location</th><th>Keeper</th><th>Phone</th></tr>
        {% for w in warehouses %}
        <tr>
            <td>{{w[5]}}</td><td>{{w[1]}}</td><td>{{w[2] or '—'}}</td><td>{{w[3] or '—'}}</td><td>{{w[4] or '—'}}</td>
        </tr>
        {% else %}
        <tr><td colspan="5" style="color:var(--ink-soft);">No warehouses added yet.</td></tr>
        {% endfor %}
<script>
    function toggleForm(formId) {
        var f = document.getElementById(formId);
        f.style.display = (f.style.display === "block") ? "none" : "block";
    }
</script>
'''

STOCK_TEMPLATE = STYLE + '''
<div class="container">
    <h2>Stock &amp; Transfers</h2>

    <h3>Total Stock (All Warehouses Combined)</h3>
    <table>
        <tr><th>Material</th><th>Total Available</th><th>Status</th></tr>
        {% for t in total_stock %}
        <tr {% if t.low %}style="background:#fdecea;"{% endif %}>
            <td>{{t.material}} ({{t.uom}})</td><td>{{t.qty}}</td>
            <td>{% if t.low %}<span class="out-tag">⚠ Low Stock</span>{% else %}<span class="in-tag">OK</span>{% endif %}</td>
        </tr>
        {% else %}
        <tr><td colspan="3" style="color:var(--ink-soft);">No stock movements yet.</td></tr>
        {% endfor %}
    </table>

    <h3>Stock by Warehouse</h3>
    <table>
        <tr><th>Warehouse</th><th>Material</th><th>Available Qty</th><th>Status</th></tr>
        {% for s in live_stock %}
        <tr {% if s.low %}style="background:#fdecea;"{% endif %}>
            <td>{{s.warehouse}}</td><td>{{s.material}} ({{s.uom}})</td><td>{{s.qty}}</td>
            <td>{% if s.low %}<span class="out-tag">⚠ Low Stock</span>{% else %}<span class="in-tag">OK</span>{% endif %}</td>
        </tr>
        {% else %}
        <tr><td colspan="4" style="color:var(--ink-soft);">No stock movements yet.</td></tr>
        {% endfor %}
    </table>

    <h3>New Stock Entry</h3>
    <button type="button" class="toggle-btn" onclick="toggleForm('stockForm')">➕ Add Entry</button>
    {% if stock_error %}<p class="error">{{ stock_error }}</p>{% endif %}
    <form class="card collapsible-form" id="stockForm" method="post">
        <label class="field-label">Entry Type</label>
        <select name="txn_type" id="txn_type" onchange="toggleFields()" required>
            <option value="INWARD">Material Inward (Purchase from Vendor)</option>
            <option value="TRANSFER">Send to Site (Warehouse → Site)</option>
        </select>
        <label class="field-label">Date</label>
        <input type="date" name="txn_date" required>
        <label class="field-label">Warehouse</label>
        <select name="warehouse_id" required>
            {% for w in warehouses %}<option value="{{w[0]}}">{{w[1]}}</option>{% endfor %}
        </select>
        <label class="field-label">Material</label>
        <select name="material_id" required>
            {% for m in materials %}<option value="{{m[0]}}">{{m[1]}} ({{m[3]}})</option>{% endfor %}
        </select>
        <label class="field-label">Quantity</label>
        <input type="number" step="0.01" min="0.01" name="quantity" required>

        <div id="inward_fields">
            <label class="field-label">Vendor</label>
            <select name="vendor_id">
                <option value="">— none —</option>
                {% for v in vendors %}<option value="{{v[0]}}">{{v[1]}}</option>{% endfor %}
            </select>
            <label class="field-label">Invoice / Challan Number</label>
            <input type="text" name="invoice_number" placeholder="Bill number">
            <label class="field-label">Rate (per unit)</label>

        <div id="site_fields" style="display:none;">
            <label class="field-label">Destination Site</label>
            <select name="site_id">
                <option value="">— none —</option>
                {% for s in all_sites %}<option value="{{s[0]}}">{{s[1]}}</option>{% endfor %}
            </select>
            <label class="field-label">Purpose / Work Type</label>
            <input type="text" name="purpose" placeholder="e.g. Slab casting, Plaster, Masonry">
            <label class="field-label">Transporter / Driver Name</label>
            <input type="text" name="transporter" placeholder="Driver name">
            <label class="field-label">Vehicle Number</label>
            <input type="text" name="vehicle_number" placeholder="Truck number">
            <label class="field-label">Transfer Status</label>
            <select name="status">
                <option value="Pending">Pending</option>
                <option value="In-Transit">In-Transit</option>
                <option value="Received">Received</option>

        <button type="submit">Save Entry</button>
    </form>

    <h3>Recent Stock Movements</h3>
    <table>
        <tr><th>Date</th><th>Type</th><th>Warehouse</th><th>Material</th><th>Qty</th><th>Details</th><th>Document</th></tr>
        {% for l in ledger %}
        <tr>
            <td>{{l[1]}}</td><td>{{ 'Inward' if l[2]=='INWARD' else ('Issued to Worker' if l[2]=='ISSUE_WORKER' else 'Transfer') }}</td>
            <td>{{l[16]}}</td><td>{{l[17]}}</td><td>{{l[5]}}</td>
            <td>
                {% if l[2] == 'INWARD' %}Vendor: {{l[18] or '—'}}, Invoice: {{l[7] or '—'}}, Rate: {{l[8] or '—'}}
                {% elif l[2] == 'TRANSFER' %}Site: {{l[19] or '—'}}, Purpose: {{l[12] or '—'}}, Transporter: {{l[13] or '—'}}, Vehicle: {{l[14] or '—'}}, Status: {{l[15] or '—'}}
                {% elif l[2] == 'ISSUE_WORKER' %}Purpose: {{l[12] or '—'}}
                {% endif %}
            </td>
            <td>
                {% if l[2] == 'INWARD' %}<a href="/owner/stock/po/{{l[0]}}" target="_blank">📄 View PO</a>{% else %}—{% endif %}
        {% else %}
        <tr><td colspan="7" style="color:var(--ink-soft);">No stock entries recorded yet.</td></tr>
        {% endfor %}
<p style="color:var(--ink-soft); font-size:13px; padding: 0 20px;">Data permanent hai — kisi bhi entry ko delete nahi kiya ja sakta. Galat entry ke liye ek chhoti sahi entry alag se add kar dijiye.</p>
<script>
    function toggleForm(formId) {
        var f = document.getElementById(formId);
        f.style.display = (f.style.display === "block") ? "none" : "block";
    }
    function toggleFields() {
        var t = document.getElementById('txn_type').value;
        document.getElementById('inward_fields').style.display = (t === 'INWARD') ? 'block' : 'none';
        document.getElementById('site_fields').style.display = (t === 'TRANSFER') ? 'block' : 'none';
    }
    toggleFields();
</script>
'''

REPORTS_TEMPLATE = STYLE + '''
<div class="container">
    <h2>Daily Reports</h2>
    <form class="card" method="get" action="/owner/reports/download">
        <label class="field-label">Select Date</label>
        <input type="date" name="report_date" value="{{ today }}" required>
        <button type="submit">Download PDF Report</button>
    </form>
    <p style="color:var(--ink-soft); font-size:13px;">Report me us date ke saare stock movements (inward, outward, transfers) shamil honge, PDF format me.</p>
</div>
'''

WORKERS_TEMPLATE = STYLE + '''
<div class="container">
    <h2>Workers &amp; Attendance — {{ site_name }}</h2>

    <h3>Worker Directory</h3>
    <button type="button" class="toggle-btn" onclick="toggleForm('workerForm')">➕ Add Worker</button>
    <form class="card collapsible-form" id="workerForm" action="/workers" method="post">
        <label class="field-label">Worker Name</label>
        <input type="text" name="name" placeholder="Full name" required>
        <label class="field-label">Contact Number</label>
        <input type="text" name="phone" placeholder="Mobile number">
        <label class="field-label">Role / Designation</label>
        <select name="role" required>
            <option value="Mistri (Mason)">Mistri (Mason)</option>
            <option value="Helper">Helper</option>
            <option value="Supervisor">Supervisor</option>
            <option value="Electrician">Electrician</option>
            <option value="Plumber">Plumber</option>
            <option value="JCB Driver">JCB Driver</option>
        </select>
        <label class="field-label">Worker Type</label>
        <select name="worker_type" required>
            <option value="Company Staff">Company Staff (Paid)</option>
            <option value="Daily Wager">Daily Wager (Paid)</option>
            <option value="Sub-Contractor">Sub-Contractor / Self-Employed</option>
        </select>
        <label class="field-label">Rate Type</label>
        <select name="rate_type" required>
            <option value="Daily">Daily Rate</option>
            <option value="Monthly">Monthly Salary</option>
            <option value="PerSqFt">Per Sq.Ft Rate</option>
        </select>
        <label class="field-label">Rate Amount</label>
        <input type="number" step="0.01" min="0" name="rate_amount" required>
        <button type="submit">Save Worker</button>
    </form>

    <table>
        <tr><th>Date Added</th><th>Name</th><th>Phone</th><th>Role</th><th>Type</th><th>Rate</th></tr>
        {% for w in workers %}
        <tr>
            <td>{{w[7]}}</td><td>{{w[1]}}</td><td>{{w[2] or '—'}}</td><td>{{w[3]}}</td><td>{{w[4]}}</td>
            <td>{{w[6]}} ({{w[5]}})</td>
        </tr>
        {% else %}
        <tr><td colspan="6" style="color:var(--ink-soft);">No workers added yet.</td></tr>
        {% endfor %}
    </table>

    <h3>Attendance</h3>

    <button type="button" class="toggle-btn" onclick="toggleForm('attInForm')">➕ Mark Time In (Worker Arrived)</button>
    <form class="card collapsible-form" id="attInForm" action="/workers/attendance/in" method="post">
        <label class="field-label">Worker</label>
        <select name="worker_id" required>
            {% for w in workers %}<option value="{{w[0]}}">{{w[1]}}</option>{% endfor %}
        </select>
        <label class="field-label">Date</label>
        <input type="date" name="att_date" required>
        <label class="field-label">Time In</label>
        <input type="time" name="time_in" required>
        <button type="submit">Mark Time In</button>
    </form>

    <button type="button" class="toggle-btn" onclick="toggleForm('attOutForm')">➕ Mark Time Out (Worker Leaving)</button>
    <form class="card collapsible-form" id="attOutForm" action="/workers/attendance/out" method="post">
        <label class="field-label">Select Pending Entry (Worker — Date — In Time)</label>
        <select name="attendance_id" required>
            {% for p in pending_attendance %}
            <option value="{{p[0]}}">{{p[5]}} — {{p[1]}} — In: {{p[3]}}</option>
            {% else %}
            <option value="">— koi bhi pending entry nahi hai, pehle Time In maaro —</option>
            {% endfor %}
        </select>
        <label class="field-label">Time Out</label>
        <input type="time" name="time_out" required>
        <button type="submit">Mark Time Out</button>
    </form>
    <p style="color:var(--ink-soft); font-size:13px;">8 ghante se zyada kaam automatically Overtime me count hoga.</p>

    <button type="button" class="toggle-btn" onclick="toggleForm('attAbsentForm')">➕ Mark Absent</button>
    <form class="card collapsible-form" id="attAbsentForm" action="/workers/attendance/absent" method="post">
        <label class="field-label">Worker</label>
        <select name="worker_id" required>
            {% for w in workers %}<option value="{{w[0]}}">{{w[1]}}</option>{% endfor %}
        </select>
        <label class="field-label">Date</label>
        <input type="date" name="att_date" required>
        <button type="submit">Mark Absent</button>
    </form>

    <table>
        <tr><th>Date</th><th>Worker</th><th>Status</th><th>In</th><th>Out</th><th>Hours</th><th>Overtime</th></tr>
        {% for a in attendance %}
        <tr>
            <td>{{a[1]}}</td><td>{{a[7]}}</td>
            <td class="{{ 'in-tag' if a[2]=='Present' else 'out-tag' }}">{{a[2]}}</td>
            <td>{{a[3] or '—'}}</td><td>{{a[4] or '—'}}</td><td>{{a[5]}}</td>
            <td>{{ a[6] }}{% if a[6] > 0 %} <span class="out-tag">OT</span>{% endif %}</td>
        </tr>
        {% else %}
        <tr><td colspan="7" style="color:var(--ink-soft);">No attendance recorded yet.</td></tr>
        {% endfor %}
    </table>

    <h3>Issue Material to Worker</h3>
    <button type="button" class="toggle-btn" onclick="toggleForm('issueForm')">➕ Issue Material</button>
    {% if issue_error %}<p class="error">{{ issue_error }}</p>{% endif %}
    <form class="card collapsible-form" id="issueForm" action="/workers/issue-material" method="post">
        <label class="field-label">Worker</label>
        <select name="worker_id" required>
            {% for w in workers %}<option value="{{w[0]}}">{{w[1]}}</option>{% endfor %}
        </select>
        <label class="field-label">Warehouse (Issued From)</label>
        <select name="warehouse_id" required>
            {% for wh in warehouses %}<option value="{{wh[0]}}">{{wh[1]}}</option>{% endfor %}
        </select>
        <label class="field-label">Material</label>
        <select name="material_id" required>
            {% for m in materials %}<option value="{{m[0]}}">{{m[1]}} ({{m[3]}})</option>{% endfor %}
        </select>
        <label class="field-label">Quantity Issued</label>
        <input type="number" step="0.01" min="0.01" name="quantity" required>
        <label class="field-label">Work Done / Purpose</label>
        <input type="text" name="purpose" placeholder="e.g. 1st Floor Slab Casting" required>
        <button type="submit">Save Issue Entry</button>
    </form>

    <table>
        <tr><th>Date</th><th>Worker</th><th>Warehouse</th><th>Material</th><th>Qty</th><th>Purpose</th></tr>
        {% for i in issues %}
        <tr>
            <td>{{i[1]}}</td><td>{{i[16]}}</td><td>{{i[17]}}</td><td>{{i[18]}}</td><td>{{i[5]}}</td><td>{{i[12]}}</td>
        </tr>
        {% else %}
        <tr><td colspan="6" style="color:var(--ink-soft);">No material issued to workers yet.</td></tr>
        {% endfor %}
<script>
    function toggleForm(formId) {
        var f = document.getElementById(formId);
        f.style.display = (f.style.display === "block") ? "none" : "block";
    }
</script>
'''


# ---------------- OWNER: MATERIAL MASTER ----------------
@app.route('/owner/materials', methods=['GET', 'POST'])
def material_master():
    if not require_owner():
        return redirect(url_for('login'))
    conn = get_conn()
    c = conn.cursor()
    if request.method == 'POST':
        try:
            code = request.form['code'].strip()
            name = request.form['name'].strip()
            category = request.form['category']
            uom = request.form['uom'].strip()
            min_stock = float(request.form['min_stock'])
            if code and name and uom:
                c.execute("INSERT INTO material_master (code, name, category, uom, min_stock, created_date) VALUES (?, ?, ?, ?, ?, ?)",
                          (code, name, category, uom, min_stock, datetime.now().strftime('%Y-%m-%d')))
                conn.commit()
        except pyodbc.IntegrityError:
            pass
        except (ValueError, KeyError):
            pass
    c.execute("SELECT id, code, name, category, uom, min_stock, created_date FROM material_master ORDER BY name")
    materials = c.fetchall()
    conn.close()
    return render_template_string(nav('material_master', is_owner=True) + MATERIAL_MASTER_TEMPLATE, materials=materials)


# ---------------- OWNER: VENDORS ----------------
@app.route('/owner/vendors', methods=['GET', 'POST'])
def vendors():
    if not require_owner():
        return redirect(url_for('login'))
    conn = get_conn()
    c = conn.cursor()
    if request.method == 'POST':
        try:
            name = request.form['name'].strip()
            phone = request.form.get('phone', '').strip()
            email = request.form.get('email', '').strip()
            gst_number = request.form.get('gst_number', '').strip()
            pending_payment = float(request.form.get('pending_payment') or 0)
            if name:
                c.execute("INSERT INTO vendors (name, phone, email, gst_number, pending_payment, created_date) VALUES (?, ?, ?, ?, ?, ?)",
                          (name, phone, email, gst_number, pending_payment, datetime.now().strftime('%Y-%m-%d')))
                conn.commit()
        except (ValueError, KeyError):
            pass
    c.execute("SELECT id, name, phone, email, gst_number, pending_payment, created_date FROM vendors ORDER BY name")
    vendor_rows = c.fetchall()
    conn.close()
    return render_template_string(nav('vendors', is_owner=True) + VENDORS_TEMPLATE, vendors=vendor_rows)


# ---------------- OWNER: WAREHOUSES ----------------
@app.route('/owner/warehouses', methods=['GET', 'POST'])
def warehouses():
    if not require_owner():
        return redirect(url_for('login'))
    conn = get_conn()
    c = conn.cursor()
    if request.method == 'POST':
        try:
            name = request.form['name'].strip()
            location = request.form.get('location', '').strip()
            keeper_name = request.form.get('keeper_name', '').strip()
            keeper_phone = request.form.get('keeper_phone', '').strip()
            if name:
                c.execute("INSERT INTO warehouses (name, location, keeper_name, keeper_phone, created_date) VALUES (?, ?, ?, ?, ?)",
                          (name, location, keeper_name, keeper_phone, datetime.now().strftime('%Y-%m-%d')))
                conn.commit()
        except (ValueError, KeyError):
            pass
    c.execute("SELECT id, name, location, keeper_name, keeper_phone, created_date FROM warehouses ORDER BY name")
    warehouse_rows = c.fetchall()
    conn.close()
    return render_template_string(nav('warehouses', is_owner=True) + WAREHOUSES_TEMPLATE, warehouses=warehouse_rows)


# ---------------- OWNER: STOCK LEDGER ----------------
def get_stock_qty(c, warehouse_id, material_id):
    """Ek warehouse me ek material ka available stock nikalta hai."""
    c.execute('''
        SELECT SUM(CASE WHEN txn_type='INWARD' THEN quantity ELSE 0 END) -
               SUM(CASE WHEN txn_type IN ('TRANSFER','ISSUE_WORKER') THEN quantity ELSE 0 END)
        FROM stock_ledger WHERE warehouse_id=? AND material_id=?
    ''', (warehouse_id, material_id))
    row = c.fetchone()
    return (row[0] or 0) if row else 0


def compute_live_stock(c):
    c.execute('''
        SELECT wh.id, wh.name, mm.id, mm.name, mm.uom, mm.min_stock,
            SUM(CASE WHEN sl.txn_type='INWARD' THEN sl.quantity ELSE 0 END) -
            SUM(CASE WHEN sl.txn_type IN ('TRANSFER','ISSUE_WORKER') THEN sl.quantity ELSE 0 END) AS qty
        FROM stock_ledger sl
        JOIN warehouses wh ON wh.id = sl.warehouse_id
        JOIN material_master mm ON mm.id = sl.material_id
        GROUP BY wh.id, wh.name, mm.id, mm.name, mm.uom, mm.min_stock
    ''')
    rows = c.fetchall()
    result = []
    for wh_id, wh_name, mat_id, mat_name, uom, min_stock, qty in rows:
        qty = qty or 0
        result.append({
            'warehouse': wh_name, 'material': mat_name, 'uom': uom,
            'qty': qty, 'low': qty < min_stock
        })
    return result


def compute_total_stock(c):
    """Sab warehouses ko milaakar, har material ka total stock (Tally-style summary)."""
    c.execute('''
        SELECT mm.id, mm.name, mm.uom, mm.min_stock,
            SUM(CASE WHEN sl.txn_type='INWARD' THEN sl.quantity ELSE 0 END) -
            SUM(CASE WHEN sl.txn_type IN ('TRANSFER','ISSUE_WORKER') THEN sl.quantity ELSE 0 END) AS qty
        FROM stock_ledger sl
        JOIN material_master mm ON mm.id = sl.material_id
        GROUP BY mm.id, mm.name, mm.uom, mm.min_stock
    ''')
    rows = c.fetchall()
    result = []
    for mat_id, mat_name, uom, min_stock, qty in rows:
        qty = qty or 0
        result.append({'material': mat_name, 'uom': uom, 'qty': qty, 'low': qty < min_stock})
    return result


@app.route('/owner/stock', methods=['GET', 'POST'])
def stock():
    if not require_owner():
        return redirect(url_for('login'))
    conn = get_conn()
    c = conn.cursor()

    stock_error = None
    if request.method == 'POST':
        try:
            txn_type = request.form['txn_type']
            txn_date = request.form['txn_date']
            warehouse_id = int(request.form['warehouse_id'])
            material_id = int(request.form['material_id'])
            quantity = float(request.form['quantity'])
            vendor_id = request.form.get('vendor_id') or None
            invoice_number = request.form.get('invoice_number', '').strip() or None
            rate = request.form.get('rate') or None
            site_id = request.form.get('site_id') or None
            purpose = request.form.get('purpose', '').strip() or None
            transporter = request.form.get('transporter', '').strip() or None
            vehicle_number = request.form.get('vehicle_number', '').strip() or None
            status = request.form.get('status') or None

            if vendor_id:
                vendor_id = int(vendor_id)
            if rate:
                rate = float(rate)
            if site_id:
                site_id = int(site_id)

            if txn_type not in ('INWARD', 'TRANSFER') or quantity <= 0:
                stock_error = "Invalid entry."
            elif txn_type == 'TRANSFER':
                # Jitna material warehouse me available hai, usse zyada bhej nahi sakte
                available = get_stock_qty(c, warehouse_id, material_id)
                if quantity > available:
                    stock_error = f"Sirf {available} unit hi available hai is warehouse me — itna transfer nahi kar sakte."
                else:
                    c.execute('''INSERT INTO stock_ledger
                        (txn_date, txn_type, warehouse_id, material_id, quantity, site_id,
                         purpose, transporter, vehicle_number, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (txn_date, txn_type, warehouse_id, material_id, quantity, site_id,
                         purpose, transporter, vehicle_number, status))
                    conn.commit()
            else:  # INWARD — koi limit nahi, naya stock aa raha hai
                c.execute('''INSERT INTO stock_ledger
                    (txn_date, txn_type, warehouse_id, material_id, quantity, vendor_id, invoice_number, rate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (txn_date, txn_type, warehouse_id, material_id, quantity, vendor_id, invoice_number, rate))
                conn.commit()
        except (ValueError, KeyError):
            stock_error = "Please fill in all required fields correctly."

    c.execute("SELECT id, name, location, keeper_name, keeper_phone FROM warehouses ORDER BY name")
    warehouse_rows = c.fetchall()
    c.execute("SELECT id, name, category, uom, min_stock FROM material_master ORDER BY name")
    material_rows = c.fetchall()
    c.execute("SELECT id, name FROM vendors ORDER BY name")
    vendor_rows = c.fetchall()
    c.execute("SELECT id, name FROM sites ORDER BY name")
    all_sites = c.fetchall()

    live_stock = compute_live_stock(c)
    total_stock = compute_total_stock(c)

    c.execute('''
        SELECT sl.*, wh.name, mm.name, v.name, s.name
        FROM stock_ledger sl
        JOIN warehouses wh ON wh.id = sl.warehouse_id
        JOIN material_master mm ON mm.id = sl.material_id
        LEFT JOIN vendors v ON v.id = sl.vendor_id
        LEFT JOIN sites s ON s.id = sl.site_id
        ORDER BY sl.txn_date DESC, sl.id DESC
    ''')
    ledger = c.fetchall()
    conn.close()

    return render_template_string(
        nav('stock', is_owner=True) + STOCK_TEMPLATE,
        warehouses=warehouse_rows, materials=material_rows, vendors=vendor_rows,
        all_sites=all_sites, live_stock=live_stock, total_stock=total_stock,
        ledger=ledger, stock_error=stock_error
    )


# ---------------- OWNER: REPORTS ----------------
@app.route('/owner/reports')
def reports():
    if not require_owner():
        return redirect(url_for('login'))
    return render_template_string(
        nav('reports', is_owner=True) + REPORTS_TEMPLATE,
        today=datetime.now().strftime('%Y-%m-%d')
    )


@app.route('/owner/reports/download')
def reports_download():
    if not require_owner():
        return redirect(url_for('login'))

    report_date = request.args.get('report_date', datetime.now().strftime('%Y-%m-%d'))
    conn = None
    try:
        conn = get_conn(); c = conn.cursor()

        # Site material movement for the selected date.
        c.execute("""
            SELECT m.entry_date, s.name, m.item, m.quantity, m.unit,
                   m.entry_type, m.source, rs.name, v.name
            FROM materials m
            JOIN sites s ON s.id=m.site_id
            LEFT JOIN sites rs ON rs.id=m.related_site_id
            LEFT JOIN vendors v ON v.id=m.vendor_id
            WHERE LEFT(m.entry_date,10)=?
            ORDER BY m.id
        """, (report_date,))
        material_rows=c.fetchall()

        # Employee/workforce detail: actual employee master records, not just counts.
        c.execute("""
            SELECT s.name, w.name, w.phone, w.role, w.worker_type,
                   w.rate_type, w.rate_amount, w.created_date
            FROM workers w
            JOIN sites s ON s.id=w.site_id
            ORDER BY s.name, w.name
        """)
        worker_rows=c.fetchall()

        # All sites and their dates/status.
        c.execute("""
            SELECT name, location, created_date, site_start_date, site_end_date
            FROM sites ORDER BY name
        """)
        sites=c.fetchall()
        conn.close(); conn=None

        buffer=io.BytesIO()
        doc=SimpleDocTemplate(buffer,pagesize=landscape(A4),
                              topMargin=10*mm,bottomMargin=10*mm,
                              leftMargin=8*mm,rightMargin=8*mm)
        styles=getSampleStyleSheet()
        title=ParagraphStyle('RptTitle',parent=styles['Title'],fontSize=16,leading=19,spaceAfter=4)
        section=ParagraphStyle('RptSection',parent=styles['Heading2'],fontSize=10,leading=12,spaceBefore=7,spaceAfter=4)
        cell=ParagraphStyle('RptCell',parent=styles['Normal'],fontSize=6.3,leading=7.2)
        head=ParagraphStyle('RptHead',parent=cell,textColor=colors.white)
        elements=[Paragraph('Daily Site, Material & Workforce Report',title),
                  Paragraph('Report Date: '+str(report_date),styles['Normal']),Spacer(1,3*mm)]

        def add_table(headers,rows,widths):
            if not rows:
                return
            data=[[Paragraph(str(x),head) for x in headers]]
            for row in rows:
                data.append([Paragraph('—' if x is None or x=='' else str(x),cell) for x in row])
            t=Table(data,repeatRows=1,colWidths=widths,hAlign='LEFT')
            t.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1f2937')),
                ('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.35,colors.grey),
                ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),3),
                ('RIGHTPADDING',(0,0),(-1,-1),3),('TOPPADDING',(0,0),(-1,-1),3),
                ('BOTTOMPADDING',(0,0),(-1,-1),3),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f3f4f6')])]))
            elements.append(t); elements.append(Spacer(1,3*mm))

        elements.append(Paragraph('1. Purchase / Site Material / Transfer Movement',section))
        add_table(['Date','Site','Material','Qty','Unit','Direction','Source','Related Site','Vendor'],
                  [(r[0],r[1],r[2],r[3],r[4],'Incoming' if r[5]=='IN' else 'Outgoing',r[6],r[7],r[8]) for r in material_rows],
                  [27*mm,35*mm,42*mm,16*mm,16*mm,23*mm,28*mm,35*mm,30*mm])

        elements.append(Paragraph('2. Worker / Employee Details',section))
        add_table(['Site','Employee Name','Contact','Role','Worker Type','Rate Type','Rate Amount','Added Date'],
                  worker_rows,
                  [35*mm,42*mm,28*mm,38*mm,35*mm,25*mm,25*mm,25*mm])

        elements.append(Paragraph('3. Site Details',section))
        site_rows=[]
        for name,location,created,start_date,end_date in sites:
            status='Closed' if end_date and str(end_date)<str(report_date) else 'Live'
            site_rows.append((name,location,start_date or created,end_date or '—',status))
        add_table(['Site','Location','Site Start','Site End','Status'],site_rows,
                  [55*mm,70*mm,35*mm,35*mm,25*mm])

        doc.build(elements); buffer.seek(0)
        return Response(buffer.read(),mimetype='application/pdf',headers={
            'Content-Disposition':'attachment; filename=daily_site_material_workforce_'+str(report_date)+'.pdf'})
    except Exception as exc:
        if conn is not None:
            try: conn.close()
            except Exception: pass
        app.logger.exception('Daily report export failed')
        return 'Report export failed. Error: '+str(exc),500


# ---------------- OWNER: PURCHASE ORDER (PO) ----------------
@app.route('/owner/stock/po/<int:entry_id>')
def stock_po(entry_id):
    if not require_owner():
        return redirect(url_for('login'))
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        SELECT sl.id, sl.txn_date, sl.quantity, sl.rate, sl.invoice_number,
               wh.name, wh.location, mm.name, mm.uom, v.name, v.phone, v.email, v.gst_number
        FROM stock_ledger sl
        JOIN warehouses wh ON wh.id = sl.warehouse_id
        JOIN material_master mm ON mm.id = sl.material_id
        LEFT JOIN vendors v ON v.id = sl.vendor_id
        WHERE sl.id = ? AND sl.txn_type = 'INWARD'
    ''', (entry_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return "Purchase Order not found.", 404

    (po_id, txn_date, quantity, rate, invoice_number,
     wh_name, wh_location, mat_name, uom, vendor_name, vendor_phone, vendor_email, vendor_gst) = row

    rate = rate or 0
    total = round(quantity * rate, 2)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("PURCHASE ORDER", styles['Title']))
    elements.append(Paragraph(f"PO No: PO-{po_id:05d}", styles['Normal']))
    elements.append(Paragraph(f"Date: {txn_date}", styles['Normal']))
    elements.append(Spacer(1, 8*mm))

    elements.append(Paragraph("<b>Vendor Details</b>", styles['Heading3']))
    vendor_info = [
        ['Vendor Name', vendor_name or '—'],
        ['Phone', vendor_phone or '—'],
        ['Email', vendor_email or '—'],
        ['GST Number', vendor_gst or '—'],
    ]
    vt = Table(vendor_info, colWidths=[40*mm, 120*mm])
    vt.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(vt)
    elements.append(Spacer(1, 8*mm))

    elements.append(Paragraph("<b>Delivery Location</b>", styles['Heading3']))
    elements.append(Paragraph(f"{wh_name} — {wh_location or ''}", styles['Normal']))
    elements.append(Spacer(1, 8*mm))

    elements.append(Paragraph("<b>Order Details</b>", styles['Heading3']))
    order_data = [
        ['Material', 'Unit', 'Quantity', 'Rate', 'Total'],
        [mat_name, uom, str(quantity), f"{rate}", f"{total}"],
    ]
    ot = Table(order_data, colWidths=[50*mm, 25*mm, 30*mm, 30*mm, 30*mm])
    ot.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(ot)
    elements.append(Spacer(1, 6*mm))
    elements.append(Paragraph(f"Invoice / Challan Number: {invoice_number or '—'}", styles['Normal']))
    elements.append(Spacer(1, 15*mm))
    elements.append(Paragraph("Authorized Signatory: ______________________", styles['Normal']))

    doc.build(elements)
    buffer.seek(0)

    return Response(
        buffer.read(),
        mimetype='application/pdf',
        headers={'Content-Disposition': f'inline; filename=PO-{po_id:05d}.pdf'}
    )


# ---------------- SITE: WORKERS & ATTENDANCE ----------------
@app.route('/workers', methods=['GET', 'POST'])
def workers():
    if not require_site():
        return redirect(url_for('login'))
    if request.method == 'GET':
        return redirect(url_for('work'))
    site_id = session['site_id']
    conn = get_conn()
    c = conn.cursor()

    if request.method == 'POST':
        try:
            name = request.form['name'].strip()
            phone = request.form.get('phone', '').strip()
            role = request.form['role']
            worker_type = request.form['worker_type']
            rate_type = request.form['rate_type']
            rate_amount = float(request.form['rate_amount'])
            if name and role:
                c.execute('''INSERT INTO workers
                    (site_id, name, phone, role, worker_type, rate_type, rate_amount, created_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (site_id, name, phone, role, worker_type, rate_type, rate_amount, datetime.now().strftime('%Y-%m-%d')))
                conn.commit()
        except (ValueError, KeyError):
            pass

    c.execute("SELECT id, name, phone, role, worker_type, rate_type, rate_amount, created_date FROM workers WHERE site_id=? ORDER BY name", (site_id,))
    worker_rows = c.fetchall()

    c.execute('''
        SELECT wa.id, wa.att_date, wa.status, wa.time_in, wa.time_out, wa.hours, wa.overtime_hours, w.name
        FROM worker_attendance wa
        JOIN workers w ON w.id = wa.worker_id
        WHERE w.site_id = ?
        ORDER BY wa.att_date DESC, wa.id DESC
    ''', (site_id,))
    attendance_rows = c.fetchall()

    # Attendance jinka Time In ho chuka hai lekin Time Out abhi baaki hai
    c.execute('''
        SELECT wa.id, wa.att_date, wa.status, wa.time_in, wa.time_out, w.name
        FROM worker_attendance wa
        JOIN workers w ON w.id = wa.worker_id
        WHERE w.site_id = ? AND wa.time_out IS NULL AND wa.status = 'Present'
        ORDER BY wa.att_date DESC, wa.id DESC
    ''', (site_id,))
    pending_attendance = c.fetchall()

    c.execute("SELECT id, name, location, keeper_name, keeper_phone FROM warehouses ORDER BY name")
    warehouse_rows = c.fetchall()
    c.execute("SELECT id, name, category, uom, min_stock FROM material_master ORDER BY name")
    material_rows = c.fetchall()

    c.execute('''
        SELECT sl.*, w.name, wh.name, mm.name
        FROM stock_ledger sl
        JOIN workers w ON w.id = sl.worker_id
        JOIN warehouses wh ON wh.id = sl.warehouse_id
        JOIN material_master mm ON mm.id = sl.material_id
        WHERE sl.txn_type = 'ISSUE_WORKER' AND w.site_id = ?
        ORDER BY sl.txn_date DESC, sl.id DESC
    ''', (site_id,))
    issue_rows = c.fetchall()

    conn.close()
    return redirect(url_for('work'))


@app.route('/workers/attendance/in', methods=['POST'])
def worker_attendance_in():
    if not require_site():
        return redirect(url_for('login'))
    conn = get_conn()
    c = conn.cursor()
    try:
        worker_id = int(request.form['worker_id'])
        att_date = request.form['att_date']
        time_in = request.form['time_in'].strip()
        # confirm worker belongs to this site before inserting
        c.execute("SELECT id FROM workers WHERE id=? AND site_id=?", (worker_id, session['site_id']))
        if c.fetchone() and time_in:
            c.execute('''INSERT INTO worker_attendance (worker_id, att_date, status, time_in, time_out, hours, overtime_hours)
                VALUES (?, ?, 'Present', ?, NULL, 0, 0)''', (worker_id, att_date, time_in))
            conn.commit()
    except (ValueError, KeyError):
        pass
    conn.close()
    return redirect(url_for('work'))


@app.route('/workers/attendance/out', methods=['POST'])
def worker_attendance_out():
    if not require_site():
        return redirect(url_for('login'))
    conn = get_conn()
    c = conn.cursor()
    try:
        attendance_id = int(request.form['attendance_id'])
        time_out = request.form['time_out'].strip()

        # confirm this attendance record belongs to a worker of this site, and is still pending
        c.execute('''
            SELECT wa.time_in FROM worker_attendance wa
            JOIN workers w ON w.id = wa.worker_id
            WHERE wa.id = ? AND w.site_id = ? AND wa.time_out IS NULL
        ''', (attendance_id, session['site_id']))
        row = c.fetchone()
        if row and time_out:
            time_in = row[0]
            hours = 0.0
            overtime_hours = 0.0
            if time_in:
                t_in = datetime.strptime(time_in, '%H:%M')
                t_out = datetime.strptime(time_out, '%H:%M')
                worked = (t_out - t_in).total_seconds() / 3600
                if worked < 0:
                    worked += 24  # overnight shift ke liye
                # 8 ghante se upar jo bhi hai, wo overtime me chala jayega
                if worked > 8:
                    hours = 8.0
                    overtime_hours = round(worked - 8, 2)
                else:
                    hours = round(worked, 2)
                    overtime_hours = 0.0
            c.execute("UPDATE worker_attendance SET time_out=?, hours=?, overtime_hours=? WHERE id=?",
                      (time_out, hours, overtime_hours, attendance_id))
            conn.commit()
    except (ValueError, KeyError):
        pass
    conn.close()
    return redirect(url_for('work'))


@app.route('/workers/attendance/absent', methods=['POST'])
def worker_attendance_absent():
    if not require_site():
        return redirect(url_for('login'))
    conn = get_conn()
    c = conn.cursor()
    try:
        worker_id = int(request.form['worker_id'])
        att_date = request.form['att_date']
        c.execute("SELECT id FROM workers WHERE id=? AND site_id=?", (worker_id, session['site_id']))
        if c.fetchone():
            c.execute('''INSERT INTO worker_attendance (worker_id, att_date, status, time_in, time_out, hours, overtime_hours)
                VALUES (?, ?, 'Absent', NULL, NULL, 0, 0)''', (worker_id, att_date))
            conn.commit()
    except (ValueError, KeyError):
        pass
    conn.close()
    return redirect(url_for('work'))


@app.route('/workers/issue-material', methods=['POST'])
def issue_material_to_worker():
    if not require_site():
        return redirect(url_for('login'))
    conn = get_conn()
    c = conn.cursor()
    issue_error = None
    try:
        worker_id = int(request.form['worker_id'])
        warehouse_id = int(request.form['warehouse_id'])
        material_id = int(request.form['material_id'])
        quantity = float(request.form['quantity'])
        purpose = request.form['purpose'].strip()
        c.execute("SELECT id FROM workers WHERE id=? AND site_id=?", (worker_id, session['site_id']))
        if c.fetchone() and quantity > 0:
            available = get_stock_qty(c, warehouse_id, material_id)
            if quantity > available:
                issue_error = f"Is warehouse me sirf {available} unit available hai — itna maal issue nahi ho sakta."
            else:
                now = datetime.now().strftime('%Y-%m-%d')
                c.execute('''INSERT INTO stock_ledger
                    (txn_date, txn_type, warehouse_id, material_id, quantity, site_id, worker_id, purpose)
                    VALUES (?, 'ISSUE_WORKER', ?, ?, ?, ?, ?, ?)''',
                    (now, warehouse_id, material_id, quantity, session['site_id'], worker_id, purpose))
                conn.commit()
    except (ValueError, KeyError):
        issue_error = "Please fill in all fields correctly."
    conn.close()
    if issue_error:
        return redirect(url_for('workers', issue_error=issue_error))
    return redirect(url_for('work'))


def wait_for_sql_server(retry_seconds=5):
    """SQL Server chalu hone tak wait karta hai. Jab tak connect nahi hota,
    app start nahi hogi — har retry_seconds baad dobara try karega."""
    attempt = 1
    while True:
        try:
            test_conn = get_conn()
            test_conn.close()
            print("✅ SQL Server se connection ho gaya.")
            return
        except pyodbc.Error as e:
            print(f"⏳ SQL Server abhi available nahi hai (attempt {attempt}). "
                  f"{retry_seconds} second baad phir try karunga...")
            print(f"   Error detail: {e}")
            attempt += 1
            time.sleep(retry_seconds)


if __name__ == '__main__':
    wait_for_sql_server()   # jab tak SQL Server ready na ho, aage nahi badhega
    init_db()

    # Server mode: agar AUTO_OPEN_BROWSER=1 set hai to hi local browser khulega.
    # Phone app (APK) is server se network par connect karega, isliye default
    # off rakha hai — server headless PC/machine par bhi chal sake.
    if os.environ.get('AUTO_OPEN_BROWSER', '0') == '1':
        Timer(1.5, open_browser).start()

    port = int(os.environ.get('PORT', 8080))
    # host=0.0.0.0 already set hai, isliye ye LAN/network ke doosre devices
    # (jaise aapka phone) se bhi is server tak pahunch sakte hain.
    app.run(host='0.0.0.0', port=port, debug=False)
