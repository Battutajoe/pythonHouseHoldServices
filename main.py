from kivy.config import Config
from kivy.utils import platform  

# Standard Kivy imports
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.image import Image
from kivy.core.image import Image as CoreImage
from kivy.network.urlrequest import UrlRequest  # For non-blocking HTTP requests
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.resources import resource_add_path
from kivy.logger import Logger as logger

# Standard Python and third-party imports
import os
import json
import requests
from requests import post, get
import socketio
from socketio import Client as SocketIOClient  # Correct
import logging
from functools import partial
import jwt
from jwt import decode
from platform import platform as sys_platform  # Renamed to avoid conflict with kivy.utils.platform
from functools import lru_cache
import configparser
import traceback
from kivy.storage.jsonstore import JsonStore
from threading import Thread


# Conditional imports
print("Starting imports")
# Conditional imports
try:
    if platform == "android":
        from android.permissions import request_permissions, Permission  # type: ignore
        from android.storage import app_storage_path  # type: ignore
        logger.info("Android-specific modules loaded successfully.")
    else:
        logger.info("Running in non-Android environment; using dummy implementations.")
        request_permissions = lambda x: None
        Permission = None
        app_storage_path = lambda: os.getcwd()
except Exception as e:
    logger.error(f"Failed to load Android-specific modules: {str(e)}. Using dummy implementations.")
    request_permissions = lambda x: None
    Permission = None
    app_storage_path = lambda: os.getcwd()

print("Imports completed")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger.info('App: Starting operation...')

# Define the Flask server URL
SERVER_URL = 'http://192.168.213.152:5000'
sio = socketio.Client()

# Logging function
def log(message):
    try:
        print(message)
        logger.info(message)  # Use logger.info for better integration with Kivy's logging system
    except Exception as e:
        logger.error(f"Logging failed: {str(e)}")

log("Starting Kivy app")

# Custom Screen Manager to store token and role
class MyScreenManager(ScreenManager):
    def __init__(self, **kwargs):
        log("Initializing MyScreenManager")
        try:
            super(MyScreenManager, self).__init__(**kwargs)
            self.token = None  # JWT token for authentication
            self.role = None  # User role (user/admin)
            log("MyScreenManager initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing MyScreenManager: {str(e)}", exc_info=True)
            traceback.print_exc()
            raise

log("MyScreenManager class defined")


class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super(LoginScreen, self).__init__(**kwargs)
        self.layout = BoxLayout(orientation="vertical", padding=20, spacing=15)
        
        # Username input
        self.username_input = TextInput(
            hint_text="Enter Username",
            multiline=False,
            size_hint=(1, None),
            height=50
        )
        
        # Password input
        self.password_input = TextInput(
            hint_text="Enter Password",
            password=True,
            multiline=False,
            size_hint=(1, None),
            height=50
        )
        
        # Login button
        self.login_button = Button(
            text="Login",
            size_hint=(1, None),
            height=50,
            background_color=(0, 0.5, 1, 1)
        )
        self.login_button.bind(on_press=self.login_user)
        
        # Message label
        self.message_label = Label(
            text="",
            size_hint=(1, None),
            height=50,
            color=(1, 0, 0, 1)
        )
        
        # Register button
        self.register_button = Button(
            text="Don't have an account? Register",
            size_hint=(1, None),
            height=40
        )
        self.register_button.bind(on_press=self.go_to_register)
        
        # Forgot password button
        self.forgot_password_button = Button(
            text="Forgot Password?",
            size_hint=(1, None),
            height=40
        )
        self.forgot_password_button.bind(on_press=self.go_to_forgot_password)
        
        # Add widgets to layout
        self.layout.add_widget(self.username_input)
        self.layout.add_widget(self.password_input)
        self.layout.add_widget(self.login_button)
        self.layout.add_widget(self.message_label)
        self.layout.add_widget(self.register_button)
        self.layout.add_widget(self.forgot_password_button)
        
        # Add layout to screen
        self.add_widget(self.layout)

    def on_enter(self):
        """Reset fields when entering the screen."""
        self.message_label.text = ""
        self.username_input.text = ""
        self.password_input.text = ""
        logger.info("Entered LoginScreen")

    def login_user(self, instance):
        """Handles user login with non-blocking request."""
        username = self.username_input.text.strip()
        password = self.password_input.text.strip()
        
        if not username or not password:
            self.message_label.text = "⚠ Username and Password are required."
            self.message_label.color = (1, 0, 0, 1)
            logger.warning("Login attempted without username or password")
            return
        
        # Prepare data for login request
        data = {"username": username, "password": password}
        headers = {"Content-Type": "application/json"}
        logger.info(f"Attempting login for {username}")
        self.message_label.text = "🔄 Logging in..."
        self.message_label.color = (0, 1, 0, 1)
        
        # Get the app instance
        app = App.get_running_app()
        if not app:
            logger.error("App instance not available for login")
            self.message_label.text = "⚠ App error. Please restart."
            self.message_label.color = (1, 0, 0, 1)
            return
        
        # Send login request
        UrlRequest(
            url=f'{app.server_url}/api/login',
            req_body=json.dumps(data),
            req_headers=headers,
            on_success=self.on_login_success,
            on_failure=self.on_login_failure,
            on_error=self.on_login_error
        )

    def on_login_success(self, req, result):
        """Handle successful login."""
        token = result.get("token")
        user_id = result.get("user_id")
        
        if not token or not user_id:
            logger.warning("Login failed: No token or user_id received")
            self.message_label.text = "⚠ Invalid login response."
            self.message_label.color = (1, 0, 0, 1)
            return
        
        try:
            # Decode the token to get the user role
            decoded = jwt.decode(token, options={"verify_signature": False})
            role = decoded.get("role", "user")
            
            # Store token and user_id in the app instance
            app = App.get_running_app()
            app.token = token
            app.user_id = user_id
            
            logger.info(f"Login successful for user_id: {user_id}, role: {role}")
            self.message_label.text = "✅ Login successful!"
            self.message_label.color = (0, 1, 0, 1)
            
            # Navigate to the appropriate screen based on role
            Clock.schedule_once(
                lambda dt: setattr(
                    self.manager,
                    "current",
                    "admin_dashboard" if role == "admin" else "home"
                ),
                1
            )
        except jwt.DecodeError as e:
            logger.error(f"Token decode error: {e}")
            self.message_label.text = "⚠ Error decoding token."
            self.message_label.color = (1, 0, 0, 1)

    def on_login_failure(self, req, result):
        """Handle login failure."""
        error = result.get("error", "Invalid credentials")
        logger.warning(f"Login failed: {error}")
        self.message_label.text = f"❌ {error}"
        self.message_label.color = (1, 0, 0, 1)

    def on_login_error(self, req, error):
        """Handle login network error."""
        logger.error(f"Login error: {error}")
        self.message_label.text = f"❌ Server error: {str(error)}"
        self.message_label.color = (1, 0, 0, 1)

    def go_to_register(self, instance):
        """Navigate to register screen."""
        logger.info("Navigating to RegistrationScreen")
        self.manager.current = "register"

    def go_to_forgot_password(self, instance):
        """Navigate to forgot password screen."""
        logger.info("Navigating to ForgotPasswordScreen")
        self.manager.current = "forgot_password"


class RegistrationScreen(Screen):
    def __init__(self, **kwargs):
        super(RegistrationScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=30, spacing=20)
        
        # Username input
        self.username_input = TextInput(
            hint_text="Enter Username",
            multiline=False,
            size_hint=(1, None),
            height=50
        )
        
        # Password input
        self.password_input = TextInput(
            hint_text="Enter Password",
            password=True,
            multiline=False,
            size_hint=(1, None),
            height=50
        )
        
        # Role input
        self.role_input = TextInput(
            hint_text="Role (default: user)",
            multiline=False,
            size_hint=(1, None),
            height=50
        )
        
        # Register button
        self.register_button = Button(
            text="Register",
            size_hint=(1, None),
            height=50,
            background_color=(0, 0.5, 1, 1)
        )
        self.register_button.bind(on_press=self.register_user)
        
        # Message label
        self.message_label = Label(
            text="",
            size_hint=(1, None),
            height=50,
            color=(1, 0, 0, 1)
        )
        
        # Login button
        self.login_button = Button(
            text="Already have an account? Login",
            size_hint=(1, None),
            height=40
        )
        self.login_button.bind(on_press=self.go_to_login)
        
        # Add widgets to layout
        layout.add_widget(self.username_input)
        layout.add_widget(self.password_input)
        layout.add_widget(self.role_input)
        layout.add_widget(self.register_button)
        layout.add_widget(self.message_label)
        layout.add_widget(self.login_button)
        
        # Add layout to screen
        self.add_widget(layout)

    def on_enter(self):
        """Reset fields when entering the screen."""
        self.message_label.text = ""
        self.username_input.text = ""
        self.password_input.text = ""
        self.role_input.text = ""
        logger.info("Entered RegistrationScreen")

    def register_user(self, instance):
        """Handles user registration with non-blocking request."""
        username = self.username_input.text.strip()
        password = self.password_input.text.strip()
        role = self.role_input.text.strip() or 'user'

        if not username or not password:
            self.message_label.text = "⚠ Username and Password are required."
            self.message_label.color = (1, 0, 0, 1)
            logger.warning("Registration attempted without username or password")
            return
        
        if role not in ['user', 'admin']:
            self.message_label.text = "⚠ Role must be 'user' or 'admin'."
            self.message_label.color = (1, 0, 0, 1)
            logger.warning(f"Invalid role provided: {role}")
            return

        # Prepare data for registration request
        data = {'username': username, 'password': password, 'role': role}
        headers = {'Content-Type': 'application/json'}
        logger.info(f"Registering user: {username}, role: {role}")
        self.message_label.text = "🔄 Registering..."
        self.message_label.color = (0, 1, 0, 1)
        
        # Get the app instance
        app = App.get_running_app()
        if not app:
            logger.error("App instance not available for registration")
            self.message_label.text = "⚠ App error. Please restart."
            self.message_label.color = (1, 0, 0, 1)
            return
        
        # Send registration request
        UrlRequest(
            url=f'{app.server_url}/api/register',
            req_body=json.dumps(data),
            req_headers=headers,
            on_success=self.on_register_success,
            on_failure=self.on_register_failure,
            on_error=self.on_register_error
        )

    def on_register_success(self, req, result):
        """Handle successful registration."""
        logger.info("Registration successful")
        self.message_label.text = "✅ Registration successful! Redirecting to login..."
        self.message_label.color = (0, 1, 0, 1)
        Clock.schedule_once(lambda dt: setattr(self.manager, 'current', 'login'), 1)

    def on_register_failure(self, req, result):
        """Handle registration failure."""
        error = result.get('error', 'Registration failed')
        logger.warning(f"Registration failed: {error}")
        self.message_label.text = f"❌ {error}"
        self.message_label.color = (1, 0, 0, 1)

    def on_register_error(self, req, error):
        """Handle registration network error."""
        logger.error(f"Registration error: {error}")
        self.message_label.text = f"❌ Server error: {str(error)}"
        self.message_label.color = (1, 0, 0, 1)

    def go_to_login(self, instance):
        """Navigate to login screen."""
        logger.info("Navigating to LoginScreen")
        self.manager.current = 'login'


class ForgotPasswordScreen(Screen):
    def __init__(self, **kwargs):
        super(ForgotPasswordScreen, self).__init__(**kwargs)
        self.layout = BoxLayout(orientation="vertical", padding=20, spacing=15)
        
        # Email input
        self.email_input = TextInput(
            hint_text="Enter Email",
            multiline=False,
            size_hint=(1, None),
            height=50
        )
        
        # Submit button
        self.submit_button = Button(
            text="Submit",
            size_hint=(1, None),
            height=50,
            background_color=(0, 0.5, 1, 1)
        )
        self.submit_button.bind(on_press=self.submit_forgot_password)
        
        # Message label
        self.message_label = Label(
            text="",
            size_hint=(1, None),
            height=50,
            color=(1, 0, 0, 1)
        )
        
        # Back button
        self.back_button = Button(
            text="Back to Login",
            size_hint=(1, None),
            height=40
        )
        self.back_button.bind(on_press=self.go_back_to_login)
        
        # Add widgets to layout
        self.layout.add_widget(self.email_input)
        self.layout.add_widget(self.submit_button)
        self.layout.add_widget(self.message_label)
        self.layout.add_widget(self.back_button)
        
        # Add layout to screen
        self.add_widget(self.layout)

    def on_enter(self):
        """Reset fields when entering the screen."""
        self.message_label.text = ""
        self.email_input.text = ""
        logger.info("Entered ForgotPasswordScreen")

    def submit_forgot_password(self, instance):
        """Handles forgot password request."""
        email = self.email_input.text.strip()
        
        if not email or '@' not in email:
            self.message_label.text = "⚠ Valid email is required."
            self.message_label.color = (1, 0, 0, 1)
            logger.warning("Forgot password attempted without valid email")
            return
        
        # Prepare data for forgot password request
        data = {"email": email}
        headers = {"Content-Type": "application/json"}
        logger.info(f"Sending forgot password request for {email}")
        self.message_label.text = "🔄 Sending reset link..."
        self.message_label.color = (0, 1, 0, 1)
        
        # Get the app instance
        app = App.get_running_app()
        if not app:
            logger.error("App instance not available for forgot password request")
            self.message_label.text = "⚠ App error. Please restart."
            self.message_label.color = (1, 0, 0, 1)
            return
        
        # Send forgot password request
        UrlRequest(
            url=f'{app.server_url}/api/forgot-password',
            req_body=json.dumps(data),
            req_headers=headers,
            on_success=self.on_forgot_password_success,
            on_failure=self.on_forgot_password_failure,
            on_error=self.on_forgot_password_error
        )

    def on_forgot_password_success(self, req, result):
        """Handle successful forgot password request."""
        logger.info("Forgot password request successful")
        self.message_label.text = "✅ Reset link sent. Check your email (or use token directly)."
        self.message_label.color = (0, 1, 0, 1)
        
        # Optionally navigate to reset password screen with token
        # app = App.get_running_app()
        # app.reset_token = result.get('token')
        # Clock.schedule_once(lambda dt: setattr(self.manager, 'current', 'reset_password'), 1)

    def on_forgot_password_failure(self, req, result):
        """Handle forgot password failure."""
        error = result.get("error", "Failed to send reset link")
        logger.warning(f"Forgot password failed: {error}")
        self.message_label.text = f"❌ {error}"
        self.message_label.color = (1, 0, 0, 1)

    def on_forgot_password_error(self, req, error):
        """Handle forgot password network error."""
        logger.error(f"Forgot password error: {error}")
        self.message_label.text = f"❌ Server error: {str(error)}"
        self.message_label.color = (1, 0, 0, 1)

    def go_back_to_login(self, instance):
        """Navigate back to login screen."""
        logger.info("Navigating back to LoginScreen")
        self.manager.current = "login"


class ResetPasswordScreen(Screen):
    def __init__(self, **kwargs):
        super(ResetPasswordScreen, self).__init__(**kwargs)
        self.layout = BoxLayout(orientation="vertical", padding=20, spacing=15)
        
        # Token input
        self.token_input = TextInput(
            hint_text="Enter Reset Token",
            multiline=False,
            size_hint=(1, None),
            height=50
        )
        
        # New password input
        self.new_password_input = TextInput(
            hint_text="Enter New Password",
            password=True,
            multiline=False,
            size_hint=(1, None),
            height=50
        )
        
        # Confirm new password input
        self.confirm_password_input = TextInput(
            hint_text="Confirm New Password",
            password=True,
            multiline=False,
            size_hint=(1, None),
            height=50
        )
        
        # Submit button
        self.submit_button = Button(
            text="Reset Password",
            size_hint=(1, None),
            height=50,
            background_color=(0, 0.5, 1, 1)
        )
        self.submit_button.bind(on_press=self.submit_reset_password)
        
        # Message label
        self.message_label = Label(
            text="",
            size_hint=(1, None),
            height=50,
            color=(1, 0, 0, 1)
        )
        
        # Back button
        self.back_button = Button(
            text="Back to Login",
            size_hint=(1, None),
            height=40
        )
        self.back_button.bind(on_press=self.go_back_to_login)
        
        # Add widgets to layout
        self.layout.add_widget(self.token_input)
        self.layout.add_widget(self.new_password_input)
        self.layout.add_widget(self.confirm_password_input)
        self.layout.add_widget(self.submit_button)
        self.layout.add_widget(self.message_label)
        self.layout.add_widget(self.back_button)
        
        # Add layout to screen
        self.add_widget(self.layout)

    def on_enter(self):
        """Reset fields when entering the screen."""
        self.message_label.text = ""
        self.token_input.text = ""
        self.new_password_input.text = ""
        self.confirm_password_input.text = ""
        logger.info("Entered ResetPasswordScreen")

    def submit_reset_password(self, instance):
        """Handles reset password request."""
        token = self.token_input.text.strip()
        new_password = self.new_password_input.text.strip()
        confirm_password = self.confirm_password_input.text.strip()
        
        # Validate inputs
        if not token or not new_password or not confirm_password:
            self.message_label.text = "⚠ All fields are required."
            self.message_label.color = (1, 0, 0, 1)
            logger.warning("Reset password attempted with missing fields")
            return
        
        if new_password != confirm_password:
            self.message_label.text = "⚠ Passwords do not match."
            self.message_label.color = (1, 0, 0, 1)
            logger.warning("Reset password attempted with mismatched passwords")
            return
        
        # Prepare data for reset password request
        data = {
            "token": token,
            "new_password": new_password
        }
        headers = {
            "Content-Type": "application/json"
        }
        logger.info(f"Resetting password with token: {token}")
        self.message_label.text = "🔄 Resetting password..."
        self.message_label.color = (0, 1, 0, 1)
        
        # Get the app instance
        app = App.get_running_app()
        if not app:
            logger.error("App instance not available for reset password request")
            self.message_label.text = "⚠ App error. Please restart."
            self.message_label.color = (1, 0, 0, 1)
            return
        
        # Send reset password request
        UrlRequest(
            url=f'{app.server_url}/api/reset-password',
            req_body=json.dumps(data),
            req_headers=headers,
            on_success=self.on_reset_password_success,
            on_failure=self.on_reset_password_failure,
            on_error=self.on_reset_password_error
        )

    def on_reset_password_success(self, req, result):
        """Handle successful reset password request."""
        logger.info("Password reset successful")
        self.message_label.text = "✅ Password reset successfully! Redirecting to login..."
        self.message_label.color = (0, 1, 0, 1)
        Clock.schedule_once(lambda dt: setattr(self.manager, "current", "login"), 1)

    def on_reset_password_failure(self, req, result):
        """Handle reset password failure."""
        error = result.get("error", "Failed to reset password")
        logger.warning(f"Reset password failed: {error}")
        self.message_label.text = f"❌ {error}"
        self.message_label.color = (1, 0, 0, 1)

    def on_reset_password_error(self, req, error):
        """Handle reset password network error."""
        logger.error(f"Reset password error: {error}")
        self.message_label.text = f"❌ Server error: {str(error)}"
        self.message_label.color = (1, 0, 0, 1)

    def go_back_to_login(self, instance):
        """Navigate back to login screen."""
        logger.info("Navigating back to LoginScreen")
        self.manager.current = "login"


class DashboardScreen(Screen):
    def __init__(self, **kwargs):
        super(DashboardScreen, self).__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Welcome message and logout button
        self.message_label = Label(
            text="Welcome to Your Dashboard",
            size_hint=(1, None),
            height=40,
            font_size=18,
            bold=True,
            color=(0, 0, 0, 1)
        )
        self.layout.add_widget(self.message_label)
        
        self.logout_button = Button(
            text="Logout",
            size_hint=(1, None),
            height=40,
            background_color=(0.8, 0.2, 0.2, 1),
            color=(1, 1, 1, 1)
        )
        self.logout_button.bind(on_press=self.logout_user)
        self.layout.add_widget(self.logout_button)
        
        # Fetch services button and services list
        fetch_services_button = Button(
            text="Fetch Available Services",
            size_hint=(1, None),
            height=40,
            background_color=(0.2, 0.6, 0.8, 1),
            color=(1, 1, 1, 1)
        )
        fetch_services_button.bind(on_press=self.fetch_services)
        self.layout.add_widget(fetch_services_button)
        
        self.services_list = GridLayout(cols=1, spacing=10, size_hint_y=None)
        self.services_list.bind(minimum_height=self.services_list.setter('height'))
        scrollview_services = ScrollView(size_hint=(1, 0.4))
        scrollview_services.add_widget(self.services_list)
        self.layout.add_widget(scrollview_services)
        
        # Cart section
        self.cart_label = Label(
            text="Your Cart:",
            size_hint=(1, None),
            height=30,
            font_size=16,
            bold=True,
            color=(0, 0, 0, 1)
        )
        self.layout.add_widget(self.cart_label)
        
        self.cart_list = GridLayout(cols=1, spacing=10, size_hint_y=None)
        self.cart_list.bind(minimum_height=self.cart_list.setter('height'))
        scrollview_cart = ScrollView(size_hint=(1, 0.3))
        scrollview_cart.add_widget(self.cart_list)
        self.layout.add_widget(scrollview_cart)
        
        # Checkout button
        self.checkout_button = Button(
            text="Checkout",
            size_hint=(1, None),
            height=40,
            background_color=(0.2, 0.8, 0.2, 1),
            color=(1, 1, 1, 1)
        )
        self.checkout_button.bind(on_press=self.initiate_payment)
        self.layout.add_widget(self.checkout_button)
        
        # Fetch orders button and orders list
        fetch_orders_button = Button(
            text="Fetch Your Orders",
            size_hint=(1, None),
            height=40,
            background_color=(0.2, 0.6, 0.8, 1),
            color=(1, 1, 1, 1)
        )
        fetch_orders_button.bind(on_press=self.fetch_orders)
        self.layout.add_widget(fetch_orders_button)
        
        self.orders_list = GridLayout(cols=1, spacing=10, size_hint_y=None)
        self.orders_list.bind(minimum_height=self.orders_list.setter('height'))
        scrollview_orders = ScrollView(size_hint=(1, 0.4))
        scrollview_orders.add_widget(self.orders_list)
        self.layout.add_widget(scrollview_orders)
        
        self.add_widget(self.layout)
        
        # Register Socket.IO handler using app-level connection
        try:
            app = App.get_running_app()
            app.sio.on("order_updated", self.handle_order_update)
            logger.info("Initialized DashboardScreen with Socket.IO handler")
        except AttributeError:
            logger.error("Socket.IO not initialized in app. Real-time updates unavailable.")

    def on_enter(self):
        """Fetch services and orders when the screen is entered."""
        app = App.get_running_app()
        self.message_label.text = f"Welcome, User ID: {app.user_id or 'Guest'}"
        logger.info("Entering DashboardScreen")
        Clock.schedule_once(lambda dt: self.fetch_services(None), 0)
        Clock.schedule_once(lambda dt: self.fetch_orders(None), 0)

    def fetch_services(self, instance):
        """Fetch services from the backend."""
        app = App.get_running_app()
        if not app or not app.token:
            self.show_popup("Error", "You are not authorized. Please log in again.")
            logger.warning("No token found for fetch_services")
            self.manager.current = 'login'
            return
        
        self.message_label.text = "🔄 Fetching services..."
        self.message_label.color = (0, 1, 0, 1)
        logger.info("Fetching services")
        
        categories = ["cleaning", "food", "groceries", "fruits", "gardening"]
        self.services_list.clear_widgets()
        for category in categories:
            UrlRequest(
                url=f"{app.server_url}/api/services/{category}",
                req_headers={"Authorization": f"Bearer {app.token}"},
                on_success=partial(self.on_fetch_services_success, category),
                on_failure=self.on_fetch_services_failure,
                on_error=self.on_fetch_services_error
            )

    def on_fetch_services_success(self, category, req, result):
        """Handle successful services fetch."""
        services = result.get("services", [])
        logger.info(f"Fetched services for {category}: {len(services)} items")
        if not services:
            self.display_message(self.services_list, f"No services available for {category}.")
            return
        
        for service in services:
            self.add_service_to_list(service['name'], service['price'], service['id'])
        self.message_label.text = "✅ Services loaded."
        self.message_label.color = (0, 1, 0, 1)

    def add_service_to_list(self, service_name, price, service_id):
        """Add a service to the services list."""
        service_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=40)
        service_box.add_widget(Label(text=f"{service_name}", size_hint=(0.4, 1)))
        service_box.add_widget(Label(text=f"KES {price}", size_hint=(0.3, 1)))
        add_to_cart_button = Button(
            text="Add to Cart",
            size_hint=(0.3, 1),
            background_color=(0.2, 0.8, 0.2, 1),
            color=(1, 1, 1, 1)
        )
        add_to_cart_button.bind(on_press=lambda x: self.add_to_cart(service_id, service_name, price))
        service_box.add_widget(add_to_cart_button)
        self.services_list.add_widget(service_box)

    def add_to_cart(self, service_id, service_name, price):
        """Add a service to the cart."""
        app = App.get_running_app()
        if not app or not app.token:
            self.show_popup("Error", "You must be logged in to add items to the cart.")
            logger.warning("No token found for add_to_cart")
            self.manager.current = 'login'
            return
        
        # Add item to cart
        cart_item = {
            "service_id": service_id,
            "service_name": service_name,
            "price": price,
            "quantity": 1  # Default quantity
        }
        if not hasattr(app, 'cart'):
            app.cart = []
        app.cart.append(cart_item)
        self.update_cart_display()
        self.show_popup("Success", f"✅ {service_name} added to cart!")

    def update_cart_display(self):
        """Update the cart display with current items."""
        self.cart_list.clear_widgets()
        app = App.get_running_app()
        if not hasattr(app, 'cart') or not app.cart:
            self.cart_label.text = "Your Cart: (Empty)"
            return
        
        self.cart_label.text = "Your Cart:"
        total_amount = 0
        for item in app.cart:
            cart_item_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=40)
            cart_item_box.add_widget(Label(text=f"{item['service_name']}", size_hint=(0.4, 1)))
            cart_item_box.add_widget(Label(text=f"KES {item['price']}", size_hint=(0.3, 1)))
            remove_button = Button(
                text="Remove",
                size_hint=(0.3, 1),
                background_color=(0.8, 0.2, 0.2, 1),
                color=(1, 1, 1, 1)
            )
            remove_button.bind(on_press=lambda x, item=item: self.remove_from_cart(item))
            cart_item_box.add_widget(remove_button)
            self.cart_list.add_widget(cart_item_box)
            total_amount += item['price']
        
        # Display total amount
        total_label = Label(
            text=f"Total: KES {total_amount}",
            size_hint=(1, None),
            height=40,
            font_size=16,
            bold=True,
            color=(0, 0, 0, 1)
        )
        self.cart_list.add_widget(total_label)

    def remove_from_cart(self, item):
        """Remove an item from the cart."""
        app = App.get_running_app()
        if hasattr(app, 'cart') and item in app.cart:
            app.cart.remove(item)
            self.update_cart_display()
            self.show_popup("Success", f"✅ {item['service_name']} removed from cart!")

    def initiate_payment(self, instance):
        """Initiate payment for all items in the cart."""
        app = App.get_running_app()
        if not hasattr(app, 'cart') or not app.cart:
            self.show_popup("Error", "Your cart is empty. Add items to proceed.")
            return
        
        # Prepare payment data
        total_amount = sum(item['price'] for item in app.cart)
        phone_number = "254712345678"  # Hardcoded for now; add TextInput in UI for real use
        payment_data = {
            "phone_number": phone_number,
            "amount": str(total_amount),
            "account_reference": f"Cart Payment for User {app.user_id}",
            "transaction_desc": "Payment for cart items"
        }
        headers = {
            "Authorization": f"Bearer {app.token}",
            "Content-Type": "application/json"
        }
        logger.info(f"Initiating payment for cart: {payment_data}")
        UrlRequest(
            url=f"{app.server_url}/api/mpesa/payment",
            req_body=json.dumps(payment_data),
            req_headers=headers,
            on_success=self.on_payment_success,
            on_failure=self.on_payment_failure,
            on_error=self.on_payment_error
        )

    def on_payment_success(self, req, result):
        """Handle successful payment initiation."""
        logger.info(f"Payment initiated successfully: {result}")
        self.show_popup("Success", "✅ Payment initiated! Check your phone to complete it.")
        # Clear the cart after successful payment
        app = App.get_running_app()
        if hasattr(app, 'cart'):
            app.cart = []
        self.update_cart_display()
        self.fetch_orders(None)

    def on_payment_failure(self, req, result):
        """Handle payment initiation failure."""
        error = result.get("error", "Unknown error")
        logger.warning(f"Payment initiation failed: {error}")
        self.show_popup("Error", f"❌ Payment failed: {error}")
        self.message_label.text = "❌ Payment failed."
        self.message_label.color = (1, 0, 0, 1)

    def on_payment_error(self, req, error):
        """Handle payment initiation error."""
        logger.error(f"Error initiating payment: {error}")
        self.show_popup("Error", f"❌ Payment error: {str(error)}")
        self.message_label.text = "❌ Payment error."
        self.message_label.color = (1, 0, 0, 1)

    def fetch_orders(self, instance):
        """Fetch orders for the logged-in user."""
        app = App.get_running_app()
        if not app or not app.token:
            self.show_popup("Error", "You are not authorized. Please log in again.")
            logger.warning("No token found for fetch_orders")
            self.manager.current = 'login'
            return
        
        logger.info("Fetching user orders")
        self.orders_list.clear_widgets()
        UrlRequest(
            url=f"{app.server_url}/api/orders/my",
            req_headers={"Authorization": f"Bearer {app.token}"},
            on_success=self.on_fetch_orders_success,
            on_failure=self.on_fetch_orders_failure,
            on_error=self.on_fetch_orders_error
        )

    def on_fetch_orders_success(self, req, result):
        """Handle successful orders fetch."""
        orders = result if isinstance(result, list) else result.get("orders", [])
        logger.info(f"Fetched {len(orders)} orders")
        self.orders_list.clear_widgets()
        if not orders:
            self.display_message(self.orders_list, "No orders placed yet.")
            return
        
        for order in orders:
            self.add_order_to_list(order)
        self.message_label.text = "✅ Orders loaded."
        self.message_label.color = (0, 1, 0, 1)

    def add_order_to_list(self, order):
        """Add an order to the orders list."""
        order_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=40)
        order_box.add_widget(Label(text=f"ID: {order.get('id', 'N/A')}", size_hint=(0.2, 1)))
        order_box.add_widget(Label(text=f"{order.get('service_name', 'Unknown')}", size_hint=(0.3, 1)))
        order_box.add_widget(Label(text=f"KES {order.get('total_price', '0')}", size_hint=(0.2, 1)))
        order_box.add_widget(Label(text=f"{order.get('status', 'Pending')}", size_hint=(0.3, 1)))
        self.orders_list.add_widget(order_box)

    def handle_order_update(self, data):
        """Handle real-time order updates from WebSocket."""
        logger.info(f"Received order update: {data}")
        self.message_label.text = f"🔄 Order {data.get('order_id')} updated: {data.get('status')}"
        self.message_label.color = (0, 1, 0, 1)
        Clock.schedule_once(lambda dt: self.fetch_orders(None), 0.5)

    def logout_user(self, instance):
        """Log out the user."""
        logger.info("Logging out user")
        app = App.get_running_app()
        app.token = None
        app.user_id = None
        self.manager.current = 'login'

    def display_message(self, widget, message):
        """Display a message in a widget."""
        widget.clear_widgets()
        widget.add_widget(Label(text=message, color=(0.8, 0.2, 0.2, 1)))

    def show_popup(self, title, message):
        """Show a popup with a message."""
        popup_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        popup_label = Label(text=message)
        close_button = Button(
            text="OK",
            size_hint=(1, None),
            height=40,
            background_color=(0.2, 0.6, 0.8, 1),
            color=(1, 1, 1, 1)
        )
        popup_layout.add_widget(popup_label)
        popup_layout.add_widget(close_button)
        popup = Popup(title=title, content=popup_layout, size_hint=(0.7, 0.3))
        close_button.bind(on_press=popup.dismiss)
        popup.open()


class AdminDashboard(Screen):
    def __init__(self, **kwargs):
        super(AdminDashboard, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Dashboard title
        self.message_label = Label(
            text="Admin Dashboard - Manage Orders",
            size_hint=(1, None),
            height=40,
            font_size=18,
            bold=True,
            color=(0, 0, 0, 1)
        )
        layout.add_widget(self.message_label)
        
        # Fetch orders button
        fetch_button = Button(
            text="Fetch All Orders",
            size_hint=(1, None),
            height=50,
            background_color=(0.2, 0.6, 0.8, 1),
            color=(1, 1, 1, 1)
        )
        fetch_button.bind(on_press=self.fetch_orders)
        layout.add_widget(fetch_button)
        
        # Orders list with scroll view
        self.orders_list = GridLayout(cols=1, spacing=10, size_hint_y=None)
        self.orders_list.bind(minimum_height=self.orders_list.setter('height'))
        scrollview = ScrollView(size_hint=(1, 1))
        scrollview.add_widget(self.orders_list)
        layout.add_widget(scrollview)
        
        # Logout button
        logout_button = Button(
            text="Logout",
            size_hint=(1, None),
            height=50,
            background_color=(1, 0, 0, 1),
            color=(1, 1, 1, 1)
        )
        logout_button.bind(on_press=self.logout_user)
        layout.add_widget(logout_button)
        
        self.add_widget(layout)

    def on_enter(self):
        """Fetch orders and register Socket.IO handler when the screen is entered."""
        app = App.get_running_app()
        self.message_label.text = f"Admin Dashboard - User ID: {app.user_id or 'Admin'}"
        logger.info("Entering AdminDashboard")
        
        # Register Socket.IO handler
        if hasattr(app, 'sio'):
            app.sio.on("order_updated", self.handle_order_update)
            logger.info("Socket.IO handler registered for order updates")
        else:
            logger.error("Socket.IO not initialized in app. Real-time updates unavailable.")
        
        # Fetch orders
        Clock.schedule_once(lambda dt: self.fetch_orders(None), 0)

    def fetch_orders(self, instance):
        """Fetch all orders from the backend."""
        app = App.get_running_app()
        if not app or not app.token:
            self.show_popup("Error", "You are not authorized. Please log in again.")
            logger.warning("No token found for fetch_orders")
            self.manager.current = 'login'
            return
        
        self.message_label.text = "🔄 Fetching orders..."
        self.message_label.color = (0, 1, 0, 1)
        logger.info("Fetching all orders")
        self.orders_list.clear_widgets()
        UrlRequest(
            url=f"{app.server_url}/api/orders",
            req_headers={'Authorization': f'Bearer {app.token}'},
            on_success=self.on_fetch_orders_success,
            on_failure=self.on_fetch_orders_failure,
            on_error=self.on_fetch_orders_error
        )

    def on_fetch_orders_success(self, req, result):
        """Handle successful orders fetch."""
        orders = result.get("orders", [])
        logger.info(f"Fetched {len(orders)} orders")
        self.display_orders(orders)
        self.message_label.text = "✅ Orders loaded."
        self.message_label.color = (0, 1, 0, 1)

    def on_fetch_orders_failure(self, req, result):
        """Handle orders fetch failure."""
        error = result.get("error", f"Failed to fetch orders (Status: {req.resp_status})")
        logger.warning(f"Order fetch failed: {error}")
        self.display_message(f"❌ {error}")
        self.message_label.text = "❌ Failed to load orders."
        self.message_label.color = (1, 0, 0, 1)

    def on_fetch_orders_error(self, req, error):
        """Handle orders fetch error."""
        logger.error(f"Error fetching orders: {error}")
        self.display_message(f"❌ Error: {str(error)}")
        self.message_label.text = "❌ Error loading orders."
        self.message_label.color = (1, 0, 0, 1)

    def display_orders(self, orders):
        """Display orders in the orders list."""
        self.orders_list.clear_widgets()
        if not orders:
            self.display_message("No pending orders.")
            return
        
        for order in orders:
            order_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=50)
            order_label = Label(
                text=f"ID: {order['id']} | User: {order.get('user_id', 'Unknown')} | {order.get('service_name', 'Unknown')} | {order['status']}",
                size_hint=(0.6, 1))
            confirm_order_button = Button(
                text="Confirm Order",
                size_hint=(0.2, 1),
                background_color=(0, 1, 0, 1),
                color=(1, 1, 1, 1))
            confirm_order_button.bind(on_press=partial(self.confirm_order, order['id']))
            confirm_payment_button = Button(
                text="Confirm Payment",
                size_hint=(0.2, 1),
                background_color=(0.8, 0.8, 0, 1),
                color=(1, 1, 1, 1))
            confirm_payment_button.bind(on_press=partial(self.confirm_payment, order['id']))
            
            order_box.add_widget(order_label)
            order_box.add_widget(confirm_order_button)
            order_box.add_widget(confirm_payment_button)
            self.orders_list.add_widget(order_box)

    def confirm_order(self, order_id, instance):
        """Confirm an order by updating its status."""
        app = App.get_running_app()
        if not app or not app.token:
            self.show_popup("Error", "You are not authorized. Please log in again.")
            logger.warning("No token found for confirm_order")
            self.manager.current = 'login'
            return
        
        headers = {
            'Authorization': f'Bearer {app.token}',
            'Content-Type': 'application/json'
        }
        data = {"status": "Processing"}
        logger.info(f"Confirming order {order_id}")
        self.message_label.text = f"🔄 Confirming order {order_id}..."
        self.message_label.color = (0, 1, 0, 1)
        
        UrlRequest(
            url=f"{app.server_url}/api/orders/{order_id}",
            req_body=json.dumps(data),
            req_headers=headers,
            method='PATCH',
            on_success=self.on_confirm_order_success,
            on_failure=self.on_confirm_order_failure,
            on_error=self.on_confirm_order_error
        )

    def on_confirm_order_success(self, req, result):
        """Handle successful order confirmation."""
        order_id = result.get('order', {}).get('id', 'unknown')
        logger.info(f"Order {order_id} confirmed successfully")
        self.show_popup("Success", f"Order {order_id} confirmed successfully!")
        self.message_label.text = "✅ Order confirmed."
        self.message_label.color = (0, 1, 0, 1)
        Clock.schedule_once(lambda dt: self.fetch_orders(None), 0.5)

    def on_confirm_order_failure(self, req, result):
        """Handle order confirmation failure."""
        error = result.get("error", f"Failed to confirm order (Status: {req.resp_status})")
        logger.warning(f"Order confirmation failed: {error}")
        self.show_popup("Error", f"❌ {error}")
        self.message_label.text = "❌ Order confirmation failed."
        self.message_label.color = (1, 0, 0, 1)

    def on_confirm_order_error(self, req, error):
        """Handle order confirmation error."""
        logger.error(f"Error confirming order: {error}")
        self.show_popup("Error", f"❌ Error confirming order: {str(error)}")
        self.message_label.text = "❌ Order confirmation error."
        self.message_label.color = (1, 0, 0, 1)

    def confirm_payment(self, order_id, instance):
        """Confirm payment for an order."""
        app = App.get_running_app()
        if not app or not app.token:
            self.show_popup("Error", "You are not authorized. Please log in again.")
            logger.warning("No token found for confirm_payment")
            self.manager.current = 'login'
            return
        
        headers = {
            'Authorization': f'Bearer {app.token}',
            'Content-Type': 'application/json'
        }
        data = {"status": "PAID"}  # Match backend M-Pesa status
        logger.info(f"Confirming payment for order {order_id}")
        self.message_label.text = f"🔄 Confirming payment for order {order_id}..."
        self.message_label.color = (0, 1, 0, 1)
        
        UrlRequest(
            url=f"{app.server_url}/api/orders/{order_id}",
            req_body=json.dumps(data),
            req_headers=headers,
            method='PATCH',
            on_success=self.on_confirm_payment_success,
            on_failure=self.on_confirm_payment_failure,
            on_error=self.on_confirm_payment_error
        )

    def on_confirm_payment_success(self, req, result):
        """Handle successful payment confirmation."""
        order_id = result.get('order', {}).get('id', 'unknown')
        logger.info(f"Payment confirmed for order {order_id}")
        self.show_popup("Success", f"Payment for order {order_id} confirmed successfully!")
        self.message_label.text = "✅ Payment confirmed."
        self.message_label.color = (0, 1, 0, 1)
        Clock.schedule_once(lambda dt: self.fetch_orders(None), 0.5)

    def on_confirm_payment_failure(self, req, result):
        """Handle payment confirmation failure."""
        error = result.get("error", f"Failed to confirm payment (Status: {req.resp_status})")
        logger.warning(f"Payment confirmation failed: {error}")
        self.show_popup("Error", f"❌ {error}")
        self.message_label.text = "❌ Payment confirmation failed."
        self.message_label.color = (1, 0, 0, 1)

    def on_confirm_payment_error(self, req, error):
        """Handle payment confirmation error."""
        logger.error(f"Error confirming payment: {error}")
        self.show_popup("Error", f"❌ Error confirming payment: {str(error)}")
        self.message_label.text = "❌ Payment confirmation error."
        self.message_label.color = (1, 0, 0, 1)

    def handle_order_update(self, data):
        """Handle real-time order updates from WebSocket."""
        if not hasattr(App.get_running_app(), 'sio'):
            logger.warning("Socket.IO not initialized. Skipping order update.")
            return
        logger.info(f"Received order update: {data}")
        self.message_label.text = f"🔄 Order {data.get('order_id')} updated: {data.get('status')}"
        self.message_label.color = (0, 1, 0, 1)
        Clock.schedule_once(lambda dt: self.fetch_orders(None), 0.5)

    def logout_user(self, instance):
        """Log out the admin user."""
        logger.info("Logging out admin user")
        app = App.get_running_app()
        app.token = None
        app.user_id = None
        self.manager.current = 'login'

    def display_message(self, message):
        """Display a message in the orders list."""
        self.orders_list.clear_widgets()
        self.orders_list.add_widget(Label(text=message, size_hint=(1, None), height=40, color=(0.8, 0.2, 0.2, 1)))

    def show_popup(self, title, message):
        """Show a popup with a message."""
        popup_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        popup_label = Label(text=message)
        close_button = Button(
            text="OK",
            size_hint=(1, None),
            height=40,
            background_color=(0.2, 0.6, 0.8, 1),
            color=(1, 1, 1, 1))
        popup_layout.add_widget(popup_label)
        popup_layout.add_widget(close_button)
        popup = Popup(title=title, content=popup_layout, size_hint=(0.7, 0.3))
        close_button.bind(on_press=popup.dismiss)
        popup.open()


class UserDashboard(Screen):
    def __init__(self, **kwargs):
        super(UserDashboard, self).__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Dashboard title
        self.message_label = Label(
            text="User Dashboard",
            size_hint=(1, None),
            height=40,
            font_size=18,
            bold=True,
            color=(0, 0, 0, 1)
        )
        self.layout.add_widget(self.message_label)
        
        # Tabbed panel for services
        self.tabs = TabbedPanel(do_default_tab=False)
        
        # Home tab
        home_tab = TabbedPanelItem(text="Home")
        home_tab.add_widget(self.create_home_layout())
        self.tabs.add_widget(home_tab)
        
        # Service tabs (Cleaning, Food, Groceries, Fruits, Gardening)
        for category in ["cleaning", "food", "groceries", "fruits", "gardening"]:
            tab = TabbedPanelItem(text=category.capitalize())
            tab.add_widget(self.create_service_tab(category))
            self.tabs.add_widget(tab)
        
        self.layout.add_widget(self.tabs)
        
        # Logout button
        logout_button = Button(
            text="Logout",
            size_hint=(1, None),
            height=50,
            background_color=(1, 0, 0, 1),
            color=(1, 1, 1, 1)
        )
        logout_button.bind(on_press=self.logout_user)
        self.layout.add_widget(logout_button)
        
        self.add_widget(self.layout)

        # Initialize cart
        self.cart = []

        # Register Socket.IO handler using app-level connection
        try:
            app = App.get_running_app()
            app.sio.on("order_updated", self.handle_order_update)
            logger.info("Initialized UserDashboard with Socket.IO handler")
        except AttributeError:
            logger.error("Socket.IO not initialized in app. Real-time updates unavailable.")

    def on_enter(self):
        """Update title with user ID and fetch orders on entering the screen."""
        app = App.get_running_app()
        self.message_label.text = f"User Dashboard - ID: {app.user_id or 'Guest'}"
        logger.info("Entering UserDashboard")
        Clock.schedule_once(lambda dt: self.fetch_orders(None), 0)

    def create_home_layout(self):
        """Create the layout for the Home tab."""
        home_layout = BoxLayout(orientation="vertical", spacing=10, padding=10)
        
        # Welcome message
        welcome_label = Label(
            text="Welcome to your dashboard!",
            size_hint=(1, None),
            height=40,
            color=(0, 0, 0, 1)
        )
        home_layout.add_widget(welcome_label)
        
        # Fetch orders button
        fetch_orders_button = Button(
            text="Fetch Your Orders",
            size_hint=(1, None),
            height=50,
            background_color=(0.2, 0.6, 0.8, 1),
            color=(1, 1, 1, 1)
        )
        fetch_orders_button.bind(on_press=self.fetch_orders)
        home_layout.add_widget(fetch_orders_button)
        
        # Orders list with scroll view
        self.orders_list = GridLayout(cols=1, spacing=10, size_hint_y=None)
        self.orders_list.bind(minimum_height=self.orders_list.setter('height'))
        scrollview_orders = ScrollView(size_hint=(1, 0.6))
        scrollview_orders.add_widget(self.orders_list)
        home_layout.add_widget(scrollview_orders)
        
        # Payment and tracking buttons
        payment_button = Button(
            text="Make Full Payment",
            size_hint=(1, None),
            height=50,
            background_color=(0.2, 0.8, 0.2, 1),
            color=(1, 1, 1, 1)
        )
        payment_button.bind(on_press=self.show_payment_popup)
        home_layout.add_widget(payment_button)
        
        track_orders_button = Button(
            text="Track Orders",
            size_hint=(1, None),
            height=50,
            background_color=(0.8, 0.8, 0, 1),
            color=(1, 1, 1, 1)
        )
        track_orders_button.bind(on_press=self.track_orders)
        home_layout.add_widget(track_orders_button)
        
        return home_layout

    def track_orders(self, instance):
        """Fetch and display the user's orders."""
        logger.info("Tracking orders")
        self.fetch_orders(instance)

    def fetch_orders(self, instance):
        """Fetch orders for the logged-in user."""
        app = App.get_running_app()
        if not app or not app.token:
            self.message_label.text = "⚠ You are not authorized. Please log in again."
            self.message_label.color = (1, 0, 0, 1)
            logger.warning("No token found for fetch_orders")
            self.manager.current = 'login'
            return
        
        logger.info("Fetching user orders")
        self.orders_list.clear_widgets()
        UrlRequest(
            url=f"{app.server_url}/api/orders/my",
            req_headers={"Authorization": f"Bearer {app.token}"},
            on_success=self.on_fetch_orders_success,
            on_failure=self.on_fetch_orders_failure,
            on_error=self.on_fetch_orders_error
        )

    def on_fetch_orders_success(self, req, result):
        """Handle successful orders fetch."""
        orders = result.get("orders", [])
        logger.info(f"Fetched {len(orders)} orders")
        self.orders_list.clear_widgets()
        
        if not orders:
            self.message_label.text = "No orders placed yet."
            self.message_label.color = (1, 0, 0, 1)
            return
        
        for order in orders:
            self.add_order_to_list(order)
        
        self.message_label.text = "✅ Orders loaded."
        self.message_label.color = (0, 1, 0, 1)

    def on_fetch_orders_failure(self, req, result):
        """Handle orders fetch failure."""
        error = result.get("error", f"Failed to fetch orders (Status: {req.resp_status})")
        logger.warning(f"Order fetch failed: {error}")
        self.message_label.text = f"❌ {error}"
        self.message_label.color = (1, 0, 0, 1)

    def on_fetch_orders_error(self, req, error):
        """Handle orders fetch error."""
        logger.error(f"Error fetching orders: {error}")
        self.message_label.text = f"❌ Error: {str(error)}"
        self.message_label.color = (1, 0, 0, 1)

    def add_order_to_list(self, order):
        """Add an order to the orders list."""
        order_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=50)
        order_box.add_widget(Label(text=f"ID: {order.get('id', 'Unknown')}", size_hint=(0.2, 1)))
        order_box.add_widget(Label(text=f"{order.get('service_name', 'Unknown')}", size_hint=(0.3, 1)))
        order_box.add_widget(Label(text=f"KES {order.get('total_price', 0)}", size_hint=(0.2, 1)))
        order_box.add_widget(Label(text=f"{order.get('status', 'Pending')}", size_hint=(0.3, 1)))
        self.orders_list.add_widget(order_box)

    def create_service_tab(self, category):
        """Create a tab layout for a specific service category."""
        tab_layout = BoxLayout(orientation="vertical", spacing=10, padding=10)
        
        # Fetch services button
        fetch_button = Button(
            text=f"Fetch {category.capitalize()} Services",
            size_hint=(1, None),
            height=50,
            background_color=(0.2, 0.6, 0.8, 1),
            color=(1, 1, 1, 1)
        )
        fetch_button.bind(on_press=lambda x: self.fetch_services(category))
        tab_layout.add_widget(fetch_button)
        
        # Services list with scroll view
        service_list = GridLayout(cols=1, spacing=10, size_hint_y=None)
        service_list.bind(minimum_height=service_list.setter('height'))
        scrollview_services = ScrollView(size_hint=(1, 0.8))
        scrollview_services.add_widget(service_list)
        setattr(self, f"{category}_services_list", service_list)
        tab_layout.add_widget(scrollview_services)
        
        return tab_layout

    def fetch_services(self, category):
        """Fetch services for a specific category."""
        app = App.get_running_app()
        if not app or not app.token:
            service_list = getattr(self, f"{category}_services_list", None)
            self.display_message(service_list, "⚠ You are not authorized. Please log in again.")
            logger.warning("No token found for fetch_services")
            self.manager.current = 'login'
            return
        
        service_list = getattr(self, f"{category}_services_list", None)
        if service_list is None:
            self.message_label.text = "❌ Service list not found."
            self.message_label.color = (1, 0, 0, 1)
            logger.error(f"Service list missing for {category}")
            return
        
        self.message_label.text = f"🔄 Fetching {category.capitalize()} services..."
        self.message_label.color = (0, 1, 0, 1)
        logger.info(f"Fetching services for {category}")
        service_list.clear_widgets()
        UrlRequest(
            url=f"{app.server_url}/api/services/{category}",
            req_headers={"Authorization": f"Bearer {app.token}"},
            on_success=partial(self.on_fetch_services_success, category, service_list),
            on_failure=self.on_fetch_services_failure,
            on_error=self.on_fetch_services_error
        )

    def on_fetch_services_success(self, category, service_list, req, result):
        """Handle successful services fetch."""
        services = result.get("services", [])
        logger.info(f"Fetched {len(services)} services for {category}")
        service_list.clear_widgets()
        
        if not services:
            self.display_message(service_list, f"No {category} services available.")
            return
        
        for service in services:
            self.add_service_to_list(service['id'], service['name'], service['price'], service_list)
        
        self.message_label.text = f"✅ {category.capitalize()} services loaded."
        self.message_label.color = (0, 1, 0, 1)

    def on_fetch_services_failure(self, req, result):
        """Handle services fetch failure."""
        category = req.url.split('/')[-1]
        service_list = getattr(self, f"{category}_services_list", None)
        error = result.get("error", f"Failed to fetch services (Status: {req.resp_status})")
        logger.warning(f"Service fetch failed for {category}: {error}")
        if service_list:
            self.display_message(service_list, f"❌ {error}")
        self.message_label.text = f"❌ Failed to load {category} services."
        self.message_label.color = (1, 0, 0, 1)

    def on_fetch_services_error(self, req, error):
        """Handle services fetch error."""
        category = req.url.split('/')[-1]
        service_list = getattr(self, f"{category}_services_list", None)
        logger.error(f"Error fetching services for {category}: {error}")
        if service_list:
            self.display_message(service_list, f"❌ Error: {str(error)}")
        self.message_label.text = f"❌ Error loading {category} services."
        self.message_label.color = (1, 0, 0, 1)

    def add_service_to_list(self, service_id, service_name, price, service_list):
        """Add a service to the services list."""
        service_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=50)
        service_box.add_widget(Label(text=f"{service_name} - KES {price}", size_hint=(0.7, 1)))
        
        # Add to cart button
        add_to_cart_button = Button(
            text="Add to Cart",
            size_hint=(0.3, 1),
            background_color=(0, 1, 0, 1),
            color=(1, 1, 1, 1)
        )
        add_to_cart_button.bind(on_press=lambda x: self.add_to_cart(service_id, service_name, price))
        service_box.add_widget(add_to_cart_button)
        
        service_list.add_widget(service_box)

    def add_to_cart(self, service_id, service_name, price):
        """Add a service to the cart."""
        self.cart.append({"service_id": service_id, "service_name": service_name, "price": price})
        self.show_popup("Success", f"Added {service_name} to cart!")
        logger.info(f"Added {service_name} to cart")

    def show_payment_popup(self, instance):
        """Show a popup to collect the user's phone number for full payment."""
        if not self.cart:
            self.show_popup("Error", "Your cart is empty.")
            logger.warning("No items in cart for payment")
            return
        
        total_amount = sum(item["price"] for item in self.cart)
        popup_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        popup_label = Label(text=f"Pay KES {total_amount} for {len(self.cart)} item(s).\nEnter M-Pesa phone number:")
        self.phone_number_input = TextInput(hint_text="e.g., 254712345678", multiline=False)
        confirm_button = Button(
            text="Confirm Payment",
            size_hint=(1, None),
            height=50,
            background_color=(0.2, 0.6, 0.8, 1),
            color=(1, 1, 1, 1)
        )
        confirm_button.bind(on_press=lambda x: self.process_full_payment())
        popup_layout.add_widget(popup_label)
        popup_layout.add_widget(self.phone_number_input)
        popup_layout.add_widget(confirm_button)
        
        self.payment_popup = Popup(title="M-Pesa Payment", content=popup_layout, size_hint=(0.8, 0.4))
        self.payment_popup.open()

    def process_full_payment(self):
        """Process full payment for all items in the cart."""
        phone_number = self.phone_number_input.text.strip()
        if not phone_number or not phone_number.startswith("254") or len(phone_number) != 12:
            self.show_popup("Error", "Please enter a valid M-Pesa phone number (e.g., 254712345678).")
            logger.warning(f"Invalid phone number for payment: {phone_number}")
            return
        
        app = App.get_running_app()
        if not app or not app.token:
            self.show_popup("Error", "You are not authorized. Please log in again.")
            logger.warning("No token found for payment")
            self.manager.current = 'login'
            return
        
        headers = {
            "Authorization": f"Bearer {app.token}",
            "Content-Type": "application/json"
        }
        
        # Calculate total amount
        total_amount = sum(item["price"] for item in self.cart)
        
        data = {
            "phone_number": phone_number,
            "amount": str(total_amount),  # Backend expects string
            "service_ids": [item["service_id"] for item in self.cart],
            "account_reference": f"Payment for {len(self.cart)} items",
            "transaction_desc": f"Full payment for user {app.user_id}"
        }
        logger.info(f"Processing payment: KES {total_amount} for {len(self.cart)} items")
        self.message_label.text = "🔄 Initiating payment..."
        self.message_label.color = (0, 1, 0, 1)
        
        UrlRequest(
            url=f"{app.server_url}/api/mpesa/payment",
            req_body=json.dumps(data),
            req_headers=headers,
            on_success=self.on_full_payment_success,
            on_failure=self.on_full_payment_failure,
            on_error=self.on_full_payment_error
        )
        self.payment_popup.dismiss()

    def on_full_payment_success(self, req, result):
        """Handle successful full payment."""
        logger.info(f"Full payment initiated successfully: {result}")
        self.show_popup("Success", "✅ Payment initiated! Check your phone to complete it.")
        self.cart = []  # Clear cart after payment
        self.message_label.text = "✅ Payment initiated."
        self.message_label.color = (0, 1, 0, 1)
        Clock.schedule_once(lambda dt: self.fetch_orders(None), 0.5)

    def on_full_payment_failure(self, req, result):
        """Handle full payment failure."""
        error_message = result.get("error", f"Failed to initiate payment (Status: {req.resp_status})")
        logger.warning(f"Full payment failed: {error_message}")
        self.show_popup("Error", f"❌ {error_message}")
        self.message_label.text = "❌ Payment failed."
        self.message_label.color = (1, 0, 0, 1)

    def on_full_payment_error(self, req, error):
        """Handle full payment error."""
        logger.error(f"Error initiating payment: {error}")
        self.show_popup("Error", f"❌ Error initiating payment: {str(error)}")
        self.message_label.text = "❌ Payment error."
        self.message_label.color = (1, 0, 0, 1)

    def logout_user(self, instance):
        """Log out the user."""
        logger.info("Logging out user")
        app = App.get_running_app()
        app.token = None
        app.user_id = None
        self.manager.current = 'login'

    def display_message(self, widget, message):
        """Display a message in a widget."""
        if widget:
            widget.clear_widgets()
            widget.add_widget(Label(text=message, size_hint=(1, None), height=40, color=(0.8, 0.2, 0.2, 1)))

    def show_popup(self, title, message):
        """Show a popup with a message."""
        popup_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        popup_label = Label(text=message)
        close_button = Button(
            text="OK",
            size_hint=(1, None),
            height=50,
            background_color=(0.2, 0.6, 0.8, 1),
            color=(1, 1, 1, 1)
        )
        popup_layout.add_widget(popup_label)
        popup_layout.add_widget(close_button)
        popup = Popup(title=title, content=popup_layout, size_hint=(0.8, 0.4))
        close_button.bind(on_press=popup.dismiss)
        popup.open()


class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super(HomeScreen, self).__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', spacing=15, padding=20)
        self._setup_background()
        self._setup_title()
        self._setup_cart_summary()
        self._setup_services()
        self._setup_logout_button()
        self.add_widget(self.layout)
        logger.info("Initialized HomeScreen")

    def _setup_background(self):
        """Set up the background color and rectangle."""
        with self.canvas.before:
            Color(0.1, 0.6, 0.8, 1)  # Light blue background
            self.rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self.update_rect, pos=self.update_rect)

    def _setup_title(self):
        """Set up the title label and cart icon."""
        title_layout = BoxLayout(orientation='horizontal', size_hint=(1, None), height='60dp', spacing=10)
        
        # Title label
        title_label = Label(
            text="🏡 Welcome to Home Services",
            font_size='24sp',
            bold=True,
            size_hint=(0.8, 1),
            color=(0, 0, 0, 1)
        )
        title_layout.add_widget(title_label)

        # Cart icon and button
        cart_button = Button(
            text="🛒 0",  # Initial cart count
            font_size='18sp',
            size_hint=(0.2, 1),
            background_color=(0.9, 0.9, 0.1, 1),
            color=(0, 0, 0, 1)
        )
        cart_button.bind(on_press=self.go_to_cart)
        title_layout.add_widget(cart_button)
        self.cart_button = cart_button  # Store reference to update cart count

        self.layout.add_widget(title_layout)

    def _setup_cart_summary(self):
        """Set up the cart summary section."""
        self.cart_summary = Label(
            text="Cart: 0 items | Total: KES 0",
            font_size='18sp',
            size_hint=(1, None),
            height='40dp',
            color=(0, 0, 0, 1)
        )
        self.layout.add_widget(self.cart_summary)

    def _setup_services(self):
        """Set up the services scroll view and buttons."""
        scroll_view = ScrollView(size_hint=(1, 0.7))
        service_grid = BoxLayout(orientation='vertical', spacing=15, size_hint_y=None)
        service_grid.bind(minimum_height=service_grid.setter('height'))

        services = [
            ("Cleaning Services", "cleaning.png", self.go_to_cleaning),
            ("Food Delivery", "food.png", self.go_to_food),
            ("Groceries Delivery", "groceries.png", self.go_to_groceries),
            ("Fruit Delivery", "fruits.png", self.go_to_fruit),
            ("Gardening Services", "gardening.png", self.go_to_gardening),
        ]

        for service_name, icon, action in services:
            btn_layout = self._create_service_button(service_name, icon, action)
            service_grid.add_widget(btn_layout)

        scroll_view.add_widget(service_grid)
        self.layout.add_widget(scroll_view)

    def _create_service_button(self, service_name, icon, action):
        """Create a service button with an icon and action."""
        btn_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='80dp', padding=10, spacing=15)
        try:
            app = App.get_running_app()
            icon_img = app.load_image(f"assets/{icon}", fallback="assets/icon.png")
            icon_img.size_hint = (None, None)
            icon_img.size = ('60dp', '60dp')
        except Exception as e:
            logger.error(f"Error loading image: {e}")
            icon_img = Image(source="assets/icon.png", size_hint=(None, None), size=('60dp', '60dp'))

        btn = Button(
            text=service_name,
            font_size='18sp',
            size_hint=(1, None),
            height='60dp',
            background_color=(0, 0.6, 0.4, 1),
            color=(1, 1, 1, 1)
        )
        btn.bind(on_press=action)
        btn_layout.add_widget(icon_img)
        btn_layout.add_widget(btn)
        return btn_layout

    def _setup_logout_button(self):
        """Set up the logout button."""
        logout_button = Button(
            text="Logout",
            font_size='18sp',
            size_hint=(1, None),
            height='60dp',
            background_color=(1, 0, 0, 1),
            color=(1, 1, 1, 1)
        )
        logout_button.bind(on_press=self.logout_user)
        self.layout.add_widget(logout_button)

    def on_enter(self):
        """Update UI when entering the screen."""
        logger.info("Entering HomeScreen")
        self.update_cart_summary()

    def update_rect(self, *args):
        """Update background rectangle size and position."""
        self.rect.size = self.size
        self.rect.pos = self.pos

    def update_cart_summary(self):
        """Update the cart summary and cart button."""
        app = App.get_running_app()
        if hasattr(app, 'cart'):
            cart = app.cart
            total_items = len(cart)
            total_amount = sum(item["price"] for item in cart)
            self.cart_summary.text = f"Cart: {total_items} items | Total: KES {total_amount}"
            self.cart_button.text = f"🛒 {total_items}"
        else:
            self.cart_summary.text = "Cart: 0 items | Total: KES 0"
            self.cart_button.text = "🛒 0"

    def go_to_cleaning(self, instance):
        """Navigate to cleaning screen."""
        logger.info("Navigating to cleaning screen")
        self.manager.current = 'cleaning'

    def go_to_food(self, instance):
        """Navigate to food screen."""
        logger.info("Navigating to food screen")
        self.manager.current = 'food'

    def go_to_groceries(self, instance):
        """Navigate to groceries screen."""
        logger.info("Navigating to groceries screen")
        self.manager.current = 'groceries'

    def go_to_fruit(self, instance):
        """Navigate to fruit screen."""
        logger.info("Navigating to fruit screen")
        self.manager.current = 'fruit'

    def go_to_gardening(self, instance):
        """Navigate to gardening screen."""
        logger.info("Navigating to gardening screen")
        self.manager.current = 'gardening'

    def go_to_cart(self, instance):
        """Navigate to cart screen."""
        logger.info("Navigating to cart screen")
        self.manager.current = 'cart'

    def logout_user(self, instance):
        """Log out and redirect to login screen."""
        logger.info("Logging out from HomeScreen")
        app = App.get_running_app()
        app.token = None
        app.user_id = None
        app.cart = []  # Clear cart on logout
        self.manager.current = 'login'


class CleaningScreen(Screen):
    def __init__(self, **kwargs):
        super(CleaningScreen, self).__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=15, spacing=10)
        self.services = []  # Store full service data for mapping name to ID

        self._setup_ui()
        self._setup_socket_io_handler()
        logger.info("Initialized CleaningScreen")

    def _setup_ui(self):
        """Set up the UI components."""
        # Title
        self.layout.add_widget(Label(
            text="🧹 Cleaning Services",
            font_size='22sp',
            bold=True,
            size_hint=(1, None),
            height='50dp',
            color=(0, 0, 0, 1)
        ))

        # Feedback label
        self.feedback_label = Label(
            text="",
            size_hint=(1, None),
            height='30dp',
            color=(1, 0, 0, 1)
        )
        self.layout.add_widget(self.feedback_label)

        # Service selection
        self.layout.add_widget(Label(text="Choose cleaning service:", color=(0, 0, 0, 1)))
        self.service_spinner = Spinner(
            text='Loading Services...',
            values=[],
            size_hint=(None, None),
            size=('250dp', '44dp')
        )
        self.service_spinner.bind(text=self._update_price)
        self.layout.add_widget(self.service_spinner)

        # Price display
        self.price_label = Label(
            text="Price: KES 0",
            font_size='16sp',
            size_hint=(1, None),
            height='30dp',
            color=(0, 0, 0, 1)
        )
        self.layout.add_widget(self.price_label)

        # Location input
        self.layout.add_widget(Label(text="Enter delivery location:", color=(0, 0, 0, 1)))
        self.location_input = TextInput(
            hint_text="Delivery Location",
            multiline=False,
            size_hint=(1, None),
            height='44dp'
        )
        self.layout.add_widget(self.location_input)

        # Quantity input
        self.layout.add_widget(Label(text="Enter quantity:", color=(0, 0, 0, 1)))
        self.quantity_input = TextInput(
            hint_text="1",
            multiline=False,
            input_filter='int',
            size_hint=(1, None),
            height='44dp'
        )
        self.layout.add_widget(self.quantity_input)

        # Add to Cart button
        add_to_cart_button = Button(
            text="Add to Cart",
            background_color=(0.2, 0.6, 0.2, 1),
            color=(1, 1, 1, 1),
            font_size='18sp',
            size_hint=(1, None),
            height='44dp'
        )
        add_to_cart_button.bind(on_press=self._add_to_cart)
        self.layout.add_widget(add_to_cart_button)

        # Cart button
        cart_button = Button(
            text="🛒 Go to Cart",
            background_color=(0.9, 0.9, 0.1, 1),
            color=(0, 0, 0, 1),
            font_size='18sp',
            size_hint=(1, None),
            height='44dp'
        )
        cart_button.bind(on_press=self._go_to_cart)
        self.layout.add_widget(cart_button)

        # Back button
        back_button = Button(
            text="Back to Home",
            background_color=(0.6, 0.2, 0.2, 1),
            color=(1, 1, 1, 1),
            font_size='18sp',
            size_hint=(1, None),
            height='44dp'
        )
        back_button.bind(on_press=self._go_back_home)
        self.layout.add_widget(back_button)

        self.add_widget(self.layout)

    def _setup_socket_io_handler(self):
        """Set up Socket.IO handler for real-time updates."""
        try:
            app = App.get_running_app()
            app.sio.on("order_updated", self._handle_order_update)
            logger.info("Socket.IO handler registered for order updates")
        except AttributeError as e:
            logger.error(f"Socket.IO not initialized: {e}")

    def on_enter(self):
        """Fetch services when entering the screen."""
        logger.info("Entering CleaningScreen")
        self.feedback_label.text = ""
        self.location_input.text = ""
        self.quantity_input.text = "1"
        Clock.schedule_once(lambda dt: self._fetch_services(), 0)

    def _fetch_services(self):
        """Fetch cleaning services from the backend."""
        app = App.get_running_app()
        if not app.token:
            self.feedback_label.text = "⚠ Authentication error. Please log in again."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning("No token found for fetch_services")
            self.manager.current = 'login'
            return

        self.feedback_label.text = "🔄 Loading services..."
        self.feedback_label.color = (0, 1, 0, 1)
        logger.info("Fetching cleaning services")
        UrlRequest(
            url=f'{app.server_url}/api/services/cleaning',
            req_headers={'Authorization': f'Bearer {app.token}'},
            on_success=self._on_fetch_services_success,
            on_failure=self._on_fetch_services_failure,
            on_error=self._on_fetch_services_error
        )

    def _on_fetch_services_success(self, req, result):
        """Handle successful services fetch."""
        self.services = result.get("services", [])
        logger.info(f"Fetched {len(self.services)} cleaning services")
        if not self.services:
            self.feedback_label.text = "No cleaning services available."
            self.feedback_label.color = (1, 0, 0, 1)
            self.service_spinner.text = "No Services"
            self.service_spinner.values = []
            return
        self.service_spinner.values = [service['name'] for service in self.services]
        self.service_spinner.text = "Select Cleaning Service"
        self.feedback_label.text = "✅ Services loaded."
        self.feedback_label.color = (0, 1, 0, 1)

    def _on_fetch_services_failure(self, req, result):
        """Handle services fetch failure."""
        error = result.get("error", f"Failed to fetch services (Status: {req.resp_status})")
        logger.warning(f"Service fetch failed: {error}")
        self.feedback_label.text = f"❌ {error}"
        self.feedback_label.color = (1, 0, 0, 1)

    def _on_fetch_services_error(self, req, error):
        """Handle services fetch error."""
        logger.error(f"Error fetching services: {error}")
        self.feedback_label.text = f"❌ Error: {str(error)}"
        self.feedback_label.color = (1, 0, 0, 1)

    def _update_price(self, spinner, text):
        """Update price label based on selected service."""
        for service in self.services:
            if service['name'] == text:
                self.price_label.text = f"Price: KES {service['price']}"
                logger.info(f"Updated price for {text}: KES {service['price']}")
                break

    def _add_to_cart(self, instance):
        """Add the selected service to the cart."""
        cleaning_service = self.service_spinner.text
        location = self.location_input.text.strip()
        quantity_text = self.quantity_input.text.strip()

        if cleaning_service == "Select Cleaning Service" or cleaning_service == "No Services":
            self.feedback_label.text = "⚠ Please select a cleaning service."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning("No service selected")
            return
        if not location:
            self.feedback_label.text = "⚠ Please enter the delivery location."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning("No location provided")
            return
        if not quantity_text.isdigit() or int(quantity_text) <= 0:
            self.feedback_label.text = "⚠ Quantity must be a positive number."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning("Invalid quantity")
            return

        app = App.get_running_app()
        if not hasattr(app, 'cart'):
            app.cart = []

        service_id = next((s['id'] for s in self.services if s['name'] == cleaning_service), None)
        price = next((s['price'] for s in self.services if s['name'] == cleaning_service), 0)
        if not service_id:
            self.feedback_label.text = "⚠ Service not found."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.error("Service ID not found")
            return

        cart_item = {
            "service_id": service_id,
            "service_name": cleaning_service,
            "price": price * int(quantity_text),
            "quantity": int(quantity_text),
            "location": location
        }
        app.cart.append(cart_item)
        self.feedback_label.text = f"✅ Added {cleaning_service} to cart."
        self.feedback_label.color = (0, 1, 0, 1)
        logger.info(f"Added to cart: {cart_item}")

    def _go_to_cart(self, instance):
        """Navigate to the cart screen."""
        logger.info("Navigating to CartScreen")
        self.manager.current = 'cart'

    def _go_back_home(self, instance):
        """Navigate back to home screen."""
        logger.info("Navigating back to HomeScreen")
        self.manager.current = 'home'

    def _handle_order_update(self, data):
        """Handle real-time order updates from WebSocket."""
        logger.info(f"Received order update: {data}")
        self.feedback_label.text = f"🔄 Order {data.get('order_id')} updated: {data.get('status')}"
        self.feedback_label.color = (0, 1, 0, 1)


class FoodScreen(Screen):
    def __init__(self, **kwargs):
        super(FoodScreen, self).__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=15, spacing=10)
        self.services = []  # Store full service data for mapping name to ID

        self._setup_ui()
        self._setup_socket_io_handler()
        logger.info("Initialized FoodScreen")

    def _setup_ui(self):
        """Set up the UI components."""
        # Title
        self.layout.add_widget(Label(
            text="🍔 Food Delivery",
            font_size='22sp',
            bold=True,
            size_hint=(1, None),
            height='50dp',
            color=(0, 0, 0, 1)
        ))

        # Feedback label
        self.feedback_label = Label(
            text="",
            size_hint=(1, None),
            height='30dp',
            color=(1, 0, 0, 1)
        )
        self.layout.add_widget(self.feedback_label)

        # Service selection
        self.layout.add_widget(Label(text="Choose food item:", color=(0, 0, 0, 1)))
        self.service_spinner = Spinner(
            text='Loading Food Items...',
            values=[],
            size_hint=(None, None),
            size=('250dp', '44dp')
        )
        self.service_spinner.bind(text=self._update_price)
        self.layout.add_widget(self.service_spinner)

        # Price display
        self.price_label = Label(
            text="Price: KES 0",
            font_size='16sp',
            size_hint=(1, None),
            height='30dp',
            color=(0, 0, 0, 1)
        )
        self.layout.add_widget(self.price_label)

        # Quantity input
        self.layout.add_widget(Label(text="Enter quantity:", color=(0, 0, 0, 1)))
        self.quantity_input = TextInput(
            hint_text="1",
            multiline=False,
            input_filter='int',
            size_hint=(1, None),
            height='44dp'
        )
        self.layout.add_widget(self.quantity_input)

        # Location input
        self.layout.add_widget(Label(text="Enter delivery location:", color=(0, 0, 0, 1)))
        self.location_input = TextInput(
            hint_text="Delivery Location",
            multiline=False,
            size_hint=(1, None),
            height='44dp'
        )
        self.layout.add_widget(self.location_input)

        # Add to Cart button
        add_to_cart_button = Button(
            text="Add to Cart",
            background_color=(0.2, 0.6, 0.2, 1),
            color=(1, 1, 1, 1),
            font_size='18sp',
            size_hint=(1, None),
            height='44dp'
        )
        add_to_cart_button.bind(on_press=self._add_to_cart)
        self.layout.add_widget(add_to_cart_button)

        # Cart button
        cart_button = Button(
            text="🛒 Go to Cart",
            background_color=(0.9, 0.9, 0.1, 1),
            color=(0, 0, 0, 1),
            font_size='18sp',
            size_hint=(1, None),
            height='44dp'
        )
        cart_button.bind(on_press=self._go_to_cart)
        self.layout.add_widget(cart_button)

        # Back button
        back_button = Button(
            text="Back to Home",
            background_color=(0.6, 0.2, 0.2, 1),
            color=(1, 1, 1, 1),
            font_size='18sp',
            size_hint=(1, None),
            height='44dp'
        )
        back_button.bind(on_press=self._go_back_home)
        self.layout.add_widget(back_button)

        self.add_widget(self.layout)

    def _setup_socket_io_handler(self):
        """Set up Socket.IO handler for real-time updates."""
        try:
            app = App.get_running_app()
            app.sio.on("order_updated", self._handle_order_update)
            logger.info("Socket.IO handler registered for order updates")
        except AttributeError as e:
            logger.error(f"Socket.IO not initialized: {e}")

    def on_enter(self):
        """Fetch services when entering the screen."""
        logger.info("Entering FoodScreen")
        self.feedback_label.text = ""
        self.location_input.text = ""
        self.quantity_input.text = "1"
        Clock.schedule_once(lambda dt: self._fetch_services(), 0)

    def _fetch_services(self):
        """Fetch food services from the backend."""
        app = App.get_running_app()
        if not app.token:
            self.feedback_label.text = "⚠ Authentication error. Please log in again."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning("No token found for fetch_services")
            self.manager.current = 'login'
            return

        self.feedback_label.text = "🔄 Loading food items..."
        self.feedback_label.color = (0, 1, 0, 1)
        logger.info("Fetching food services")
        UrlRequest(
            url=f'{app.server_url}/api/services/food',
            req_headers={'Authorization': f'Bearer {app.token}'},
            on_success=self._on_fetch_services_success,
            on_failure=self._on_fetch_services_failure,
            on_error=self._on_fetch_services_error
        )

    def _on_fetch_services_success(self, req, result):
        """Handle successful services fetch."""
        self.services = result.get("services", [])
        logger.info(f"Fetched {len(self.services)} food services")
        if not self.services:
            self.feedback_label.text = "No food items available."
            self.feedback_label.color = (1, 0, 0, 1)
            self.service_spinner.text = "No Food Items"
            self.service_spinner.values = []
            return
        self.service_spinner.values = [service['name'] for service in self.services]
        self.service_spinner.text = "Select Food Item"
        self.feedback_label.text = "✅ Food items loaded."
        self.feedback_label.color = (0, 1, 0, 1)

    def _on_fetch_services_failure(self, req, result):
        """Handle services fetch failure."""
        error = result.get("error", f"Failed to fetch food items (Status: {req.resp_status})")
        logger.warning(f"Service fetch failed: {error}")
        self.feedback_label.text = f"❌ {error}"
        self.feedback_label.color = (1, 0, 0, 1)

    def _on_fetch_services_error(self, req, error):
        """Handle services fetch error."""
        logger.error(f"Error fetching food services: {error}")
        self.feedback_label.text = f"❌ Error: {str(error)}"
        self.feedback_label.color = (1, 0, 0, 1)

    def _update_price(self, spinner, text):
        """Update price label based on selected service."""
        for service in self.services:
            if service['name'] == text:
                self.price_label.text = f"Price: KES {service['price']}"
                logger.info(f"Updated price for {text}: KES {service['price']}")
                break

    def _add_to_cart(self, instance):
        """Add the selected food item to the cart."""
        food_service = self.service_spinner.text
        location = self.location_input.text.strip()
        quantity_text = self.quantity_input.text.strip()

        if food_service == "Select Food Item" or food_service == "No Food Items":
            self.feedback_label.text = "⚠ Please select a food item."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning("No food item selected")
            return
        if not location:
            self.feedback_label.text = "⚠ Please enter the delivery location."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning("No location provided")
            return
        if not quantity_text.isdigit() or int(quantity_text) <= 0:
            self.feedback_label.text = "⚠ Quantity must be a positive number."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning("Invalid quantity")
            return

        app = App.get_running_app()
        if not hasattr(app, 'cart'):
            app.cart = []

        service_id = next((s['id'] for s in self.services if s['name'] == food_service), None)
        price = next((s['price'] for s in self.services if s['name'] == food_service), 0)
        if not service_id:
            self.feedback_label.text = "⚠ Food item not found."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.error("Service ID not found")
            return

        cart_item = {
            "service_id": service_id,
            "service_name": food_service,
            "price": price * int(quantity_text),
            "quantity": int(quantity_text),
            "location": location
        }
        app.cart.append(cart_item)
        self.feedback_label.text = f"✅ Added {food_service} to cart."
        self.feedback_label.color = (0, 1, 0, 1)
        logger.info(f"Added to cart: {cart_item}")

    def _go_to_cart(self, instance):
        """Navigate to the cart screen."""
        logger.info("Navigating to CartScreen")
        self.manager.current = 'cart'

    def _go_back_home(self, instance):
        """Navigate back to home screen."""
        logger.info("Navigating back to HomeScreen")
        self.manager.current = 'home'

    def _handle_order_update(self, data):
        """Handle real-time order updates from WebSocket."""
        logger.info(f"Received order update: {data}")
        self.feedback_label.text = f"🔄 Order {data.get('order_id')} updated: {data.get('status')}"
        self.feedback_label.color = (0, 1, 0, 1)


class GroceriesScreen(Screen):
    def __init__(self, **kwargs):
        super(GroceriesScreen, self).__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=15, spacing=10)
        self.services = []  # Store full service data for mapping name to ID

        self._setup_ui()
        self._setup_socket_io_handler()
        logger.info("Initialized GroceriesScreen")

    def _setup_ui(self):
        """Set up the UI components."""
        # Title
        self.layout.add_widget(Label(
            text="🛒 Groceries Delivery",
            font_size='22sp',
            bold=True,
            size_hint=(1, None),
            height='50dp',
            color=(0, 0, 0, 1)
        ))

        # Feedback label
        self.feedback_label = Label(
            text="",
            size_hint=(1, None),
            height='30dp',
            color=(1, 0, 0, 1)
        )
        self.layout.add_widget(self.feedback_label)

        # Service selection
        self.layout.add_widget(Label(text="Choose grocery item:", color=(0, 0, 0, 1)))
        self.service_spinner = Spinner(
            text='Loading Groceries...',
            values=[],
            size_hint=(None, None),
            size=('250dp', '44dp')
        )
        self.service_spinner.bind(text=self._update_price)
        self.layout.add_widget(self.service_spinner)

        # Price display
        self.price_label = Label(
            text="Price: KES 0",
            font_size='16sp',
            size_hint=(1, None),
            height='30dp',
            color=(0, 0, 0, 1)
        )
        self.layout.add_widget(self.price_label)

        # Quantity input
        self.layout.add_widget(Label(text="Enter quantity:", color=(0, 0, 0, 1)))
        self.quantity_input = TextInput(
            hint_text="1",
            multiline=False,
            input_filter='int',
            size_hint=(1, None),
            height='44dp'
        )
        self.layout.add_widget(self.quantity_input)

        # Location input
        self.layout.add_widget(Label(text="Enter delivery location:", color=(0, 0, 0, 1)))
        self.location_input = TextInput(
            hint_text="Delivery Location",
            multiline=False,
            size_hint=(1, None),
            height='44dp'
        )
        self.layout.add_widget(self.location_input)

        # Add to Cart button
        add_to_cart_button = Button(
            text="Add to Cart",
            background_color=(0.2, 0.6, 0.2, 1),
            color=(1, 1, 1, 1),
            font_size='18sp',
            size_hint=(1, None),
            height='44dp'
        )
        add_to_cart_button.bind(on_press=self._add_to_cart)
        self.layout.add_widget(add_to_cart_button)

        # Cart button
        cart_button = Button(
            text="🛒 Go to Cart",
            background_color=(0.9, 0.9, 0.1, 1),
            color=(0, 0, 0, 1),
            font_size='18sp',
            size_hint=(1, None),
            height='44dp'
        )
        cart_button.bind(on_press=self._go_to_cart)
        self.layout.add_widget(cart_button)

        # Back button
        back_button = Button(
            text="Back to Home",
            background_color=(0.6, 0.2, 0.2, 1),
            color=(1, 1, 1, 1),
            font_size='18sp',
            size_hint=(1, None),
            height='44dp'
        )
        back_button.bind(on_press=self._go_back_home)
        self.layout.add_widget(back_button)

        self.add_widget(self.layout)

    def _setup_socket_io_handler(self):
        """Set up Socket.IO handler for real-time updates."""
        try:
            app = App.get_running_app()
            app.sio.on("order_updated", self._handle_order_update)
            logger.info("Socket.IO handler registered for order updates")
        except AttributeError as e:
            logger.error(f"Socket.IO not initialized: {e}")

    def on_enter(self):
        """Fetch services when entering the screen."""
        logger.info("Entering GroceriesScreen")
        self.feedback_label.text = ""
        self.location_input.text = ""
        self.quantity_input.text = "1"
        Clock.schedule_once(lambda dt: self._fetch_services(), 0)

    def _fetch_services(self):
        """Fetch grocery services from the backend."""
        app = App.get_running_app()
        if not app.token:
            self.feedback_label.text = "⚠ Authentication error. Please log in again."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning("No token found for fetch_services")
            self.manager.current = 'login'
            return

        self.feedback_label.text = "🔄 Loading groceries..."
        self.feedback_label.color = (0, 1, 0, 1)
        logger.info("Fetching grocery services")
        UrlRequest(
            url=f'{app.server_url}/api/services/groceries',
            req_headers={'Authorization': f'Bearer {app.token}'},
            on_success=self._on_fetch_services_success,
            on_failure=self._on_fetch_services_failure,
            on_error=self._on_fetch_services_error
        )

    def _on_fetch_services_success(self, req, result):
        """Handle successful services fetch."""
        self.services = result.get("services", [])
        logger.info(f"Fetched {len(self.services)} grocery services")
        if not self.services:
            self.feedback_label.text = "No grocery items available."
            self.feedback_label.color = (1, 0, 0, 1)
            self.service_spinner.text = "No Groceries"
            self.service_spinner.values = []
            return
        self.service_spinner.values = [service['name'] for service in self.services]
        self.service_spinner.text = "Select Grocery Item"
        self.feedback_label.text = "✅ Groceries loaded."
        self.feedback_label.color = (0, 1, 0, 1)

    def _on_fetch_services_failure(self, req, result):
        """Handle services fetch failure."""
        error = result.get("error", f"Failed to fetch groceries (Status: {req.resp_status})")
        logger.warning(f"Service fetch failed: {error}")
        self.feedback_label.text = f"❌ {error}"
        self.feedback_label.color = (1, 0, 0, 1)

    def _on_fetch_services_error(self, req, error):
        """Handle services fetch error."""
        logger.error(f"Error fetching grocery services: {error}")
        self.feedback_label.text = f"❌ Error: {str(error)}"
        self.feedback_label.color = (1, 0, 0, 1)

    def _update_price(self, spinner, text):
        """Update price label based on selected service."""
        for service in self.services:
            if service['name'] == text:
                self.price_label.text = f"Price: KES {service['price']}"
                logger.info(f"Updated price for {text}: KES {service['price']}")
                break

    def _add_to_cart(self, instance):
        """Add the selected grocery item to the cart."""
        grocery_service = self.service_spinner.text
        location = self.location_input.text.strip()
        quantity_text = self.quantity_input.text.strip()

        if grocery_service == "Select Grocery Item" or grocery_service == "No Groceries":
            self.feedback_label.text = "⚠ Please select a grocery item."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning("No grocery item selected")
            return
        if not location:
            self.feedback_label.text = "⚠ Please enter the delivery location."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning("No location provided")
            return
        if not quantity_text.isdigit() or int(quantity_text) <= 0:
            self.feedback_label.text = "⚠ Quantity must be a positive number."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning("Invalid quantity")
            return

        app = App.get_running_app()
        if not hasattr(app, 'cart'):
            app.cart = []

        service_id = next((s['id'] for s in self.services if s['name'] == grocery_service), None)
        price = next((s['price'] for s in self.services if s['name'] == grocery_service), 0)
        if not service_id:
            self.feedback_label.text = "⚠ Grocery item not found."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.error("Service ID not found")
            return

        cart_item = {
            "service_id": service_id,
            "service_name": grocery_service,
            "price": price * int(quantity_text),
            "quantity": int(quantity_text),
            "location": location
        }
        app.cart.append(cart_item)
        self.feedback_label.text = f"✅ Added {grocery_service} to cart."
        self.feedback_label.color = (0, 1, 0, 1)
        logger.info(f"Added to cart: {cart_item}")

    def _go_to_cart(self, instance):
        """Navigate to the cart screen."""
        logger.info("Navigating to CartScreen")
        self.manager.current = 'cart'

    def _go_back_home(self, instance):
        """Navigate back to home screen."""
        logger.info("Navigating back to HomeScreen")
        self.manager.current = 'home'

    def _handle_order_update(self, data):
        """Handle real-time order updates from WebSocket."""
        logger.info(f"Received grocery order update: {data}")
        self.feedback_label.text = f"🔄 Order {data.get('order_id')} updated: {data.get('status')}"
        self.feedback_label.color = (0, 1, 0, 1)


class FruitScreen(Screen):
    def __init__(self, **kwargs):
        super(FruitScreen, self).__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=15, spacing=10)
        self.services = []  # Store full service data for mapping name to ID

        self._setup_ui()
        self._setup_socket_io_handler()
        logger.info("Initialized FruitScreen")

    def _setup_ui(self):
        """Set up the UI components."""
        # Title
        self.layout.add_widget(Label(
            text="🍎 Fruit Delivery",
            font_size='22sp',
            bold=True,
            size_hint=(1, None),
            height='50dp',
            color=(0, 0, 0, 1)
        ))

        # Feedback label
        self.feedback_label = Label(
            text="",
            size_hint=(1, None),
            height='30dp',
            color=(1, 0, 0, 1)
        )
        self.layout.add_widget(self.feedback_label)

        # Service selection
        self.layout.add_widget(Label(text="Choose fruit:", color=(0, 0, 0, 1)))
        self.service_spinner = Spinner(
            text='Loading Fruits...',
            values=[],
            size_hint=(None, None),
            size=('250dp', '44dp')
        )
        self.service_spinner.bind(text=self._update_price)
        self.layout.add_widget(self.service_spinner)

        # Price display
        self.price_label = Label(
            text="Price: KES 0",
            font_size='16sp',
            size_hint=(1, None),
            height='30dp',
            color=(0, 0, 0, 1)
        )
        self.layout.add_widget(self.price_label)

        # Quantity input
        self.layout.add_widget(Label(text="Enter quantity:", color=(0, 0, 0, 1)))
        self.quantity_input = TextInput(
            hint_text="1",
            multiline=False,
            input_filter='int',
            size_hint=(1, None),
            height='44dp'
        )
        self.layout.add_widget(self.quantity_input)

        # Location input
        self.layout.add_widget(Label(text="Enter delivery location:", color=(0, 0, 0, 1)))
        self.location_input = TextInput(
            hint_text="Delivery Location",
            multiline=False,
            size_hint=(1, None),
            height='44dp'
        )
        self.layout.add_widget(self.location_input)

        # Add to Cart button
        add_to_cart_button = Button(
            text="Add to Cart",
            background_color=(0.2, 0.6, 0.2, 1),
            color=(1, 1, 1, 1),
            font_size='18sp',
            size_hint=(1, None),
            height='44dp'
        )
        add_to_cart_button.bind(on_press=self._add_to_cart)
        self.layout.add_widget(add_to_cart_button)

        # Cart button
        cart_button = Button(
            text="🛒 Go to Cart",
            background_color=(0.9, 0.9, 0.1, 1),
            color=(0, 0, 0, 1),
            font_size='18sp',
            size_hint=(1, None),
            height='44dp'
        )
        cart_button.bind(on_press=self._go_to_cart)
        self.layout.add_widget(cart_button)

        # Back button
        back_button = Button(
            text="Back to Home",
            background_color=(0.6, 0.2, 0.2, 1),
            color=(1, 1, 1, 1),
            font_size='18sp',
            size_hint=(1, None),
            height='44dp'
        )
        back_button.bind(on_press=self._go_back_home)
        self.layout.add_widget(back_button)

        self.add_widget(self.layout)

    def _setup_socket_io_handler(self):
        """Set up Socket.IO handler for real-time updates."""
        try:
            app = App.get_running_app()
            app.sio.on("order_updated", self._handle_order_update)
            logger.info("Socket.IO handler registered for order updates")
        except AttributeError as e:
            logger.error(f"Socket.IO not initialized: {e}")

    def on_enter(self):
        """Fetch services when entering the screen."""
        logger.info("Entering FruitScreen")
        self.feedback_label.text = ""
        self.location_input.text = ""
        self.quantity_input.text = "1"
        Clock.schedule_once(lambda dt: self._fetch_services(), 0)

    def _fetch_services(self):
        """Fetch fruit services from the backend."""
        app = App.get_running_app()
        if not app.token:
            self.feedback_label.text = "⚠ Authentication error. Please log in again."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning("No token found for fetch_services")
            self.manager.current = 'login'
            return

        self.feedback_label.text = "🔄 Loading fruits..."
        self.feedback_label.color = (0, 1, 0, 1)
        logger.info("Fetching fruit services")
        UrlRequest(
            url=f'{app.server_url}/api/services/fruits',
            req_headers={'Authorization': f'Bearer {app.token}'},
            on_success=self._on_fetch_services_success,
            on_failure=self._on_fetch_services_failure,
            on_error=self._on_fetch_services_error
        )

    def _on_fetch_services_success(self, req, result):
        """Handle successful services fetch."""
        self.services = result.get("services", [])
        logger.info(f"Fetched {len(self.services)} fruit services")
        if not self.services:
            self.feedback_label.text = "No fruits available."
            self.feedback_label.color = (1, 0, 0, 1)
            self.service_spinner.text = "No Fruits"
            self.service_spinner.values = []
            return
        self.service_spinner.values = [service['name'] for service in self.services]
        self.service_spinner.text = "Select Fruit"
        self.feedback_label.text = "✅ Fruits loaded."
        self.feedback_label.color = (0, 1, 0, 1)

    def _on_fetch_services_failure(self, req, result):
        """Handle services fetch failure."""
        error = result.get("error", f"Failed to fetch fruits (Status: {req.resp_status})")
        logger.warning(f"Service fetch failed: {error}")
        self.feedback_label.text = f"❌ {error}"
        self.feedback_label.color = (1, 0, 0, 1)

    def _on_fetch_services_error(self, req, error):
        """Handle services fetch error."""
        logger.error(f"Error fetching fruit services: {error}")
        self.feedback_label.text = f"❌ Error: {str(error)}"
        self.feedback_label.color = (1, 0, 0, 1)

    def _update_price(self, spinner, text):
        """Update price label based on selected service."""
        for service in self.services:
            if service['name'] == text:
                self.price_label.text = f"Price: KES {service['price']}"
                logger.info(f"Updated price for {text}: KES {service['price']}")
                break

    def _add_to_cart(self, instance):
        """Add the selected fruit to the cart."""
        fruit_service = self.service_spinner.text
        location = self.location_input.text.strip()
        quantity_text = self.quantity_input.text.strip()

        if fruit_service == "Select Fruit" or fruit_service == "No Fruits":
            self.feedback_label.text = "⚠ Please select a fruit."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning("No fruit selected")
            return
        if not location:
            self.feedback_label.text = "⚠ Please enter the delivery location."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning("No location provided")
            return
        if not quantity_text.isdigit() or int(quantity_text) <= 0:
            self.feedback_label.text = "⚠ Quantity must be a positive number."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning("Invalid quantity")
            return

        app = App.get_running_app()
        if not hasattr(app, 'cart'):
            app.cart = []

        service_id = next((s['id'] for s in self.services if s['name'] == fruit_service), None)
        price = next((s['price'] for s in self.services if s['name'] == fruit_service), 0)
        if not service_id:
            self.feedback_label.text = "⚠ Fruit not found."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.error("Service ID not found")
            return

        cart_item = {
            "service_id": service_id,
            "service_name": fruit_service,
            "price": price * int(quantity_text),
            "quantity": int(quantity_text),
            "location": location
        }
        app.cart.append(cart_item)
        self.feedback_label.text = f"✅ Added {fruit_service} to cart."
        self.feedback_label.color = (0, 1, 0, 1)
        logger.info(f"Added to cart: {cart_item}")

    def _go_to_cart(self, instance):
        """Navigate to the cart screen."""
        logger.info("Navigating to CartScreen")
        self.manager.current = 'cart'

    def _go_back_home(self, instance):
        """Navigate back to home screen."""
        logger.info("Navigating back to HomeScreen")
        self.manager.current = 'home'

    def _handle_order_update(self, data):
        """Handle real-time order updates from WebSocket."""
        logger.info(f"Received fruit order update: {data}")
        self.feedback_label.text = f"🔄 Order {data.get('order_id')} updated: {data.get('status')}"
        self.feedback_label.color = (0, 1, 0, 1)


class GardeningScreen(Screen):
    def __init__(self, **kwargs):
        super(GardeningScreen, self).__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=15, spacing=10)
        self.services = []  # Store full service data for mapping name to ID

        self._setup_ui()
        self._setup_socket_io_handler()
        logger.info("Initialized GardeningScreen")

    def _setup_ui(self):
        """Set up the UI components."""
        # Title
        self.layout.add_widget(Label(
            text="🌿 Gardening Services",
            font_size='22sp',
            bold=True,
            size_hint=(1, None),
            height='50dp',
            color=(0, 0, 0, 1)
        ))

        # Feedback label
        self.feedback_label = Label(
            text="",
            size_hint=(1, None),
            height='30dp',
            color=(1, 0, 0, 1)
        )
        self.layout.add_widget(self.feedback_label)

        # Service selection
        self.layout.add_widget(Label(text="Choose a service:", color=(0, 0, 0, 1)))
        self.service_spinner = Spinner(
            text='Loading Services...',
            values=[],
            size_hint=(None, None),
            size=('250dp', '44dp')
        )
        self.service_spinner.bind(text=self._update_price)
        self.layout.add_widget(self.service_spinner)

        # Price display
        self.price_label = Label(
            text="Price: KES 0",
            font_size='16sp',
            size_hint=(1, None),
            height='30dp',
            color=(0, 0, 0, 1)
        )
        self.layout.add_widget(self.price_label)

        # Quantity input
        self.layout.add_widget(Label(text="Enter quantity:", color=(0, 0, 0, 1)))
        self.quantity_input = TextInput(
            hint_text="1",
            multiline=False,
            input_filter='int',
            size_hint=(1, None),
            height='44dp'
        )
        self.layout.add_widget(self.quantity_input)

        # Location input
        self.layout.add_widget(Label(text="Enter delivery location:", color=(0, 0, 0, 1)))
        self.location_input = TextInput(
            hint_text="Delivery Location",
            multiline=False,
            size_hint=(1, None),
            height='44dp'
        )
        self.layout.add_widget(self.location_input)

        # Add to Cart button
        add_to_cart_button = Button(
            text="Add to Cart",
            background_color=(0.2, 0.6, 0.2, 1),
            color=(1, 1, 1, 1),
            font_size='18sp',
            size_hint=(1, None),
            height='44dp'
        )
        add_to_cart_button.bind(on_press=self._add_to_cart)
        self.layout.add_widget(add_to_cart_button)

        # Cart button
        cart_button = Button(
            text="🛒 Go to Cart",
            background_color=(0.9, 0.9, 0.1, 1),
            color=(0, 0, 0, 1),
            font_size='18sp',
            size_hint=(1, None),
            height='44dp'
        )
        cart_button.bind(on_press=self._go_to_cart)
        self.layout.add_widget(cart_button)

        # Back button
        back_button = Button(
            text="Back to Home",
            background_color=(0.6, 0.2, 0.2, 1),
            color=(1, 1, 1, 1),
            font_size='18sp',
            size_hint=(1, None),
            height='44dp'
        )
        back_button.bind(on_press=self._go_back_home)
        self.layout.add_widget(back_button)

        self.add_widget(self.layout)

    def _setup_socket_io_handler(self):
        """Set up Socket.IO handler for real-time updates."""
        try:
            app = App.get_running_app()
            app.sio.on("order_updated", self._handle_order_update)
            logger.info("Socket.IO handler registered for order updates")
        except AttributeError as e:
            logger.error(f"Socket.IO not initialized: {e}")

    def on_enter(self):
        """Fetch services when entering the screen."""
        logger.info("Entering GardeningScreen")
        self.feedback_label.text = ""
        self.location_input.text = ""
        self.quantity_input.text = "1"
        Clock.schedule_once(lambda dt: self._fetch_services(), 0)

    def _fetch_services(self):
        """Fetch gardening services from the backend."""
        app = App.get_running_app()
        if not app.token:
            self.feedback_label.text = "⚠ Authentication error. Please log in again."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning("No token found for fetch_services")
            self.manager.current = 'login'
            return

        self.feedback_label.text = "🔄 Loading services..."
        self.feedback_label.color = (0, 1, 0, 1)
        logger.info("Fetching gardening services")
        UrlRequest(
            url=f'{app.server_url}/api/services/gardening',
            req_headers={'Authorization': f'Bearer {app.token}'},
            on_success=self._on_fetch_services_success,
            on_failure=self._on_fetch_services_failure,
            on_error=self._on_fetch_services_error
        )

    def _on_fetch_services_success(self, req, result):
        """Handle successful services fetch."""
        self.services = result.get("services", [])
        logger.info(f"Fetched {len(self.services)} gardening services")
        if not self.services:
            self.feedback_label.text = "No gardening services available."
            self.feedback_label.color = (1, 0, 0, 1)
            self.service_spinner.text = "No Services"
            self.service_spinner.values = []
            return
        self.service_spinner.values = [service['name'] for service in self.services]
        self.service_spinner.text = "Select Service"
        self.feedback_label.text = "✅ Services loaded."
        self.feedback_label.color = (0, 1, 0, 1)

    def _on_fetch_services_failure(self, req, result):
        """Handle services fetch failure."""
        error = result.get("error", f"Failed to fetch services (Status: {req.resp_status})")
        logger.warning(f"Service fetch failed: {error}")
        self.feedback_label.text = f"❌ {error}"
        self.feedback_label.color = (1, 0, 0, 1)

    def _on_fetch_services_error(self, req, error):
        """Handle services fetch error."""
        logger.error(f"Error fetching gardening services: {error}")
        self.feedback_label.text = f"❌ Error: {str(error)}"
        self.feedback_label.color = (1, 0, 0, 1)

    def _update_price(self, spinner, text):
        """Update price label based on selected service."""
        for service in self.services:
            if service['name'] == text:
                self.price_label.text = f"Price: KES {service['price']}"
                logger.info(f"Updated price for {text}: KES {service['price']}")
                break

    def _add_to_cart(self, instance):
        """Add the selected gardening service to the cart."""
        gardening_service = self.service_spinner.text
        location = self.location_input.text.strip()
        quantity_text = self.quantity_input.text.strip()

        if gardening_service == "Select Service" or gardening_service == "No Services":
            self.feedback_label.text = "⚠ Please select a service."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning("No service selected")
            return
        if not location:
            self.feedback_label.text = "⚠ Please enter the delivery location."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning("No location provided")
            return
        if not quantity_text.isdigit() or int(quantity_text) <= 0:
            self.feedback_label.text = "⚠ Quantity must be a positive number."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning("Invalid quantity")
            return

        app = App.get_running_app()
        if not hasattr(app, 'cart'):
            app.cart = []

        service_id = next((s['id'] for s in self.services if s['name'] == gardening_service), None)
        price = next((s['price'] for s in self.services if s['name'] == gardening_service), 0)
        if not service_id:
            self.feedback_label.text = "⚠ Service not found."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.error("Service ID not found")
            return

        cart_item = {
            "service_id": service_id,
            "service_name": gardening_service,
            "price": price * int(quantity_text),
            "quantity": int(quantity_text),
            "location": location
        }
        app.cart.append(cart_item)
        self.feedback_label.text = f"✅ Added {gardening_service} to cart."
        self.feedback_label.color = (0, 1, 0, 1)
        logger.info(f"Added to cart: {cart_item}")

    def _go_to_cart(self, instance):
        """Navigate to the cart screen."""
        logger.info("Navigating to CartScreen")
        self.manager.current = 'cart'

    def _go_back_home(self, instance):
        """Navigate back to home screen."""
        logger.info("Navigating back to HomeScreen")
        self.manager.current = 'home'

    def _handle_order_update(self, data):
        """Handle real-time order updates from WebSocket."""
        logger.info(f"Received gardening order update: {data}")
        self.feedback_label.text = f"🔄 Order {data.get('order_id')} updated: {data.get('status')}"
        self.feedback_label.color = (0, 1, 0, 1)


class CartScreen(Screen):
    def __init__(self, **kwargs):
        super(CartScreen, self).__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=15, spacing=10)
        self._setup_ui()
        logger.info("Initialized CartScreen")

    def _setup_ui(self):
        """Set up the UI components."""
        # Title
        self.layout.add_widget(Label(
            text="🛒 Your Cart",
            font_size='22sp',
            bold=True,
            size_hint=(1, None),
            height='50dp',
            color=(0, 0, 0, 1)
        ))

        # Feedback label
        self.feedback_label = Label(
            text="",
            size_hint=(1, None),
            height='30dp',
            color=(1, 0, 0, 1)
        )
        self.layout.add_widget(self.feedback_label)

        # Cart items list with scroll view
        self.cart_list = GridLayout(cols=1, spacing=10, size_hint_y=None)
        self.cart_list.bind(minimum_height=self.cart_list.setter('height'))
        scrollview = ScrollView(size_hint=(1, 0.7))
        scrollview.add_widget(self.cart_list)
        self.layout.add_widget(scrollview)

        # Total amount label
        self.total_label = Label(
            text="Total: KES 0",
            font_size='18sp',
            size_hint=(1, None),
            height='40dp',
            color=(0, 0, 0, 1)
        )
        self.layout.add_widget(self.total_label)

        # Checkout button
        checkout_button = Button(
            text="Checkout",
            background_color=(0.2, 0.6, 0.2, 1),
            color=(1, 1, 1, 1),
            font_size='18sp',
            size_hint=(1, None),
            height='50dp'
        )
        checkout_button.bind(on_press=self._initiate_payment)
        self.layout.add_widget(checkout_button)

        # Back button
        back_button = Button(
            text="Back to Home",
            background_color=(0.6, 0.2, 0.2, 1),
            color=(1, 1, 1, 1),
            font_size='18sp',
            size_hint=(1, None),
            height='50dp'
        )
        back_button.bind(on_press=self._go_back_home)
        self.layout.add_widget(back_button)

        self.add_widget(self.layout)

    def on_enter(self):
        """Update the cart display when entering the screen."""
        logger.info("Entering CartScreen")
        self._update_cart_display()

    def _update_cart_display(self):
        """Update the cart items and total amount."""
        app = App.get_running_app()
        self.cart_list.clear_widgets()
        total_amount = 0

        if not hasattr(app, 'cart') or not app.cart:
            self.cart_list.add_widget(Label(
                text="Your cart is empty.",
                size_hint=(1, None),
                height='40dp',
                color=(0.8, 0.2, 0.2, 1)
            ))
            self.total_label.text = "Total: KES 0"
            return

        for item in app.cart:
            item_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='50dp', spacing=10)
            item_layout.add_widget(Label(
                text=f"{item['service_name']} x {item['quantity']}",
                size_hint=(0.6, 1)
            ))
            item_layout.add_widget(Label(
                text=f"KES {item['price']}",
                size_hint=(0.2, 1)
            ))
            remove_button = Button(
                text="Remove",
                size_hint=(0.2, 1),
                background_color=(1, 0, 0, 1),
                color=(1, 1, 1, 1)
            )
            remove_button.bind(on_press=lambda btn, item=item: self._remove_item(item))
            item_layout.add_widget(remove_button)
            self.cart_list.add_widget(item_layout)
            total_amount += item['price']

        self.total_label.text = f"Total: KES {total_amount}"

    def _remove_item(self, item):
        """Remove an item from the cart."""
        app = App.get_running_app()
        if hasattr(app, 'cart'):
            app.cart = [i for i in app.cart if i != item]
            self._update_cart_display()
            self.feedback_label.text = f"✅ Removed {item['service_name']} from cart."
            self.feedback_label.color = (0, 1, 0, 1)
            logger.info(f"Removed item: {item}")

    def _initiate_payment(self, instance):
        """Initiate payment for all items in the cart."""
        app = App.get_running_app()
        if not hasattr(app, 'cart') or not app.cart:
            self.feedback_label.text = "⚠ Your cart is empty."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning("Cart is empty")
            return

        total_amount = sum(item['price'] for item in app.cart)
        self._show_payment_popup(total_amount)

    def _show_payment_popup(self, total_amount):
        """Show a popup to collect the user's phone number for payment."""
        phone_popup = BoxLayout(orientation='vertical', padding=10, spacing=10)
        phone_label = Label(text=f"Pay KES {total_amount}\nEnter M-Pesa phone number:")
        self.phone_input = TextInput(hint_text="e.g., 254712345678", multiline=False)
        confirm_button = Button(
            text="Confirm Payment",
            size_hint=(1, None),
            height='44dp',
            background_color=(0.2, 0.6, 0.8, 1),
            color=(1, 1, 1, 1)
        )
        phone_popup.add_widget(phone_label)
        phone_popup.add_widget(self.phone_input)
        phone_popup.add_widget(confirm_button)

        popup = Popup(title="M-Pesa Payment", content=phone_popup, size_hint=(0.8, 0.4))
        confirm_button.bind(on_press=lambda x: self._process_payment(popup, total_amount))
        popup.open()

    def _process_payment(self, popup, total_amount):
        """Process M-Pesa payment after phone number input."""
        phone_number = self.phone_input.text.strip()
        if not phone_number or not phone_number.startswith("254") or len(phone_number) != 12:
            self.feedback_label.text = "⚠ Invalid phone number (use 254XXXXXXXXX)."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning(f"Invalid phone number: {phone_number}")
            return

        app = App.get_running_app()
        if not app.token:
            self.feedback_label.text = "⚠ You are not authorized. Please log in again."
            self.feedback_label.color = (1, 0, 0, 1)
            logger.warning("No token found for payment")
            self.manager.current = 'login'
            return

        payment_data = {
            "phone_number": phone_number,
            "amount": str(total_amount),  # Backend expects string
            "order_ids": [item['service_id'] for item in app.cart],
            "account_reference": f"Payment for {len(app.cart)} items",
            "transaction_desc": f"Payment for user {app.user_id}"
        }
        headers = {
            "Authorization": f"Bearer {app.token}",
            "Content-Type": "application/json"
        }
        logger.info(f"Initiating M-Pesa payment: {payment_data}")
        self.feedback_label.text = "🔄 Initiating payment..."
        self.feedback_label.color = (0, 1, 0, 1)

        UrlRequest(
            url=f"{app.server_url}/api/mpesa/payment",
            req_body=json.dumps(payment_data),
            req_headers=headers,
            on_success=self._on_payment_success,
            on_failure=self._on_payment_failure,
            on_error=self._on_payment_error
        )
        popup.dismiss()

    def _on_payment_success(self, req, result):
        """Handle successful payment initiation."""
        logger.info(f"Payment initiated successfully: {result}")
        self.feedback_label.text = "✅ Payment initiated! Check your phone to complete it."
        self.feedback_label.color = (0, 1, 0, 1)
        app = App.get_running_app()
        app.cart = []  # Clear the cart after successful payment
        self._update_cart_display()

    def _on_payment_failure(self, req, result):
        """Handle payment initiation failure."""
        error = result.get("error", f"Failed to initiate payment (Status: {req.resp_status})")
        logger.warning(f"Payment initiation failed: {error}")
        self.feedback_label.text = f"❌ {error}"
        self.feedback_label.color = (1, 0, 0, 1)

    def _on_payment_error(self, req, error):
        """Handle payment initiation error."""
        logger.error(f"Error initiating payment: {error}")
        self.feedback_label.text = f"❌ Error: {str(error)}"
        self.feedback_label.color = (1, 0, 0, 1)

    def _go_back_home(self, instance):
        """Navigate back to home screen."""
        logger.info("Navigating back to HomeScreen")
        self.manager.current = 'home'


class ServiceApp(App):
    DEFAULT_SERVER_URL = "http://192.168.213.152:5000"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = configparser.ConfigParser()
        self._load_config()  # Load and validate the configuration file
        self.sio = socketio.Client()  # Initialize Socket.IO client
        self.server_url = self.config.get("Server", "url", fallback=self.DEFAULT_SERVER_URL)
        self.token = None
        self.user_id = None
        self.cart = []  # Initialize cart to store selected items
        self.session = requests.Session()
        self._directory = self._get_storage_path()  # Use a private attribute for directory
        self._is_running = True  # Flag to control the app's lifecycle

    @property
    def directory(self):
        """Getter for the directory property."""
        return self._directory

    @directory.setter
    def directory(self, value):
        """Setter for the directory property."""
        self._directory = value

    def _load_config(self):
        """Load and validate the configuration file."""
        try:
            if not os.path.exists("config.ini"):
                logger.warning("config.ini not found, creating with default settings")
                self.config["Server"] = {"url": self.DEFAULT_SERVER_URL}
                self.config["Graphics"] = {"width": "460", "height": "740", "resizable": "0"}
                with open("config.ini", "w") as configfile:
                    self.config.write(configfile)
            self.config.read("config.ini")
            logger.info("Configuration file loaded successfully")
        except Exception as e:
            logger.error(f"Error loading config: {str(e)}")
            self.config = {"Server": {"url": self.DEFAULT_SERVER_URL}, "Graphics": {"width": "460", "height": "740", "resizable": "0"}}

    def _get_storage_path(self):
        """Get the writable storage path, adjusted for Android."""
        try:
            if platform == "android":
                from android.storage import app_storage_path  # type: ignore
                path = app_storage_path()
                logger.info(f"Using Android storage path: {path}")
                return path
            else:
                path = self.user_data_dir
                logger.info(f"Using fallback storage path: {path}")
                return path
        except Exception as e:
            logger.error(f"Error getting storage path: {str(e)}")
            return self.user_data_dir  # Fallback to user data directory

    def load_image(self, path, fallback="assets/icon.png"):
        """Load an image with fallback, adjusted for Android paths."""
        try:
            app = App.get_running_app()
            if not app:
                logger.error("App instance not available for image loading")
                return Image()
            full_path = os.path.join(app.directory, path)
            if os.path.exists(full_path):
                logger.info(f"Loading image from {full_path}")
                return Image(source=full_path)
            full_fallback = os.path.join(app.directory, fallback)
            logger.warning(f"Icon not found at {full_path}, using fallback: {full_fallback}")
            return Image(source=full_fallback) if os.path.exists(full_fallback) else Image()
        except Exception as e:
            logger.error(f"Error loading image {path}: {str(e)}")
            return Image()

    def connect_socketio(self):
        """Establish a Socket.IO connection with reconnection support."""
        def attempt_connection(attempt=1, max_attempts=3):
            try:
                logger.info(f"Attempting Socket.IO connection to {self.server_url} (Attempt {attempt}/{max_attempts})")
                self.sio.connect(self.server_url, wait_timeout=5)
                logger.info("Socket.IO connected successfully")
                return True
            except Exception as e:
                logger.error(f"Socket.IO connection failed: {str(e)}")
                if attempt < max_attempts:
                    logger.info("Retrying in 2 seconds...")
                    Clock.schedule_once(lambda dt: attempt_connection(attempt + 1, max_attempts), 2)
                else:
                    logger.warning("Max connection attempts reached. Running without real-time updates.")
                return False

        if not self.server_url:
            logger.error("Server URL is not set. Cannot connect to Socket.IO.")
            return

        # Run connection attempts in a separate thread to avoid blocking the main thread
        Thread(target=attempt_connection, daemon=True).start()

        @self.sio.event
        def connect():
            logger.info("Socket.IO connection established")

        @self.sio.event
        def disconnect():
            logger.warning("Socket.IO disconnected")
            Clock.schedule_once(lambda dt: attempt_connection(), 2)

        @self.sio.on("order_updated")
        def on_order_updated(data):
            logger.info(f"Order update received: {data}")
            # Broadcast order updates to all screens
            for screen in self.root.screens:
                if hasattr(screen, "handle_order_update"):
                    screen.handle_order_update(data)

    def build(self):
        """Build the app with screen manager and configurations."""
        try:
            width = self.config.getint("Graphics", "width", fallback=460)
            height = self.config.getint("Graphics", "height", fallback=740)
            Config.set("graphics", "width", str(width))
            Config.set("graphics", "height", str(height))
            Config.set("graphics", "resizable", "0")
            Config.write()
            logger.info("Graphics configuration set successfully")
        except Exception as e:
            logger.error(f"Failed to set graphics config: {str(e)}")

        sm = ScreenManager()
        screens = [
            ("login", "LoginScreen"),
            ("register", "RegistrationScreen"),
            ("forgot_password", "ForgotPasswordScreen"),
            ("reset_password", "ResetPasswordScreen"),
            ("dashboard", "DashboardScreen"),
            ("admin_dashboard", "AdminDashboard"),
            ("user_dashboard", "UserDashboard"),
            ("home", "HomeScreen"),
            ("cleaning", "CleaningScreen"),
            ("food", "FoodScreen"),
            ("groceries", "GroceriesScreen"),
            ("fruit", "FruitScreen"),
            ("gardening", "GardeningScreen"),
            ("cart", "CartScreen"),  # Add CartScreen here
        ]

        for name, screen_class in screens:
            try:
                screen = globals()[screen_class](name=name)
                sm.add_widget(screen)
                logger.info(f"Added screen: {name}")
            except KeyError:
                logger.warning(f"Screen class '{screen_class}' not defined, skipping")

        sm.current = "login" if "login" in [n for n, _ in screens] else screens[0][0]
        return sm

    def on_start(self):
        """Handle app startup, including Android permissions and Socket.IO connection."""
        try:
            logger.info("ServiceApp started")
            if platform == "android" and request_permissions and Permission:
                request_permissions([Permission.INTERNET, Permission.WRITE_EXTERNAL_STORAGE])
                logger.info("Requested Android permissions")
            self.connect_socketio()
        except Exception as e:
            logger.error(f"Error in on_start: {str(e)}", exc_info=True)
            raise

    def on_stop(self):
        """Handle app shutdown, ensuring resources are released."""
        logger.info("Shutting down ServiceApp")
        self._is_running = False
        self.sio.disconnect()  # Disconnect Socket.IO
        self.session.close()  # Close the requests session
        logger.info("ServiceApp shutdown complete")

# Run the app
if __name__ == '__main__':
    ServiceApp().run()