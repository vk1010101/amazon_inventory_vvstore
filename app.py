from flask import Flask, render_template, request, redirect, url_for, flash, session
import csv
import os
import uuid
import json
from datetime import datetime
from collections import defaultdict
from functools import wraps
from urllib.parse import urlparse
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import pyodbc
import logging
import sys

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
        cursor.execute(
            """
            IF COL_LENGTH('dbo.vanshul_Products', 'InitialQuantity') IS NULL
            BEGIN
                ALTER TABLE ICP.dbo.vanshul_Products
                ADD InitialQuantity INT NULL;

                UPDATE ICP.dbo.vanshul_Products
                SET InitialQuantity = Quantity
                WHERE InitialQuantity IS NULL;
            END
            """
        )
        cursor.execute(
            """
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Customers' AND xtype='U')
            BEGIN
                CREATE TABLE ICP.dbo.Customers (
                    Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
                    FullName NVARCHAR(255) NOT NULL,
                    Email NVARCHAR(255) NOT NULL UNIQUE,
                    PasswordHash NVARCHAR(255) NOT NULL,
                    CreatedAt DATETIME DEFAULT GETDATE()
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
    cart = get_cart()
    cart_count, cart_total = build_cart_summary(cart)
    return {
        'now': datetime.utcnow,
        'supplier_user': session.get('supplier_user'),
        'customer_user': session.get('customer_user'),
        'cart_count': cart_count,
        'cart_total': cart_total,
    }


def get_cart():
    return session.get('cart', {})


def save_cart(cart):
    session['cart'] = cart
    session.modified = True


def build_cart_summary(cart):
    total_items = sum(item['quantity'] for item in cart.values()) if cart else 0
    total_amount = sum(item['quantity'] * item['unit_price'] for item in cart.values()) if cart else 0
    return total_items, total_amount


def map_row(cursor, row):
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))


def verify_password(stored_password, provided_password):
    if stored_password is None or provided_password is None:
        return False

    stored_password = str(stored_password)
    if stored_password.startswith('pbkdf2:'):
        return check_password_hash(stored_password, provided_password)
    return stored_password == provided_password


def fetch_supplier_account(identifier):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT TOP 1 *
            FROM Admins
            WHERE Email = ? OR Username = ?
            """,
            (identifier, identifier),
        )
        row = cursor.fetchone()
        return map_row(cursor, row) if row else None
    finally:
        cursor.close()
        conn.close()


def fetch_customer_account(email):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT TOP 1 *
            FROM Customers
            WHERE Email = ?
            """,
            (email,),
        )
        row = cursor.fetchone()
        return map_row(cursor, row) if row else None
    finally:
        cursor.close()
        conn.close()


def create_customer_account(full_name, email, password):
    hashed_password = generate_password_hash(password)
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO Customers (Id, FullName, Email, PasswordHash)
            VALUES (?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), full_name, email, hashed_password),
        )
        conn.commit()
    except pyodbc.IntegrityError as exc:
        conn.rollback()
        raise ValueError('An account with that email already exists.') from exc
    finally:
        cursor.close()
        conn.close()


def supplier_login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not session.get('supplier_user'):
            flash('Please sign in with your supplier credentials to continue.', 'warning')
            return redirect(url_for('supplier_login', next=request.path))
        return view_func(*args, **kwargs)

    return wrapped_view


def customer_login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not session.get('customer_user'):
            flash('Please sign in to manage your cart and checkout.', 'warning')
            referrer = request.referrer
            next_target = None
            if referrer:
                parsed = urlparse(referrer)
                if not parsed.netloc or parsed.netloc == request.host:
                    next_target = parsed.path or url_for('storefront')
            if not next_target:
                next_target = url_for('storefront')
            return redirect(url_for('customer_login', next=next_target))
        return view_func(*args, **kwargs)

    return wrapped_view


def resolve_next(default_endpoint):
    next_target = request.args.get('next') or request.form.get('next')
    if next_target:
        if next_target.startswith('/'):
            return next_target
        parsed = urlparse(next_target)
        if not parsed.netloc or parsed.netloc == request.host:
            return parsed.path or url_for(default_endpoint)
    return url_for(default_endpoint)


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
@supplier_login_required
def index():
    search_query = request.args.get('search', '').strip()
    try:
        conn = get_db()
        cursor = conn.cursor()
        if search_query:
            like_query = f"%{search_query}%"
            cursor.execute(
                """
                SELECT * FROM vanshul_Products
                WHERE ItemName LIKE ? OR Category LIKE ? OR Supplier LIKE ?
                """,
                (like_query, like_query, like_query),
            )
        else:
            cursor.execute("SELECT * FROM vanshul_Products")
        products = cursor.fetchall()
        products_dict = [map_row(cursor, row) for row in products]

        total_quantity = sum(row.get('Quantity', 0) or 0 for row in products_dict)
        total_inventory_value = sum((row.get('Quantity', 0) or 0) * (row.get('PurchasePrice') or 0) for row in products_dict)
        potential_revenue = sum((row.get('Quantity', 0) or 0) * (row.get('SellingPrice') or 0) for row in products_dict)
        margins = [row.get('ProfitMargin') for row in products_dict if row.get('ProfitMargin') is not None]
        avg_margin = round(sum(margins) / len(margins), 2) if margins else 0.0

        low_stock_items = []
        category_distribution = defaultdict(int)
        for row in products_dict:
            qty = row.get('Quantity') or 0
            initial_qty = row.get('InitialQuantity') or qty
            if initial_qty <= 0:
                stock_ratio = 1
            else:
                stock_ratio = qty / initial_qty
            row['InitialQuantity'] = initial_qty
            row['stock_ratio'] = stock_ratio
            row['is_low_stock'] = initial_qty > 0 and stock_ratio <= 0.4
            if row['is_low_stock']:
                low_stock_items.append(row)
            category_distribution[(row.get('Category') or 'Uncategorised').strip() or 'Uncategorised'] += qty

        analytics = {
            'total_inventory_value': total_inventory_value,
            'potential_revenue': potential_revenue,
            'average_margin': avg_margin,
            'low_stock_count': len(low_stock_items),
            'category_distribution': sorted(category_distribution.items(), key=lambda item: item[1], reverse=True),
            'search_query': search_query,
        }

        logger.info(f"Retrieved {len(products_dict)} products from database")
        cursor.close()
        conn.close()
        return render_template(
            'index.html',
            inventory=products_dict,
            total_quantity=total_quantity,
            analytics=analytics,
            low_stock_items=low_stock_items,
            active_page='dashboard',
        )
    except pyodbc.Error as e:
        logger.error(f"Error in index route: {e}")
        flash(f"Error loading inventory: {e}", 'danger')
        return render_template(
            'index.html',
            inventory=[],
            total_quantity=0,
            analytics={'total_inventory_value': 0, 'potential_revenue': 0, 'average_margin': 0, 'low_stock_count': 0, 'category_distribution': [], 'search_query': search_query},
            low_stock_items=[],
            active_page='dashboard',
        )

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
@supplier_login_required
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
            cursor.execute(
                """
                INSERT INTO vanshul_Products (ItemName, Category, Supplier, PurchasePrice, SalePrice, ProfitMargin, SellingPrice, Quantity, InitialQuantity, PhotoPaths)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_name,
                    category,
                    supplier,
                    purchase_price,
                    sale_price,
                    profit_margin,
                    selling_price,
                    quantity,
                    quantity,
                    json.dumps(photo_paths) if photo_paths else None,
                ),
            )
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
@supplier_login_required
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
                            int(row['quantity']),
                            None,  # PhotoPaths
                        )
                        cursor.execute(
                            """
                            INSERT INTO vanshul_Products (ItemName, Category, Supplier, PurchasePrice, ProfitMargin, SellingPrice, Quantity, InitialQuantity, PhotoPaths)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            new_product,
                        )
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


@app.route('/supplier/login', methods=['GET', 'POST'])
def supplier_login():
    if session.get('supplier_user'):
        flash('You are already signed in to the supplier console.', 'info')
        return redirect(url_for('index'))

    next_url = resolve_next('index')
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')
        if not identifier or not password:
            flash('Enter both username/email and password.', 'warning')
        else:
            account = fetch_supplier_account(identifier)
            stored_password = None
            if account:
                stored_password = (
                    account.get('PasswordHash')
                    or account.get('Password')
                    or account.get('password')
                )
            if account and verify_password(stored_password, password):
                session['supplier_user'] = {
                    'id': account.get('Id'),
                    'name': account.get('FullName')
                    or account.get('Name')
                    or account.get('DisplayName')
                    or account.get('Email')
                    or account.get('Username')
                    or identifier,
                    'email': account.get('Email') or account.get('Username') or identifier,
                }
                flash('Welcome back to the supplier dashboard.', 'success')
                return redirect(next_url)
            flash('Invalid supplier credentials. Please try again.', 'danger')

    return render_template('supplier_login.html', next=next_url)


@app.route('/supplier/logout')
def supplier_logout():
    session.pop('supplier_user', None)
    flash('You have been signed out of the supplier console.', 'info')
    return redirect(url_for('supplier_login'))


@app.route('/customer/register', methods=['GET', 'POST'])
def customer_register():
    if session.get('customer_user'):
        flash('You are already signed in.', 'info')
        return redirect(url_for('storefront'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not full_name or not email or not password:
            flash('Please complete all required fields.', 'warning')
        elif password != confirm_password:
            flash('Passwords do not match.', 'warning')
        else:
            try:
                create_customer_account(full_name, email, password)
                flash('Account created successfully. You can now sign in.', 'success')
                return redirect(url_for('customer_login'))
            except ValueError as exc:
                flash(str(exc), 'danger')

    return render_template('customer_register.html')


@app.route('/customer/login', methods=['GET', 'POST'])
def customer_login():
    if session.get('customer_user'):
        flash('You are already signed in.', 'info')
        return redirect(url_for('storefront'))

    next_url = resolve_next('storefront')
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if not email or not password:
            flash('Enter both email and password.', 'warning')
        else:
            account = fetch_customer_account(email)
            if account and verify_password(account.get('PasswordHash'), password):
                session['customer_user'] = {
                    'id': account.get('Id'),
                    'name': account.get('FullName'),
                    'email': account.get('Email'),
                }
                flash('Welcome back to VVStore.', 'success')
                return redirect(next_url)
            flash('Incorrect email or password.', 'danger')

    return render_template('customer_login.html', next=next_url)


@app.route('/customer/logout')
def customer_logout():
    session.pop('customer_user', None)
    flash('You have signed out successfully.', 'info')
    return redirect(url_for('customer_login'))


@app.route('/storefront')
def storefront():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vanshul_Products")
        products = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        search_query = request.args.get('q', '').strip()
        category_filter = request.args.get('category', '').strip()

        all_products = []
        category_map = defaultdict(list)
        for row in products:
            product = dict(zip(columns, row))
            if product.get('PhotoPaths'):
                try:
                    product['photo_list'] = json.loads(product['PhotoPaths'])
                except json.JSONDecodeError:
                    product['photo_list'] = []
            else:
                product['photo_list'] = []

            if product.get('SalePrice') and product['SalePrice'] < product['SellingPrice']:
                product['discount'] = round(((product['SellingPrice'] - product['SalePrice']) / product['SellingPrice']) * 100, 2)
                product['display_price'] = product['SalePrice']
            else:
                product['discount'] = 0.0
                product['display_price'] = product['SellingPrice']

            product_category = (product.get('Category') or 'General').strip() or 'General'
            category_map[product_category].append(product)
            all_products.append(product)

        def matches_filters(item):
            matches_search = True
            matches_category = True
            if search_query:
                needle = search_query.lower()
                matches_search = (
                    needle in (item.get('ItemName') or '').lower()
                    or needle in (item.get('Category') or '').lower()
                    or needle in (item.get('Supplier') or '').lower()
                )
            if category_filter:
                matches_category = category_filter.lower() == (item.get('Category') or 'General').lower()
            return matches_search and matches_category

        filtered_products = [item for item in all_products if matches_filters(item)]
        total_quantity = sum(item.get('Quantity') or 0 for item in filtered_products)

        featured_categories = []
        for category, items in sorted(category_map.items(), key=lambda entry: len(entry[1]), reverse=True)[:4]:
            sample_product = next((itm for itm in items if itm.get('photo_list')), items[0] if items else None)
            featured_categories.append(
                {
                    'name': category,
                    'count': len(items),
                    'sample_photo': (sample_product.get('photo_list')[0] if sample_product and sample_product.get('photo_list') else None),
                    'sample_id': sample_product.get('Id') if sample_product else None,
                }
            )

        spotlight_product = next((item for item in filtered_products if item.get('photo_list')), filtered_products[0] if filtered_products else None)

        cursor.close()
        conn.close()

        return render_template(
            'storefront.html',
            inventory=filtered_products,
            total_quantity=total_quantity,
            featured_categories=featured_categories,
            spotlight_product=spotlight_product,
            search_query=search_query,
            category_filter=category_filter,
            active_page='storefront',
        )
    except pyodbc.Error as e:
        logger.error(f"Error in storefront route: {e}")
        flash(f"Error loading products: {e}", 'danger')
        return render_template(
            'storefront.html',
            inventory=[],
            total_quantity=0,
            featured_categories=[],
            spotlight_product=None,
            search_query=request.args.get('q', '').strip(),
            category_filter=request.args.get('category', '').strip(),
            active_page='storefront',
        )


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
@customer_login_required
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
@customer_login_required
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
@customer_login_required
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
@customer_login_required
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
@customer_login_required
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
@customer_login_required
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