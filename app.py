import os
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime
from io import BytesIO
from flask import Flask, render_template, request, jsonify, send_file
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

# Supabase PostgreSQL connection string from Environment Variables
DATABASE_URL = os.environ.get('DATABASE_URL')

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
    # Dimensions and Paddings
    width = 900
    margin = 40
    header_height = 250
    item_height = 50
    footer_height = 180
    height = header_height + (len(items) * item_height) + footer_height
    
    # Colors
    bg_color = (250, 245, 240)
    primary_color = (211, 84, 0)
    secondary_color = (44, 62, 80)
    text_light = (127, 140, 141)
    accent_bg = (255, 255, 255)
    border_color = (223, 230, 233)
    
    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    try:
        font_super = ImageFont.truetype("arialbd.ttf", 45)
        font_title = ImageFont.truetype("arialbd.ttf", 32)
        font_header = ImageFont.truetype("arial.ttf", 22)
        font_text = ImageFont.truetype("arial.ttf", 20)
        font_bold = ImageFont.truetype("arialbd.ttf", 20)
    except:
        font_super = ImageFont.load_default()
        font_title = ImageFont.load_default()
        font_header = ImageFont.load_default()
        font_text = ImageFont.load_default()
        font_bold = ImageFont.load_default()

    # Top decorative bar
    draw.rectangle([0, 0, width, 15], fill=primary_color)
    draw.text((width/2, 60), "SISTEMA DE ENTREGA DE PAN", font=font_super, fill=primary_color, anchor="mm")
    
    details_y = 100
    draw.rectangle([margin, details_y, width-margin, details_y+120], fill=accent_bg, outline=border_color, width=2)
    
    draw.text((margin + 20, details_y + 20), "CLIENTE:", font=font_bold, fill=text_light)
    draw.text((margin + 20, details_y + 50), customer_name, font=font_title, fill=secondary_color)
    
    draw.text((width - margin - 250, details_y + 20), "FACTURA N°:", font=font_bold, fill=text_light)
    draw.text((width - margin - 250, details_y + 50), f"{invoice_id:06d}", font=font_title, fill=primary_color)
    draw.text((width - margin - 250, details_y + 85), f"Fecha: {date_str}", font=font_text, fill=text_light)

    table_y = details_y + 150
    draw.rectangle([margin, table_y, width-margin, table_y+40], fill=primary_color)
    
    col_x = [margin+20, margin+350, margin+500, margin+700]
    draw.text((col_x[0], table_y + 10), "PRODUCTO", font=font_bold, fill="white")
    draw.text((col_x[1], table_y + 10), "CANT.", font=font_bold, fill="white")
    draw.text((col_x[2], table_y + 10), "PRECIO", font=font_bold, fill="white")
    draw.text((col_x[3], table_y + 10), "SUBTOTAL", font=font_bold, fill="white")
    
    y = table_y + 40
    
    for i, item in enumerate(items):
        row_bg = accent_bg if i % 2 == 0 else (249, 250, 251)
        draw.rectangle([margin, y, width-margin, y+item_height], fill=row_bg, outline=border_color, width=1)
        
        text_y = y + 15
        draw.text((col_x[0], text_y), item['bread_type'], font=font_bold, fill=secondary_color)
        draw.text((col_x[1], text_y), str(item['quantity']), font=font_text, fill=secondary_color)
        draw.text((col_x[2], text_y), f"${item['unit_price']:.2f}", font=font_text, fill=secondary_color)
        draw.text((col_x[3], text_y), f"${item['total_price']:.2f}", font=font_bold, fill=primary_color)
        
        y += item_height
    
    y += 20
    draw.rectangle([width-margin-300, y, width-margin, y+70], fill=accent_bg, outline=primary_color, width=3)
    draw.text((width-margin-280, y + 22), "TOTAL:", font=font_title, fill=secondary_color)
    draw.text((width-margin-20, y + 22), f"${total_amount:.2f}", font=font_super, fill=primary_color, anchor="rm")
    
    y += 100
    draw.text((width/2, y), "¡Gracias por su preferencia!", font=font_header, fill=text_light, anchor="mm")
    
    draw.rectangle([0, height-15, width, height], fill=primary_color)

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
