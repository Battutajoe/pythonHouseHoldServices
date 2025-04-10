from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime
from enum import Enum

db = SQLAlchemy()
bcrypt = Bcrypt()

class OrderStatus(Enum):
    PENDING = "Pending"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    PAID = "Paid"
    FAILED = "Failed"

    @classmethod
    def get_status(cls, status: str):
        """Get the OrderStatus enum from a string value."""
        try:
            return cls(status)
        except ValueError:
            raise ValueError(f"Invalid status: {status}. Must be one of {[s.value for s in cls]}")

class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    _password = db.Column("password", db.String(200), nullable=False)
    role = db.Column(db.String(30), default="user", nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    orders = db.relationship("Order", back_populates="user", lazy="dynamic", cascade="all, delete-orphan")
    cart_items = db.relationship("Cart", back_populates="user", lazy="dynamic", cascade="all, delete-orphan")

    def __init__(self, username: str, password: str, role: str = "user"):
        if not isinstance(username, str) or not username.strip():
            raise ValueError("Username must be a non-empty string")
        if not isinstance(password, str) or not password.strip():
            raise ValueError("Password must be a non-empty string")
        if role not in ["user", "admin"]:
            raise ValueError("Role must be 'user' or 'admin'")
        self.username = username
        self.password = password
        self.role = role

    def verify_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self._password, password)

    @property
    def password(self) -> str:
        raise AttributeError("Password is not readable!")

    @password.setter
    def password(self, password: str):
        self._password = bcrypt.generate_password_hash(password).decode("utf-8")

    def delete(self):
        """Soft delete the user by setting the deleted_at timestamp."""
        self.deleted_at = datetime.utcnow()
        db.session.commit()

    @classmethod
    def query_active(cls):
        """Query only active (non-deleted) users."""
        return cls.query.filter(cls.deleted_at.is_(None))

    def serialize(self) -> dict:
        """Serialize the user object to a dictionary."""
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None
        }

    def serialize_cart(self) -> list:
        """Serialize the user's cart with service details."""
        return [item.serialize_with_service() for item in self.cart_items]

    def serialize_orders(self) -> list:
        """Serialize the user's orders with service details."""
        return [order.serialize_with_service() for order in self.orders]

    def __repr__(self):
        return f"<User id={self.id} username={self.username} role={self.role}>"

class Service(db.Model):
    __tablename__ = "service"
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default="KES", nullable=False)
    description = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    orders = db.relationship("Order", back_populates="service", lazy="dynamic", cascade="all, delete-orphan")
    cart_items = db.relationship("Cart", back_populates="service", lazy="dynamic", cascade="all, delete-orphan")

    def __init__(self, category: str, name: str, price: float, currency: str = "KES", description: str = "", is_active: bool = True):
        if not isinstance(category, str) or not category.strip():
            raise ValueError("Category must be a non-empty string")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Name must be a non-empty string")
        if not isinstance(price, (int, float)) or price < 0:
            raise ValueError("Price must be a non-negative number")
        if not isinstance(currency, str) or len(currency) != 3:
            raise ValueError("Currency must be a 3-character string")
        if not isinstance(description, str):
            raise ValueError("Description must be a string")
        if not isinstance(is_active, bool):
            raise ValueError("is_active must be a boolean")
        self.category = category
        self.name = name
        self.price = float(price)
        self.currency = currency
        self.description = description
        self.is_active = is_active

    def delete(self):
        """Soft delete the service by setting the deleted_at timestamp."""
        self.deleted_at = datetime.utcnow()
        db.session.commit()

    @classmethod
    def query_active(cls):
        """Query only active (non-deleted and active) services."""
        return cls.query.filter(cls.deleted_at.is_(None), cls.is_active.is_(True))

    def serialize(self) -> dict:
        """Serialize the service object to a dictionary."""
        return {
            "id": self.id,
            "category": self.category,
            "name": self.name,
            "price": self.price,
            "currency": self.currency,
            "description": self.description,
            "is_active": self.is_active
        }

    def serialize_for_cart(self) -> dict:
        """Serialize the service for use in the cart."""
        return {
            "id": self.id,
            "name": self.name,
            "price": self.price,
            "currency": self.currency,
            "description": self.description,
            "is_active": self.is_active
        }

    def __repr__(self):
        return f"<Service id={self.id} category={self.category} name={self.name}>"

class Cart(db.Model):
    __tablename__ = "cart"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=False, index=True)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    location = db.Column(db.String(255), nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    user = db.relationship("User", back_populates="cart_items")
    service = db.relationship("Service", back_populates="cart_items")

    def __init__(self, user_id: int, service_id: int, quantity: int, location: str):
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("User ID must be a positive integer")
        if not isinstance(service_id, int) or service_id <= 0:
            raise ValueError("Service ID must be a positive integer")
        if not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("Quantity must be a positive integer")
        if not isinstance(location, str):
            raise ValueError("Location must be a string")
        self.user_id = user_id
        self.service_id = service_id
        self.quantity = quantity
        self.location = location

    def delete(self):
        """Soft delete the cart item by setting the deleted_at timestamp."""
        self.deleted_at = datetime.utcnow()
        db.session.commit()

    @classmethod
    def query_active(cls):
        """Query only active (non-deleted) cart items."""
        return cls.query.filter(cls.deleted_at.is_(None))

    def serialize(self) -> dict:
        """Serialize the cart item to a dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "service_id": self.service_id,
            "quantity": self.quantity,
            "location": self.location,
            "created_at": self.created_at.isoformat(),
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None
        }

    def serialize_with_service(self) -> dict:
        """Serialize the cart item with service details."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "service_id": self.service_id,
            "service_name": self.service.name if self.service else "Unknown Service",
            "price": self.service.price if self.service else 0,
            "currency": self.service.currency if self.service else "KES",
            "quantity": self.quantity,
            "location": self.location,
            "total_price": (self.service.price * self.quantity) if self.service else 0,
            "created_at": self.created_at.isoformat(),
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None
        }

    def __repr__(self):
        return f"<Cart id={self.id} user_id={self.user_id} service_id={self.service_id}>"

class Order(db.Model):
    __tablename__ = "order"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=False, index=True)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    location = db.Column(db.String(255), nullable=False, default="")
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING, index=True)
    checkout_request_id = db.Column(db.String(100), nullable=True, unique=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)
    user = db.relationship("User", back_populates="orders")
    service = db.relationship("Service", back_populates="orders")

    def __init__(self, user_id: int, service_id: int, quantity: int, location: str, total_price: float, status: OrderStatus = OrderStatus.PENDING, checkout_request_id: str = None):
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("User ID must be a positive integer")
        if not isinstance(service_id, int) or service_id <= 0:
            raise ValueError("Service ID must be a positive integer")
        if not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("Quantity must be a positive integer")
        if not isinstance(location, str):
            raise ValueError("Location must be a string")
        if not isinstance(total_price, (int, float)) or total_price < 0:
            raise ValueError("Total price must be non-negative")
        if status not in OrderStatus:
            raise ValueError("Status must be a valid OrderStatus value")
        self.user_id = user_id
        self.service_id = service_id
        self.quantity = quantity
        self.location = location
        self.total_price = float(total_price)
        self.status = status
        self.checkout_request_id = checkout_request_id

    def delete(self):
        """Soft delete the order by setting the deleted_at timestamp."""
        self.deleted_at = datetime.utcnow()
        db.session.commit()

    @classmethod
    def query_active(cls):
        """Query only active (non-deleted) orders."""
        return cls.query.filter(cls.deleted_at.is_(None))

    def serialize(self) -> dict:
        """Serialize the order object to a dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "service_id": self.service_id,
            "quantity": self.quantity,
            "location": self.location,
            "total_price": self.total_price,
            "status": self.status.value,
            "checkout_request_id": self.checkout_request_id,
            "created_at": self.created_at.isoformat(),
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None
        }

    def serialize_with_service(self) -> dict:
        """Serialize the order with service details."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "service_id": self.service_id,
            "service_name": self.service.name if self.service else "Unknown Service",
            "price": self.service.price if self.service else 0,
            "currency": self.service.currency if self.service else "KES",
            "quantity": self.quantity,
            "location": self.location,
            "total_price": self.total_price,
            "status": self.status.value,
            "checkout_request_id": self.checkout_request_id,
            "created_at": self.created_at.isoformat(),
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None
        }

    def __repr__(self):
        return f"<Order id={self.id} user_id={self.user_id} service_id={self.service_id} status={self.status}>"