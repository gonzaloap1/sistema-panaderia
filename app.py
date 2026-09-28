import os
import traceback
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime
from io import BytesIO
from flask import Flask, render_template, request, jsonify, send_file
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

# Supabase PostgreSQL connection string from Environment Variables
DATABASE_URL = os.environ.get('DATABASE_URL')

@app.errorhandler(500)
def handle_500(e):
    return f"<h1>Error 500</h1><pre>{traceback.format_exc()}</pre><p>DATABASE_URL set: {bool(DATABASE_URL)}</p>", 500

@app.route('/debug')
def debug_route():
    info = f"DATABASE_URL set: {bool(DATABASE_URL)}\n"
    if DATABASE_URL:
        masked = DATABASE_URL[:20] + "..." + DATABASE_URL[-15:]
        info += f"URL preview: {masked}\n"
        try:
            conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            info += "Connection: SUCCESS\n"
            conn.close()
        except Exception as ex:
            info += f"Connection FAILED: {ex}\n"
    return f"<pre>{info}</pre>"

BREAD_TYPES = [
    "Francés", "Sobado", "Campesino", "Canilla", "Sándwich", 
    "Coco", "Piñita", "Frutas", "Guayaba", "Golfeado", 
    "Palmerita", "Tornillos", "Roja", "Marmoleada", "De pan", 
    "Suspiro", "Pasta", "Polvorosa", "Panelitas", "Rosca", "Tostada"
]

def get_db_connection():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL no configurada en las variables de entorno.")
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

def init_db():
    if not DATABASE_URL:
        print("Saltando inicialización de DB local, se requiere DATABASE_URL de Supabase.")
        return
        
    conn = get_db_connection()
    c = conn.cursor()
    # Invoices table (Postgres uses SERIAL)
    c.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            id SERIAL PRIMARY KEY,
            customer_name TEXT,
            date TEXT,
            total_amount REAL
        )
    ''')
    # Invoice items table
    c.execute('''
        CREATE TABLE IF NOT EXISTS invoice_items (
            id SERIAL PRIMARY KEY,
            invoice_id INTEGER,
            bread_type TEXT,
            quantity INTEGER,
            unit_price REAL,
            total_price REAL,
            FOREIGN KEY (invoice_id) REFERENCES invoices (id)
        )
    ''')
    # Prices table
    c.execute('''
        CREATE TABLE IF NOT EXISTS bread_prices (
            bread_type TEXT PRIMARY KEY,
            current_price REAL
        )
    ''')
    
    # Initialize prices if not present (Postgres syntax)
    for bread in BREAD_TYPES:
        c.execute('''
            INSERT INTO bread_prices (bread_type, current_price) 
            VALUES (%s, %s)
            ON CONFLICT (bread_type) DO NOTHING
        ''', (bread, 0.0))
        
    conn.commit()
    conn.close()

def create_invoice_image(customer_name, items, total_amount, date_str, invoice_id):
    width = 650
    margin = 28
    item_height = 58
    table_header_height = 48

    table_start_y = 250
    table_end_y = table_start_y + table_header_height + (len(items) * item_height)
    total_box_y = table_end_y + 40
    min_height = 980
    height = max(min_height, total_box_y + 190)

    bg_color = (252, 248, 244)
    primary = (211, 84, 0)
    secondary = (44, 62, 80)
    text_muted = (120, 130, 140)
    accent_bg = (255, 255, 255)
    border_color = (225, 228, 232)

    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Load bundled TrueType fonts so text is sharp, large and supports accents (ñ, á, é, etc.) on Linux/Vercel
    font_dir = os.path.join(os.path.dirname(__file__), 'static', 'fonts')
    bold_path = os.path.join(font_dir, 'arialbd.ttf')
    reg_path = os.path.join(font_dir, 'arial.ttf')

    try:
        font_title = ImageFont.truetype(bold_path, 30)
        font_sub = ImageFont.truetype(reg_path, 18)
        font_small_bold = ImageFont.truetype(bold_path, 17)
        font_client = ImageFont.truetype(bold_path, 26)
        font_factura = ImageFont.truetype(bold_path, 22)
        font_date = ImageFont.truetype(reg_path, 17)
        font_tbl_header = ImageFont.truetype(bold_path, 19)
        font_row_bold = ImageFont.truetype(bold_path, 22)
        font_row_reg = ImageFont.truetype(reg_path, 20)
        font_total_label = ImageFont.truetype(bold_path, 24)
        font_total_val = ImageFont.truetype(bold_path, 40)
        font_footer = ImageFont.truetype(bold_path, 19)
    except Exception:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_small_bold = ImageFont.load_default()
        font_client = ImageFont.load_default()
        font_factura = ImageFont.load_default()
        font_date = ImageFont.load_default()
        font_tbl_header = ImageFont.load_default()
        font_row_bold = ImageFont.load_default()
        font_row_reg = ImageFont.load_default()
        font_total_label = ImageFont.load_default()
        font_total_val = ImageFont.load_default()
        font_footer = ImageFont.load_default()

    # Top accent bar
    draw.rectangle([0, 0, width, 14], fill=primary)

    # Header
    draw.text((width/2, 48), 'SISTEMA DE ENTREGA DE PAN', font=font_title, fill=primary, anchor='mm')
    draw.text((width/2, 80), 'COMPROBANTE DE ENTREGA', font=font_sub, fill=text_muted, anchor='mm')
    draw.line([(margin, 105), (width - margin, 105)], fill=border_color, width=2)

    # Client & Invoice Info Card
    card_top = 120
    card_bottom = 230
    draw.rectangle([margin, card_top, width - margin, card_bottom], fill=accent_bg, outline=border_color, width=2)

    draw.text((margin + 18, card_top + 18), 'CLIENTE:', font=font_small_bold, fill=text_muted)
    draw.text((margin + 18, card_top + 48), customer_name, font=font_client, fill=secondary)

    right_x = width - margin - 18
    draw.text((right_x, card_top + 18), f'FACTURA N°: #{invoice_id:06d}', font=font_factura, fill=primary, anchor='rt')
    draw.text((right_x, card_top + 50), f'Fecha: {date_str[:10]}', font=font_date, fill=secondary, anchor='rt')
    draw.text((right_x, card_top + 76), f'Hora: {date_str[11:]}', font=font_date, fill=text_muted, anchor='rt')

    # Table Header
    draw.rectangle([margin, table_start_y, width - margin, table_start_y + table_header_height], fill=primary)

    col_prod = margin + 18
    col_cant = margin + 250
    col_price = margin + 370
    col_sub = width - margin - 18

    draw.text((col_prod, table_start_y + 14), 'PRODUCTO', font=font_tbl_header, fill='white')
    draw.text((col_cant, table_start_y + 14), 'CANT.', font=font_tbl_header, fill='white', anchor='mt')
    draw.text((col_price, table_start_y + 14), 'PRECIO', font=font_tbl_header, fill='white', anchor='mt')
    draw.text((col_sub, table_start_y + 14), 'SUBTOTAL', font=font_tbl_header, fill='white', anchor='rt')

    # Table Rows
    y = table_start_y + table_header_height
    for i, item in enumerate(items):
        row_bg = accent_bg if i % 2 == 0 else (248, 249, 250)
        draw.rectangle([margin, y, width - margin, y + item_height], fill=row_bg, outline=border_color, width=1)
        
        text_y = y + 17
        draw.text((col_prod, text_y), item['bread_type'], font=font_row_bold, fill=secondary)
        draw.text((col_cant, text_y), str(item['quantity']), font=font_row_bold, fill=secondary, anchor='mt')
        
        price_val = float(item['unit_price'])
        draw.text((col_price, text_y), f"${price_val:.2f}", font=font_row_reg, fill=secondary, anchor='mt')
        
        tot_val = float(item['total_price'])
        draw.text((col_sub, text_y), f"${tot_val:.2f}", font=font_row_bold, fill=primary, anchor='rt')
        y += item_height

    # Summary units
    total_units = sum(int(item['quantity']) for item in items)
    draw.text((margin + 10, y + 14), f'Total de panes: {total_units}', font=font_sub, fill=secondary)

    # Total Box
    t_box_y = y + 45
    draw.rectangle([margin, t_box_y, width - margin, t_box_y + 80], fill=accent_bg, outline=primary, width=3)
    draw.text((margin + 22, t_box_y + 40), 'TOTAL A PAGAR:', font=font_total_label, fill=secondary, anchor='lm')
    draw.text((width - margin - 22, t_box_y + 40), f"${float(total_amount):.2f}", font=font_total_val, fill=primary, anchor='rm')

    # Footer
    footer_y = t_box_y + 120
    draw.text((width/2, footer_y), '¡Gracias por su preferencia!', font=font_footer, fill=text_muted, anchor='mm')

    # Bottom decorative bar
    draw.rectangle([0, height - 14, width, height], fill=primary)

    return img

_db_initialized = False

@app.before_request
def ensure_db():
    global _db_initialized
    if not _db_initialized and DATABASE_URL:
        init_db()
        _db_initialized = True

@app.route('/')
def index():
    prices = {}
    if DATABASE_URL:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT bread_type, current_price FROM bread_prices')
        prices = {row[0]: row[1] for row in c.fetchall()}
        conn.close()
    
    return render_template('index.html', bread_types=BREAD_TYPES, bread_prices=prices)

@app.route('/history')
def history():
    return render_template('history.html')

@app.route('/api/invoices')
def api_invoices():
    if not DATABASE_URL:
        return jsonify([])
        
    search = request.args.get('search', '')
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=DictCursor)
    
    if search:
        c.execute("SELECT id, customer_name, date, total_amount FROM invoices WHERE customer_name ILIKE %s ORDER BY id DESC", ('%' + search + '%',))
    else:
        c.execute("SELECT id, customer_name, date, total_amount FROM invoices ORDER BY id DESC")
        
    invoices = []
    for row in c.fetchall():
        invoices.append({
            'id': row['id'],
            'customer_name': row['customer_name'],
            'date': row['date'],
            'total_amount': row['total_amount']
        })
    conn.close()
    return jsonify(invoices)

@app.route('/download/<int:invoice_id>')
def download_invoice(invoice_id):
    if not DATABASE_URL:
        return "Database not configured", 500
        
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=DictCursor)
    
    c.execute("SELECT customer_name, date, total_amount FROM invoices WHERE id=%s", (invoice_id,))
    inv = c.fetchone()
    if not inv:
        conn.close()
        return "Invoice not found", 404
        
    customer_name, date_str, total_amount = inv['customer_name'], inv['date'], inv['total_amount']
    
    c.execute("SELECT bread_type, quantity, unit_price, total_price FROM invoice_items WHERE invoice_id=%s", (invoice_id,))
    items_rows = c.fetchall()
    conn.close()
    
    items = []
    for row in items_rows:
        items.append({
            'bread_type': row['bread_type'],
            'quantity': row['quantity'],
            'unit_price': row['unit_price'],
            'total_price': row['total_price']
        })
        
    img = create_invoice_image(customer_name, items, total_amount, date_str, invoice_id)
    
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    return send_file(img_io, mimetype='image/png', as_attachment=True, download_name=f'factura_{invoice_id}.png')

@app.route('/generate', methods=['POST'])
def generate_invoice():
    if not DATABASE_URL:
        return jsonify({"error": "Base de datos no configurada."}), 500
        
    data = request.json
    customer_name = data.get('customer_name', 'Consumidor Final')
    items = data.get('items', [])
    
    if not items:
        return jsonify({"error": "No hay productos seleccionados"}), 400

    total_amount = sum(float(item['total_price']) for item in items)
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Save Invoice (Postgres returns id with RETURNING)
    c.execute('INSERT INTO invoices (customer_name, date, total_amount) VALUES (%s, %s, %s) RETURNING id',
              (customer_name, date_str, total_amount))
    invoice_id = c.fetchone()[0]
    
    # 2. Save Items & Update Prices
    for item in items:
        c.execute('INSERT INTO invoice_items (invoice_id, bread_type, quantity, unit_price, total_price) VALUES (%s, %s, %s, %s, %s)',
                  (invoice_id, item['bread_type'], item['quantity'], item['unit_price'], item['total_price']))
        
        # Postgres UPSERT
        c.execute('''
            INSERT INTO bread_prices (bread_type, current_price) 
            VALUES (%s, %s)
            ON CONFLICT (bread_type) DO UPDATE SET current_price = EXCLUDED.current_price
        ''', (item['bread_type'], item['unit_price']))
                  
    conn.commit()
    conn.close()

    # Generate Image
    img = create_invoice_image(customer_name, items, total_amount, date_str, invoice_id)
    
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    return send_file(img_io, mimetype='image/png', as_attachment=True, download_name=f'factura_{invoice_id}.png')

if __name__ == '__main__':
    # Optional: for local testing without Vercel if you have a local postgres
    # init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
