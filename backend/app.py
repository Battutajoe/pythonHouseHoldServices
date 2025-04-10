import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
import logging
from datetime import datetime
from marshmallow import Schema, fields, ValidationError
from dotenv import load_dotenv
from flask_socketio import SocketIO
from models import db, User, Order, Service, OrderStatus, Cart  # Add Cart to imports
import requests
import base64
import socket

# Load environment variables
load_dotenv()

# Initialize Flask Extensions
bcrypt = Bcrypt()
jwt = JWTManager()
socketio = SocketIO()

# Configure logging to file
logging.basicConfig(
    filename='app.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def create_app():
    """Flask Application Factory"""
    app = Flask(__name__)

    # Configurations from environment variables
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-for-dev')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///site.db')
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'fallback-jwt-secret')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize Extensions
    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
    socketio.init_app(app, cors_allowed_origins="*")

    # Create database tables and seed initial data
    with app.app_context():
        db.create_all()
        if not User.query.first():
            admin = User(username="admin", password="admin123", role="admin")
            db.session.add(admin)
            db.session.commit()
            logging.info("✅ Admin user seeded successfully")
        # Seed services from populate_services
        from populate_services import populate_services
        populate_services(app)

    return app

# Create App Instance
app = create_app()

# ----------------- SCHEMAS FOR VALIDATION ----------------- #

class RegisterSchema(Schema):
    username = fields.Str(required=True, validate=lambda x: 3 <= len(x) <= 80)
    password = fields.Str(required=True, validate=lambda x: len(x) >= 6)
    role = fields.Str(load_default="user", validate=lambda x: x in ["user", "admin"])

class LoginSchema(Schema):
    username = fields.Str(required=True)
    password = fields.Str(required=True)

class OrderSchema(Schema):
    service_id = fields.Int(required=True)
    quantity = fields.Int(load_default=1, validate=lambda x: x > 0)
    location = fields.Str(load_default="")

class UpdateOrderSchema(Schema):
    status = fields.Str(
        required=True,
        validate=lambda x: x in [status.value for status in OrderStatus]
    )

class ForgotPasswordSchema(Schema):
    email = fields.Str(required=True, validate=lambda x: "@" in x)

class ResetPasswordSchema(Schema):
    token = fields.Str(required=True)
    new_password = fields.Str(required=True, validate=lambda x: len(x) >= 6)

# ----------------- HELPER FUNCTION ----------------- #

def error_response(message, status_code):
    """Return a standardized error response."""
    return jsonify({"error": message}), status_code

# ----------------- AUTHENTICATION ROUTES ----------------- #

@app.route('/api/register', methods=['POST'])
def register():
    """Registers a new user with encrypted password."""
    try:
        data = RegisterSchema().load(request.get_json())
        if User.query_active().filter_by(username=data['username']).first():
            return error_response("Username already exists", 400)

        new_user = User(
            username=data['username'],
            password=data['password'],
            role=data['role']
        )
        db.session.add(new_user)
        db.session.commit()
        logging.info(f"User {data['username']} registered successfully")
        return jsonify({"message": "User registered successfully"}), 201
    except ValidationError as err:
        logging.warning(f"Validation error during registration: {err.messages}")
        return error_response(err.messages, 422)
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error during registration: {str(e)}")
        return error_response("Internal server error", 500)

@app.route('/api/login', methods=['POST'])
def login():
    """Authenticates user and returns a JWT token."""
    try:
        data = LoginSchema().load(request.get_json())
        user = User.query_active().filter_by(username=data['username']).first()
        if not user or not user.verify_password(data['password']):
            return error_response("Invalid credentials", 401)

        access_token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
        logging.info(f"User {data['username']} logged in successfully")
        return jsonify({
            "token": access_token,
            "user_id": user.id
        }), 200
    except ValidationError as err:
        logging.warning(f"Validation error during login: {err.messages}")
        return error_response(err.messages, 422)
    except Exception as e:
        logging.error(f"Error during login: {str(e)}")
        return error_response("Internal server error", 500)

# ----------------- PASSWORD RESET ROUTES ----------------- #

@app.route('/api/forgot-password', methods=['POST'])
def forgot_password():
    """Handles forgot password request."""
    try:
        data = ForgotPasswordSchema().load(request.get_json())
        user = User.query_active().filter_by(email=data['email']).first()
        if not user:
            return error_response("User not found", 404)

        reset_token = create_access_token(identity=str(user.id), expires_delta=False)
        logging.info(f"Password reset token for {user.username}: {reset_token}")
        return jsonify({"message": "Password reset email sent", "token": reset_token}), 200
    except ValidationError as err:
        logging.warning(f"Validation error during forgot password: {err.messages}")
        return error_response(err.messages, 422)
    except Exception as e:
        logging.error(f"Error during forgot password: {str(e)}")
        return error_response("Internal server error", 500)

@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    """Handles password reset request."""
    try:
        data = ResetPasswordSchema().load(request.get_json())
        user_id = get_jwt_identity()
        user = User.query_active().get_or_404(int(user_id))
        user.password = data['new_password']
        db.session.commit()
        logging.info(f"Password reset for user {user.username}")
        return jsonify({"message": "Password reset successfully"}), 200
    except ValidationError as err:
        logging.warning(f"Validation error during reset password: {err.messages}")
        return error_response(err.messages, 422)
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error during reset password: {str(e)}")
        return error_response("Internal server error", 500)

# ----------------- CART ROUTES ----------------- #

@app.route('/api/cart', methods=['POST'])
@jwt_required()
def add_to_cart():
    """Add an item to the user's cart."""
    try:
        user_id = get_jwt_identity()
        data = OrderSchema().load(request.get_json())

        # Check if the service exists
        service = Service.query_active().filter_by(id=data['service_id']).first()
        if not service:
            return error_response("Service not found", 404)

        # Add item to cart
        cart_item = Cart(
            user_id=int(user_id),
            service_id=data['service_id'],
            quantity=data['quantity'],
            location=data['location']
        )
        db.session.add(cart_item)
        db.session.commit()

        # Emit WebSocket event for real-time updates
        socketio.emit("cart_updated", {"message": "Item added to cart", "cart_item": cart_item.serialize_with_service()})

        logging.info(f"Item added to cart for user {user_id}")
        return jsonify({"message": "Item added to cart", "cart_item": cart_item.serialize_with_service()}), 201
    except ValidationError as err:
        logging.warning(f"Validation error in add_to_cart: {err.messages}")
        return error_response(err.messages, 422)
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error adding to cart: {str(e)}")
        return error_response("Internal server error", 500)

@app.route('/api/cart', methods=['GET'])
@jwt_required()
def get_cart():
    """Get all items in the user's cart."""
    try:
        user_id = get_jwt_identity()
        user = User.query_active().filter_by(id=int(user_id)).first()
        if not user:
            return error_response("User not found", 404)

        cart_items = user.serialize_cart()
        return jsonify({"cart": cart_items}), 200
    except Exception as e:
        logging.error(f"Error fetching cart: {str(e)}")
        return error_response("Internal server error", 500)

@app.route('/api/cart/<int:cart_item_id>', methods=['DELETE'])
@jwt_required()
def remove_from_cart(cart_item_id):
    """Remove an item from the user's cart."""
    try:
        user_id = get_jwt_identity()
        cart_item = Cart.query_active().filter_by(id=cart_item_id, user_id=int(user_id)).first()
        if not cart_item:
            return error_response("Cart item not found", 404)

        db.session.delete(cart_item)
        db.session.commit()

        # Emit WebSocket event for real-time updates
        socketio.emit("cart_updated", {"message": "Item removed from cart", "cart_item_id": cart_item_id})

        logging.info(f"Item removed from cart for user {user_id}")
        return jsonify({"message": "Item removed from cart"}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error removing from cart: {str(e)}")
        return error_response("Internal server error", 500)

# ----------------- M-PESA PAYMENT ROUTES ----------------- #

def get_mpesa_access_token():
    """Get M-Pesa API access token."""
    consumer_key = os.getenv("MPESA_CONSUMER_KEY")
    consumer_secret = os.getenv("MPESA_CONSUMER_SECRET")
    
    if not consumer_key or not consumer_secret:
        logging.error("M-Pesa consumer key or secret is missing.")
        raise Exception("M-Pesa consumer key or secret is missing.")
    
    credentials = f"{consumer_key}:{consumer_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()

    headers = {
        "Authorization": f"Basic {encoded_credentials}"
    }
    
    try:
        response = requests.get(
            "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials",
            headers=headers
        )
        response.raise_for_status()
        access_token = response.json().get("access_token")
        if not access_token:
            logging.error("Access token not found in the response.")
            raise Exception("Access token not found in the response.")
        return access_token
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get M-Pesa access token: {str(e)}")
        raise Exception("Failed to get M-Pesa access token")

@app.route('/api/mpesa/payment', methods=['POST'])
@jwt_required()
def mpesa_payment():
    """Handle M-Pesa payment for all items in the cart."""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        phone_number = data.get("phone_number")

        if not phone_number:
            return error_response("Phone number is required", 400)

        # Fetch all items in the user's cart
        cart_items = Cart.query_active().filter_by(user_id=int(user_id)).all()
        if not cart_items:
            return error_response("Cart is empty", 400)

        # Calculate total amount
        total_amount = 0
        for item in cart_items:
            service = Service.query_active().filter_by(id=item.service_id).first()
            if not service:
                return error_response(f"Service {item.service_id} not found", 404)
            total_amount += service.price * item.quantity

        # Initiate M-Pesa payment
        access_token = get_mpesa_access_token()
        shortcode = os.getenv("MPESA_SHORTCODE")
        passkey = os.getenv("MPESA_PASSKEY")
        callback_url = os.getenv("MPESA_CALLBACK_URL", "http://192.168.213.152:5000/api/mpesa/callback")

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(f"{shortcode}{passkey}{timestamp}".encode()).decode()

        payload = {
            "BusinessShortCode": shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": total_amount,
            "PartyA": phone_number,
            "PartyB": shortcode,
            "PhoneNumber": phone_number,
            "CallBackURL": callback_url,
            "AccountReference": f"Cart Payment for User {user_id}",
            "TransactionDesc": "Payment for cart items",
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        logging.debug(f"M-Pesa STK Push payload: {payload}")
        response = requests.post(
            "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers=headers
        )
        if response.status_code != 200:
            raise Exception(f"Failed to initiate STK Push: {response.text}")

        response_data = response.json()

        # Save orders to the database after successful payment initiation
        for item in cart_items:
            order = Order(
                user_id=int(user_id),
                service_id=item.service_id,
                quantity=item.quantity,
                location=item.location,
                total_price=Service.query_active().filter_by(id=item.service_id).first().price * item.quantity,
                status=OrderStatus.PROCESSING,
                checkout_request_id=response_data.get("CheckoutRequestID")
            )
            db.session.add(order)

        # Clear the cart
        Cart.query_active().filter_by(user_id=int(user_id)).delete()
        db.session.commit()

        socketio.emit("order_updated", {"message": "Payment initiated for cart items"})
        return jsonify(response_data), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error in mpesa_payment: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ----------------- SERVICE ROUTES ----------------- #

@app.route('/api/services/<category>', methods=['GET'])
@jwt_required()
def get_services_by_category(category):
    """Fetches services based on category with pagination."""
    try:
        identity = get_jwt_identity()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        if page < 1 or per_page < 1:
            return error_response("Invalid pagination parameters", 400)

        logging.info(f"User {identity} fetching services - category: {category}, page: {page}, per_page: {per_page}")

        services_paginated = Service.query_active().filter_by(category=category).order_by(Service.name.asc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        if not services_paginated.items:
            return jsonify({"services": []}), 200

        services_list = [{"id": s.id, "name": s.name, "price": float(s.price)} for s in services_paginated.items]
        return jsonify({
            "services": services_list,
            "total": services_paginated.total,
            "pages": services_paginated.pages
        }), 200
    except ValueError as ve:
        logging.error(f"ValueError in get_services_by_category: {str(ve)}")
        return error_response("Invalid request parameters", 400)
    except Exception as e:
        logging.error(f"Error fetching services: {str(e)}")
        return error_response("Internal server error", 500)

# ----------------- ORDER ROUTES ----------------- #

@app.route('/api/orders/my', methods=['GET'])
@jwt_required()
def get_user_orders():
    """Fetches orders for the logged-in user with pagination."""
    try:
        user_id = get_jwt_identity()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        logging.info(f"User {user_id} fetching their orders, page: {page}, per_page: {per_page}")

        orders_paginated = Order.query_active().filter_by(user_id=int(user_id)).order_by(Order.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        return jsonify({
            "orders": [order.serialize_with_service() for order in orders_paginated.items],
            "total": orders_paginated.total,
            "pages": orders_paginated.pages
        }), 200
    except ValueError as ve:
        logging.error(f"ValueError in get_user_orders: {str(ve)}")
        return error_response("Invalid request parameters", 400)
    except Exception as e:
        logging.error(f"Error fetching user orders: {str(e)}")
        return error_response("Internal server error", 500)

@app.route('/api/orders', methods=['GET'])
@jwt_required()
def get_orders():
    """Fetches orders based on user role with pagination."""
    try:
        user_id = get_jwt_identity()
        user = User.query_active().filter_by(id=int(user_id)).first()
        if not user:
            return error_response("User not found", 404)

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        logging.info(f"User {user_id} (role: {user.role}) fetching orders, page: {page}, per_page: {per_page}")

        if user.role == 'admin':
            orders_paginated = Order.query_active().order_by(Order.created_at.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )
        else:
            orders_paginated = Order.query_active().filter_by(user_id=int(user_id)).order_by(Order.created_at.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )

        return jsonify({
            "orders": [order.serialize_with_service() for order in orders_paginated.items],
            "total": orders_paginated.total,
            "pages": orders_paginated.pages
        }), 200
    except ValueError as ve:
        logging.error(f"ValueError in get_orders: {str(ve)}")
        return error_response("Invalid request parameters", 400)
    except Exception as e:
        logging.error(f"Error fetching orders: {str(e)}")
        return error_response("Internal server error", 500)

@app.route('/api/orders/<int:order_id>', methods=['PATCH'])
@jwt_required()
def update_order_status(order_id):
    """Admin updates the status of an order."""
    try:
        user_id = get_jwt_identity()
        user = User.query_active().filter_by(id=int(user_id)).first()
        if not user:
            return error_response("User not found", 404)
        if user.role != 'admin':
            return error_response("Unauthorized - Admin access required", 403)

        data = UpdateOrderSchema().load(request.get_json())
        
        order = Order.query_active().filter_by(id=order_id).first()
        if not order:
            return error_response("Order not found", 404)

        order.status = OrderStatus(data['status'])
        db.session.commit()

        socketio.emit("order_updated", order.serialize_with_service())
        logging.info(f"Order {order_id} status updated to {data['status']} by admin {user_id}")
        return jsonify({"message": "Order status updated successfully", "order": order.serialize_with_service()}), 200
    except ValidationError as err:
        logging.warning(f"Validation error in update_order_status: {err.messages}")
        return error_response(err.messages, 422)
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating order status: {str(e)}")
        return error_response("Internal server error", 500)

# ----------------- ADDITIONAL ROUTES ----------------- #

@app.route('/api/server_ip', methods=['GET'])
def get_server_ip():
    """Return the server's current IP for dynamic discovery."""
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        logging.info(f"Server IP requested: {ip}")
        return jsonify({"server_ip": ip}), 200
    except socket.gaierror as e:
        logging.error(f"Failed to get server IP: {str(e)}")
        return error_response("Unable to determine server IP", 500)

@socketio.on('connect')
def handle_connect():
    """Log Socket.IO client connections."""
    logging.info(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    """Log Socket.IO client disconnections."""
    logging.info(f"Client disconnected: {request.sid}")

# ----------------- RUN THE APP ----------------- #

if __name__ == '__main__':
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        logging.info(f"Starting server on {local_ip}:5000")
        socketio.run(app, host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        logging.error(f"Error determining IP: {str(e)}. Falling back to 0.0.0.0:5000")
        socketio.run(app, host='0.0.0.0', port=5000, debug=True)