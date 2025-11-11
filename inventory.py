import pandas as pd
import pyodbc

# 1️⃣ Load your CSV file
csv_path = r"C:\path\to\your\suppliers_data.csv"  # 👈 update this path
data = pd.read_csv(csv_path)

# 2️⃣ Connect to SQL Server
conn = pyodbc.connect(
    'DRIVER={SQL Server};'
    'SERVER=localhost;'          # 👈 change if your server name is different
    'DATABASE=InventoryDB;'
    'Trusted_Connection=yes;'
)

cursor = conn.cursor()

# 3️⃣ Insert each row into the Suppliers table
for index, row in data.iterrows():
    cursor.execute("""
        INSERT INTO Suppliers 
        (supplier_name, contact_person, phone_number, email, address, city, state, postal_code, country)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    row['supplier_name'], row['contact_person'], row['phone_number'],
    row['email'], row['address'], row['city'], row['state'],
    row['postal_code'], row['country'])

conn.commit()
cursor.close()
conn.close()

print("✅ Data successfully inserted into the Suppliers table!")
