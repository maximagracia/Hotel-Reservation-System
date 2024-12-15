from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with your secret key for session management
socketio = SocketIO(app)


# Function to get a database connection
def get_db_connection():
    conn = sqlite3.connect('hotel.db')  # Ensure this is your correct database file
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/admin')
def admin():
    if 'logged_in' in session:
        return render_template('admin.html')
    return redirect(url_for('admin_login'))


@app.route('/subscribe', methods=['POST'])
def subscribe():
    email = request.form['email']
    # Add logic to save the email to a database or send it to a mailing list
    return render_template('thankyou.html', email=email)


@app.route('/cancel_booking/<int:booking_id>', methods=['POST'])
def cancel_booking(booking_id):
    try:
        conn = sqlite3.connect('hotel.db', timeout=5)  # Add timeout to avoid locking issues
        cursor = conn.cursor()
        cursor.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
        conn.commit()
        message = "Booking successfully canceled."
    except sqlite3.OperationalError as e:
        message = f"An error occurred: {e}"
    finally:
        conn.close()  # Ensure the connection is closed

    return redirect(url_for('view_guests', message=message))


@app.route('/view_guests')
def view_guests():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Join customers and bookings to display guest information along with bookings
    cursor.execute('''
        SELECT bookings.id, customers.customer_name, customers.email, customers.phone, 
               bookings.check_in, bookings.check_out, bookings.room_type, bookings.status
        FROM bookings
        JOIN customers ON bookings.customer_id = customers.id
    ''')
    guests = cursor.fetchall()
    conn.close()

    message = request.args.get('message')  # Get the message from the query string
    return render_template('view_guests.html', guests=guests, message=message)  # Pass message to template


@app.route('/generate_reports')
def generate_reports():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Calculate active bookings
    cursor.execute("SELECT COUNT(*) FROM bookings WHERE check_out > date('now')")
    active_bookings = cursor.fetchone()[0]

    # Calculate total rooms
    cursor.execute("SELECT COUNT(*) FROM rooms")
    total_rooms = cursor.fetchone()[0]

    # Calculate occupancy rate
    occupancy_rate = (active_bookings / total_rooms * 100) if total_rooms > 0 else 0

    # Calculate total revenue based on room pricing
    cursor.execute('''
        SELECT SUM(r.pricing) 
        FROM bookings b
        JOIN rooms r ON b.room_type = r.ID
    ''')
    total_revenue = cursor.fetchone()[0] or 0  # Handle None case

    conn.close()
    return render_template('generate_reports.html', occupancy_rate=occupancy_rate, total_revenue=total_revenue)


@app.route('/room_price')
def room_price():
    return render_template('room_price.html')


@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == 'POST':
        customer_name = request.form['customer_name']
        feedback_text = request.form['feedback_text']

        # Insert feedback into the database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO feedback (customer_name, feedback_text)
            VALUES (?, ?)
        ''', (customer_name, feedback_text))
        conn.commit()
        conn.close()

        return redirect(url_for('index'))  # Redirect to the home page after submission

    return render_template('feedback.html')  # Show feedback form


@app.route('/view_feedback')
def view_feedback():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Retrieve all feedback from the database
    cursor.execute('SELECT * FROM feedback ORDER BY id DESC')
    feedback_list = cursor.fetchall()

    conn.close()

    return render_template('view_feedback.html', feedback_list=feedback_list)


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None  # Initialize an error variable

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()  # Get the database connection
        cursor = conn.cursor()

        cursor.execute("SELECT passsword FROM admin WHERE username = ?", (username,))
        result = cursor.fetchone()

        if result and password == result[0]:  # Direct comparison without encryption
            session['logged_in'] = True
            return redirect(url_for('admin'))  # Redirect to admin page
        else:
            error = "Invalid credentials"  # Set error message

    return render_template('login.html', error=error)  # Pass the error message to the template


@app.route('/overview')
def overview():
    return render_template('overview.html')


# Room and gallery routes
@app.route('/rooms/single')
def single_room():
    return render_template('single_room.html')


@app.route('/rooms/double')
def double_room():
    return render_template('double_room.html')


@app.route('/rooms/deluxe')
def deluxe_room():
    return render_template('deluxe_room.html')


@app.route('/rooms/suite')
def suite_room():
    return render_template('suite_room.html')


@app.route('/gallery/interior')
def interior():
    return render_template('interior.html')


@app.route('/gallery/exterior')
def exterior():
    return render_template('exterior.html')


@app.route('/gallery/landscape')
def landscape():
    return render_template('landscape.html')


@app.route('/gallery/architecture')
def architecture():
    return render_template('architecture.html')


@app.route('/legals/terms_conditions')
def terms_conditions():
    return render_template('terms_conditions.html')


@app.route('/legals/about')
def about():
    return render_template('about.html')


@app.route('/legals/privacy')
def privacy():
    return render_template('privacy.html')


@app.route('/check_availability', methods=['POST'])
def check_availability():
    check_in_date = request.form['check_in_date']
    check_out_date = request.form['check_out_date']

    # Connect to your SQLite database
    conn = sqlite3.connect('hotel.db')
    cursor = conn.cursor()

    # Check for availability, excluding canceled bookings
    cursor.execute('''
        SELECT * FROM bookings 
        WHERE status = 'booked' AND (
            (check_in <= ? AND check_out >= ?) OR 
            (check_in <= ? AND check_out >= ?) OR 
            (check_in >= ? AND check_out <= ?)
        )
    ''', (check_out_date, check_in_date, check_out_date, check_out_date, check_in_date, check_out_date))

    bookings = cursor.fetchall()
    conn.close()

    if bookings:
        # Dates are already booked
        error_message = "Sorry, the preferred dates are already booked."
        return render_template('index.html', error_message=error_message)
    else:
        # Dates are available, redirect to reservation form
        return redirect(url_for('reservation_form', check_in=check_in_date, check_out=check_out_date))


# Route for reservation form
@app.route('/reservation_form')
def reservation_form():
    check_in = request.args.get('check_in')
    check_out = request.args.get('check_out')
    return render_template('reservation_form.html', check_in=check_in, check_out=check_out)


# Route for handling reservation submission
@app.route('/reserve', methods=['POST'])
def reserve():
    customer_name = request.form['customer_name']
    email = request.form['email']
    phone = request.form['phone']
    check_in_date = request.form['check_in_date']  # Date string (YYYY-MM-DD)
    check_out_date = request.form['check_out_date']  # Date string (YYYY-MM-DD)
    room_type = request.form['room_type']

    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Insert customer into the customers table
    cursor.execute('''
        INSERT INTO customers (customer_name, email, phone)
        VALUES (?, ?, ?)
    ''', (customer_name, email, phone))
    customer_id = cursor.lastrowid  # Get the ID of the newly inserted customer

    # Check for room availability
    cursor.execute('''
        SELECT * FROM bookings
        WHERE room_type = ?
        AND status != 'cancelled'
        AND (check_in BETWEEN ? AND ? OR check_out BETWEEN ? AND ?)
    ''', (room_type, check_in_date, check_out_date, check_in_date, check_out_date))

    existing_booking = cursor.fetchone()

    if existing_booking:
        # Room is already booked for the selected dates, so return an error message
        conn.close()
        return render_template('error.html')  # Or the appropriate page

    # If no overlapping booking, proceed with inserting the new reservation
    cursor.execute('''
        INSERT INTO bookings (customer_id, check_in, check_out, room_type, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (customer_id, check_in_date, check_out_date, room_type, 'confirmed'))

    conn.commit()  # Commit the transaction to save changes
    conn.close()  # Close the connection

    return render_template(
        'success.html',
        guest_name=customer_name,
        email=email,
        phone=phone,
        check_in=check_in_date,
        check_out=check_out_date,
        room_type=room_type
    )


# Route for success page after reservation is made
@app.route('/success')
def success():
    return render_template('success.html')  # Render the success.html template


@app.route('/hotel/search', methods=['GET'])
def search_hotels():
    # Get parameters from the search form
    price_min = request.args.get('price_min', type=float)
    price_max = request.args.get('price_max', type=float)
    guests = request.args.get('guests', type=int)
    room_type = request.args.get('room_type', default='', type=str)  # New parameter for room type
    sort_by = request.args.get('sort_by', default='price_asc', type=str)  # New parameter for sorting

    # Connect to the database
    conn = get_db_connection()

    # Build the base query
    query = "SELECT * FROM rooms WHERE pricing BETWEEN ? AND ? AND guests >= ?"
    params = [price_min, price_max, guests]

    # Add room type filter if specified
    if room_type:
        query += " AND room_type = ?"
        params.append(room_type)

    # Add sorting
    if sort_by == 'price_asc':
        query += " ORDER BY pricing ASC"
    elif sort_by == 'price_desc':
        query += " ORDER BY pricing DESC"
    elif sort_by == 'rating_desc':
        query += " ORDER BY rating DESC"  # Assuming you have a rating column in your database

    # Execute the query with parameters
    available_rooms = conn.execute(query, params).fetchall()
    conn.close()

    # Render the search results page with the available rooms
    return render_template('search_results.html', price_min=price_min, price_max=price_max, guests=guests,
                           rooms=available_rooms)


def get_available_rooms(price_min, price_max, guests):
    # Connect to the SQLite database
    conn = sqlite3.connect('rooms.db')
    cursor = conn.cursor()

    # Query for available rooms based on price range and guest capacity
    cursor.execute("""
        SELECT * FROM rooms
        WHERE room_price BETWEEN ? AND ? AND guests >= ?
    """, (price_min, price_max, guests))

    # Fetch all matching rooms
    available_rooms = cursor.fetchall()

    # Close the connection
    conn.close()

    return available_rooms


if __name__ == '__main__':
    socketio.run(app, debug=True)
