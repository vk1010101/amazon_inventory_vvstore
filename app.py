from flask import Flask, render_template, request, redirect, url_for, flash, session
import csv
import os
import uuid
import json
from datetime import datetime
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
app.config['SESSION_PERMANENT'] = False

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
        cursor.execute(
            """
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='vanshul_Products' AND xtype='U')
            BEGIN
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
            END
            """
        )
        cursor.execute(
            """
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='vanshul_Orders' AND xtype='U')
            BEGIN
                CREATE TABLE ICP.dbo.vanshul_Orders (
                    Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
                    OrderNumber NVARCHAR(50) NOT NULL UNIQUE,
                    CustomerEmail NVARCHAR(255),
                    Status NVARCHAR(50) DEFAULT 'Pending',
                    TotalAmount DECIMAL(18, 2) NOT NULL DEFAULT 0,
                    CreatedAt DATETIME DEFAULT GETDATE()
                )
            END
            """
        )
        cursor.execute(
            """
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='vanshul_OrderItems' AND xtype='U')
            BEGIN
                CREATE TABLE ICP.dbo.vanshul_OrderItems (
                    OrderItemId UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
                    OrderId UNIQUEIDENTIFIER NOT NULL,
                    ProductId UNIQUEIDENTIFIER NOT NULL,
                    Quantity INT NOT NULL,
                    UnitPrice DECIMAL(18, 2) NOT NULL,
                    LineTotal DECIMAL(18, 2) NOT NULL,
                    CONSTRAINT FK_Order_OrderId FOREIGN KEY (OrderId) REFERENCES vanshul_Orders(Id),
                    CONSTRAINT FK_Order_ProductId FOREIGN KEY (ProductId) REFERENCES vanshul_Products(Id)
                )
            END
            """
        )
        conn.commit()
    except pyodbc.Error as e:
        logger.error(f"Failed to ensure tables exist: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

# Call create_table on app startup (if needed)
create_table()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


@app.context_processor
def inject_utilities():
    return {'now': datetime.utcnow}


def get_cart():
    return session.get('cart', {})


def save_cart(cart):
    session['cart'] = cart
    session.modified = True


def build_cart_summary(cart):
    total_items = sum(item['quantity'] for item in cart.values()) if cart else 0
    total_amount = sum(item['quantity'] * item['unit_price'] for item in cart.values()) if cart else 0
    return total_items, total_amount


def fetch_product(product_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM vanshul_Products WHERE Id = ?", (product_id,))
        row = cursor.fetchone()
        if not row:
            return None
        columns = [column[0] for column in cursor.description]
        product_dict = dict(zip(columns, row))
        if product_dict.get('PhotoPaths'):
            try:
                product_dict['photo_list'] = json.loads(product_dict['PhotoPaths'])
            except json.JSONDecodeError:
                product_dict['photo_list'] = []
        else:
            product_dict['photo_list'] = []
        if product_dict.get('SalePrice') and product_dict['SalePrice'] < product_dict['SellingPrice']:
            product_dict['display_price'] = product_dict['SalePrice']
        else:
            product_dict['display_price'] = product_dict['SellingPrice']
        return product_dict
    finally:
        cursor.close()
        conn.close()


def create_order_records(order_items, customer_email=None, status='Completed'):
    if not order_items:
        raise ValueError('No order items provided')

    conn = get_db()
    cursor = conn.cursor()
    try:
        order_id = str(uuid.uuid4())
        order_number = f"VV-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        total_amount = sum(item['quantity'] * item['unit_price'] for item in order_items)

        cursor.execute(
            """
            INSERT INTO vanshul_Orders (Id, OrderNumber, CustomerEmail, Status, TotalAmount)
            VALUES (?, ?, ?, ?, ?)
            """,
            (order_id, order_number, customer_email, status, total_amount),
        )

        for item in order_items:
            cursor.execute(
                """
                UPDATE vanshul_Products
                SET Quantity = Quantity - ?
                WHERE Id = ? AND Quantity >= ?
                """,
                (item['quantity'], item['product_id'], item['quantity']),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Insufficient inventory for {item['name']}")

            cursor.execute(
                """
                INSERT INTO vanshul_OrderItems (OrderItemId, OrderId, ProductId, Quantity, UnitPrice, LineTotal)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    order_id,
                    item['product_id'],
                    item['quantity'],
                    item['unit_price'],
                    item['quantity'] * item['unit_price'],
                ),
            )

        conn.commit()
        return order_number, total_amount
    except Exception as exc:
        conn.rollback()
        raise exc
    finally:
        cursor.close()
        conn.close()

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
        return render_template('index.html', inventory=products_dict, total_quantity=total_quantity, active_page='dashboard')
    except pyodbc.Error as e:
        logger.error(f"Error in index route: {e}")
        flash(f"Error loading inventory: {e}", 'danger')
        return render_template('index.html', inventory=[], total_quantity=0, active_page='dashboard')

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
    return render_template('upload.html', active_page='upload')

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
    return render_template('bulk_upload.html', active_page='bulk_upload')

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
                product['display_price'] = product['SalePrice']
            else:
                product['discount'] = 0.0
                product['display_price'] = product['SellingPrice']
            products_dict.append(product)
        total_quantity = sum(row['Quantity'] for row in products_dict) if products_dict else 0
        logger.info(f"Retrieved {len(products_dict)} products for storefront")
        cursor.close()
        conn.close()
        cart_count, _ = build_cart_summary(get_cart())
        return render_template(
            'storefront.html',
            inventory=products_dict,
            total_quantity=total_quantity,
            cart_count=cart_count,
            active_page='storefront',
        )
    except pyodbc.Error as e:
        logger.error(f"Error in storefront route: {e}")
        flash(f"Error loading products: {e}", 'danger')
        return render_template('storefront.html', inventory=[], total_quantity=0, cart_count=0)


@app.route('/product/<id>')
def product_detail(id):
    try:
        product = fetch_product(id)
        if not product:
            flash('Product not found', 'danger')
            return redirect(url_for('storefront'))
        if product.get('SalePrice') and product['SalePrice'] < product['SellingPrice']:
            product['discount'] = round(((product['SellingPrice'] - product['SalePrice']) / product['SellingPrice']) * 100, 2)
        else:
            product['discount'] = 0.0
        cart_count, _ = build_cart_summary(get_cart())
        logger.info(f"Retrieved product ID: {id}")
        return render_template('product_detail.html', item=product, cart_count=cart_count)
    except pyodbc.Error as e:
        logger.error(f"Error in product detail route: {e}")
        flash(f"Error loading product: {e}", 'danger')
        return redirect(url_for('storefront'))


@app.route('/add_to_cart/<product_id>', methods=['POST'])
def add_to_cart(product_id):
    quantity = request.form.get('quantity', '1')
    try:
        quantity = max(1, int(quantity))
    except ValueError:
        flash('Invalid quantity supplied.', 'danger')
        return redirect(request.referrer or url_for('storefront'))

    product = fetch_product(product_id)
    if not product:
        flash('Unable to find that product.', 'danger')
        return redirect(request.referrer or url_for('storefront'))

    if product['Quantity'] < quantity:
        flash('Requested quantity exceeds available stock.', 'warning')
        return redirect(request.referrer or url_for('storefront'))

    cart = get_cart()
    if product_id in cart:
        new_quantity = cart[product_id]['quantity'] + quantity
        if new_quantity > product['Quantity']:
            flash('Cannot add more than available stock to the cart.', 'warning')
            return redirect(request.referrer or url_for('storefront'))
        cart[product_id]['quantity'] = new_quantity
    else:
        cart[product_id] = {
            'product_id': product_id,
            'name': product['ItemName'],
            'unit_price': float(product['display_price']),
            'quantity': quantity,
            'photo': product['photo_list'][0] if product['photo_list'] else None,
        }
    save_cart(cart)
    total_items, _ = build_cart_summary(cart)
    flash(f"Added {product['ItemName']} to the cart.", 'success')
    logger.info(f"Cart updated: {total_items} items total")
    return redirect(request.referrer or url_for('storefront'))


@app.route('/update_cart/<product_id>', methods=['POST'])
def update_cart(product_id):
    cart = get_cart()
    if product_id not in cart:
        flash('Item not in cart.', 'danger')
        return redirect(url_for('view_cart'))

    quantity = request.form.get('quantity', '1')
    try:
        quantity = int(quantity)
    except ValueError:
        flash('Invalid quantity provided.', 'danger')
        return redirect(url_for('view_cart'))

    if quantity <= 0:
        cart.pop(product_id, None)
    else:
        product = fetch_product(product_id)
        if not product:
            flash('Product not found for update.', 'danger')
            return redirect(url_for('view_cart'))
        if product['Quantity'] < quantity:
            flash('Requested quantity exceeds available stock.', 'warning')
            return redirect(url_for('view_cart'))
        cart[product_id]['quantity'] = quantity

    save_cart(cart)
    flash('Cart updated successfully.', 'success')
    return redirect(url_for('view_cart'))


@app.route('/remove_from_cart/<product_id>', methods=['POST'])
def remove_from_cart(product_id):
    cart = get_cart()
    if product_id in cart:
        removed_item = cart.pop(product_id)
        save_cart(cart)
        flash(f"Removed {removed_item['name']} from the cart.", 'info')
    else:
        flash('Item not found in cart.', 'warning')
    return redirect(url_for('view_cart'))


@app.route('/cart')
def view_cart():
    cart = get_cart()
    total_items, total_amount = build_cart_summary(cart)
    return render_template(
        'cart.html',
        cart_items=cart.values(),
        total_items=total_items,
        total_amount=total_amount,
    )


@app.route('/checkout', methods=['POST'])
def checkout():
    cart = get_cart()
    if not cart:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('view_cart'))

    customer_email = request.form.get('email') or None
    order_items = [
        {
            'product_id': item['product_id'],
            'name': item['name'],
            'quantity': item['quantity'],
            'unit_price': item['unit_price'],
        }
        for item in cart.values()
    ]

    try:
        order_number, total_amount = create_order_records(order_items, customer_email)
        session.pop('cart', None)
        flash(f'Order {order_number} placed successfully. Total ₹{total_amount:.2f}', 'success')
        return redirect(url_for('storefront'))
    except ValueError as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('view_cart'))
    except Exception as exc:
        logger.error(f'Checkout failed: {exc}')
        flash('We were unable to complete your order. Please try again.', 'danger')
        return redirect(url_for('view_cart'))


@app.route('/buy_now/<product_id>', methods=['POST'])
def buy_now(product_id):
    quantity = request.form.get('quantity', '1')
    try:
        quantity = max(1, int(quantity))
    except ValueError:
        flash('Invalid quantity supplied.', 'danger')
        return redirect(request.referrer or url_for('storefront'))

    product = fetch_product(product_id)
    if not product:
        flash('Product not found.', 'danger')
        return redirect(request.referrer or url_for('storefront'))

    if product['Quantity'] < quantity:
        flash('Requested quantity exceeds available stock.', 'warning')
        return redirect(request.referrer or url_for('storefront'))

    order_items = [
        {
            'product_id': product_id,
            'name': product['ItemName'],
            'quantity': quantity,
            'unit_price': float(product['display_price']),
        }
    ]

    try:
        order_number, total_amount = create_order_records(order_items)
        flash(f'Order {order_number} confirmed. Total ₹{total_amount:.2f}', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    except Exception as exc:
        logger.error(f'Buy now failed: {exc}')
        flash('We were unable to process your purchase.', 'danger')
    return redirect(url_for('storefront'))

if __name__ == '__main__':
    app.run(debug=True)  # Start the Flask server