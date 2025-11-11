from flask import Flask, render_template, request, redirect, url_for, flash
import csv
import os
import uuid
import json
from werkzeug.utils import secure_filename
import pyodbc
import logging
import sys
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Check Python version
if sys.version_info < (3, 7):
    logger.error("Python version must be 3.7 or higher. Current version: %s", sys.version)
    sys.exit(1)

try:
    import pyodbc
    logger.info("pyodbc module imported successfully")
except ImportError:
    logger.error("pyodbc module is missing. Please install it with 'pip install pyodbc'")
    sys.exit(1)

app = Flask(__name__)
app.secret_key = 'super-secret-key-2025'
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/photos')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload folder exists
upload_folder = app.config['UPLOAD_FOLDER']
if not os.path.exists(upload_folder):
    os.makedirs(upload_folder)
    logger.info(f"Created upload folder: {upload_folder}")

# Database Configuration
def get_db():
    server = os.getenv('DB_SERVER', '208.91.198.196')
    database = os.getenv('DB_NAME', 'ICP')
    username = os.getenv('DB_USER', 'ICP')
    password = os.getenv('DB_PASSWORD', 'Teams@@2578')
    driver = os.getenv('DB_DRIVER', '{ODBC Driver 18 for SQL Server}')
    conn_str = (
        fr'DRIVER={driver};SERVER={server};DATABASE={database};'
        fr'UID={username};PWD={password};Encrypt=yes;TrustServerCertificate=yes;'
    )
    try:
        conn = pyodbc.connect(conn_str)
        logger.info("Database connection established successfully")
        return conn
    except pyodbc.Error as e:
        logger.error(f"Database connection failed: {e}")
        raise

# Create table manually using pyodbc
def create_table():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE ICP.dbo.vanshul_Products (
                Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
                ItemName NVARCHAR(255) NOT NULL,
                Category NVARCHAR(100),
                Supplier NVARCHAR(100),
                PurchasePrice FLOAT NOT NULL,
                SalePrice FLOAT,
                ProfitMargin FLOAT DEFAULT 20.0,
                SellingPrice FLOAT NOT NULL,
                Quantity INT NOT NULL,
                PhotoPaths NVARCHAR(MAX),
                CreatedAt DATETIME DEFAULT GETDATE()
            )
        """)
        conn.commit()
        logger.info("vanshul_Products table created successfully")
    except pyodbc.Error as e:
        logger.error(f"Failed to create table: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

# Call create_table on app startup (if needed)
create_table()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
@app.route('/index')
def index():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vanshul_Products")
        products = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        products_dict = [dict(zip(columns, row)) for row in products]
        total_quantity = sum(row['Quantity'] for row in products_dict) if products_dict else 0
        logger.info(f"Retrieved {len(products_dict)} products from database")
        cursor.close()
        conn.close()
        return render_template('index.html', inventory=products_dict, total_quantity=total_quantity)
    except pyodbc.Error as e:
        logger.error(f"Error in index route: {e}")
        flash(f"Error loading inventory: {e}", 'danger')
        return render_template('index.html', inventory=[], total_quantity=0)

@app.route('/products')
def products():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vanshul_Products")
        products = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        products_dict = [dict(zip(columns, row)) for row in products]
        total_quantity = sum(row['Quantity'] for row in products_dict) if products_dict else 0
        logger.info(f"Retrieved {len(products_dict)} products for client view")
        cursor.close()
        conn.close()
        return render_template('products.html', inventory=products_dict, total_quantity=total_quantity)
    except pyodbc.Error as e:
        logger.error(f"Error in products route: {e}")
        flash(f"Error loading products: {e}", 'danger')
        return render_template('products.html', inventory=[], total_quantity=0)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        try:
            item_name = request.form['item_name']
            category = request.form.get('category', 'General')
            supplier = request.form.get('supplier', 'Unknown')
            purchase_price = float(request.form['purchase_price'])
            sale_price = float(request.form['sale_price']) if request.form.get('sale_price') else None
            profit_margin = float(request.form.get('profit_margin', 20))
            quantity = int(request.form['quantity'])

            if sale_price is None:
                selling_price = purchase_price * (1 + profit_margin / 100)
            else:
                selling_price = sale_price

            photo_paths = []
            if 'photos' in request.files:
                photos = request.files.getlist('photos')
                uploaded_photos = 0
                for photo in photos:
                    if photo.filename != '' and allowed_file(photo.filename):
                        file_ext = secure_filename(photo.filename).rsplit('.', 1)[1].lower()
                        unique_filename = f"{uuid.uuid4()}.{file_ext}"
                        photo_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                        photo.save(photo_path)
                        photo_paths.append(unique_filename)
                        uploaded_photos += 1
                    else:
                        flash(f'Skipped invalid photo: {photo.filename}', 'warning')
                if uploaded_photos > 0:
                    flash(f'{uploaded_photos} photos uploaded successfully!', 'success')
                else:
                    flash('No valid photos uploaded. Please use .png, .jpg, .jpeg, .gif, or .webp files.', 'warning')

            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO vanshul_Products (ItemName, Category, Supplier, PurchasePrice, SalePrice, ProfitMargin, SellingPrice, Quantity, PhotoPaths)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (item_name, category, supplier, purchase_price, sale_price, profit_margin, selling_price, quantity, json.dumps(photo_paths) if photo_paths else None))
            conn.commit()
            logger.info(f"Added product: {item_name} with {len(photo_paths)} photos")
            flash(f'Product "{item_name}" added successfully with {len(photo_paths)} photos!', 'success')
            cursor.close()
            conn.close()
        except ValueError as e:
            if 'conn' in locals():
                conn.rollback()
                cursor.close()
                conn.close()
            logger.error(f"ValueError in upload: {e}")
            flash(f'Invalid input data. Please check numbers: {str(e)}', 'danger')
        except pyodbc.Error as e:
            if 'conn' in locals():
                conn.rollback()
                cursor.close()
                conn.close()
            logger.error(f"Error in upload: {e}")
            flash(f'Error adding product: {str(e)}', 'danger')
        return redirect(url_for('index'))
    return render_template('upload.html')

@app.route('/bulk_upload', methods=['GET', 'POST'])
def bulk_upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        if file and file.filename.endswith('.csv'):
            conn = get_db()
            cursor = conn.cursor()
            try:
                stream = file.stream
                csv_reader = csv.DictReader(stream)
                added_count = 0
                for row in csv_reader:
                    try:
                        new_product = (
                            row['item_name'],
                            row.get('category', 'General'),
                            row.get('supplier', 'Unknown'),
                            float(row['purchase_price']),
                            float(row.get('profit_margin', 20)),
                            float(row['purchase_price']) * (1 + float(row.get('profit_margin', 20)) / 100),
                            int(row['quantity']),
                            None  # PhotoPaths
                        )
                        cursor.execute("""
                            INSERT INTO vanshul_Products (ItemName, Category, Supplier, PurchasePrice, ProfitMargin, SellingPrice, Quantity, PhotoPaths)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, new_product)
                        added_count += 1
                    except (KeyError, ValueError):
                        flash('Invalid CSV format. Required: item_name, purchase_price, quantity', 'danger')
                        continue
                conn.commit()
                logger.info(f"Bulk uploaded {added_count} products")
                flash(f'{added_count} products uploaded!', 'success')
            except pyodbc.Error as e:
                conn.rollback()
                logger.error(f"Error in bulk upload: {e}")
                flash(f'Error uploading products: {str(e)}', 'danger')
            finally:
                cursor.close()
                conn.close()
        else:
            flash('Please upload a valid CSV file', 'danger')
        return redirect(url_for('index'))
    return render_template('bulk_upload.html')

@app.route('/storefront')
def storefront():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vanshul_Products")
        products = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        products_dict = []
        for row in products:
            product = dict(zip(columns, row))
            # Parse PhotoPaths JSON
            if product['PhotoPaths']:
                try:
                    product['photo_list'] = json.loads(product['PhotoPaths'])
                except json.JSONDecodeError:
                    product['photo_list'] = []
            else:
                product['photo_list'] = []
            # Calculate discount
            if product['SalePrice'] and product['SalePrice'] < product['SellingPrice']:
                product['discount'] = round(((product['SellingPrice'] - product['SalePrice']) / product['SellingPrice']) * 100, 2)
            else:
                product['discount'] = 0.0
            products_dict.append(product)
        total_quantity = sum(row['Quantity'] for row in products_dict) if products_dict else 0
        logger.info(f"Retrieved {len(products_dict)} products for storefront")
        cursor.close()
        conn.close()
        return render_template('storefront.html', inventory=products_dict, total_quantity=total_quantity)
    except pyodbc.Error as e:
        logger.error(f"Error in storefront route: {e}")
        flash(f"Error loading products: {e}", 'danger')
        return render_template('storefront.html', inventory=[], total_quantity=0)
    

@app.route('/product/<id>')
def product_detail(id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vanshul_Products WHERE Id = ?", (id,))
        row = cursor.fetchone()  # Renamed to 'row' to avoid confusion
        if not row:
            flash('Product not found', 'danger')
            return redirect(url_for('storefront'))
        columns = [column[0] for column in cursor.description]
        product_dict = dict(zip(columns, row))  # Dict from tuple
        # Parse PhotoPaths JSON
        if product_dict['PhotoPaths']:
            try:
                product_dict['photo_list'] = json.loads(product_dict['PhotoPaths'])
            except json.JSONDecodeError:
                product_dict['photo_list'] = []
        else:
            product_dict['photo_list'] = []
        # Calculate discount (fixed: base on SellingPrice, not PurchasePrice)
        if product_dict['SalePrice'] and product_dict['SalePrice'] < product_dict['SellingPrice']:
            product_dict['discount'] = round(((product_dict['SellingPrice'] - product_dict['SalePrice']) / product_dict['SellingPrice']) * 100, 2)
        else:
            product_dict['discount'] = 0.0
        logger.info(f"Retrieved product ID: {id}")
        cursor.close()
        conn.close()
        return render_template('product_detail.html', item=product_dict)
    except pyodbc.Error as e:
        logger.error(f"Error in product detail route: {e}")
        flash(f"Error loading product: {e}", 'danger')
        return redirect(url_for('storefront'))

if __name__ == '__main__':
    app.run(debug=True)  # Start the Flask server